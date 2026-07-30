"""Siembra el catalogo de patrones de error.

La definicion vive en phonology/patterns.py (codigo, versionado) y se
proyecta a la tabla. Un solo lugar de verdad: si agregas un patron alli,
esto lo sincroniza.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import ErrorPatternRow
from app.phonology.patterns import PATTERNS


def sync_error_patterns(db: Session) -> int:
    existing = {row.code: row for row in db.query(ErrorPatternRow).all()}
    touched = 0

    for pattern in PATTERNS:
        row = existing.get(pattern.code)
        if row is None:
            db.add(
                ErrorPatternRow(
                    code=pattern.code,
                    label_es=pattern.label_es,
                    explanation_es=pattern.explanation_es,
                    minimal_pairs=list(pattern.minimal_pairs),
                )
            )
            touched += 1
        else:
            row.label_es = pattern.label_es
            row.explanation_es = pattern.explanation_es
            row.minimal_pairs = list(pattern.minimal_pairs)
            touched += 1

    db.flush()
    return touched
