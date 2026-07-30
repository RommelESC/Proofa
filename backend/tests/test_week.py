"""Pruebas del resumen semanal.

Es la pantalla que más veces vas a mirar, así que una cifra inflada aquí es la
que más daño hace. El caso que se protege sobre todo es el del cero: ya hundió
la media de una sesión una vez.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.services.week_service import DAYS, Reading, summarize, usable

HOY = date(2026, 7, 30)  # jueves


def leer(dias_atras: int, *, minutos=5.0, wpm=120.0, overall=90.0, completeness=100.0):
    return Reading(
        day=HOY - timedelta(days=dias_atras),
        minutes=minutos,
        wpm=wpm,
        overall=overall,
        completeness=completeness,
    )


# --- El cero que se cuela ---


def test_una_grabacion_vacia_no_cuenta():
    """Completitud 0.0 es falsa en Python: con `or` pasaría como perfecta."""
    assert usable([leer(0, completeness=0.0)]) == []


def test_completitud_no_medida_se_asume_buena():
    assert len(usable([leer(0, completeness=None)])) == 1


def test_las_descartadas_se_reportan_en_vez_de_esconderse():
    d = summarize([leer(0), leer(0, completeness=0.0), leer(1, completeness=0.0)], HOY)
    assert d["discarded"] == 2
    assert d["attempts"] == 1


# --- La tira de días ---


def test_siempre_hay_siete_dias_aunque_no_practicaras():
    d = summarize([], HOY)
    assert len(d["days"]) == DAYS
    assert all(x["minutes"] == 0 for x in d["days"])


def test_el_ultimo_dia_es_hoy():
    d = summarize([], HOY)
    assert d["days"][-1]["is_today"] is True
    assert sum(x["is_today"] for x in d["days"]) == 1


def test_las_iniciales_corresponden_al_dia_real():
    # 30/07/2026 es jueves; la ventana arranca el viernes anterior.
    d = summarize([], HOY)
    assert [x["initial"] for x in d["days"]] == ["V", "S", "D", "L", "M", "M", "J"]


def test_los_minutos_caen_en_su_dia():
    d = summarize([leer(0, minutos=10), leer(2, minutos=4)], HOY)
    por_dia = {x["date"]: x["minutes"] for x in d["days"]}
    assert por_dia[HOY.isoformat()] == 10
    assert por_dia[(HOY - timedelta(days=2)).isoformat()] == 4


def test_lo_de_hace_mas_de_una_semana_queda_fuera():
    d = summarize([leer(DAYS)], HOY)
    assert d["attempts"] == 0
    assert d["minutes"] == 0


# --- Los totales ---


def test_promedia_solo_lo_evaluable():
    d = summarize([leer(0, overall=90), leer(0, overall=50, completeness=10.0)], HOY)
    assert d["accuracy"] == 90


def test_sin_velocidad_medida_no_se_inventa():
    d = summarize([leer(0, wpm=None)], HOY)
    assert d["wpm"] is None


def test_semana_vacia_no_devuelve_ceros_enganosos():
    d = summarize([], HOY)
    assert d["wpm"] is None and d["accuracy"] is None
