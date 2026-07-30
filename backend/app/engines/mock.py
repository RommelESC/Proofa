"""Motor sintetico. NO evalua audio de verdad.

Para que sirve: ejercitar el circuito completo (grabar -> API -> Postgres ->
deteccion de patrones -> mapa de calor) sin llaves ni descargas de 2 GB.
Genera errores deterministas sesgados hacia la taxonomia L1-espanol, de modo
que los detectores se activan y puedes ver la UI real funcionando hoy.

Los scores son FALSOS. Toda respuesta viene marcada con `synthetic: true`.
"""

from __future__ import annotations

import zlib
from pathlib import Path

from app.engines.base import PronunciationEngine
from app.phonology.g2p import phonemize_sentence
from app.phonology.scoring import word_score
from app.schemas.assessment import (
    AssessmentResult,
    EngineHealth,
    PhonemeScore,
    Prosody,
    WordErrorType,
    WordScore,
)

# Sustituciones que un hispanohablante hace tipicamente. El mock las aplica
# para que los detectores de patterns.py tengan algo real que encontrar.
TYPICAL_SUBSTITUTIONS: dict[str, str] = {
    "θ": "s", "ð": "d", "v": "b", "z": "s", "ɪ": "i",
    "ə": "a", "ŋ": "n", "j": "dʒ", "ʒ": "ʃ", "ɹ": "r",
}


def _stable(*parts: str) -> int:
    """Hash estable entre procesos (hash() de Python esta salteado)."""
    return zlib.crc32("|".join(parts).encode("utf-8"))


class MockEngine(PronunciationEngine):
    name = "mock"
    version = "1"

    def assess(
        self,
        audio_path: Path,
        expected_text: str,
        *,
        locale: str = "en-US",
    ) -> AssessmentResult:
        words: list[WordScore] = []

        for w_idx, (surface, ipa_seq) in enumerate(phonemize_sentence(expected_text)):
            phonemes: list[PhonemeScore] = []

            for p_idx, expected in enumerate(ipa_seq):
                seed = _stable(surface.lower(), expected, str(p_idx))
                bucket = seed % 100
                substitute = TYPICAL_SUBSTITUTIONS.get(expected)

                # ~22% de los fonemas "dificiles" fallan; ~6% del resto.
                fails = bucket < (22 if substitute else 6)

                if fails and substitute:
                    produced, score = substitute, 25.0 + (seed % 25)
                elif fails:
                    produced, score = None, 30.0 + (seed % 20)
                else:
                    produced, score = expected, 78.0 + (seed % 22)

                phonemes.append(
                    PhonemeScore(
                        index=p_idx,
                        expected_ipa=expected,
                        produced_ipa=produced,
                        score=round(score, 1),
                    )
                )

            score = word_score(phonemes, default=85.0)
            error = (
                WordErrorType.MISPRONUNCIATION if score < 60 else WordErrorType.NONE
            )

            words.append(
                WordScore(
                    index=w_idx,
                    surface=surface,
                    score=score,
                    error_type=error,
                    stress_ok=(_stable(surface.lower(), "stress") % 100) >= 12,
                    phonemes=phonemes,
                )
            )

        overall = round(sum(w.score for w in words) / len(words), 1) if words else 0.0
        word_count = len(words)

        return AssessmentResult(
            engine=self.name,
            engine_version=self.version,
            overall=overall,
            words=words,
            prosody=Prosody(
                wpm=float(110 + _stable(expected_text) % 60),
                fluency=round(60.0 + _stable(expected_text, "flu") % 35, 1),
                completeness=100.0,
                prosody_score=round(55.0 + _stable(expected_text, "pro") % 40, 1),
                pause_count=word_count // 8,
            ),
            raw={
                "synthetic": True,
                "warning": "Scores generados, no medidos. Cambia PRONUNCIATION_ENGINE para evaluar de verdad.",
                "audio_file": audio_path.name,
                "locale": locale,
            },
        )

    def health(self) -> EngineHealth:
        return EngineHealth(
            name=self.name,
            version=self.version,
            ready=True,
            detail="Motor sintetico: los scores son falsos, sirven solo para probar el circuito.",
        )
