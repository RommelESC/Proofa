"""Orquesta un intento de lectura en voz alta.

Flujo: audio -> disco -> motor -> deteccion de patrones -> Postgres.

El `raw` del motor se guarda intacto y las tablas normalizadas se derivan
de el. Eso es lo que permite, mas adelante, re-evaluar todo el historial
con otro motor o recalcular la taxonomia sin volver a grabar nada.
"""

from __future__ import annotations

import hashlib
import logging
import wave
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.engines import get_engine
from app.models import (
    Asset,
    AssetKind,
    Attempt,
    PatternHitRow,
    PhonemeScoreRow,
    WordScoreRow,
)
from app.phonology import PATTERNS_BY_CODE, detect
from app.schemas.assessment import AssessmentResult, WordErrorType
from app.services.session_service import current_session

log = logging.getLogger(__name__)


def _wav_info(path: Path) -> tuple[int | None, int | None]:
    """(duracion_ms, sample_rate) leyendo solo la cabecera. `wave` es stdlib."""
    try:
        with wave.open(str(path), "rb") as wf:
            frames, rate = wf.getnframes(), wf.getframerate()
            return (int(1000 * frames / rate) if rate else None, rate)
    except Exception as exc:  # noqa: BLE001 - un audio raro no debe tumbar el intento
        log.warning("no se pudo leer la cabecera WAV de %s: %s", path.name, exc)
        return None, None


def store_recording(db: Session, audio_bytes: bytes) -> tuple[Asset, Path]:
    """Guarda el audio direccionado por contenido: mismo audio, mismo asset.

    El archivo se nombra con su digest, asi que el disco ya deduplicaba. La
    FILA no: sin esta busqueda previa, dos audios identicos creaban dos
    registros apuntando al mismo WAV. Importa de verdad para el TTS cacheado,
    donde la misma oracion con la misma voz produce siempre los mismos bytes.
    """
    settings = get_settings()
    digest = hashlib.sha256(audio_bytes).hexdigest()

    day_dir = settings.assets_dir / "recordings" / datetime.now(timezone.utc).strftime("%Y-%m")
    day_dir.mkdir(parents=True, exist_ok=True)
    path = day_dir / f"{digest[:16]}.wav"
    if not path.exists():
        path.write_bytes(audio_bytes)

    existing = db.execute(select(Asset).where(Asset.sha256 == digest)).scalar_one_or_none()
    if existing is not None:
        return existing, settings.assets_dir / existing.path

    duration_ms, sample_rate = _wav_info(path)
    asset = Asset(
        kind=AssetKind.RECORDING,
        path=str(path.relative_to(settings.assets_dir)),
        sha256=digest,
        sample_rate=sample_rate,
        duration_ms=duration_ms,
    )
    db.add(asset)
    db.flush()
    return asset, path


def assess_and_store(
    db: Session,
    *,
    audio_bytes: bytes,
    expected_text: str,
    sentence_id: int | None = None,
    session_id: int | None = None,
    engine_name: str | None = None,
) -> tuple[Attempt, AssessmentResult]:
    asset, path = store_recording(db, audio_bytes)

    # La sesion se resuelve aqui y no en el router: asi la agrupan igual las
    # grabaciones del lector y las de la vista de fonemas, sin que ninguna de
    # las dos tenga que acordarse de gestionar un ciclo de vida.
    if session_id is None:
        session_id = current_session(db).id

    engine = get_engine(engine_name)
    result = engine.assess(path, expected_text)

    # La taxonomia L1-espanol corre sobre el resultado normalizado, asi que
    # funciona igual con cualquier motor.
    result.patterns = detect(result.words)

    wpm = result.prosody.wpm
    if wpm is None and asset.duration_ms:
        wpm = round(len(result.words) / (asset.duration_ms / 60_000), 1)

    attempt = Attempt(
        sentence_id=sentence_id,
        session_id=session_id,
        audio_asset_id=asset.id,
        engine=result.engine,
        engine_version=result.engine_version,
        expected_text=expected_text,
        overall=result.overall,
        wpm=wpm,
        fluency=result.prosody.fluency,
        completeness=result.prosody.completeness,
        prosody_score=result.prosody.prosody_score,
        duration_ms=asset.duration_ms,
        raw=result.raw,
    )

    # Se construye el grafo completo y SQLAlchemy resuelve el orden de
    # inserciones y las claves foraneas. Asi los indices del motor
    # (word_index / phoneme_index) se traducen a FK reales una sola vez,
    # aqui, en lugar de quedar como referencias sueltas en la base.
    word_rows: dict[int, WordScoreRow] = {}
    phoneme_rows: dict[tuple[int, int], PhonemeScoreRow] = {}

    for word in result.words:
        word_row = WordScoreRow(
            word_index=word.index,
            surface=word.surface,
            score=word.score,
            error_type=word.error_type.value,
            stress_ok=word.stress_ok,
            start_ms=word.start_ms,
            end_ms=word.end_ms,
        )
        for ph in word.phonemes:
            phoneme_row = PhonemeScoreRow(
                phoneme_index=ph.index,
                expected_ipa=ph.expected_ipa,
                produced_ipa=ph.produced_ipa,
                score=ph.score,
            )
            word_row.phonemes.append(phoneme_row)
            phoneme_rows[(word.index, ph.index)] = phoneme_row

        attempt.words.append(word_row)
        word_rows[word.index] = word_row

    for hit in result.patterns:
        word_row = word_rows.get(hit.word_index)
        if word_row is None:
            log.warning("hit %s apunta a la palabra %s, inexistente", hit.code, hit.word_index)
            continue
        word_row.pattern_hits.append(
            PatternHitRow(
                pattern_code=hit.code,
                phoneme=phoneme_rows.get((hit.word_index, hit.phoneme_index))
                if hit.phoneme_index is not None
                else None,
                confidence=hit.confidence,
                detail=hit.detail,
            )
        )

    db.add(attempt)
    db.flush()
    return attempt, result


# Por debajo de esto la lectura quedo tan incompleta que el score global deja
# de significar algo. Medido: decir «I think» y parar da completitud 18 y un
# global de 45 — indistinguible de haber leido todo con mala pronunciacion.
MIN_COMPLETENESS = 60.0


def _usability(result: AssessmentResult) -> str | None:
    """Devuelve un aviso si la grabacion no es evaluable, o None si lo es.

    Mostrar «45» sobre una lectura truncada es desinformacion: el alumno lee
    «pronuncie mal» cuando en realidad solto el boton antes de terminar. Hace
    el mismo dano que un falso positivo, y es igual de facil de evitar.
    """
    spoken = sum(1 for w in result.words if w.error_type != WordErrorType.OMISSION)
    if not result.words or spoken == 0 or result.overall == 0:
        return "No se detectó voz. Revisa el micrófono y vuelve a intentarlo."

    completeness = result.prosody.completeness
    if completeness is not None and completeness < MIN_COMPLETENESS:
        return (
            f"Solo se leyó el {completeness:.0f}% de la frase. El score no es "
            "comparable con una lectura completa: vuelve a grabar y lee hasta el final."
        )
    return None


def coaching_payload(result: AssessmentResult, *, max_focus: int = 2) -> dict:
    """Lo que se le mostraria al alumno (y lo que se le pasaria a Claude).

    Deliberadamente limitado a `max_focus` errores: corregir todo a la vez
    es tecnicamente correcto y pedagogicamente pesimo.
    """
    warning = _usability(result)
    if warning is not None:
        # Sin diagnostico sobre una grabacion no evaluable: un patron
        # detectado en dos palabras sueltas no dice nada de tu pronunciacion.
        return {
            "overall": result.overall,
            "engine": result.engine,
            "synthetic": bool(result.raw.get("synthetic")),
            "usable": False,
            "warning": warning,
            "focus": [],
            "worst_words": [],
        }

    by_code: dict[str, list] = {}
    for hit in result.patterns:
        by_code.setdefault(hit.code, []).append(hit)

    ranked = sorted(
        by_code.items(),
        key=lambda kv: (len(kv[1]), max(h.confidence for h in kv[1])),
        reverse=True,
    )

    focus = []
    for code, hits in ranked[:max_focus]:
        pattern = PATTERNS_BY_CODE.get(code)
        if pattern is None:
            continue
        focus.append(
            {
                "code": code,
                "label": pattern.label_es,
                "explanation": pattern.explanation_es,
                "minimal_pairs": list(pattern.minimal_pairs),
                "occurrences": len(hits),
                "examples": [h.detail for h in hits[:4]],
            }
        )

    return {
        "overall": result.overall,
        "engine": result.engine,
        "synthetic": bool(result.raw.get("synthetic")),
        "usable": True,
        "warning": None,
        "focus": focus,
        "worst_words": [
            {
                "index": w.index,
                "surface": w.surface,
                "score": w.score,
                # El IPA viaja al TTS para forzar la pronunciacion exacta: sin
                # el, la sintesis puede leer la palabra de una forma razonable
                # que no es la que se esta corrigiendo.
                "ipa": "".join(p.expected_ipa for p in w.phonemes),
            }
            for w in result.worst_words[:5]
        ],
    }
