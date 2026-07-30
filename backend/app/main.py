from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import SessionLocal
from app.engines import ENGINES, get_engine
from app.phonology import PATTERNS
from app.services import sync_error_patterns

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # La base puede no estar lista todavia; /api/health debe seguir
    # respondiendo para poder diagnosticar justamente eso.
    try:
        with SessionLocal() as db:
            n = sync_error_patterns(db)
            db.commit()
        log.info("patrones de error sincronizados: %s", n)
    except Exception as exc:  # noqa: BLE001
        log.warning("no se pudo sincronizar la taxonomia (base no lista?): %s", exc)

    # En un hilo aparte y sin esperarlo: cargar un modelo local tarda segundos
    # y el servidor tiene que estar respondiendo mientras. Si falla, la app
    # sigue funcionando sin glosas y /api/health lo dice.
    threading.Thread(target=_prewarm_llm, daemon=True).start()
    yield


def _prewarm_llm() -> None:
    try:
        from app.llm import get_llm

        get_llm().prewarm()
    except Exception as exc:  # noqa: BLE001
        log.info("no se pudo precalentar el LLM: %s", exc)


settings = get_settings()

app = FastAPI(
    title="Ingles - lectura en voz alta",
    description="Lee un texto en voz alta y recibe correccion fonetica en contexto.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import (  # noqa: E402
    attempts,
    books,
    content,
    drills,
    progress,
    sessions,
    shadowing,
    speech,
)

app.include_router(attempts.router)
app.include_router(books.router)
app.include_router(content.router)
app.include_router(drills.router)
app.include_router(progress.router)
app.include_router(sessions.router)
app.include_router(shadowing.router)
app.include_router(speech.router)


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    from app.phonology.g2p import get_g2p

    engines = {}
    for name in ENGINES:
        try:
            engines[name] = get_engine(name).health().model_dump()
        except Exception as exc:  # noqa: BLE001
            engines[name] = {"name": name, "ready": False, "detail": str(exc)}

    db_ok, db_detail = True, "ok"
    try:
        from sqlalchemy import text

        with SessionLocal() as db:
            db.execute(text("select 1"))
    except Exception as exc:  # noqa: BLE001
        db_ok, db_detail = False, str(exc)[:200]

    from app.llm import get_llm

    try:
        llm = get_llm().health().model_dump()
    except Exception as exc:  # noqa: BLE001
        llm = {"name": settings.llm_provider, "ready": False, "detail": str(exc)}

    return {
        "active_engine": settings.pronunciation_engine,
        "engines": engines,
        "llm": llm,
        "g2p": get_g2p().name,
        "error_patterns": len(PATTERNS),
        "database": {"ok": db_ok, "detail": db_detail},
    }
