from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.drill_service import drill

router = APIRouter(prefix="/api", tags=["drills"])


@router.get("/drills")
async def get_drill(
    ipa: str | None = Query(None, description="Fonema a practicar; por defecto el que peor llevas"),
    limit: int = Query(6, ge=1, le=20),
    book_id: int | None = Query(None, description="Por defecto, el libro que estas leyendo"),
    db: Session = Depends(get_db),
) -> dict:
    """Material de practica para tu punto debil, sacado de tu propio libro.

    El primer barrido fonemiza el vocabulario del libro y tarda unos segundos;
    va fuera del event loop para no bloquear al resto. Despues queda en cache.
    """
    return await run_in_threadpool(drill, db, ipa=ipa, limit=limit, book_id=book_id)
