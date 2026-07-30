"""Azure Speech Pronunciation Assessment.

El motor de mayor calidad disponible sin entrenar nada. Da scores por
palabra y por fonema, mas fluidez, completitud y prosodia.

Limitacion importante para este proyecto: Azure te dice QUE fonema fallo,
pero no QUE dijiste en su lugar. Lo aproximamos con `NBestPhonemes` (los
candidatos que el reconocedor considero). Por eso varios detectores de
patterns.py disparan con menos confianza aqui que con el motor local, que
si devuelve la secuencia realmente producida.

Sin verificar contra una llave real todavia: revisar el mapeo de campos
la primera vez que se conecte.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.config import get_settings
from app.engines.base import EngineNotReady, PronunciationEngine
from app.schemas.assessment import (
    AssessmentResult,
    EngineHealth,
    PhonemeScore,
    Prosody,
    WordErrorType,
    WordScore,
)

log = logging.getLogger(__name__)

TICKS_PER_MS = 10_000  # Azure reporta offsets en unidades de 100 ns

# Umbrales para afirmar «dijiste X en vez de Y». Verificados contra respuestas
# reales del servicio (ver tests/test_azure_parsing.py).
#
# Lo que NO es NBestPhonemes: no es la probabilidad de haber producido ese
# sonido. Es un ranking normalizado donde el primer candidato casi siempre
# saca 100, incluso cuando el fonema esperado se pronuncio bien. En una
# medicion real, /b/ con AccuracyScore 60 traia NBest[0] = /ʊ/ con 100 y /b/
# en segundo lugar con 95: la /b/ SI sonaba, y ese /ʊ/ era la vocal contigua
# filtrandose en la ventana de alineacion.
#
# La senal confiable es el AccuracyScore propio del fonema. NBest solo sirve
# para nombrar el sustituto cuando ya sabemos que el esperado fallo.
SUBSTITUTION_MAX_ACCURACY = 45.0  # el fonema esperado tiene que haber fallado claro
SUBSTITUTION_MIN_MARGIN = 30.0    # y el competidor ganarle por un margen amplio
OMISSION_MAX_ACCURACY = 25.0

_ERROR_TYPE_MAP = {
    "none": WordErrorType.NONE,
    "mispronunciation": WordErrorType.MISPRONUNCIATION,
    "omission": WordErrorType.OMISSION,
    "insertion": WordErrorType.INSERTION,
    "unexpectedbreak": WordErrorType.UNEXPECTED_BREAK,
    "monotone": WordErrorType.MONOTONE,
}


class AzureEngine(PronunciationEngine):
    name = "azure"
    version = "pa-v1"

    def __init__(self) -> None:
        settings = get_settings()
        self._key = settings.azure_speech_key
        self._region = settings.azure_speech_region

    def _sdk(self):
        try:
            import azure.cognitiveservices.speech as speechsdk
        except ImportError as exc:
            raise EngineNotReady(
                "Falta el SDK. Instala: pip install -r requirements-azure.txt"
            ) from exc
        if not self._key:
            raise EngineNotReady("AZURE_SPEECH_KEY vacia en .env")
        return speechsdk

    def assess(
        self,
        audio_path: Path,
        expected_text: str,
        *,
        locale: str = "en-US",
    ) -> AssessmentResult:
        speechsdk = self._sdk()

        speech_config = speechsdk.SpeechConfig(subscription=self._key, region=self._region)
        audio_config = speechsdk.audio.AudioConfig(filename=str(audio_path))

        pa_config = speechsdk.PronunciationAssessmentConfig(
            reference_text=expected_text,
            grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
            granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
            enable_miscue=True,
        )
        # IPA en vez de SAPI: el resto del proyecto habla IPA.
        for attr, value in (("phoneme_alphabet", "IPA"), ("nbest_phoneme_count", 5)):
            try:
                setattr(pa_config, attr, value)
            except Exception:  # noqa: BLE001 - varia entre versiones del SDK
                log.warning("azure: no se pudo fijar %s en esta version del SDK", attr)
        try:
            pa_config.enable_prosody_assessment()
        except Exception:  # noqa: BLE001
            log.warning("azure: prosodia no disponible en esta version del SDK")

        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config, language=locale, audio_config=audio_config
        )
        pa_config.apply_to(recognizer)
        result = recognizer.recognize_once()

        if result.reason == speechsdk.ResultReason.Canceled:
            details = speechsdk.CancellationDetails(result)
            raise EngineNotReady(f"Azure cancelo la peticion: {details.reason} {details.error_details}")

        payload = json.loads(
            result.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonResult) or "{}"
        )
        return self._parse(payload, locale)

    @staticmethod
    def _produced_phoneme(
        expected: str, accuracy: float, candidates: list[dict]
    ) -> str | None:
        """Que sonido se produjo realmente, o None si no hay evidencia.

        Solo se afirma una sustitucion cuando se cumplen las tres:
          1. el fonema esperado fallo de forma clara (accuracy baja),
          2. otro candidato quedo por encima de el, y
          3. le gana por un margen amplio.

        Sin las tres, se devuelve el esperado. Preferimos perder algun error
        real antes que inventar uno: un falso positivo destruye la confianza
        del alumno mucho mas rapido de lo que un falso negativo retrasa su
        avance.
        """
        if accuracy >= SUBSTITUTION_MAX_ACCURACY or not candidates:
            return expected if accuracy > OMISSION_MAX_ACCURACY else None

        top = candidates[0]
        top_ipa = top.get("Phoneme")
        if not top_ipa or top_ipa == expected:
            # El esperado sigue siendo el candidato mas probable: sono mal,
            # pero no hay otro sonido que senalar.
            return expected if accuracy > OMISSION_MAX_ACCURACY else None

        own = next((c for c in candidates if c.get("Phoneme") == expected), None)
        own_score = float(own.get("Score", 0.0)) if own else 0.0
        if float(top.get("Score", 0.0)) - own_score < SUBSTITUTION_MIN_MARGIN:
            # Empate tecnico: el ranking no distingue de verdad entre los dos.
            return expected if accuracy > OMISSION_MAX_ACCURACY else None

        return top_ipa

    def _parse(self, payload: dict, locale: str) -> AssessmentResult:
        nbest = (payload.get("NBest") or [{}])[0]
        overall_pa = nbest.get("PronunciationAssessment", {})

        words: list[WordScore] = []
        for w_idx, w in enumerate(nbest.get("Words", [])):
            w_pa = w.get("PronunciationAssessment", {})
            phonemes: list[PhonemeScore] = []

            for p_idx, p in enumerate(w.get("Phonemes", [])):
                p_pa = p.get("PronunciationAssessment", {})
                expected = p.get("Phoneme", "")
                score = float(p_pa.get("AccuracyScore", 0.0))

                produced = self._produced_phoneme(
                    expected, score, p_pa.get("NBestPhonemes") or []
                )

                phonemes.append(
                    PhonemeScore(
                        index=p_idx,
                        expected_ipa=expected,
                        produced_ipa=produced,
                        score=score,
                    )
                )

            offset, duration = w.get("Offset"), w.get("Duration")
            words.append(
                WordScore(
                    index=w_idx,
                    surface=w.get("Word", ""),
                    score=float(w_pa.get("AccuracyScore", 0.0)),
                    error_type=_ERROR_TYPE_MAP.get(
                        str(w_pa.get("ErrorType", "None")).lower(), WordErrorType.NONE
                    ),
                    start_ms=offset // TICKS_PER_MS if offset is not None else None,
                    end_ms=(offset + duration) // TICKS_PER_MS
                    if offset is not None and duration is not None
                    else None,
                    phonemes=phonemes,
                )
            )

        return AssessmentResult(
            engine=self.name,
            engine_version=self.version,
            overall=float(overall_pa.get("PronScore", overall_pa.get("AccuracyScore", 0.0))),
            words=words,
            prosody=Prosody(
                fluency=overall_pa.get("FluencyScore"),
                completeness=overall_pa.get("CompletenessScore"),
                prosody_score=overall_pa.get("ProsodyScore"),
            ),
            raw=payload,
        )

    def health(self) -> EngineHealth:
        try:
            self._sdk()
        except EngineNotReady as exc:
            return EngineHealth(name=self.name, version=self.version, ready=False, detail=str(exc))
        return EngineHealth(
            name=self.name,
            version=self.version,
            ready=True,
            detail=f"region={self._region}",
        )
