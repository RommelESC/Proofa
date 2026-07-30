from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Sentence
from app.phonology import phonemize_sentence

router = APIRouter(prefix="/api/sentences", tags=["content"])


class SentenceIn(BaseModel):
    text_en: str = Field(min_length=1)
    text_es: str | None = None
    cefr: str | None = None


class SentenceOut(BaseModel):
    id: int
    text_en: str
    text_es: str | None
    cefr: str | None


@router.post("", response_model=SentenceOut)
def create_sentence(payload: SentenceIn, db: Session = Depends(get_db)) -> Sentence:
    """Practica de texto suelto: no exige importar un libro."""
    sentence = Sentence(text_en=payload.text_en, text_es=payload.text_es, cefr=payload.cefr)
    db.add(sentence)
    db.flush()
    return sentence


@router.get("", response_model=list[SentenceOut])
def list_sentences(limit: int = 50, db: Session = Depends(get_db)) -> list[Sentence]:
    stmt = select(Sentence).order_by(Sentence.created_at.desc()).limit(min(limit, 200))
    return list(db.execute(stmt).scalars())


@router.get("/preview-phonemes")
def preview_phonemes(text: str) -> dict:
    """Como *deberia* sonar. Util para depurar el g2p sin grabar nada."""
    return {
        "words": [{"surface": w, "expected_ipa": ipa} for w, ipa in phonemize_sentence(text)]
    }
