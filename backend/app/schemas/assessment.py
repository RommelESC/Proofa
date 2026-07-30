"""Contrato unico de evaluacion de pronunciacion.

Todos los motores (mock, azure, local) devuelven exactamente esta forma.
Claude nunca ve audio: consume este objeto.

Regla de oro del proyecto: `AssessmentResult.raw` guarda el payload integro
del motor sin tocar. Las tablas normalizadas se derivan de el, asi que si
manana cambias de motor o refinas la taxonomia de errores, puedes recalcular
todo el historial sin volver a evaluar el audio.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class WordErrorType(StrEnum):
    NONE = "none"
    MISPRONUNCIATION = "mispronunciation"
    OMISSION = "omission"        # la palabra no se dijo
    INSERTION = "insertion"      # se dijo algo que no estaba en el texto
    UNEXPECTED_BREAK = "unexpected_break"
    MONOTONE = "monotone"


class PhonemeScore(BaseModel):
    """Un fonema esperado y lo que realmente produjiste.

    `produced_ipa is None` significa omision: el fonema no aparecio.
    Esta es la unidad atomica de todo el analisis longitudinal del proyecto.
    """

    index: int
    expected_ipa: str
    produced_ipa: str | None = None
    score: float = Field(ge=0, le=100)


class WordScore(BaseModel):
    index: int
    surface: str
    score: float = Field(ge=0, le=100)
    error_type: WordErrorType = WordErrorType.NONE
    stress_ok: bool | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    phonemes: list[PhonemeScore] = Field(default_factory=list)


class Prosody(BaseModel):
    """Lo que separa 'entendible' de 'fluido'."""

    wpm: float | None = None
    fluency: float | None = None        # 0..100
    completeness: float | None = None   # 0..100, cuanto del texto leiste
    prosody_score: float | None = None  # 0..100, entonacion y ritmo
    pause_count: int | None = None


class PatternHit(BaseModel):
    """Un error de la taxonomia L1-espanol detectado en una palabra concreta."""

    code: str            # p.ej. "TH_TO_S"
    word_index: int
    phoneme_index: int | None = None
    confidence: float = Field(ge=0, le=1)
    detail: str = ""


class AssessmentResult(BaseModel):
    engine: str
    engine_version: str
    overall: float = Field(ge=0, le=100)
    words: list[WordScore] = Field(default_factory=list)
    prosody: Prosody = Field(default_factory=Prosody)
    patterns: list[PatternHit] = Field(default_factory=list)
    raw: dict = Field(default_factory=dict)

    @property
    def worst_words(self) -> list[WordScore]:
        """Palabras a corregir, peores primero. Solo las realmente falladas."""
        bad = [w for w in self.words if w.score < 70 or w.error_type != WordErrorType.NONE]
        return sorted(bad, key=lambda w: w.score)


class EngineHealth(BaseModel):
    name: str
    version: str
    ready: bool
    detail: str = ""
