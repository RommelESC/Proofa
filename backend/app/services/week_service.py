"""Resumen de los ultimos siete dias, para la pantalla de inicio.

Tres cifras y una tira de dias. Deliberadamente pocas: el sitio donde entras
cada dia no es donde se analiza nada, es donde decides si hoy practicas. Todo
el detalle vive en Progreso.

Como en el resto del proyecto, solo cuentan las grabaciones evaluables. Una
lectura truncada puntua bajisimo por completitud, no por pronunciacion, y
meterla en la media semanal contaria una historia falsa justo en la pantalla
que mas veces vas a mirar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Attempt

DAYS = 7

# Mismo umbral que el informe de sesion y el marcapasos.
MIN_COMPLETENESS = 60.0

# Iniciales de lunes a domingo, que es como empieza la semana aqui.
WEEKDAY_INITIALS = ("L", "M", "M", "J", "V", "S", "D")


@dataclass(frozen=True)
class Reading:
    """Lo minimo que hace falta de un intento para resumir la semana."""

    day: date
    minutes: float
    wpm: float | None
    overall: float
    completeness: float | None


def usable(readings: list[Reading]) -> list[Reading]:
    # `is None` explicito: una completitud de 0.0 es falsa en Python y con
    # `or` se colaria como si fuera perfecta. Ese error ya hundio una media
    # antes; aqui no se repite.
    return [
        r
        for r in readings
        if (r.completeness if r.completeness is not None else 100.0) >= MIN_COMPLETENESS
    ]


def summarize(readings: list[Reading], today: date) -> dict:
    """Totales de la semana y la tira de dias, de lunes a hoy."""
    buenas = usable(readings)
    start = today - timedelta(days=DAYS - 1)

    por_dia: dict[date, list[Reading]] = {}
    for r in buenas:
        if r.day >= start:
            por_dia.setdefault(r.day, []).append(r)

    dias = []
    for i in range(DAYS):
        d = start + timedelta(days=i)
        grupo = por_dia.get(d, [])
        dias.append(
            {
                "date": d.isoformat(),
                "initial": WEEKDAY_INITIALS[d.weekday()],
                "minutes": round(sum(r.minutes for r in grupo), 1),
                "attempts": len(grupo),
                "is_today": d == today,
            }
        )

    de_la_semana = [r for r in buenas if r.day >= start]
    velocidades = [r.wpm for r in de_la_semana if r.wpm]

    return {
        "days": dias,
        "minutes": round(sum(r.minutes for r in de_la_semana)),
        "wpm": round(sum(velocidades) / len(velocidades)) if velocidades else None,
        "accuracy": (
            round(sum(r.overall for r in de_la_semana) / len(de_la_semana))
            if de_la_semana
            else None
        ),
        "attempts": len(de_la_semana),
        "discarded": len(readings) - len(buenas),
    }


def week(db: Session, *, today: date | None = None) -> dict:
    now = datetime.now(timezone.utc)
    today = today or now.date()
    since = now - timedelta(days=DAYS + 1)

    rows = db.execute(
        select(
            Attempt.recorded_at,
            Attempt.duration_ms,
            Attempt.wpm,
            Attempt.overall,
            Attempt.completeness,
        ).where(Attempt.recorded_at >= since)
    ).all()

    readings = [
        Reading(
            day=r.recorded_at.date(),
            minutes=(r.duration_ms or 0) / 60_000,
            wpm=r.wpm,
            overall=r.overall,
            completeness=r.completeness,
        )
        for r in rows
    ]
    return summarize(readings, today)
