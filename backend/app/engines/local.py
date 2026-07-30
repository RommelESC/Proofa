"""Motor offline: wav2vec2 fonemico + alineacion forzada.

Este es el entregable real de la parte open source: sin llaves, sin costo
por minuto, sin que la voz salga de la maquina.

Ventaja tecnica sobre Azure que no es obvia: este modelo devuelve la
secuencia de fonemas REALMENTE producida, no solo un score del esperado.
Eso permite decir "dijiste /s/ donde iba /θ/" en vez de solo "esa th
estuvo mal", que es justo lo que necesitan los detectores de patterns.py.

Advertencia deliberada: un reconocedor entrenado para maxima exactitud
(p.ej. Whisper) NO sirve aqui. Whisper te corrige el acento al transcribir
y borra el error que queremos medir. Por eso usamos un modelo fonemico.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.engines.base import EngineNotReady, PronunciationEngine
from app.phonology.align import align, similarity_score
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

log = logging.getLogger(__name__)

TARGET_SR = 16_000

# eSpeak marca longitud y acento; a nosotros solo nos interesa la calidad
# del sonido, asi que lo normalizamos fuera.
_DIACRITICS = re.compile(r"[ːˈˌ̩̯͡]")
_ESPEAK_FIXES = {"ɡ": "ɡ", "r": "ɹ", "ɐ": "ə", "ᵻ": "ɪ", "ɑ̃": "ɑ"}


def _normalize(phoneme: str) -> str:
    p = _DIACRITICS.sub("", phoneme).strip()
    return _ESPEAK_FIXES.get(p, p)


class LocalW2V2Engine(PronunciationEngine):
    name = "local-w2v2"

    def __init__(self) -> None:
        self._model_id = get_settings().local_w2v2_model
        self.version = self._model_id.split("/")[-1]

    @lru_cache(maxsize=1)  # noqa: B019 - singleton por proceso, es lo que queremos
    def _load(self):
        try:
            import torch
            from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
        except ImportError as exc:
            raise EngineNotReady(
                "Faltan dependencias. Instala: pip install -r requirements-local.txt"
            ) from exc

        log.info("local: cargando %s (la primera vez descarga ~1-2 GB)", self._model_id)
        processor = Wav2Vec2Processor.from_pretrained(self._model_id)
        model = Wav2Vec2ForCTC.from_pretrained(self._model_id)
        model.eval()
        return torch, processor, model

    def _transcribe_phonemes(self, audio_path: Path) -> list[str]:
        torch, processor, model = self._load()
        try:
            import soundfile as sf
        except ImportError as exc:
            raise EngineNotReady("Falta soundfile (requirements-local.txt)") from exc

        audio, sr = sf.read(str(audio_path), dtype="float32", always_2d=True)
        audio = audio.mean(axis=1)  # a mono

        if sr != TARGET_SR:
            import numpy as np

            n = int(len(audio) * TARGET_SR / sr)
            audio = np.interp(
                np.linspace(0, len(audio), n, endpoint=False),
                np.arange(len(audio)),
                audio,
            ).astype("float32")

        inputs = processor(audio, sampling_rate=TARGET_SR, return_tensors="pt", padding=True)
        with torch.no_grad():
            logits = model(inputs.input_values).logits
        ids = torch.argmax(logits, dim=-1)
        decoded = processor.batch_decode(ids)[0]

        return [p for p in (_normalize(x) for x in decoded.split()) if p]

    def assess(
        self,
        audio_path: Path,
        expected_text: str,
        *,
        locale: str = "en-US",
    ) -> AssessmentResult:
        produced = self._transcribe_phonemes(audio_path)

        # Aplanamos lo esperado guardando a que palabra pertenece cada fonema,
        # alineamos las dos secuencias completas y repartimos de vuelta.
        per_word = phonemize_sentence(expected_text)
        flat_expected: list[str] = []
        owner: list[tuple[int, int]] = []  # (indice de palabra, indice dentro de la palabra)
        for w_idx, (_, seq) in enumerate(per_word):
            for p_idx, ph in enumerate(seq):
                flat_expected.append(ph)
                owner.append((w_idx, p_idx))

        pairs = align(flat_expected, produced)

        scores: dict[tuple[int, int], PhonemeScore] = {}
        for exp_i, prod_j in pairs:
            if exp_i is None:
                continue  # insercion: la registramos en raw, no penaliza una palabra concreta
            w_idx, p_idx = owner[exp_i]
            got = produced[prod_j] if prod_j is not None else None
            scores[(w_idx, p_idx)] = PhonemeScore(
                index=p_idx,
                expected_ipa=flat_expected[exp_i],
                produced_ipa=got,
                score=similarity_score(flat_expected[exp_i], got),
            )

        words: list[WordScore] = []
        for w_idx, (surface, seq) in enumerate(per_word):
            phonemes = [
                scores.get(
                    (w_idx, p_idx),
                    PhonemeScore(index=p_idx, expected_ipa=ph, produced_ipa=None, score=15.0),
                )
                for p_idx, ph in enumerate(seq)
            ]
            score = word_score(phonemes)
            spoken = sum(1 for p in phonemes if p.produced_ipa)
            words.append(
                WordScore(
                    index=w_idx,
                    surface=surface,
                    score=score,
                    error_type=(
                        WordErrorType.OMISSION
                        if phonemes and spoken == 0
                        else WordErrorType.MISPRONUNCIATION
                        if score < 60
                        else WordErrorType.NONE
                    ),
                    phonemes=phonemes,
                )
            )

        overall = round(sum(w.score for w in words) / len(words), 1) if words else 0.0
        matched = sum(1 for e, p in pairs if e is not None and p is not None)
        completeness = round(100 * matched / len(flat_expected), 1) if flat_expected else 0.0

        return AssessmentResult(
            engine=self.name,
            engine_version=self.version,
            overall=overall,
            words=words,
            prosody=Prosody(completeness=completeness),
            raw={
                "model": self._model_id,
                "produced_phonemes": produced,
                "expected_phonemes": flat_expected,
                "alignment": [[e, p] for e, p in pairs],
            },
        )

    def health(self) -> EngineHealth:
        try:
            import importlib.util

            missing = [
                m for m in ("torch", "transformers", "soundfile")
                if importlib.util.find_spec(m) is None
            ]
        except Exception as exc:  # noqa: BLE001
            return EngineHealth(name=self.name, version=self.version, ready=False, detail=str(exc))

        if missing:
            return EngineHealth(
                name=self.name,
                version=self.version,
                ready=False,
                detail=f"Faltan modulos: {', '.join(missing)}. pip install -r requirements-local.txt",
            )
        return EngineHealth(
            name=self.name,
            version=self.version,
            ready=True,
            detail=f"modelo={self._model_id} (se carga en la primera peticion)",
        )
