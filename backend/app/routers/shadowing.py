from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Attempt, WordScoreRow
from app.services.shadow_service import Timed, compare
from app.services.speech_service import speech_marks
from app.tts import TTSNotReady

router = APIRouter(prefix="/api/shadowing", tags=["shadowing"])


def _model_timeline(text: str) -> list[Timed]:
    """Los tiempos del modelo, sacados de las marcas del sintetizador."""
    out = []
    for m in speech_marks(text):
        start = m["text_offset"]
        out.append(
            Timed(
                surface=text[start : start + m["length"]],
                start_ms=m["audio_ms"],
                duration_ms=m["duration_ms"],
            )
        )
    return out


@router.get("/compare")
async def compare_rhythm(
    attempt_id: int = Query(..., description="Grabacion tuya ya evaluada"),
    db: Session = Depends(get_db),
) -> dict:
    """Tu ritmo contra el del modelo, palabra por palabra.

    Se calcula bajo demanda en vez de guardarse: los dos lados son derivados
    (tus tiempos ya estan en `word_scores`, los del modelo salen del audio
    cacheado), asi que persistir esto seria una tercera copia que puede quedar
    desincronizada de las otras dos.
    """
    attempt = db.get(Attempt, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Ese intento no existe")

    rows = list(
        db.execute(
            select(WordScoreRow)
            .where(WordScoreRow.attempt_id == attempt_id)
            .order_by(WordScoreRow.word_index)
        ).scalars()
    )
    yours = [
        Timed(r.surface, r.start_ms, r.end_ms - r.start_ms)
        for r in rows
        if r.start_ms is not None and r.end_ms is not None
    ]
    if not yours:
        raise HTTPException(
            status_code=409,
            detail="Esa grabacion no tiene tiempos por palabra; el motor no los reporto.",
        )

    try:
        model = await run_in_threadpool(_model_timeline, attempt.expected_text)
    except (TTSNotReady, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    result = compare(yours, model)
    result["text"] = attempt.expected_text
    result["attempt_id"] = attempt_id
    return result
