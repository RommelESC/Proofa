from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.session_service import session_report

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("/report")
def report(
    session_id: int | None = Query(None, description="Por defecto, la ultima sesion"),
    db: Session = Depends(get_db),
) -> dict:
    """Que paso en una sesion de practica.

    No hay endpoint para abrir ni cerrar sesiones a proposito: se derivan del
    ritmo de grabacion. Un boton de «terminar» se olvida, y las sesiones sin
    cerrar arruinan los agregados de despues.
    """
    return session_report(db, session_id=session_id)
