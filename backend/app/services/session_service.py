"""Sesiones de practica y su informe de cierre.

La tabla `reading_sessions` existia desde el primer dia y no se usaba: los
intentos se guardaban sueltos, asi que no habia forma de decir «hoy hiciste
esto». Sin ese corte, el progreso solo se puede mirar en agregados de 30 dias,
que es demasiado lento para notar nada.

Decision de diseno: la sesion se DERIVA del ritmo de grabacion, no la abre y
cierra el frontend. Un boton de «terminar sesion» se olvida siempre, y las
sesiones sin cerrar envenenan cualquier agregado despues. El hueco entre
grabaciones ya dice cuando paraste — medido sobre el historial real, los huecos
dentro de un bloque de practica van de 0 a 23 minutos y entre bloques hay
saltos de horas, asi que 30 minutos separa limpio.

Y el informe compara la sesion contra tu historial EXCLUYENDOLA. Igual que con
un intento suelto: una sesion incluida en su propia vara se disimula.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Attempt,
    ErrorPatternRow,
    PatternHitRow,
    PhonemeScoreRow,
    ReadingSession,
    WordScoreRow,
)
from app.services.baseline_service import (
    WEAK,
    build_baselines,
    dominant_engine,
    phoneme_tallies,
)

log = logging.getLogger(__name__)

# Medido sobre el historial real: dentro de un bloque de practica los huecos
# llegan a 23 minutos; entre bloques hay saltos de horas.
SESSION_GAP = timedelta(minutes=30)

# Por debajo de esto una sesion no da para hablar de tendencia. Decirlo es
# mejor que dibujar una flecha sobre dos puntos.
MIN_ATTEMPTS_FOR_TREND = 4

# Y por debajo de esto no da ni para resumir.
MIN_ATTEMPTS_FOR_REPORT = 2

# Mismo umbral que usa el feedback de un intento suelto: por debajo, lo que
# fallo fue la grabacion y no la boca.
MIN_COMPLETENESS = 60.0


def _completeness(attempt: Attempt) -> float:
    """Completitud, tratando «no medida» y «cero» como cosas distintas.

    Un motor que no reporta completitud no es lo mismo que un motor que midio
    que no dijiste nada.
    """
    return 100.0 if attempt.completeness is None else attempt.completeness


def _last_activity(db: Session, session: ReadingSession) -> datetime:
    last = db.execute(
        select(func.max(Attempt.recorded_at)).where(Attempt.session_id == session.id)
    ).scalar()
    return last or session.started_at


def current_session(db: Session, *, book_id: int | None = None, mode: str = "read_aloud") -> ReadingSession:
    """La sesion en curso, o una nueva si la anterior ya se enfrio.

    Cerrar la anterior con la hora de su ultima grabacion — y no con «ahora» —
    importa: la duracion de una sesion es el tiempo que practicaste, no el que
    pasó hasta que volviste.
    """
    latest = db.execute(
        select(ReadingSession).order_by(ReadingSession.started_at.desc()).limit(1)
    ).scalar_one_or_none()

    if latest is not None and latest.ended_at is None:
        last = _last_activity(db, latest)
        if datetime.now(timezone.utc) - last < SESSION_GAP:
            return latest
        latest.ended_at = last
        db.flush()

    session = ReadingSession(book_id=book_id, mode=mode)
    db.add(session)
    db.flush()
    log.info("sesion %s abierta (modo %s, libro %s)", session.id, mode, book_id)
    return session


def _attempts_in(db: Session, session_id: int) -> list[Attempt]:
    return list(
        db.execute(
            select(Attempt)
            .where(Attempt.session_id == session_id)
            .order_by(Attempt.recorded_at)
        ).scalars()
    )


def _trend(attempts: list[Attempt]) -> dict | None:
    """Primera mitad contra segunda mitad de la sesion.

    No es aprendizaje — en veinte minutos no se aprende un fonema. Es
    calentamiento o cansancio, y las dos cosas son utiles de saber: si sueles
    empezar flojo, las tres primeras grabaciones no cuentan como diagnostico.
    """
    if len(attempts) < MIN_ATTEMPTS_FOR_TREND:
        return None
    mid = len(attempts) // 2
    first = [a.overall for a in attempts[:mid]]
    second = [a.overall for a in attempts[mid:]]
    a = sum(first) / len(first)
    b = sum(second) / len(second)
    return {"first_half": round(a, 1), "second_half": round(b, 1), "delta": round(b - a, 1)}


def _weak_points(db: Session, session_id: int, days: int) -> list[dict]:
    """Tus debilidades conocidas y como fueron en esta sesion."""
    engine = dominant_engine(db, days=days)
    baselines = build_baselines(
        phoneme_tallies(db, days=days, engine=engine, exclude_session_id=session_id)
    )
    weak = {b.ipa: b.mean for b in baselines if b.verdict == WEAK}
    if not weak:
        return []

    rows = db.execute(
        select(
            PhonemeScoreRow.expected_ipa,
            func.count().label("n"),
            func.avg(PhonemeScoreRow.score).label("mean"),
        )
        .join(WordScoreRow, WordScoreRow.id == PhonemeScoreRow.word_score_id)
        .join(Attempt, Attempt.id == WordScoreRow.attempt_id)
        .where(Attempt.session_id == session_id)
        .where(PhonemeScoreRow.expected_ipa.in_(weak.keys()))
        .group_by(PhonemeScoreRow.expected_ipa)
    ).all()

    out = [
        {
            "ipa": r.expected_ipa,
            "baseline": round(weak[r.expected_ipa], 1),
            "session": round(float(r.mean), 1),
            "delta": round(float(r.mean) - weak[r.expected_ipa], 1),
            "samples": r.n,
        }
        for r in rows
    ]
    return sorted(out, key=lambda w: w["session"])


def _patterns(db: Session, session_id: int) -> list[dict]:
    rows = db.execute(
        select(
            PatternHitRow.pattern_code,
            ErrorPatternRow.label_es,
            func.count().label("hits"),
        )
        .join(WordScoreRow, WordScoreRow.id == PatternHitRow.word_score_id)
        .join(Attempt, Attempt.id == WordScoreRow.attempt_id)
        .join(ErrorPatternRow, ErrorPatternRow.code == PatternHitRow.pattern_code)
        .where(Attempt.session_id == session_id)
        .group_by(PatternHitRow.pattern_code, ErrorPatternRow.label_es)
        .order_by(func.count().desc())
    ).all()
    return [{"code": r.pattern_code, "label": r.label_es, "hits": r.hits} for r in rows]


def session_report(db: Session, *, session_id: int | None = None, days: int = 90) -> dict:
    """Que paso en una sesion de practica.

    Sin `session_id`, la ultima. Devuelve `enough: False` cuando no hay
    suficiente para decir nada — que es distinto de no haber practicado, y la
    interfaz tiene que poder distinguirlo.
    """
    if session_id is None:
        session = db.execute(
            select(ReadingSession).order_by(ReadingSession.started_at.desc()).limit(1)
        ).scalar_one_or_none()
    else:
        session = db.get(ReadingSession, session_id)

    if session is None:
        return {"session_id": None, "enough": False, "attempts": 0}

    attempts = _attempts_in(db, session.id)
    if len(attempts) < MIN_ATTEMPTS_FOR_REPORT:
        return {
            "session_id": session.id,
            "enough": False,
            "attempts": len(attempts),
            "started_at": session.started_at.isoformat(),
        }

    # Las grabaciones truncadas puntuan bajisimo por completitud, no por
    # pronunciacion. Meterlas en la media de la sesion la hunde y el informe
    # miente sobre como fue.
    #
    # Ojo con el cero: esto estaba escrito `a.completeness or 100.0`, y una
    # grabacion fallida tiene completitud 0.0, que en Python es falsa. Las
    # cinco grabaciones vacias de la sesion 2 entraban como buenas y hundian
    # la media a 35.7 con una mejor de 92.7 — el informe contaba que habias
    # empeorado cuando lo que habia pasado es que el microfono no cogio nada.
    usable = [a for a in attempts if _completeness(a) >= MIN_COMPLETENESS]
    scored = usable or attempts
    ended = session.ended_at or attempts[-1].recorded_at

    return {
        "session_id": session.id,
        "enough": True,
        "open": session.ended_at is None,
        "started_at": session.started_at.isoformat(),
        "ended_at": ended.isoformat(),
        "minutes": round((ended - session.started_at).total_seconds() / 60),
        "attempts": len(attempts),
        "discarded": len(attempts) - len(usable),
        "mean_overall": round(sum(a.overall for a in scored) / len(scored), 1),
        "best": round(max(a.overall for a in scored), 1),
        # Solo sobre las utiles. Antes, si no llegaban a cuatro, caia al
        # conjunto completo — y entonces la sesion 1 reportaba «+60.6», que en
        # realidad era «las tres primeras grabaciones no cogieron nada». Si no
        # hay suficientes medidas buenas, no hay tendencia que contar.
        "trend": _trend(usable),
        "weak_points": _weak_points(db, session.id, days),
        "patterns": _patterns(db, session.id),
    }
