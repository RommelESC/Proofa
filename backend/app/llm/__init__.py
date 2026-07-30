from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.llm.base import Gloss, LLMNotReady, LLMProvider, ProviderHealth
from app.llm.claude import ClaudeProvider
from app.llm.noop import NoopProvider
from app.llm.ollama import OllamaProvider

PROVIDERS: dict[str, type[LLMProvider]] = {
    "claude": ClaudeProvider,
    "ollama": OllamaProvider,
    "none": NoopProvider,
}


@lru_cache(maxsize=len(PROVIDERS))
def get_llm(name: str | None = None) -> LLMProvider:
    key = (name or get_settings().llm_provider).lower()
    if key not in PROVIDERS:
        raise ValueError(f"Proveedor desconocido: {key!r}. Opciones: {', '.join(PROVIDERS)}")
    return PROVIDERS[key]()


__all__ = [
    "PROVIDERS",
    "ClaudeProvider",
    "Gloss",
    "LLMNotReady",
    "LLMProvider",
    "NoopProvider",
    "OllamaProvider",
    "ProviderHealth",
    "get_llm",
]
