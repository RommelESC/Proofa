"""Practica dirigida al fonema que de verdad te cuesta.

El baseline dice cual es tu punto debil; esto es lo que cierra el circulo, que
si no queda en un informe bonito sin nada que hacer al respecto.

El material sale de TUS libros, no de una lista generica de ejercicios. Dos
razones. La primera es que vas a leer esas frases igualmente, asi que practicar
sobre ellas no es tiempo aparte. La segunda es que el vocabulario de lo que lees
es el que necesitas pronunciar: drilar «sheep/ship» esta bien, pero si tu libro
esta lleno de «thee» y «either», eso es lo que te va a tocar decir en voz alta.

Lo que el catalogo de la taxonomia si aporta es la explicacion articulatoria y
los pares minimos curados. Cuando el fonema no esta en el catalogo se dice, en
vez de inventar un consejo.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Attempt, Chapter, PhonemeScoreRow, ReadingProgress, Sentence, WordScoreRow
from app.phonology.g2p import get_g2p
from app.phonology.patterns import PATTERNS_BY_CODE
from app.services.baseline_service import build_baselines, dominant_engine, phoneme_tallies

log = logging.getLogger(__name__)

WORD_RE = re.compile(r"[A-Za-z']+")

# De fonema al patron de la taxonomia que lo explica. Explicito a proposito:
# deja a la vista que /k/, /t/ o /s/ no tienen entrada, y para esos es mejor
# callar que redactar un consejo articulatorio inventado.
PHONEME_PATTERN: dict[str, str] = {
    "θ": "TH_TO_S",
    "ð": "DH_TO_D",
    "i": "VOWEL_IY_IH",
    "ɪ": "VOWEL_IY_IH",
    "v": "B_V_MERGE",
    "z": "Z_TO_S",
    "j": "Y_TO_JH",
    "ʃ": "SH_TO_CH",
    "ŋ": "NG_TO_N",
    "ə": "SCHWA_FULL",
}

# Las palabras funcionales son donde mas vive un fonema, pero un drill de
# «he, be, we, me» aburre y ensena poco. Entran, pero contadas.
FUNCTION_WORD_MIN_FREQ = 200
MAX_FUNCTION_WORDS = 2

# Una frase de practica se lee de una vez y se repite sin perder el hilo.
DRILL_SENTENCE_MIN = 25
DRILL_SENTENCE_MAX = 95

# Debajo de esto no es una frase, es un fragmento de indice o un encabezado.
# Medido: «shouted Blaikie furiously.» y «Salaminius, Book 7, XXXVII.» pasaban
# los filtros de longitud y salian como ejercicios.
MIN_SENTENCE_WORDS = 6

# Y si demasiadas palabras no estan en el diccionario, lo que hay delante es
# una lista de nombres propios o basura de extraccion, no prosa.
MIN_KNOWN_RATIO = 0.85

# Una palabra de tres letras es lo minimo con lo que se puede practicar un
# sonido. Por debajo salian «e», «ee» y «'e» — restos de la extraccion del
# EPUB que el diccionario acepta pero que nadie pronuncia sueltos.
MIN_WORD_LETTERS = 3


@dataclass
class Corpus:
    """Vocabulario de un libro, fonemizado una vez."""

    book_id: int | None
    total_sentences: int
    ipa: dict[str, tuple[str, ...]]
    freq: Counter
    #: Palabras que el diccionario conoce de verdad. Lo demas lleva una
    #: pronunciacion adivinada y no sirve como material de practica.
    known: set[str]


_corpus: Corpus | None = None


def _sentence_query(book_id: int | None):
    stmt = select(Sentence.id, Sentence.text_en)
    if book_id is not None:
        stmt = stmt.join(Chapter, Chapter.id == Sentence.chapter_id).where(
            Chapter.book_id == book_id
        )
    return stmt


def _build_corpus(db: Session, book_id: int | None) -> Corpus:
    rows = db.execute(_sentence_query(book_id)).all()
    freq: Counter = Counter()
    for _sid, text in rows:
        freq.update(w.lower() for w in WORD_RE.findall(text))

    g = get_g2p()
    ipa = {w: tuple(g.phonemize(w)) for w in freq}
    known = {w for w in freq if g.knows(w)}
    log.info(
        "drills: corpus fonemizado — libro %s, %d oraciones, %d palabras (%d en diccionario)",
        book_id, len(rows), len(ipa), len(known),
    )
    return Corpus(book_id=book_id, total_sentences=len(rows), ipa=ipa, freq=freq, known=known)


def current_book(db: Session) -> int | None:
    """El libro en el que estas trabajando ahora mismo.

    Sin esto el drill mezcla libros: con dos importados salian ejercicios con
    «Blaikie» mientras se leia a Marco Aurelio. Practicar vocabulario de un
    libro que no estas leyendo es trabajo que no se reutiliza.
    """
    stmt = (
        select(Chapter.book_id)
        .join(ReadingProgress, ReadingProgress.chapter_id == Chapter.id)
        .order_by(ReadingProgress.updated_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def get_corpus(db: Session, book_id: int | None) -> Corpus:
    """El barrido cuesta ~3s con g2p; se hace una vez y se reusa.

    Se rehace si cambia el libro o el numero de oraciones — es decir, si
    importaste algo nuevo. Comparar el conteo es una consulta trivial y evita
    servir ejercicios de un corpus viejo.
    """
    global _corpus
    count_stmt = select(func.count()).select_from(Sentence)
    if book_id is not None:
        count_stmt = count_stmt.join(Chapter, Chapter.id == Sentence.chapter_id).where(
            Chapter.book_id == book_id
        )
    n = db.execute(count_stmt).scalar_one()

    if _corpus is None or _corpus.book_id != book_id or _corpus.total_sentences != n:
        _corpus = _build_corpus(db, book_id)
    return _corpus


def target_phoneme(db: Session, *, days: int = 90) -> tuple[str | None, str]:
    """El fonema a practicar y por que se eligio ese.

    Devuelve tambien el motivo porque no es lo mismo «esta confirmado como tu
    punto debil» que «es el peor que tienes, pero sin evidencia suficiente». La
    interfaz tiene que poder decir cual de las dos cosas es.
    """
    engine = dominant_engine(db, days=days)
    baselines = build_baselines(phoneme_tallies(db, days=days, engine=engine))
    if not baselines:
        return None, "sin datos"

    weak = [b for b in baselines if b.verdict == "weak"]
    if weak:
        return weak[0].ipa, "confirmado"

    # Sin nada confirmado, el peor con muestra suficiente sigue siendo la
    # mejor apuesta — pero se etiqueta como provisional.
    con_muestra = [b for b in baselines if b.stdev is not None]
    if con_muestra:
        return con_muestra[0].ipa, "provisional"
    return baselines[0].ipa, "provisional"


def _history(db: Session, ipa: str, *, days: int = 90) -> dict[str, float]:
    """Tu media en ese fonema, palabra por palabra."""
    engine = dominant_engine(db, days=days)
    stmt = (
        select(
            func.lower(WordScoreRow.surface).label("surface"),
            func.avg(PhonemeScoreRow.score).label("mean"),
        )
        .join(WordScoreRow, WordScoreRow.id == PhonemeScoreRow.word_score_id)
        .join(Attempt, Attempt.id == WordScoreRow.attempt_id)
        .where(PhonemeScoreRow.expected_ipa == ipa)
        .group_by(func.lower(WordScoreRow.surface))
    )
    if engine:
        stmt = stmt.where(Attempt.engine == engine)
    return {r.surface: float(r.mean) for r in db.execute(stmt).all()}


def is_complete_sentence(text: str) -> bool:
    """Si esto se puede leer en voz alta como una frase.

    Tres cosas, todas medidas contra el material que salia antes:
      - sin digitos: «Salaminius, Book 7, XXXVII.» es una referencia
      - empieza en mayuscula y acaba en puntuacion: «his readiness to hear any
        man» es un trozo partido por la segmentacion, y sin entonacion propia
        se lee raro justo cuando la entonacion es parte de lo que practicas
    """
    s = text.strip()
    if not s or any(c.isdigit() for c in s):
        return False
    return s[0].isupper() and s[-1] in ".!?"


def _usable_word(corpus: Corpus, word: str) -> bool:
    return (
        word in corpus.known
        and word.isalpha()  # fuera «'e», «'ee»
        and len(word) >= MIN_WORD_LETTERS
    )


def _pick_words(corpus: Corpus, ipa: str, history: dict[str, float], limit: int) -> list[dict]:
    carriers = [
        (w, p) for w, p in corpus.ipa.items() if ipa in p and _usable_word(corpus, w)
    ]

    def prominence(phones: tuple[str, ...]) -> float:
        """Cuanto pesa el fonema dentro de la palabra.

        En «he» la /i/ es la mitad de la palabra; en «university» se pierde.
        Cuanto mas pesa, mas claro se oye si sale mal.
        """
        return phones.count(ipa) / len(phones)

    scored = []
    for w, p in carriers:
        # Lo que ya te salio mal va primero: es evidencia, no una suposicion.
        fallado = history.get(w)
        scored.append(
            (
                0 if fallado is None else 1,          # tienes historial
                # Ascendente: el peor primero. Iba negado, y por eso «breathe»
                # (100) salia delante de «very» (74.3) — justo al reves.
                fallado if fallado is not None else 0.0,
                prominence(p),
                corpus.freq[w],
                w,
                p,
            )
        )
    scored.sort(key=lambda t: (-t[0], t[1], -t[2], -t[3]))

    out, funcionales = [], 0
    for tiene_historial, _, prom, freq, w, p in scored:
        if freq >= FUNCTION_WORD_MIN_FREQ and not tiene_historial:
            if funcionales >= MAX_FUNCTION_WORDS:
                continue
            funcionales += 1
        out.append(
            {
                "surface": w,
                "ipa": "".join(p),
                "occurrences": p.count(ipa),
                "book_frequency": freq,
                "your_mean": round(history[w], 1) if w in history else None,
            }
        )
        if len(out) >= limit:
            break
    return out


def _pick_sentences(
    db: Session, corpus: Corpus, ipa: str, limit: int, book_id: int | None
) -> list[dict]:
    rows = db.execute(
        _sentence_query(book_id).where(
            func.length(Sentence.text_en).between(DRILL_SENTENCE_MIN, DRILL_SENTENCE_MAX)
        )
    ).all()

    scored = []
    for sid, text in rows:
        if not is_complete_sentence(text):
            continue
        words = [w.lower() for w in WORD_RE.findall(text)]
        if len(words) < MIN_SENTENCE_WORDS:
            continue
        if sum(w in corpus.known for w in words) / len(words) < MIN_KNOWN_RATIO:
            continue

        carriers = [w for w in words if ipa in corpus.ipa.get(w, ()) and w in corpus.known]
        if not carriers:
            continue
        hits = sum(corpus.ipa[w].count(ipa) for w in carriers)
        # Densidad, no cuenta bruta: en una frase larga cuatro apariciones se
        # diluyen; en una corta, cada una se oye.
        scored.append((hits / len(words), hits, sid, text, carriers))

    scored.sort(key=lambda t: (-t[0], -t[1], len(t[3])))
    return [
        {"sentence_id": sid, "text": text, "hits": hits, "carriers": sorted(set(carriers))}
        for _, hits, sid, text, carriers in scored[:limit]
    ]


def drill(
    db: Session,
    *,
    ipa: str | None = None,
    limit: int = 6,
    days: int = 90,
    book_id: int | None = None,
) -> dict:
    reason = "solicitado"
    if not ipa:
        ipa, reason = target_phoneme(db, days=days)
    if not ipa:
        return {"ipa": None, "reason": "sin datos", "words": [], "sentences": [], "pattern": None}

    book_id = book_id if book_id is not None else current_book(db)
    corpus = get_corpus(db, book_id)
    history = _history(db, ipa, days=days)

    pattern = PATTERNS_BY_CODE.get(PHONEME_PATTERN.get(ipa, ""))
    return {
        "ipa": ipa,
        "reason": reason,
        "book_id": book_id,
        "your_mean": round(sum(history.values()) / len(history), 1) if history else None,
        "words": _pick_words(corpus, ipa, history, limit),
        "sentences": _pick_sentences(db, corpus, ipa, limit, book_id),
        "pattern": (
            {
                "code": pattern.code,
                "label": pattern.label_es,
                "explanation": pattern.explanation_es,
                "minimal_pairs": list(pattern.minimal_pairs),
            }
            if pattern
            else None
        ),
    }
