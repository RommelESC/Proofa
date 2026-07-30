"""Agrupa en sesiones los intentos que se guardaron antes de que existieran.

Solo rellena `session_id` donde esta nulo — no reasigna nada. Es dato derivado:
si el corte por inactividad se afina, se vuelve a correr sin perder nada.

    python -m scripts.backfill_sessions          # muestra lo que haria
    python -m scripts.backfill_sessions --apply  # lo escribe
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Attempt, Chapter, ReadingSession, Sentence  # noqa: E402
from app.services.session_service import SESSION_GAP  # noqa: E402


def group(attempts: list[Attempt]) -> list[list[Attempt]]:
    """Corta la lista donde haya un hueco mayor que SESSION_GAP."""
    blocks: list[list[Attempt]] = []
    for a in attempts:
        if blocks and a.recorded_at - blocks[-1][-1].recorded_at < SESSION_GAP:
            blocks[-1].append(a)
        else:
            blocks.append([a])
    return blocks


def book_of(db, attempts: list[Attempt]) -> int | None:
    """El libro de la sesion, si los intentos venian de uno."""
    for a in attempts:
        if a.sentence_id is None:
            continue
        book_id = db.execute(
            select(Chapter.book_id)
            .join(Sentence, Sentence.chapter_id == Chapter.id)
            .where(Sentence.id == a.sentence_id)
        ).scalar_one_or_none()
        if book_id is not None:
            return book_id
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="escribe los cambios")
    args = ap.parse_args()

    db = SessionLocal()
    huerfanos = list(
        db.execute(
            select(Attempt)
            .where(Attempt.session_id.is_(None))
            .order_by(Attempt.recorded_at)
        ).scalars()
    )
    if not huerfanos:
        print("nada que agrupar: todos los intentos ya tienen sesion")
        return

    blocks = group(huerfanos)
    print(f"{len(huerfanos)} intentos sueltos -> {len(blocks)} sesiones\n")

    for i, block in enumerate(blocks, 1):
        span = (block[-1].recorded_at - block[0].recorded_at).total_seconds() / 60
        media = sum(a.overall for a in block) / len(block)
        print(
            f"  sesion {i}: {len(block):>2} intentos  "
            f"{block[0].recorded_at:%Y-%m-%d %H:%M} +{span:.0f} min  media {media:.1f}"
        )

        if args.apply:
            session = ReadingSession(
                started_at=block[0].recorded_at,
                ended_at=block[-1].recorded_at,
                book_id=book_of(db, block),
                mode="read_aloud",
            )
            db.add(session)
            db.flush()
            for a in block:
                a.session_id = session.id

    if args.apply:
        db.commit()
        print("\nescrito.")
    else:
        print("\n(simulacion — usa --apply para escribirlo)")
    db.close()


if __name__ == "__main__":
    main()
