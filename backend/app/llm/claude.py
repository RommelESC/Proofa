"""Traduccion y glosas con la API de Claude.

Tres decisiones que valen la pena explicar:

1. Salida estructurada (`output_config.format`). El modelo devuelve un array
   con un elemento por oracion de entrada, asi que la alineacion ES/EN esta
   garantizada por el esquema y no hay que parsear texto libre.

2. Prompt caching. El prompt de sistema es identico en cada lote; marcarlo
   con `cache_control` abarata mucho importar un libro entero.

3. `effort: "low"`. Traducir es mecanico. Opus 5 rinde muy bien en niveles
   bajos de esfuerzo, asi que subirlo gastaria tokens sin mejorar el
   resultado. Las glosas usan `medium` porque desambiguar sentido en
   contexto si es un juicio fino.
"""

from __future__ import annotations

import json
import logging

from app.config import get_settings
from app.llm.base import Gloss, LLMNotReady, LLMProvider, ProviderHealth

log = logging.getLogger(__name__)

TRANSLATION_SYSTEM = """Eres un traductor literario del ingles al espanol para una
plataforma de lectura bilingue. El lector es hispanohablante y esta aprendiendo
ingles: ve ambos textos y usa el espanol para entender lo que acaba de leer.

Recibes el texto agrupado en parrafos, con cada oracion numerada. Devuelve una
traduccion por cada numero.

INTERPRETA EN CONTEXTO, no traduzcas palabra por palabra:
- Resuelve pronombres y referencias con lo que dice el resto del parrafo. Si una
  oracion dice «He took it», tu ya sabes por el parrafo que es «it»: traduce de
  forma que en espanol se entienda igual de bien.
- Las expresiones idiomaticas se traducen por su equivalente en espanol, no por
  la suma de sus palabras. «He was pulling my leg» es «me estaba tomando el
  pelo», no «me jalaba la pierna».
- Los verbos con particula (phrasal verbs) se traducen por lo que significan en
  esa frase: «give up» es rendirse, «give in» es ceder, «give away» es regalar.
- Elige la acepcion que pide el contexto. «run a business» es dirigir, no correr.
- Respeta el registro y la epoca: si el ingles es formal o antiguo, el espanol
  tambien lo es.

REGLAS DE FORMA:
- Una traduccion por oracion numerada, en el mismo orden. No fusiones ni partas
  oraciones aunque en espanol quedaria mas natural: el lector las compara
  emparejadas.
- El espanol tiene que sonar natural leido solo, sin el ingles al lado.
- No agregues notas, aclaraciones, corchetes ni el texto original.
- Espanol neutro latinoamericano."""

GLOSS_SYSTEM = """Explicas vocabulario en ingles a un hispanohablante que esta leyendo.

Da el sentido que la palabra tiene EN ESA ORACION, no su primera acepcion de
diccionario. Se breve: `sense_es` es una traduccion o definicion corta.
Usa `note_es` solo si hay algo que de verdad confunde (falso amigo, phrasal
verb, uso idiomatico); si no, dejalo vacio."""

TRANSLATION_SCHEMA = {
    "type": "object",
    "properties": {
        "translations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "i": {"type": "integer", "description": "Indice de la oracion original"},
                    "es": {"type": "string", "description": "Traduccion al espanol"},
                },
                "required": ["i", "es"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["translations"],
    "additionalProperties": False,
}

GLOSS_SCHEMA = {
    "type": "object",
    "properties": {
        "lemma": {"type": "string"},
        "pos": {"type": "string", "description": "noun, verb, adjective, ..."},
        "sense_es": {"type": "string"},
        "note_es": {"type": "string"},
    },
    "required": ["lemma", "pos", "sense_es", "note_es"],
    "additionalProperties": False,
}


class ClaudeProvider(LLMProvider):
    name = "claude"

    def __init__(self) -> None:
        settings = get_settings()
        self._model = settings.llm_model
        self._api_key = settings.anthropic_api_key
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            import anthropic
        except ImportError as exc:
            raise LLMNotReady(
                "Falta el SDK. Instala: pip install -r requirements-llm.txt"
            ) from exc
        if not self._api_key:
            raise LLMNotReady("ANTHROPIC_API_KEY vacia en .env")
        self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def _structured(self, *, system: str, prompt: str, schema: dict, effort: str) -> dict:
        client = self._get_client()
        response = client.messages.create(
            model=self._model,
            max_tokens=16000,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": prompt}],
        )

        # Los clasificadores pueden rechazar una peticion: llega HTTP 200 con
        # stop_reason "refusal" y content vacio. Hay que mirarlo antes de leer.
        if response.stop_reason == "refusal":
            detail = getattr(response.stop_details, "category", None)
            raise LLMNotReady(f"Peticion rechazada por los clasificadores ({detail})")
        if response.stop_reason == "max_tokens":
            raise LLMNotReady("Respuesta truncada: reduce el tamano del lote")

        text = next((b.text for b in response.content if b.type == "text"), "")
        return json.loads(text)

    def translate_paragraphs(self, paragraphs: list[list[str]]) -> list[list[str]]:
        flat: list[str] = []
        shape: list[int] = []
        blocks: list[str] = []

        for sentences in paragraphs:
            if not sentences:
                shape.append(0)
                continue
            start = len(flat)
            flat.extend(sentences)
            shape.append(len(sentences))
            numbered = "\n".join(
                f"{start + j}. {s}" for j, s in enumerate(sentences)
            )
            blocks.append(f"[Parrafo]\n{numbered}")

        if not flat:
            return [[] for _ in paragraphs]

        payload = self._structured(
            system=TRANSLATION_SYSTEM,
            prompt=(
                f"Traduce las {len(flat)} oraciones numeradas. Las agrupaciones "
                "marcan parrafos: usa el parrafo completo para resolver "
                "pronombres, referencias y sentido, pero devuelve una "
                "traduccion por numero.\n\n" + "\n\n".join(blocks)
            ),
            schema=TRANSLATION_SCHEMA,
            effort="low",
        )

        # Reindexamos por `i` en vez de confiar en el orden del array: si el
        # modelo se salta una, queda vacia en su sitio y no desplaza al resto
        # (un desfase silencioso arruinaria la alineacion de todo el capitulo).
        out_flat = [""] * len(flat)
        for item in payload.get("translations", []):
            idx = item.get("i")
            if isinstance(idx, int) and 0 <= idx < len(flat):
                out_flat[idx] = item.get("es", "")

        missing = sum(1 for t in out_flat if not t)
        if missing:
            log.warning("claude: %s de %s oraciones sin traducir en el lote", missing, len(flat))

        result: list[list[str]] = []
        cursor = 0
        for size in shape:
            result.append(out_flat[cursor : cursor + size])
            cursor += size
        return result

    def gloss(self, word: str, sentence: str) -> Gloss:
        payload = self._structured(
            system=GLOSS_SYSTEM,
            prompt=f'Oracion: "{sentence}"\n\nPalabra a explicar: "{word}"',
            schema=GLOSS_SCHEMA,
            effort="medium",
        )
        return Gloss(**payload)

    def health(self) -> ProviderHealth:
        try:
            self._get_client()
        except LLMNotReady as exc:
            return ProviderHealth(name=self.name, ready=False, detail=str(exc))
        return ProviderHealth(name=self.name, ready=True, detail=f"modelo={self._model}")
