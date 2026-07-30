from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.db import get_db
from app.engines import EngineNotReady
from app.services import assess_and_store, coaching_payload
from app.services.baseline_service import focus_in_attempt, weak_phonemes
from app.services.coach_panel_service import panel

router = APIRouter(prefix="/api/attempts", tags=["attempts"])

MAX_AUDIO_BYTES = 25 * 1024 * 1024


@router.post("")
async def create_attempt(
    audio: UploadFile = File(..., description="WAV PCM 16 kHz mono"),
    expected_text: str = Form(...),
    sentence_id: int | None = Form(None),
    session_id: int | None = Form(None),
    engine: str | None = Form(None),
    db: Session = Depends(get_db),
) -> dict:
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Audio vacio")
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio demasiado grande")
    if not expected_text.strip():
        raise HTTPException(status_code=400, detail="expected_text vacio")

    try:
        # Los motores bloquean (SDK de Azure, torch): fuera del event loop.
        attempt, result = await run_in_threadpool(
            assess_and_store,
            db,
            audio_bytes=audio_bytes,
            expected_text=expected_text,
            sentence_id=sentence_id,
            session_id=session_id,
            engine_name=engine,
        )
    except EngineNotReady as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # Contra tu propio historial, sin contar esta lectura: si se incluyera, una
    # lectura mala bajaria la vara con la que se la juzga.
    weak = weak_phonemes(db, engine=attempt.engine, exclude_attempt_id=attempt.id)
    said = [(p.expected_ipa, p.score) for w in result.words for p in w.phonemes]

    return {
        "attempt_id": attempt.id,
        "assessment": result.model_dump(exclude={"raw"}),
        "coaching": coaching_payload(result),
        "personal": focus_in_attempt(weak, said),
        # El detalle que se muestra al lado del texto. Viaja en la misma
        # respuesta: pedirlo aparte añadiría un viaje justo en el momento en
        # que estás esperando para seguir leyendo.
        "panel": panel(db, attempt.id),
    }


@router.get("/{attempt_id}/panel")
def get_panel(attempt_id: int, db: Session = Depends(get_db)) -> dict:
    """El panel de una lectura ya guardada, para volver a consultarla."""
    return panel(db, attempt_id)
