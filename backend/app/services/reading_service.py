"""Guardar y consultar el avance de lectura."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Attempt, Book, Chapter, ReadingProgress, Sentence


def save_position(db: Session, chapter_id: int, sentence_id: int) -> ReadingProgress:
    """Anota dónde vas. Se llama seguido mientras lees, así que es un upsert.

    `furthest_idx` usa GREATEST: volver atrás a releer no debe borrar lo más
    lejos que llegaste, o el progreso del capítulo bajaría por releer.
    """
    sentence = db.get(Sentence, sentence_id)
    if sentence is None or sentence.chapter_id != chapter_id:
        raise ValueError("La oración no pertenece a ese capítulo")

    stmt = (
        insert(ReadingProgress)
        .values(
            chapter_id=chapter_id,
            last_sentence_id=sentence_id,
            furthest_idx=sentence.idx,
        )
        .on_conflict_do_update(
            index_elements=[ReadingProgress.chapter_id],
            set_={
                "last_sentence_id": sentence_id,
                "furthest_idx": func.greatest(ReadingProgress.furthest_idx, sentence.idx),
                "updated_at": func.now(),
            },
        )
        .returning(ReadingProgress)
    )
    row = db.execute(stmt).scalar_one()
    db.commit()
    return row


def chapter_progress(db: Session, book_id: int) -> dict[int, dict]:
    """Avance por capítulo de un libro, listo para la lista de capítulos."""
    totals = db.execute(
        select(Sentence.chapter_id, func.count())
        .join(Chapter, Chapter.id == Sentence.chapter_id)
        .where(Chapter.book_id == book_id)
        .group_by(Sentence.chapter_id)
    ).all()

    progress = db.execute(
        select(ReadingProgress)
        .join(Chapter, Chapter.id == ReadingProgress.chapter_id)
        .where(Chapter.book_id == book_id)
    ).scalars()
    by_chapter = {p.chapter_id: p for p in progress}

    # «Practicado» se cuenta aparte: pasar por una oración no es haberla leído
    # en voz alta, y juntarlos inflaría el avance con puro scroll.
    practiced = dict(
        db.execute(
            select(Sentence.chapter_id, func.count(func.distinct(Attempt.sentence_id)))
            .join(Attempt, Attempt.sentence_id == Sentence.id)
            .join(Chapter, Chapter.id == Sentence.chapter_id)
            .where(Chapter.book_id == book_id)
            .group_by(Sentence.chapter_id)
        ).all()
    )

    out: dict[int, dict] = {}
    for chapter_id, total in totals:
        row = by_chapter.get(chapter_id)
        reached = (row.furthest_idx + 1) if row else 0
        out[chapter_id] = {
            "total": total,
            "reached": min(reached, total),
            "practiced": practiced.get(chapter_id, 0),
            "last_sentence_id": row.last_sentence_id if row else None,
        }
    return out


def latest_resume(db: Session) -> dict | None:
    """Dónde reanudar, sin preguntar por qué libro.

    `resume_point` necesita saber el libro, y la pantalla de inicio no lo sabe:
    lo que quiere responder es «sigue por aquí». Se resuelve por la marca de
    tiempo del avance, que es lo único que sabe cuál tocaste al final.
    """
    row = db.execute(
        select(ReadingProgress, Chapter, Book)
        .join(Chapter, Chapter.id == ReadingProgress.chapter_id)
        .join(Book, Book.id == Chapter.book_id)
        .order_by(ReadingProgress.updated_at.desc())
        .limit(1)
    ).first()
    if row is None:
        return None

    progress, chapter, book = row
    total = db.execute(
        select(func.count()).select_from(Sentence).where(Sentence.chapter_id == chapter.id)
    ).scalar_one()

    # La posición se cuenta desde la oración anclada; si se perdió al reimportar
    # queda el alcance, que sobrevive porque es un índice y no una clave.
    idx = progress.furthest_idx
    if progress.last_sentence_id is not None:
        sentence = db.get(Sentence, progress.last_sentence_id)
        if sentence is not None:
            idx = sentence.idx

    return {
        "book_id": book.id,
        "book_title": book.title,
        "chapter_id": chapter.id,
        "chapter_idx": chapter.idx,
        "chapter_title": chapter.title,
        "sentence_id": progress.last_sentence_id,
        "sentence_idx": idx,
        "sentences": total,
        "updated_at": progress.updated_at.isoformat(),
    }


def resume_point(db: Session, book_id: int) -> dict | None:
    """El capítulo donde reanudar: el último que tocaste en este libro."""
    row = db.execute(
        select(ReadingProgress, Chapter)
        .join(Chapter, Chapter.id == ReadingProgress.chapter_id)
        .where(Chapter.book_id == book_id)
        .order_by(ReadingProgress.updated_at.desc())
        .limit(1)
    ).first()
    if row is None:
        return None

    progress, chapter = row
    return {
        "chapter_id": chapter.id,
        "chapter_idx": chapter.idx,
        "chapter_title": chapter.title,
        "sentence_id": progress.last_sentence_id,
        "furthest_idx": progress.furthest_idx,
    }
