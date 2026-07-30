"""Cuánto cuesta leer un libro, medido.

Nace de una pregunta concreta: «Meditations» es una traducción del XVII y puede
ser mala primera lectura para alguien que empieza. Pero el campo `cefr` de la
tabla `books` sigue vacío a proposito — poner ahi una letra estimada seria
exactamente el error que este proyecto lleva evitando en todas partes: dar
apariencia de medida certificada a una suposicion.

Lo que si esta bien fundado es la LEGIBILIDAD. La formula de Flesch necesita
dos cosas: palabras por oracion y silabas por palabra. La primera es trivial;
la segunda es donde casi toda implementacion falla, porque cuenta silabas con
heuristicas sobre las letras («cuenta grupos de vocales, resta la -e muda»).
Aqui no hace falta adivinar: CMUdict da la pronunciacion real y las silabas se
cuentan por sus nucleos.

La banda CEFR que se devuelve es una equivalencia aproximada y va etiquetada
como tal. El numero de Flesch es la medida; la letra es una ayuda para leerlo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chapter, Sentence
from app.phonology.g2p import get_g2p

WORD_RE = re.compile(r"[A-Za-z']+")

# Nucleos silabicos: el inventario vocalico real que produce el motor, con los
# simbolos completos. Comparar por CARACTER en vez de por simbolo dejaba fuera
# `ə` y `ʌ` — las dos vocales mas frecuentes del ingles — y contaba «the» con
# cero silabas y «philosophy» con dos.
NUCLEI = frozenset(
    {"aʊ", "eɪ", "i", "oʊ", "u", "æ", "ɑ", "ɔ", "ɔɪ", "ə", "ɚ", "ɛ", "ɝ", "ɪ", "ʊ", "ʌ"}
)

# Bandas convencionales de Flesch. La equivalencia CEFR es orientativa: no hay
# una tabla oficial que las ligue, y se etiqueta como aproximada.
BANDS = (
    (90.0, "muy fácil", "A2"),
    (80.0, "fácil", "B1"),
    (70.0, "bastante fácil", "B1"),
    (60.0, "normal", "B2"),
    (50.0, "algo difícil", "B2"),
    (30.0, "difícil", "C1"),
    (float("-inf"), "muy difícil", "C2"),
)


# El punto ciego de Flesch, y no es teórico: «Meditations» puntúa 69.2 —
# «normal» — porque usa palabras cortas y germánicas en oraciones de 16
# palabras. Pero es una traducción del XVII y dice «whatsoever thou hast».
# Esa dificultad es sintáctica y léxica-arcaica, y la fórmula no la ve.
# Se cuenta aparte en vez de meterla en el número, que ya significa algo.
ARCHAIC = frozenset(
    {
        "thou", "thee", "thy", "thine", "ye",
        "hath", "hast", "hadst", "doth", "dost", "didst", "shalt", "wilt",
        "saith", "sayeth", "unto", "whence", "thence", "hither", "thither",
        "betwixt", "wherein", "whereof", "whereby", "whereto", "whatsoever",
        "whensoever", "wheresoever", "nay", "yea", "oft", "ere",
    }
)


def is_archaic(word: str) -> bool:
    w = word.lower()
    # `-eth` de tercera persona: «cometh», «recordeth». Se exige longitud para
    # no atrapar «teeth» ni «seeth».
    return w in ARCHAIC or (len(w) > 5 and w.endswith("eth") and w not in {"teeth"})


@dataclass(frozen=True)
class Counts:
    sentences: int
    words: int
    syllables: int
    unknown_words: int


def syllables(word: str, g2p=None) -> int:
    """Sílabas de una palabra, contadas por sus núcleos vocálicos."""
    g = g2p or get_g2p()
    return sum(1 for p in g.phonemize(word) if p in NUCLEI)


def flesch(counts: Counts) -> float | None:
    """Flesch Reading Ease. Más alto = más fácil."""
    if counts.sentences <= 0 or counts.words <= 0:
        return None
    wps = counts.words / counts.sentences
    spw = counts.syllables / counts.words
    return round(206.835 - 1.015 * wps - 84.6 * spw, 1)


def band(score: float | None) -> tuple[str, str] | tuple[None, None]:
    if score is None:
        return None, None
    for floor, label, cefr in BANDS:
        if score >= floor:
            return label, cefr
    return None, None


def count_text(texts: list[str], g2p=None) -> Counts:
    g = g2p or get_g2p()
    cache: dict[str, int] = {}
    total_words = total_syll = unknown = 0

    for text in texts:
        for raw in WORD_RE.findall(text):
            w = raw.lower()
            if w not in cache:
                cache[w] = syllables(w, g)
                if not g.knows(w):
                    unknown += 1
            total_words += 1
            # Una palabra sin nucleos no es una palabra: son restos de la
            # extraccion del EPUB. No suma silabas pero tampoco cuenta como
            # palabra, o hundiria la media de silabas por palabra.
            total_syll += cache[w]

    real = sum(1 for text in texts for raw in WORD_RE.findall(text) if cache.get(raw.lower(), 0) > 0)
    return Counts(
        sentences=len(texts),
        words=real or total_words,
        syllables=total_syll,
        unknown_words=unknown,
    )


# Fonemizar 74.000 palabras cuesta ~3.6s. El resultado solo cambia si el libro
# cambia, así que se guarda por (libro, nº de oraciones): reimportar mueve el
# conteo y el cálculo se rehace solo.
_cache: dict[int, tuple[int, dict]] = {}


def book_difficulty(db: Session, book_id: int) -> dict:
    rows = db.execute(
        select(Sentence.text_en)
        .join(Chapter, Chapter.id == Sentence.chapter_id)
        .where(Chapter.book_id == book_id)
        .where(Sentence.is_heading.is_(False))
    ).all()
    texts = [t for (t,) in rows if t and t.strip()]
    if not texts:
        return {"book_id": book_id, "measured": False}

    guardado = _cache.get(book_id)
    if guardado and guardado[0] == len(texts):
        return guardado[1]

    counts = count_text(texts)
    score = flesch(counts)
    label, cefr = band(score)

    arcaicas = sum(
        1 for text in texts for w in WORD_RE.findall(text) if is_archaic(w)
    )
    por_mil = round(arcaicas / counts.words * 1000, 1) if counts.words else 0.0

    resultado = {
        "archaic_per_1000": por_mil,
        # Por encima de esto el texto se lee con otra gramática, y el número de
        # Flesch se queda corto describiendo lo que cuesta.
        "archaic_heavy": por_mil >= 5.0,
        "book_id": book_id,
        "measured": True,
        "sentences": counts.sentences,
        "words": counts.words,
        "words_per_sentence": round(counts.words / counts.sentences, 1),
        "syllables_per_word": round(counts.syllables / counts.words, 2),
        "flesch": score,
        "label": label,
        # Etiquetado como aproximado a propósito: no hay tabla oficial que ligue
        # Flesch con CEFR, y el campo `books.cefr` sigue vacío por lo mismo.
        "cefr_approx": cefr,
    }
    _cache[book_id] = (len(texts), resultado)
    return resultado
