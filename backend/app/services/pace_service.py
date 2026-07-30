"""Tu velocidad de lectura, medida.

El marcapasos del modo Guiada necesita un numero. La tentacion es poner uno
«normal» sacado de una tabla — 200 wpm, 250 wpm — y eso no describe a nadie:
o vas persiguiendo una banda que se te escapa, o la banda te espera y no
entrena nada. El unico numero honesto es el tuyo.

Se usa la MEDIANA y no la media porque el historial tiene lecturas deliberadas
a media velocidad y grabaciones fallidas con wpm absurdos (640 wpm sobre 1.5
segundos de audio vacio). La media los persigue; la mediana no.

Y la sugerencia por defecto es tu propia velocidad, sin multiplicadores
inventados. Empujar es una decision tuya, no un ajuste escondido: la interfaz
ofrece pasos por encima y dice claramente que son eso.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Attempt

# Mismo umbral que el resto: por debajo, lo que fallo fue la grabacion. Importa
# especialmente aqui — un audio vacio de 1.5s produce wpm de tres cifras.
MIN_COMPLETENESS = 60.0

# Ni una lectura a rastras ni una imposible: fuera de esto la medicion es del
# motor equivocandose, no de tu boca.
MIN_PLAUSIBLE_WPM = 30.0
MAX_PLAUSIBLE_WPM = 320.0

# Sin suficientes lecturas limpias, una mediana es una anecdota.
MIN_SAMPLES = 3

# Lo que se usa mientras no haya historial. Deliberadamente lento: es mejor que
# el marcapasos vaya corto y lo subas tu a que te arrastre desde el primer dia.
FALLBACK_WPM = 110


def usable_speeds(rows: list[tuple[float | None, float | None]]) -> list[float]:
    """Filtra mediciones de wpm que describen una lectura de verdad."""
    out = []
    for wpm, completeness in rows:
        if wpm is None:
            continue
        if completeness is not None and completeness < MIN_COMPLETENESS:
            continue
        if MIN_PLAUSIBLE_WPM <= wpm <= MAX_PLAUSIBLE_WPM:
            out.append(float(wpm))
    return out


def summarize(speeds: list[float]) -> dict:
    """Mediana y rango, o el valor por defecto si no hay con que."""
    if len(speeds) < MIN_SAMPLES:
        return {
            "wpm": FALLBACK_WPM,
            "measured": False,
            "samples": len(speeds),
            "slowest": None,
            "fastest": None,
        }
    return {
        "wpm": round(statistics.median(speeds)),
        "measured": True,
        "samples": len(speeds),
        "slowest": round(min(speeds)),
        "fastest": round(max(speeds)),
    }


def reading_pace(db: Session, *, days: int = 90) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(
        select(Attempt.wpm, Attempt.completeness).where(Attempt.recorded_at >= since)
    ).all()
    data = summarize(usable_speeds([(r.wpm, r.completeness) for r in rows]))
    data["days"] = days
    return data
