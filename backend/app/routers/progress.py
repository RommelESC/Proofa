"""Analitica longitudinal.

Todo sale de `phoneme_scores` y `pattern_hits`. Estas son las metricas que
significan algo (un fonema concreto mejorando en el tiempo), no puntos ni XP.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    Attempt,
    ErrorPatternRow,
    PatternHitRow,
    PhonemeScoreRow,
    WordScoreRow,
)
from app.services.baseline_service import personal_baseline
from app.services.pace_service import reading_pace
from app.services.week_service import week

router = APIRouter(prefix="/api/progress", tags=["progress"])


def _since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


@router.get("/phonemes")
def phoneme_accuracy(days: int = 30, db: Session = Depends(get_db)) -> dict:
    """El radar: precision media por fonema esperado. Los peores primero."""
    stmt = (
        select(
            PhonemeScoreRow.expected_ipa,
            func.count().label("n"),
            func.avg(PhonemeScoreRow.score).label("mean_score"),
            func.percentile_cont(0.25)
            .within_group(PhonemeScoreRow.score)
            .label("p25"),
        )
        # phoneme -> word -> attempt: cada nivel referencia solo a su padre,
        # asi que llegar a la fecha del intento cuesta dos joins. Es el precio
        # de que la jerarquia tenga integridad referencial real.
        .join(WordScoreRow, WordScoreRow.id == PhonemeScoreRow.word_score_id)
        .join(Attempt, Attempt.id == WordScoreRow.attempt_id)
        .where(Attempt.recorded_at >= _since(days))
        .group_by(PhonemeScoreRow.expected_ipa)
        .having(func.count() >= 3)
        .order_by(func.avg(PhonemeScoreRow.score))
    )
    rows = db.execute(stmt).all()
    return {
        "days": days,
        "phonemes": [
            {
                "ipa": r.expected_ipa,
                "samples": r.n,
                "mean_score": round(float(r.mean_score), 1),
                "p25": round(float(r.p25), 1),
            }
            for r in rows
        ],
    }


@router.get("/baseline")
def baseline(
    days: int = 90, engine: str | None = None, db: Session = Depends(get_db)
) -> dict:
    """Tus puntos debiles medidos contra ti mismo, no contra un umbral fijo.

    La ventana es mas larga que la del resto de metricas a proposito: aqui no
    se mira la tendencia sino el nivel, y con pocas semanas de practica una
    ventana corta deja casi todo sin resolver.
    """
    return personal_baseline(db, days=days, engine=engine)


@router.get("/week")
def this_week(db: Session = Depends(get_db)) -> dict:
    """Minutos, velocidad y precisión de los últimos siete días."""
    return week(db)


@router.get("/pace")
def pace(days: int = 90, db: Session = Depends(get_db)) -> dict:
    """Tu velocidad medida leyendo en voz alta, para el marcapasos."""
    return reading_pace(db, days=days)


@router.get("/patterns")
def pattern_frequency(days: int = 30, db: Session = Depends(get_db)) -> dict:
    """Que errores de la taxonomia L1-espanol se repiten mas."""
    stmt = (
        select(
            PatternHitRow.pattern_code,
            ErrorPatternRow.label_es,
            func.count().label("hits"),
            func.avg(PatternHitRow.confidence).label("mean_confidence"),
        )
        .join(WordScoreRow, WordScoreRow.id == PatternHitRow.word_score_id)
        .join(Attempt, Attempt.id == WordScoreRow.attempt_id)
        .join(ErrorPatternRow, ErrorPatternRow.code == PatternHitRow.pattern_code)
        .where(Attempt.recorded_at >= _since(days))
        .group_by(PatternHitRow.pattern_code, ErrorPatternRow.label_es)
        .order_by(func.count().desc())
    )
    rows = db.execute(stmt).all()
    return {
        "days": days,
        "patterns": [
            {
                "code": r.pattern_code,
                "label": r.label_es,
                "hits": r.hits,
                "mean_confidence": round(float(r.mean_confidence), 2),
            }
            for r in rows
        ],
    }


@router.get("/timeline")
def timeline(days: int = 30, db: Session = Depends(get_db)) -> dict:
    """Score global por dia, separado por motor: mezclar motores en una
    misma serie produce saltos que parecen progreso y no lo son."""
    day = func.date_trunc("day", Attempt.recorded_at).label("day")
    stmt = (
        select(
            day,
            Attempt.engine,
            func.count().label("attempts"),
            func.avg(Attempt.overall).label("mean_overall"),
            func.avg(Attempt.wpm).label("mean_wpm"),
        )
        .where(Attempt.recorded_at >= _since(days))
        .group_by(day, Attempt.engine)
        .order_by(day)
    )
    rows = db.execute(stmt).all()
    return {
        "days": days,
        "points": [
            {
                "day": r.day.date().isoformat(),
                "engine": r.engine,
                "attempts": r.attempts,
                "mean_overall": round(float(r.mean_overall), 1),
                "mean_wpm": round(float(r.mean_wpm), 1) if r.mean_wpm is not None else None,
            }
            for r in rows
        ],
    }
