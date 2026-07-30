"""Modelos locales via Ollama (Qwen, Llama, Mistral...).

Todo se queda en tu maquina: sin llaves, sin costo por token y sin que el
texto de tus libros salga de aqui. Traducir un libro entero pasa de costar
dolares a costar tiempo de GPU.

Mantiene la garantia que importa: Ollama acepta un esquema JSON en `format`,
asi que la salida sigue siendo una traduccion por oracion de entrada. Sin
eso la alineacion bilingue se rompe en silencio.
"""

from __future__ import annotations

import json
import logging

import requests

from app.config import get_settings
from app.llm.base import Gloss, LLMNotReady, LLMProvider, ProviderHealth
from app.llm.claude import GLOSS_SCHEMA, GLOSS_SYSTEM, TRANSLATION_SCHEMA, TRANSLATION_SYSTEM

log = logging.getLogger(__name__)

TIMEOUT = (10, 600)  # (conexion, lectura): generar un lote largo tarda


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self) -> None:
        settings = get_settings()
        self._base = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_model
        # Las dos tareas tienen exigencias opuestas y medidas: la traduccion
        # corre desatendida y premia calidad; la glosa es interactiva y premia
        # latencia. Con un solo modelo una de las dos siempre sale perdiendo.
        self._gloss_model = settings.ollama_gloss_model or settings.ollama_model
        self._num_ctx = settings.ollama_num_ctx
        self._think = settings.ollama_think
        self._gloss_think = settings.ollama_gloss_think
        self._keep_alive = settings.ollama_keep_alive

    def _chat(
        self,
        *,
        system: str,
        prompt: str,
        schema: dict,
        model: str | None = None,
        think: bool | None = None,
    ) -> dict:
        model = model or self._model
        if not model:
            raise LLMNotReady("OLLAMA_MODEL vacio en .env (p.ej. qwen3:8b)")

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            # Esquema JSON: misma garantia estructural que output_config.format
            # en la API de Claude. Es lo que sostiene la alineacion.
            "format": schema,
            "stream": False,
            # Sin esto Ollama libera el modelo tras 5 minutos y la siguiente
            # palabra que toques paga la recarga entera.
            "keep_alive": self._keep_alive,
            "options": {
                # Ollama usa 4096 de contexto por defecto y RECORTA EN SILENCIO
                # lo que no cabe. Con un lote de oraciones mas su contexto de
                # parrafo eso se desborda facil, y el sintoma seria «faltan
                # traducciones» sin ningun error.
                "num_ctx": self._num_ctx,
                # Traducir no es una tarea creativa: queremos reproducibilidad.
                "temperature": 0.2,
            },
        }
        # Por defecto NO se manda `think`. Medido contra Ollama 0.30.7 con
        # qwen3.6: enviar `think: false` desactiva la gramatica que obliga al
        # esquema JSON, y el modelo devuelve prosa con Markdown. La misma
        # peticion sin ese parametro devuelve JSON valido.
        #
        # Es contraintuitivo — parece un ajuste de rendimiento inofensivo — y
        # el sintoma no apunta a la causa: se ve como «el modelo no respeta el
        # esquema», no como «desactivaste el razonamiento».
        #
        # Pero es especifico del modelo, no universal: qwen3:8b acepta
        # `think: false` y sigue respetando el esquema. Por eso cada tarea trae
        # su propio ajuste en vez de compartir uno global.
        efectivo = think if think is not None else self._think
        if efectivo is not None:
            payload["think"] = efectivo

        try:
            response = requests.post(f"{self._base}/api/chat", json=payload, timeout=TIMEOUT)
        except requests.exceptions.ConnectionError as exc:
            raise LLMNotReady(f"Ollama no responde en {self._base}. ¿Esta corriendo?") from exc
        except requests.exceptions.Timeout as exc:
            raise LLMNotReady("Ollama tardo demasiado. Prueba un lote mas chico.") from exc

        if response.status_code == 400 and "think" in response.text.lower():
            # El modelo no soporta el parametro: reintentar sin el.
            payload.pop("think", None)
            response = requests.post(f"{self._base}/api/chat", json=payload, timeout=TIMEOUT)

        if not response.ok:
            raise LLMNotReady(f"Ollama devolvio {response.status_code}: {response.text[:200]}")

        content = response.json().get("message", {}).get("content", "")
        if not content.strip():
            raise LLMNotReady("Ollama devolvio una respuesta vacia")

        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            # El fallo conocido de `think: false`: la gramatica del esquema se
            # anula y llega prosa. Se reintenta una vez sin el parametro antes
            # de darlo por perdido, porque el sintoma no se parece a la causa y
            # nadie lo diagnosticaria desde el mensaje de error.
            if "think" in payload:
                log.warning(
                    "ollama: %s ignoro el esquema con think=%s; reintentando sin el parametro",
                    model, payload["think"],
                )
                payload.pop("think")
                retry = requests.post(f"{self._base}/api/chat", json=payload, timeout=TIMEOUT)
                if retry.ok:
                    retry_content = retry.json().get("message", {}).get("content", "")
                    try:
                        return json.loads(retry_content)
                    except json.JSONDecodeError:
                        pass
            raise LLMNotReady(
                f"El modelo no respeto el esquema JSON: {content[:200]}"
            ) from exc

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
            numbered = "\n".join(f"{start + j}. {s}" for j, s in enumerate(sentences))
            blocks.append(f"[Parrafo]\n{numbered}")

        if not flat:
            return [[] for _ in paragraphs]

        payload = self._chat(
            system=TRANSLATION_SYSTEM,
            prompt=(
                f"Traduce las {len(flat)} oraciones numeradas. Las agrupaciones "
                "marcan parrafos: usa el parrafo completo para resolver "
                "pronombres, referencias y sentido, pero devuelve una "
                "traduccion por numero.\n\n" + "\n\n".join(blocks)
            ),
            schema=TRANSLATION_SCHEMA,
        )

        # Reindexado por `i`, no por posicion en el array: si el modelo se
        # salta una oracion, queda vacia en su sitio en vez de desplazar a
        # todas las siguientes. Importa mas con modelos locales, que respetan
        # el esquema con menos disciplina que uno de frontera.
        out_flat = [""] * len(flat)
        for item in payload.get("translations", []):
            idx = item.get("i")
            if isinstance(idx, int) and 0 <= idx < len(flat):
                out_flat[idx] = str(item.get("es", ""))

        missing = sum(1 for t in out_flat if not t)
        if missing:
            log.warning(
                "ollama: %s de %s oraciones sin traducir. Si se repite, baja "
                "TRANSLATION_BATCH_SIZE o sube OLLAMA_NUM_CTX.",
                missing,
                len(flat),
            )

        result: list[list[str]] = []
        cursor = 0
        for size in shape:
            result.append(out_flat[cursor : cursor + size])
            cursor += size
        return result

    def gloss(self, word: str, sentence: str) -> Gloss:
        payload = self._chat(
            system=GLOSS_SYSTEM,
            prompt=f'Oracion: "{sentence}"\n\nPalabra a explicar: "{word}"',
            schema=GLOSS_SCHEMA,
            model=self._gloss_model,
            think=self._gloss_think,
        )
        return Gloss(
            lemma=str(payload.get("lemma") or word.lower()),
            pos=str(payload.get("pos") or ""),
            sense_es=str(payload.get("sense_es") or ""),
            note_es=str(payload.get("note_es") or ""),
        )

    def prewarm(self) -> None:
        """Carga el modelo de glosas en memoria sin generar nada.

        Ollama interpreta una peticion con `messages` vacio como «solo carga el
        modelo». Solo el de glosas: el de traduccion es grande, corre
        desatendido y tenerlo ocupando memoria a la espera de un lote que puede
        no llegar hoy sale mas caro que su propia carga.

        Las `options` tienen que ser LAS MISMAS que usara la glosa. Ollama
        identifica el modelo cargado por su configuracion de ejecucion, asi que
        precalentar sin `num_ctx` deja cargado un runner de 4096 y la primera
        peticion real, que pide 8192, lo descarta y vuelve a cargar. Medido:
        precalentando sin las opciones, la primera consulta seguia costando
        5.6s con el modelo «ya en memoria».
        """
        if not self._gloss_model:
            return
        try:
            requests.post(
                f"{self._base}/api/chat",
                json={
                    "model": self._gloss_model,
                    "messages": [],
                    "keep_alive": self._keep_alive,
                    "options": {"num_ctx": self._num_ctx, "temperature": 0.2},
                },
                timeout=(5, 180),
            )
            log.info("ollama: %s precargado (keep_alive=%s)", self._gloss_model, self._keep_alive)
        except Exception as exc:  # noqa: BLE001
            # Que Ollama no este arriba no es motivo para no arrancar: la app
            # funciona sin glosas, y health() ya lo reporta.
            log.info("ollama: no se pudo precargar %s: %s", self._gloss_model, exc)

    def health(self) -> ProviderHealth:
        if not self._model:
            return ProviderHealth(
                name=self.name, ready=False, detail="OLLAMA_MODEL vacio en .env"
            )
        try:
            response = requests.get(f"{self._base}/api/tags", timeout=5)
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            return ProviderHealth(
                name=self.name, ready=False, detail=f"Ollama no responde en {self._base}: {exc}"
            )

        installed = [m.get("name", "") for m in response.json().get("models", [])]

        def missing(tag: str) -> bool:
            # Ollama acepta «qwen3» y sirve «qwen3:latest»: comparamos por prefijo.
            base = tag.split(":")[0]
            return not any(m == tag or m.split(":")[0] == base for m in installed)

        for tag in {self._model, self._gloss_model}:
            if missing(tag):
                return ProviderHealth(
                    name=self.name,
                    ready=False,
                    detail=f"El modelo «{tag}» no esta descargado. Corre: ollama pull {tag}",
                )

        detail = f"traduccion={self._model}"
        if self._gloss_model != self._model:
            detail += f" glosas={self._gloss_model}"
        return ProviderHealth(name=self.name, ready=True, detail=f"{detail} ctx={self._num_ctx}")
