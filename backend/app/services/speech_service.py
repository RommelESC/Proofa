"""Cache en disco del audio sintetizado.

La sintesis es determinista: misma voz, mismo texto, mismo IPA y misma
velocidad producen siempre los mismos bytes. Asi que se genera una vez y se
reutiliza — importa porque las palabras que fallas se repiten mucho, y sin
cache cada repaso volveria a pagar la llamada.

Sin filas en `assets` a proposito: esa tabla existe para ligar grabaciones a
intentos, y nada referencia estos archivos. El propio nombre del archivo es
el indice. Cuando llegue el TTS por oracion con marcas de tiempo — que si
necesita relacion con `sentences` — ese usara `assets` como debe.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from app.config import get_settings
from app.tts import TTSProvider, get_tts

log = logging.getLogger(__name__)

# El limite existe para no sintetizar texto arbitrario, pero tiene que caber
# una oracion de libro entera. Nacio pensando en palabras sueltas — el audio
# de referencia de una palabra que fallaste — y al llegar la narracion por
# oracion se quedo corto: en el primer capitulo de Meditations el 24% de las
# oraciones pasa de 200 caracteres y la mas larga tiene 589. Esas devolvian
# 400, el audio no cargaba, y como un <audio> que falla no emite `ended`, la
# narracion se detenia en seco justo ahi.
MAX_TEXT_LEN = 1500


def _cache_key(provider: TTSProvider, text: str, ipa: str | None, slow: bool) -> str:
    raw = "|".join([provider.name, getattr(provider, "_voice", ""), text, ipa or "", str(slow)])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def speech_file(
    text: str,
    *,
    ipa: str | None = None,
    slow: bool = False,
    provider_name: str | None = None,
) -> tuple[Path, str]:
    """Devuelve (ruta del audio, media type), sintetizando solo si hace falta."""
    text = text.strip()
    if not text:
        raise ValueError("Texto vacio")
    if len(text) > MAX_TEXT_LEN:
        raise ValueError(f"Texto demasiado largo (max {MAX_TEXT_LEN} caracteres)")

    provider = get_tts(provider_name)
    settings = get_settings()

    digest = _cache_key(provider, text, ipa, slow)
    cache_dir = settings.assets_dir / "tts" / provider.name
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{digest}.{provider.extension}"

    marks_path = path.with_suffix(".marks.json")

    if not path.exists():
        audio, marks = provider.synthesize_marked(text, ipa=ipa, slow=slow)
        if not audio:
            raise ValueError("El proveedor devolvio audio vacio")

        # Escritura atomica: un archivo a medias en el cache seria un audio
        # roto servido para siempre, porque nunca se regenera.
        tmp = path.with_suffix(path.suffix + ".part")
        tmp.write_bytes(audio)
        tmp.replace(path)

        # Las marcas se guardan junto al audio: se generan en la misma llamada
        # y pedirlas por separado costaria otra sintesis completa.
        marks_tmp = marks_path.with_suffix(".part")
        marks_tmp.write_text(
            json.dumps([m.model_dump() for m in marks], ensure_ascii=False), encoding="utf-8"
        )
        marks_tmp.replace(marks_path)

        log.info(
            "tts: generado %s (%s bytes, %s marcas) para %r",
            path.name, len(audio), len(marks), text[:40],
        )

    return path, provider.media_type


def speech_marks(
    text: str, *, ipa: str | None = None, slow: bool = False, provider_name: str | None = None
) -> list[dict]:
    """Tiempos por palabra del audio cacheado. Lo sintetiza si hace falta."""
    path, _ = speech_file(text, ipa=ipa, slow=slow, provider_name=provider_name)
    marks_path = path.with_suffix(".marks.json")
    if not marks_path.exists():
        return []
    try:
        return json.loads(marks_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        log.warning("tts: marcas ilegibles en %s", marks_path.name)
        return []
