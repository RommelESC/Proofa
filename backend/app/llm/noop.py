"""Proveedor vacio: el lector funciona sin llave de API, solo en ingles.

Degradar es mejor que no arrancar. Cuando configures ANTHROPIC_API_KEY,
las traducciones se rellenan sin tocar nada mas.
"""

from __future__ import annotations

from app.llm.base import Gloss, LLMProvider, ProviderHealth


class NoopProvider(LLMProvider):
    name = "none"

    def translate_paragraphs(self, paragraphs: list[list[str]]) -> list[list[str]]:
        return [[""] * len(p) for p in paragraphs]

    def gloss(self, word: str, sentence: str) -> Gloss:
        return Gloss(
            lemma=word.lower(),
            pos="",
            sense_es="",
            note_es="Configura ANTHROPIC_API_KEY en .env para obtener definiciones en contexto.",
        )

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            name=self.name,
            ready=True,
            detail="Sin LLM: el lector muestra solo el texto en ingles.",
        )
