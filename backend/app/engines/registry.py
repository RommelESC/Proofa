from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.engines.azure import AzureEngine
from app.engines.base import PronunciationEngine
from app.engines.local import LocalW2V2Engine
from app.engines.mock import MockEngine

ENGINES: dict[str, type[PronunciationEngine]] = {
    "mock": MockEngine,
    "azure": AzureEngine,
    "local": LocalW2V2Engine,
}


@lru_cache(maxsize=len(ENGINES))
def get_engine(name: str | None = None) -> PronunciationEngine:
    key = (name or get_settings().pronunciation_engine).lower()
    if key not in ENGINES:
        raise ValueError(f"Motor desconocido: {key!r}. Opciones: {', '.join(ENGINES)}")
    return ENGINES[key]()
