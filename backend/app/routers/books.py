from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_db
from app.llm import LLMNotReady, get_llm
from app.models import Book, Chapter, Sentence
from app.services.difficulty_service import book_difficulty
from app.services.gloss_service import lookup, most_looked_up, phonetics
from app.services.importer import import_epub, translate_chapter, translation_progress
from app.services.reading_service import (
    chapter_progress,
    latest_resume,
    resume_point,
    save_position,
)

router = APIRouter(prefix="/api", tags=["reader"])

MAX_EPUB_BYTES = 100 * 1024 * 1024


class BookOut(BaseModel):
    id: int
    title: str
    author: str | None
    cefr: str | None
    chapters: int
    sentences: int


class ChapterOut(BaseModel):
    id: int
    # De qué libro es. El lector recibe un capítulo suelto y sin esto no puede
    # pedir sus hermanos, así que saltar de capítulo obligaba a volver a la
    # Biblioteca.
    book_id: int
    idx: int
    title: str | None
    sentences: int
    # Hasta dónde llegaste leyendo (no es lo mismo que practicado).
    reached: int = 0
    # Oraciones que sí leíste en voz alta.
    practiced: int = 0
    last_sentence_id: int | None = None


class PositionIn(BaseModel):
    sentence_id: int


class SentenceOut(BaseModel):
    id: int
    idx: int
    # El lector agrupa por esto para maquetar prosa en vez de una fila por
    # oracion, y para mostrar el espanol a nivel de parrafo.
    paragraph_idx: int
    is_heading: bool
    text_en: str
    text_es: str | None


@router.post("/books/import", response_model=BookOut)
async def import_book(
    epub: UploadFile = File(..., description="Archivo .epub"),
    db: Session = Depends(get_db),
) -> BookOut:
    """Importa un EPUB del disco del usuario.

    El repositorio no distribuye libros: cada quien importa los suyos o
    descarga de dominio publico en su propia maquina.
    """
    if not (epub.filename or "").lower().endswith(".epub"):
        raise HTTPException(status_code=400, detail="Se espera un archivo .epub")

    payload = await epub.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Archivo vacio")
    if len(payload) > MAX_EPUB_BYTES:
        raise HTTPException(status_code=413, detail="Archivo demasiado grande")

    tmp = Path(tempfile.gettempdir()) / f"import-{abs(hash(epub.filename))}.epub"
    tmp.write_bytes(payload)
    try:
        book = await run_in_threadpool(import_epub, db, tmp)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        tmp.unlink(missing_ok=True)

    return _book_out(db, book)


def _book_out(db: Session, book: Book) -> BookOut:
    counts = db.execute(
        select(
            func.count(func.distinct(Chapter.id)),
            func.count(Sentence.id),
        )
        .select_from(Chapter)
        .outerjoin(Sentence, Sentence.chapter_id == Chapter.id)
        .where(Chapter.book_id == book.id)
    ).one()
    return BookOut(
        id=book.id,
        title=book.title,
        author=book.author,
        cefr=book.cefr,
        chapters=counts[0],
        sentences=counts[1],
    )


@router.get("/books", response_model=list[BookOut])
def list_books(db: Session = Depends(get_db)) -> list[BookOut]:
    books = list(db.execute(select(Book).order_by(Book.created_at.desc())).scalars())
    return [_book_out(db, b) for b in books]


@router.get("/books/{book_id}/chapters", response_model=list[ChapterOut])
def list_chapters(book_id: int, db: Session = Depends(get_db)) -> list[ChapterOut]:
    stmt = (
        select(Chapter, func.count(Sentence.id))
        .outerjoin(Sentence, Sentence.chapter_id == Chapter.id)
        .where(Chapter.book_id == book_id)
        .group_by(Chapter.id)
        .order_by(Chapter.idx)
    )
    rows = db.execute(stmt).all()
    if not rows:
        raise HTTPException(status_code=404, detail="Libro sin capitulos")

    progress = chapter_progress(db, book_id)
    return [
        ChapterOut(
            id=ch.id,
            book_id=ch.book_id,
            idx=ch.idx,
            title=ch.title,
            sentences=n,
            reached=progress.get(ch.id, {}).get("reached", 0),
            practiced=progress.get(ch.id, {}).get("practiced", 0),
            last_sentence_id=progress.get(ch.id, {}).get("last_sentence_id"),
        )
        for ch, n in rows
    ]


@router.get("/books/{book_id}/difficulty")
async def get_difficulty(book_id: int, db: Session = Depends(get_db)) -> dict:
    """Cuánto cuesta leer este libro, medido sobre su propio texto.

    El primer cálculo fonemiza el vocabulario entero y tarda unos segundos; va
    fuera del event loop y después queda cacheado.
    """
    return await run_in_threadpool(book_difficulty, db, book_id)


@router.get("/resume")
def get_latest_resume(db: Session = Depends(get_db)) -> dict:
    """Donde reanudar, mires el libro que mires. Para la pantalla de inicio."""
    return {"resume": latest_resume(db)}


@router.get("/books/{book_id}/resume")
def get_resume_point(book_id: int, db: Session = Depends(get_db)) -> dict:
    """Donde reanudar este libro, o null si nunca lo abriste."""
    return {"resume": resume_point(db, book_id)}


@router.put("/chapters/{chapter_id}/position")
def put_position(chapter_id: int, payload: PositionIn, db: Session = Depends(get_db)) -> dict:
    """Anota donde vas. Se llama seguido mientras lees: es un upsert barato."""
    try:
        row = save_position(db, chapter_id, payload.sentence_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"last_sentence_id": row.last_sentence_id, "furthest_idx": row.furthest_idx}


@router.get("/chapters/{chapter_id}", response_model=list[SentenceOut])
def read_chapter(chapter_id: int, db: Session = Depends(get_db)) -> list[Sentence]:
    stmt = select(Sentence).where(Sentence.chapter_id == chapter_id).order_by(Sentence.idx)
    sentences = list(db.execute(stmt).scalars())
    if not sentences:
        raise HTTPException(status_code=404, detail="Capitulo vacio")
    return sentences


def _translate_job(chapter_id: int) -> None:
    """Corre fuera del request: traducir un capitulo tarda."""
    with SessionLocal() as session:
        translate_chapter(session, chapter_id)
        session.commit()


@router.post("/chapters/{chapter_id}/translate")
def start_translation(
    chapter_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    progress = translation_progress(db, chapter_id)
    if progress["total"] == 0:
        raise HTTPException(status_code=404, detail="Capitulo vacio")

    health = get_llm().health()
    if not health.ready:
        raise HTTPException(status_code=503, detail=health.detail)

    if progress["pending"]:
        background.add_task(_translate_job, chapter_id)

    return {"started": bool(progress["pending"]), "progress": progress}


@router.get("/chapters/{chapter_id}/translation")
def get_translation_progress(chapter_id: int, db: Session = Depends(get_db)) -> dict:
    return translation_progress(db, chapter_id)


@router.get("/phonetics")
def get_phonetics(word: str) -> dict:
    """IPA de una palabra. Local e instantaneo: no toca el LLM.

    Existe para que la interfaz responda de inmediato al tocar una palabra,
    mientras el significado todavia viene en camino.
    """
    if not word.strip():
        raise HTTPException(status_code=400, detail="Falta `word`")
    return {"word": word, "ipa": phonetics(word)}


@router.get("/gloss")
async def gloss_word(
    word: str,
    sentence: str,
    sentence_id: int | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """Definicion de la palabra EN ESTA ORACION.

    No es una busqueda de diccionario: «run» en «run a business» no es correr.
    Con cache: la segunda consulta de la misma palabra en la misma oracion es
    inmediata.
    """
    if not word.strip() or not sentence.strip():
        raise HTTPException(status_code=400, detail="Faltan `word` o `sentence`")
    try:
        return await run_in_threadpool(lookup, db, word, sentence, sentence_id)
    except LLMNotReady as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/vocab")
def vocab(limit: int = 40, db: Session = Depends(get_db)) -> dict:
    """Las palabras que mas has vuelto a consultar."""
    return {"words": most_looked_up(db, limit)}
