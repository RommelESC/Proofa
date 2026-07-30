"""Importa un EPUB a la base y traduce sus oraciones.

Deliberadamente NO crea filas en `tokens` al importar: un libro de 100 mil
palabras generaria 100 mil filas que solo hacen falta para SRS y analitica
de vocabulario. El tap-to-define no las necesita — el frontend manda la
palabra y su oracion, y la glosa se resuelve en contexto.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.content import read_epub, split_blocks
from app.llm import LLMNotReady, get_llm
from app.models import Book, Chapter, Sentence

log = logging.getLogger(__name__)


def import_epub(db: Session, epub_path: Path, *, license_note: str | None = None) -> Book:
    parsed = read_epub(epub_path)

    book = Book(
        title=parsed.title,
        author=parsed.author,
        source=epub_path.name,
        license_note=license_note,
    )
    db.add(book)
    db.flush()

    total = 0
    for parsed_chapter in parsed.chapters:
        chapter = Chapter(book_id=book.id, idx=parsed_chapter.idx, title=parsed_chapter.title)
        db.add(chapter)
        db.flush()

        for idx, seg in enumerate(split_blocks(parsed_chapter.blocks)):
            db.add(
                Sentence(
                    chapter_id=chapter.id,
                    idx=idx,
                    paragraph_idx=seg.paragraph_idx,
                    is_heading=seg.is_heading,
                    text_en=seg.text,
                )
            )
            total += 1

    db.flush()
    log.info("importado %r: %s capitulos, %s oraciones", book.title, len(parsed.chapters), total)
    return book


def translate_chapter(db: Session, chapter_id: int) -> int:
    """Rellena `text_es` de las oraciones pendientes. Devuelve cuantas tradujo.

    Se traduce oracion por oracion PERO con el parrafo entero a la vista. Las
    dos mitades importan: la granularidad por oracion da la alineacion exacta
    sin alineadores automaticos, y el parrafo da el contexto sin el cual la
    traduccion se vuelve literal.

    Por eso un parrafo nunca se parte entre dos lotes: si la mitad viajara en
    otra peticion, el modelo perderia justo el contexto que justifica todo esto.
    """
    settings = get_settings()
    llm = get_llm()

    stmt = (
        select(Sentence)
        .where(Sentence.chapter_id == chapter_id)
        .order_by(Sentence.idx)
    )
    all_sentences = list(db.execute(stmt).scalars())
    if not all_sentences:
        return 0

    # Agrupar por parrafo conservando el orden de lectura.
    paragraphs: list[list[Sentence]] = []
    for sentence in all_sentences:
        if paragraphs and paragraphs[-1][0].paragraph_idx == sentence.paragraph_idx:
            paragraphs[-1].append(sentence)
        else:
            paragraphs.append([sentence])

    # Un parrafo ya traducido no se reenvia: seria pagar dos veces por lo mismo.
    pending = [p for p in paragraphs if any(s.text_es is None for s in p)]
    if not pending:
        return 0

    done = 0
    size = max(1, settings.translation_batch_size)

    batch: list[list[Sentence]] = []
    count = 0

    def flush() -> int:
        nonlocal batch, count
        if not batch:
            return 0
        try:
            results = llm.translate_paragraphs([[s.text_en for s in p] for p in batch])
        except LLMNotReady:
            raise
        except Exception as exc:  # noqa: BLE001 - un lote fallido no pierde los previos
            log.warning("lote de traduccion fallido (%s); se continua con el siguiente", exc)
            batch, count = [], 0
            return 0

        written = 0
        for paragraph, translations in zip(batch, results, strict=False):
            for sentence, es in zip(paragraph, translations, strict=False):
                if es and sentence.text_es is None:
                    sentence.text_es = es
                    written += 1

        # Commit por lote: traducir un libro largo tarda, y un fallo a la
        # mitad no debe tirar el trabajo ya pagado a la API.
        db.commit()
        batch, count = [], 0
        return written

    try:
        for paragraph in pending:
            # Un parrafo mas grande que el lote viaja solo, entero.
            if count and count + len(paragraph) > size:
                done += flush()
            batch.append(paragraph)
            count += len(paragraph)
        done += flush()
    except LLMNotReady as exc:
        log.warning("traduccion detenida: %s", exc)
        db.commit()

    log.info("capitulo %s: %s oraciones traducidas", chapter_id, done)
    return done


def translation_progress(db: Session, chapter_id: int) -> dict:
    stmt = select(
        func.count().label("total"),
        func.count(Sentence.text_es).label("translated"),
    ).where(Sentence.chapter_id == chapter_id)
    row = db.execute(stmt).one()
    return {
        "total": row.total,
        "translated": row.translated,
        "pending": row.total - row.translated,
    }
