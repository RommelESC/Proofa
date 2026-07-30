from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.tts.azure import AzureTTS
from app.tts.base import TTSHealth, TTSNotReady, TTSProvider

PROVIDERS: dict[str, type[TTSProvider]] = {"azure": AzureTTS}


@lru_cache(maxsize=len(PROVIDERS))
def get_tts(name: str | None = None) -> TTSProvider:
    key = (name or get_settings().tts_provider).lower()
    if key not in PROVIDERS:
        raise ValueError(f"Proveedor TTS desconocido: {key!r}. Opciones: {', '.join(PROVIDERS)}")
    return PROVIDERS[key]()


__all__ = ["PROVIDERS", "AzureTTS", "TTSHealth", "TTSNotReady", "TTSProvider", "get_tts"]
