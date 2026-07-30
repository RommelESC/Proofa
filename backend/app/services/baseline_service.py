"""Baseline personal por fonema.

Un umbral absoluto (`PHONEME_FAIL = 55`) solo ve los desastres. No puede ver
tus puntos debiles *reales*: un fonema que siempre te sale en 70 cuando el
resto te sale en 85 es lo peor que haces, y sin embargo nunca cruza la barra.
Aqui la referencia eres tu mismo.

El riesgo de personalizar es inventar. Con siete muestras y una desviacion de
26 puntos, cualquier fonema parece debil o parece bien segun el dia — y un
diagnostico redactado con seguridad sobre ese ruido es peor que no decir nada,
porque manda a practicar lo que no toca. Por eso la significancia no es un
adorno del final: un fonema solo se declara debil si la diferencia contra el
resto de tus fonemas sobrevive a su propio margen de error.

Cuando no sobrevive, la respuesta no es «no se»: es cuantas muestras mas hacen
falta para saberlo. Eso convierte la espera en algo medible.

La estadistica vive en funciones puras, separada de SQL, porque es la parte
que tiene que estar bien y la unica que se puede probar sin base de datos.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Attempt, PhonemeScoreRow, WordScoreRow

# 95% de confianza, dos colas.
Z = 1.96

# Por debajo de esto la desviacion tipica no describe nada.
MIN_SAMPLES = 5

# Mas alla de esto, «te faltan N muestras» deja de ser un objetivo y es un
# no. La diferencia existe pero es tan pequena que no vale perseguirla.
MAX_USEFUL_SAMPLES = 2000

# Y el limite que de verdad importa es en lecturas, que es lo que se invierte.
# Un fonema raro puede necesitar pocas muestras y aun asi miles de lecturas:
# «2240 lecturas mas» no es una meta, es la forma larga de decir que esa
# diferencia no se va a resolver nunca.
MAX_USEFUL_ATTEMPTS = 300

WEAK = "weak"
UNCLEAR = "unclear"
OK = "ok"


@dataclass(frozen=True)
class Tally:
    """Recuento crudo de un fonema.

    Suma y suma de cuadrados en vez de media y desviacion: asi el «resto de
    tus fonemas» se obtiene restando, sin una segunda consulta por fonema.
    """

    ipa: str
    n: int
    total: float
    total_sq: float


@dataclass(frozen=True)
class PhonemeBaseline:
    ipa: str
    samples: int
    mean: float
    stdev: float | None
    #: Media del resto de tus fonemas — la vara contra la que se compara.
    reference: float
    #: Cuanto por debajo de esa vara. Negativo significa por encima.
    gap: float
    #: Medio ancho del intervalo de confianza, con el MISMO error tipico que
    #: usa el veredicto. Asi la barra dibujada no puede contradecir al fallo:
    #: si el intervalo cruza la vara, el veredicto es `unclear`, y se ve.
    margin: float | None
    verdict: str
    #: Muestras adicionales para resolver la duda. None si ya esta resuelta
    #: o si la diferencia es demasiado pequena para resolverse nunca.
    samples_needed: int | None


def _variance(n: int, total: float, total_sq: float) -> float | None:
    """Varianza muestral a partir de los recuentos."""
    if n < 2:
        return None
    # La resta puede dar un negativo minusculo por redondeo cuando todos los
    # valores son iguales; una varianza negativa reventaria la raiz.
    return max((total_sq - total * total / n) / (n - 1), 0.0)


def build_baselines(tallies: list[Tally]) -> list[PhonemeBaseline]:
    """Compara cada fonema contra el resto de los tuyos.

    Contra *el resto* y no contra el total: el total incluye al propio fonema,
    y en los que tienen muchas muestras eso arrastra la vara hacia el valor que
    se esta juzgando, escondiendo justo las debilidades mas frecuentes.
    """
    if not tallies:
        return []

    grand_n = sum(t.n for t in tallies)
    grand_total = sum(t.total for t in tallies)
    grand_sq = sum(t.total_sq for t in tallies)

    out: list[PhonemeBaseline] = []
    for t in tallies:
        mean = t.total / t.n
        var = _variance(t.n, t.total, t.total_sq)
        stdev = math.sqrt(var) if var is not None else None

        rest_n = grand_n - t.n
        rest_var = _variance(rest_n, grand_total - t.total, grand_sq - t.total_sq)
        reference = (grand_total - t.total) / rest_n if rest_n else mean
        gap = reference - mean

        # Sin con que comparar, o sin dispersion medible, no hay veredicto.
        if rest_n < 2 or var is None or rest_var is None or t.n < MIN_SAMPLES:
            out.append(
                PhonemeBaseline(t.ipa, t.n, round(mean, 1), None, round(reference, 1),
                                round(gap, 1), None, UNCLEAR, None)
            )
            continue

        # Error tipico de la diferencia entre dos medias independientes. La
        # incertidumbre de la vara tambien cuenta: ignorarla haria pasar por
        # significativas diferencias que no lo son.
        se_diff = math.sqrt(var / t.n + rest_var / rest_n)
        margin = Z * se_diff

        if gap > margin:
            verdict, needed = WEAK, None
        elif gap <= 0:
            verdict, needed = OK, None
        else:
            verdict = UNCLEAR
            needed = _samples_needed(gap, var, rest_var / rest_n)

        out.append(
            PhonemeBaseline(
                ipa=t.ipa,
                samples=t.n,
                mean=round(mean, 1),
                stdev=round(stdev, 1) if stdev is not None else None,
                reference=round(reference, 1),
                gap=round(gap, 1),
                margin=round(margin, 1),
                verdict=verdict,
                samples_needed=needed,
            )
        )

    # Los peores primero: es el orden en el que sirve leerlo.
    return sorted(out, key=lambda b: b.mean)


def attempts_to_resolve(samples_needed: int, samples: int, attempts: int) -> int | None:
    """Grabaciones que harian falta para reunir esas muestras.

    Al ritmo de ESE fonema, no al ritmo general. Un fonema raro como /j/ sale
    0.3 veces por grabacion: dividir entre las ~21 muestras que deja una
    lectura completa prometeria una grabacion cuando de verdad hacen falta
    cuarenta y cinco. La cifra optimista es la que destruye la confianza.
    """
    if attempts <= 0 or samples <= 0:
        return None
    rate = samples / attempts
    needed = math.ceil(samples_needed / rate)
    return needed if needed <= MAX_USEFUL_ATTEMPTS else None


def _samples_needed(gap: float, var: float, se_rest_sq: float) -> int | None:
    """Muestras que harian significativa una diferencia que hoy no lo es.

    Despeja n en `gap > Z * sqrt(var/n + se_rest^2)`. Si el margen de la vara
    ya se come la diferencia, no hay n que valga: mas datos de este fonema no
    resuelven una duda que viene del resto.
    """
    room = (gap / Z) ** 2 - se_rest_sq
    if room <= 0:
        return None
    needed = math.ceil(var / room)
    return needed if needed <= MAX_USEFUL_SAMPLES else None


def _since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def focus_in_attempt(
    weak: dict[str, float], phonemes: list[tuple[str, float]]
) -> list[dict]:
    """Cuales de tus debilidades conocidas aparecieron en esta lectura.

    Es la diferencia entre un informe y un corrector. El umbral absoluto ya
    señala los desastres; esto señala lo tuyo — un sonido que hoy sacaste 68
    no dispara ninguna alarma general, pero si tu historial en ese sonido es
    70, acabas de repetir exactamente el error que arrastras.

    Y compara contra tu historial, asi que tambien puede dar buenas noticias:
    el mismo 68 sobre un historial de 60 es una mejora, no un fallo.
    """
    seen: dict[str, list[float]] = {}
    for ipa, score in phonemes:
        if ipa in weak:
            seen.setdefault(ipa, []).append(score)

    out = []
    for ipa, scores in seen.items():
        now = sum(scores) / len(scores)
        out.append(
            {
                "ipa": ipa,
                "baseline": round(weak[ipa], 1),
                "now": round(now, 1),
                "delta": round(now - weak[ipa], 1),
                "occurrences": len(scores),
            }
        )
    # Lo peor de lo tuyo primero.
    return sorted(out, key=lambda f: f["now"])


def weak_phonemes(
    db: Session, *, days: int = 90, engine: str | None = None, exclude_attempt_id: int | None = None
) -> dict[str, float]:
    """Tus debilidades confirmadas: `{ipa: media historica}`.

    `exclude_attempt_id` deja fuera la lectura que se acaba de guardar. Sin eso
    el intento se compararia contra un historial que ya lo incluye, y una
    lectura mala arrastraria su propia vara hacia abajo, disimulandose.
    """
    engine = engine or dominant_engine(db, days=days)
    tallies = phoneme_tallies(db, days=days, engine=engine, exclude_attempt_id=exclude_attempt_id)
    return {b.ipa: b.mean for b in build_baselines(tallies) if b.verdict == WEAK}


def phoneme_tallies(
    db: Session,
    *,
    days: int,
    engine: str | None,
    exclude_attempt_id: int | None = None,
    exclude_session_id: int | None = None,
) -> list[Tally]:
    """Recuentos por fonema, acotados a un motor.

    Acotar importa: motores distintos puntuan en escalas distintas y mezclarlos
    produce un baseline que no describe a nadie.
    """
    stmt = (
        select(
            PhonemeScoreRow.expected_ipa,
            func.count().label("n"),
            func.sum(PhonemeScoreRow.score).label("total"),
            func.sum(PhonemeScoreRow.score * PhonemeScoreRow.score).label("total_sq"),
        )
        .join(WordScoreRow, WordScoreRow.id == PhonemeScoreRow.word_score_id)
        .join(Attempt, Attempt.id == WordScoreRow.attempt_id)
        .where(Attempt.recorded_at >= _since(days))
        .group_by(PhonemeScoreRow.expected_ipa)
    )
    if engine:
        stmt = stmt.where(Attempt.engine == engine)
    if exclude_attempt_id is not None:
        stmt = stmt.where(WordScoreRow.attempt_id != exclude_attempt_id)
    # Para juzgar una sesion hay que dejarla fuera de su propia vara, igual que
    # con un intento suelto: si no, una sesion mala se compara contra un
    # historial que ya la incluye y se disimula.
    if exclude_session_id is not None:
        stmt = stmt.where(
            (Attempt.session_id.is_(None)) | (Attempt.session_id != exclude_session_id)
        )

    return [
        Tally(r.expected_ipa, r.n, float(r.total), float(r.total_sq))
        for r in db.execute(stmt).all()
    ]


def dominant_engine(db: Session, *, days: int) -> str | None:
    """El motor con mas intentos en la ventana."""
    stmt = (
        select(Attempt.engine, func.count().label("n"))
        .where(Attempt.recorded_at >= _since(days))
        .group_by(Attempt.engine)
        .order_by(func.count().desc())
        .limit(1)
    )
    row = db.execute(stmt).first()
    return row.engine if row else None


def personal_baseline(db: Session, *, days: int = 90, engine: str | None = None) -> dict:
    """El diagnostico completo, listo para la interfaz."""
    engine = engine or dominant_engine(db, days=days)
    tallies = phoneme_tallies(db, days=days, engine=engine)
    baselines = build_baselines(tallies)

    count_stmt = (
        select(func.count()).select_from(Attempt).where(Attempt.recorded_at >= _since(days))
    )
    if engine:
        count_stmt = count_stmt.where(Attempt.engine == engine)
    attempts = db.execute(count_stmt).scalar_one()

    total_samples = sum(t.n for t in tallies)

    cost = {
        b.ipa: attempts_to_resolve(b.samples_needed, b.samples, attempts)
        for b in baselines
        if b.samples_needed
    }

    weak = [b for b in baselines if b.verdict == WEAK]
    # El que se resuelve antes en grabaciones, que es lo que el usuario invierte
    # — no en muestras, que es una moneda que no controla.
    pending = [b for b in baselines if cost.get(b.ipa)]
    closest = min(pending, key=lambda b: cost[b.ipa]) if pending else None

    return {
        "days": days,
        "engine": engine,
        "attempts": attempts,
        "samples": total_samples,
        "reference": round(sum(t.total for t in tallies) / total_samples, 1)
        if total_samples
        else None,
        "weak": [_dump(b, cost) for b in weak],
        "phonemes": [_dump(b, cost) for b in baselines],
        # Lo que convierte «aun no se sabe» en un objetivo concreto.
        "next_answer": (
            {
                "ipa": closest.ipa,
                "samples_needed": closest.samples_needed,
                "attempts_needed": cost[closest.ipa],
            }
            if closest
            else None
        ),
    }


def _dump(b: PhonemeBaseline, cost: dict[str, int | None]) -> dict:
    return {
        "ipa": b.ipa,
        "samples": b.samples,
        "mean": b.mean,
        "stdev": b.stdev,
        "reference": b.reference,
        "gap": b.gap,
        "margin": b.margin,
        "verdict": b.verdict,
        "samples_needed": b.samples_needed,
        "attempts_needed": cost.get(b.ipa),
    }
