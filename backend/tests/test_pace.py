"""Pruebas de la velocidad de lectura medida.

El marcapasos corre a este numero, asi que una medicion contaminada no produce
un dato feo: produce una banda que te arrastra o que te espera. Todos los casos
de aqui salen del historial real.
"""

from __future__ import annotations

from app.services.pace_service import FALLBACK_WPM, MIN_SAMPLES, summarize, usable_speeds


def test_descarta_grabaciones_fallidas():
    """640 wpm sobre 1.5s de audio vacio, y 348 y 379 iguales.

    Todas con completitud 0: el motor no reconocio nada y el wpm sale de
    dividir las palabras esperadas entre una duracion minuscula.
    """
    filas = [(640.0, 0.0), (379.3, 0.0), (348.0, 0.0), (118.3, 100.0)]
    assert usable_speeds(filas) == [118.3]


def test_conserva_una_lectura_lenta_deliberada():
    # 44 wpm con completitud 82 es una lectura lenta de verdad, no un fallo.
    assert usable_speeds([(44.0, 82.0)]) == [44.0]


def test_descarta_lo_fisicamente_imposible_aunque_pase_completitud():
    assert usable_speeds([(900.0, 100.0), (5.0, 100.0)]) == []


def test_ignora_mediciones_ausentes():
    assert usable_speeds([(None, 100.0), (120.0, 100.0)]) == [120.0]


def test_completitud_no_medida_no_descarta():
    # Un motor que no la reporta no es un motor que midio un cero.
    assert usable_speeds([(120.0, None)]) == [120.0]


# --- El resumen ---


def test_usa_la_mediana_no_la_media():
    """Con una lectura lenta deliberada dentro, la media miente.

    Estos son sus siete valores reales: la media da 103, la mediana 118.
    """
    v = [44.0, 44.0, 101.9, 118.3, 118.3, 126.4, 167.5]
    assert summarize(v)["wpm"] == 118


def test_reporta_el_rango_y_la_muestra():
    d = summarize([100.0, 120.0, 140.0])
    assert (d["slowest"], d["fastest"], d["samples"]) == (100, 140, 3)
    assert d["measured"] is True


def test_sin_muestra_suficiente_no_finge_una_medicion():
    d = summarize([120.0] * (MIN_SAMPLES - 1))
    assert d["measured"] is False
    assert d["wpm"] == FALLBACK_WPM


def test_sin_nada_devuelve_el_valor_por_defecto():
    d = summarize([])
    assert d["measured"] is False
    assert d["wpm"] == FALLBACK_WPM
