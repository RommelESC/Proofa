"""Definición de una palabra en su contexto, con caché.

Dos mejoras sobre llamar al LLM directo, y las dos atacan el mismo problema:
que consultar una palabra tardaba 7-10 segundos con un modelo local.

1. **Caché**: la misma palabra en la misma oración siempre significa lo mismo.
   La segunda consulta es instantánea.
2. **IPA inmediata**: la transcripción sale del g2p local en microsegundos, sin
   tocar el LLM. Se puede mostrar mientras el significado todavía viene en
   camino, así que la interfaz responde de inmediato aunque la respuesta
   completa tarde.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.llm import LLMNotReady, get_llm
from app.models import Sentence
from app.models.vocab import Gloss as GlossRow
from app.phonology.g2p import get_g2p

log = logging.getLogger(__name__)


def phonetics(word: str) -> str:
    """IPA esperada. Local, instantánea, sin LLM."""
    return "".join(get_g2p().phonemize(word))


def lookup(
    db: Session, word: str, sentence: str, sentence_id: int | None = None
) -> dict:
    surface = word.strip().lower()
    if not surface:
        raise ValueError("Palabra vacía")

    # `sentence_id` ancla el sentido a su contexto. Sin él (texto suelto) el
    # caché es por palabra sola, que es más grueso pero sigue sirviendo.
    if sentence_id is not None and db.get(Sentence, sentence_id) is None:
        sentence_id = None

    cached = db.execute(
        select(GlossRow).where(
            GlossRow.surface_lower == surface,
            GlossRow.sentence_id == sentence_id,
        )
    ).scalar_one_or_none()

    if cached is not None:
        # Cuántas veces la miraste es la señal de que todavía no se aprende.
        cached.lookups += 1
        db.commit()
        return _out(cached, surface, cached=True)

    llm = get_llm()
    result = llm.gloss(word, sentence)

    row = GlossRow(
        surface_lower=surface,
        sentence_id=sentence_id,
        lemma=result.lemma or surface,
        pos=result.pos or "",
        sense_es=result.sense_es or "",
        note_es=result.note_es or "",
        provider=llm.name,
        model=_model_of(llm),
    )
    db.add(row)
    db.commit()
    return _out(row, surface, cached=False)


def _model_of(llm) -> str:  # noqa: ANN001
    settings = get_settings()
    if llm.name == "ollama":
        return settings.ollama_gloss_model or settings.ollama_model
    if llm.name == "claude":
        return settings.llm_model
    return ""


def _out(row: GlossRow, surface: str, *, cached: bool) -> dict:
    return {
        "lemma": row.lemma,
        "pos": row.pos,
        "sense_es": row.sense_es,
        "note_es": row.note_es,
        "ipa": phonetics(surface),
        "lookups": row.lookups,
        "cached": cached,
    }


def most_looked_up(db: Session, limit: int = 40) -> list[dict]:
    """Las palabras que más has vuelto a consultar.

    Es la lista de vocabulario que escribiste leyendo, sin pedírtela.
    """
    rows = db.execute(
        select(GlossRow).order_by(GlossRow.lookups.desc(), GlossRow.last_seen_at.desc()).limit(limit)
    ).scalars()
    return [
        {
            "surface": r.surface_lower,
            "lemma": r.lemma,
            "pos": r.pos,
            "sense_es": r.sense_es,
            "ipa": phonetics(r.surface_lower),
            "lookups": r.lookups,
        }
        for r in rows
    ]
