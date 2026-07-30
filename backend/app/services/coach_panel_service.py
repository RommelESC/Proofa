"""El panel de corrección de Coach: todo lo que se dice de UNA lectura.

`coaching_payload` resume el intento en patrones y peores palabras. Esto es
otra cosa: lo que se enseña al lado del texto mientras sigues leyendo, y por
eso baja al detalle que se puede accionar — qué fonema falló y con qué lo
cambiaste, qué palabra te saltaste y por qué se salta en español, dónde
cortaste la frase.

Todo sale de lo que ya se guarda. No hay ninguna medición nueva: los tiempos
por palabra, las sustituciones de fonema y los tipos de error estaban en la
base desde el principio; lo que faltaba era leerlos juntos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Attempt, PhonemeScoreRow, Sentence, WordScoreRow
from app.phonology.patterns import PHONEME_FAIL

# Medido sobre las grabaciones reales, y la separación es limpia: leyendo
# seguido los huecos entre palabras son de 10-30 ms (mediana 10, p75 30);
# en una lectura lenta deliberada la mediana sube a 510 ms y el máximo a 1440.
# No hay zona gris entre «hablar» y «parar», así que 300 ms parte por el medio
# del vacío en vez de por un valor inventado.
LONG_PAUSE_MS = 300

# Cuántos fonemas se señalan por oración. Corregir todo a la vez es
# técnicamente correcto y pedagógicamente pésimo — el mismo criterio que
# limita los patrones a dos.
MAX_PHONEMES = 3

# Cuántas oraciones anteriores se enseñan en la tira de abajo.
RECENT = 8

# Palabras que el español no lleva y el inglés sí. Saltárselas no es descuido:
# es la gramática materna colándose, y decirlo cambia cómo lo corriges.
L1_OMISSION_HINT = {
    "a": "en español no lleva artículo, en inglés sí",
    "an": "en español no lleva artículo, en inglés sí",
    "the": "el inglés lo exige donde el español lo omite",
    "any": "en español no lleva artículo, en inglés sí",
    "do": "el auxiliar no existe en español y por eso se cae",
    "does": "el auxiliar no existe en español y por eso se cae",
    "did": "el auxiliar no existe en español y por eso se cae",
    "it": "el español deja el sujeto implícito; el inglés lo exige",
    "is": "el español puede omitir la cópula en algunos giros",
    "to": "se pierde al arrastrar la construcción del español",
}

WORD_RE = re.compile(r"[A-Za-z']+")


@dataclass(frozen=True)
class Timed:
    surface: str
    start_ms: int
    end_ms: int


def long_pauses(words: list[Timed]) -> list[dict]:
    """Los silencios de verdad entre palabra y palabra."""
    out = []
    for a, b in zip(words, words[1:]):
        gap = b.start_ms - a.end_ms
        if gap >= LONG_PAUSE_MS:
            out.append({"after": a.surface, "before": b.surface, "ms": gap})
    return out


def context_of(text: str, surface: str, width: int = 2) -> str:
    """La palabra dentro de su frase, para que sepas cuál de todas fue."""
    words = WORD_RE.findall(text)
    lower = [w.lower() for w in words]
    try:
        i = lower.index(surface.lower())
    except ValueError:
        return ""
    return " ".join(words[max(0, i - width) : i + width + 1])


def panel(db: Session, attempt_id: int) -> dict:
    attempt = db.get(Attempt, attempt_id)
    if attempt is None:
        return {"attempt_id": attempt_id, "found": False}

    words = list(
        db.execute(
            select(WordScoreRow)
            .where(WordScoreRow.attempt_id == attempt_id)
            .order_by(WordScoreRow.word_index)
        ).scalars()
    )

    # --- Fonemas fallados, con la sustitución solo cuando hay evidencia ---
    fallos = []
    for w in words:
        for p in db.execute(
            select(PhonemeScoreRow)
            .where(PhonemeScoreRow.word_score_id == w.id)
            .order_by(PhonemeScoreRow.score)
        ).scalars():
            if p.score >= PHONEME_FAIL:
                continue
            # `produced_ipa` distinto del esperado es lo que el motor SÍ pudo
            # afirmar. Cuando coincide, sabemos que falló pero no con qué se
            # cambió — y decirlo igual sería inventar.
            sustituto = p.produced_ipa if p.produced_ipa and p.produced_ipa != p.expected_ipa else None
            fallos.append(
                {
                    "surface": w.surface,
                    "word_ipa": "".join(
                        x.expected_ipa
                        for x in db.execute(
                            select(PhonemeScoreRow)
                            .where(PhonemeScoreRow.word_score_id == w.id)
                            .order_by(PhonemeScoreRow.phoneme_index)
                        ).scalars()
                    ),
                    "phoneme": p.expected_ipa,
                    "produced": sustituto,
                    "score": round(p.score, 1),
                    "word_score": round(w.score, 1),
                }
            )
    fallos.sort(key=lambda f: f["score"])

    # --- Palabras que te saltaste ---
    omitidas = []
    for w in words:
        if w.error_type != "omission":
            continue
        veces = db.execute(
            select(func.count())
            .select_from(WordScoreRow)
            .join(Attempt, Attempt.id == WordScoreRow.attempt_id)
            .where(Attempt.session_id == attempt.session_id)
            .where(WordScoreRow.error_type == "omission")
            .where(func.lower(WordScoreRow.surface) == w.surface.lower())
        ).scalar_one()
        omitidas.append(
            {
                "surface": w.surface,
                "context": context_of(attempt.expected_text, w.surface),
                "times_in_session": veces,
                "why": L1_OMISSION_HINT.get(w.surface.lower()),
            }
        )

    # --- Ritmo ---
    timed = [
        Timed(w.surface, w.start_ms, w.end_ms)
        for w in words
        if w.start_ms is not None and w.end_ms is not None
    ]
    pausas = long_pauses(timed)
    ritmo = {
        "wpm": round(attempt.wpm) if attempt.wpm else None,
        "long_pauses": len(pausas),
        "pauses": pausas[:3],
        # La palabra ante la que cortaste: la que sigue al silencio más largo.
        "cut_before": max(pausas, key=lambda p: p["ms"])["before"] if pausas else None,
        "words": [
            {"surface": t.surface, "ms": t.end_ms - t.start_ms} for t in timed
        ],
    }

    # --- Las anteriores de esta sesión, para la tira ---
    recientes = []
    if attempt.session_id is not None:
        recientes = [
            {
                "attempt_id": a.id,
                "overall": round(a.overall, 1),
                "text": a.expected_text[:60],
                # Una grabación que el motor no pudo evaluar puntúa 0, y
                # pintarla como «pronunciación pésima» sería mentir: lo que
                # falló fue el micrófono, no la boca.
                "usable": (a.completeness if a.completeness is not None else 100.0) >= 60.0,
            }
            for a in db.execute(
                select(Attempt)
                .where(Attempt.session_id == attempt.session_id)
                .order_by(Attempt.recorded_at.desc())
                .limit(RECENT)
            ).scalars()
        ][::-1]

    idx = None
    if attempt.sentence_id is not None:
        sentence = db.get(Sentence, attempt.sentence_id)
        idx = sentence.idx if sentence else None

    return {
        "attempt_id": attempt_id,
        "found": True,
        "sentence_idx": idx,
        "overall": round(attempt.overall, 1),
        "text": attempt.expected_text,
        "phonemes": fallos[:MAX_PHONEMES],
        "omissions": omitidas,
        "rhythm": ritmo,
        "recent": recientes,
    }
