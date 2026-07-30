"""Segmentacion en oraciones.

La oracion es la unidad atomica del proyecto: unidad de alineacion ES/EN,
de TTS cacheado, de lectura en voz alta y de contexto para el SRS. Cortar
bien importa mas de lo que parece.

Usamos punkt de nltk (ya viene con g2p_en) porque en literatura hay que
distinguir "Mr. Holmes" de un fin de oracion. Si no esta, caemos a regex.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import NamedTuple

log = logging.getLogger(__name__)

# Abreviaturas frecuentes en narrativa que el respaldo por regex debe respetar.
_ABBREV = r"(?<!\bMr)(?<!\bMrs)(?<!\bMs)(?<!\bDr)(?<!\bSt)(?<!\bJr)(?<!\bSr)(?<!\bvs)(?<!\betc)"
_FALLBACK_SPLIT = re.compile(rf"{_ABBREV}(?<=[.!?])[\"'”’]?\s+(?=[A-Z\"'“])")

MIN_CHARS = 2
MAX_CHARS = 600  # una "oracion" mas larga que esto casi siempre es basura del EPUB


@lru_cache(maxsize=1)
def _punkt():
    try:
        import nltk

        try:
            nltk.data.find("tokenizers/punkt_tab")
        except LookupError:
            nltk.download("punkt_tab", quiet=True)
        from nltk.tokenize import sent_tokenize

        sent_tokenize("Mr. Holmes went home. He slept.")
        log.info("segment: usando punkt de nltk")
        return sent_tokenize
    except Exception as exc:  # noqa: BLE001
        log.warning("segment: punkt no disponible (%s). Usando regex de respaldo.", exc)
        return None


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    tokenizer = _punkt()
    raw = tokenizer(text) if tokenizer else _FALLBACK_SPLIT.split(text)

    out: list[str] = []
    for sentence in raw:
        s = sentence.strip()
        if len(s) < MIN_CHARS:
            continue
        # Un bloque larguisimo sin puntuacion suele ser un indice o una tabla
        # aplanada. Lo partimos por comas para que siga siendo legible en voz alta.
        if len(s) > MAX_CHARS:
            out.extend(p.strip() for p in re.split(r",\s+", s) if p.strip())
        else:
            out.append(s)
    return out


class SegmentedSentence(NamedTuple):
    text: str
    paragraph_idx: int
    is_heading: bool


def split_blocks(blocks: list[tuple[str, bool]]) -> list[SegmentedSentence]:
    """Segmenta bloques `(texto, es_encabezado)` conservando el parrafo.

    Los encabezados pasan enteros: punkt los trataria como prosa y partiria
    «Chapter I. The Beginning» en dos oraciones inexistentes, que despues
    aparecerian como material de lectura en voz alta.

    El indice de parrafo se conserva porque de el dependen dos cosas: que la
    traduccion pueda interpretar el contexto en vez de traducir literal, y
    que el lector pueda maquetar prosa en lugar de una fila por oracion.
    """
    out: list[SegmentedSentence] = []
    for paragraph_idx, (text, is_heading) in enumerate(blocks):
        if is_heading:
            stripped = text.strip()
            if stripped:
                out.append(SegmentedSentence(stripped, paragraph_idx, True))
        else:
            out.extend(
                SegmentedSentence(s, paragraph_idx, False) for s in split_sentences(text)
            )
    return out


def split_paragraphs(paragraphs: list[str]) -> list[str]:
    """Atajo para prosa suelta, sin distincion de encabezados."""
    return [s for p in paragraphs for s in split_sentences(p)]
