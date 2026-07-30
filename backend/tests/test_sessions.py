"""Pruebas del informe de sesion.

Los dos casos centrales son bugs reales que el informe llego a contar sobre el
historial del usuario: dijo que su media habia sido 35.7 cuando fue 80.2, y que
habia mejorado un +60.6 que en realidad era «las tres primeras grabaciones no
cogieron nada». Un informe que miente en la direccion optimista es peor que no
tener informe, porque no hay forma de notarlo desde dentro.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.services.session_service import (
    MIN_ATTEMPTS_FOR_TREND,
    SESSION_GAP,
    _completeness,
    _trend,
)
from scripts.backfill_sessions import group


@dataclass
class FakeAttempt:
    overall: float
    completeness: float | None = 100.0
    recorded_at: datetime = datetime(2026, 7, 28, 10, 0, tzinfo=timezone.utc)


# --- El cero que se colaba ---


def test_completitud_cero_no_es_completitud_desconocida():
    """Estaba escrito `a.completeness or 100.0`, y 0.0 es falso en Python.

    Es exactamente el caso que hay que excluir: el motor midio que no dijiste
    nada. Tratarlo como «completa» metia las grabaciones vacias en la media.
    """
    assert _completeness(FakeAttempt(0.0, completeness=0.0)) == 0.0


def test_completitud_no_medida_se_asume_buena():
    # Un motor que no reporta completitud no es un motor que midio un cero.
    assert _completeness(FakeAttempt(80.0, completeness=None)) == 100.0


def test_completitud_normal_pasa_tal_cual():
    assert _completeness(FakeAttempt(80.0, completeness=82.0)) == 82.0


# --- La tendencia ---


def test_sin_suficientes_medidas_no_hay_tendencia():
    """Antes caia al conjunto completo y inventaba una mejora enorme."""
    tres = [FakeAttempt(90.9), FakeAttempt(92.3), FakeAttempt(89.5)]
    assert len(tres) < MIN_ATTEMPTS_FOR_TREND
    assert _trend(tres) is None


def test_tendencia_parte_la_sesion_en_dos():
    a = [FakeAttempt(60.0), FakeAttempt(60.0), FakeAttempt(80.0), FakeAttempt(80.0)]
    t = _trend(a)
    assert t == {"first_half": 60.0, "second_half": 80.0, "delta": 20.0}


def test_tendencia_detecta_el_desgaste():
    a = [FakeAttempt(90.0), FakeAttempt(90.0), FakeAttempt(70.0), FakeAttempt(70.0)]
    assert _trend(a)["delta"] == -20.0


def test_con_numero_impar_la_segunda_mitad_se_queda_el_de_enmedio():
    a = [FakeAttempt(60.0), FakeAttempt(90.0), FakeAttempt(90.0), FakeAttempt(90.0),
         FakeAttempt(90.0)]
    assert _trend(a)["first_half"] == 75.0  # 60 y 90


# --- Donde se corta una sesion ---


def at(minutes: int) -> FakeAttempt:
    base = datetime(2026, 7, 28, 10, 0, tzinfo=timezone.utc)
    return FakeAttempt(80.0, recorded_at=base + timedelta(minutes=minutes))


def test_los_huecos_cortos_no_parten_la_sesion():
    # Medido en el historial real: dentro de un bloque hay huecos de 23 min.
    bloques = group([at(0), at(1), at(8), at(23)])
    assert len(bloques) == 1


def test_un_hueco_largo_abre_otra_sesion():
    # Y entre bloques habia un salto de 148 minutos.
    bloques = group([at(0), at(9), at(157), at(158)])
    assert [len(b) for b in bloques] == [2, 2]


def test_el_corte_esta_donde_dice_la_constante():
    justo_antes = int(SESSION_GAP.total_seconds() / 60) - 1
    justo_despues = int(SESSION_GAP.total_seconds() / 60) + 1
    assert len(group([at(0), at(justo_antes)])) == 1
    assert len(group([at(0), at(justo_despues)])) == 2


def test_sin_intentos_no_hay_bloques():
    assert group([]) == []
