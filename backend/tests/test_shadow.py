"""Pruebas de la comparacion de ritmo.

El caso central es real: la misma frase, leida por el usuario y por el
sintetizador. Los fonemas puntuaban entre 79 y 97 — o sea, bien — y aun asi el
ritmo estaba aplanado. Eso es justo lo que ninguna otra parte de la app ve.
"""

from __future__ import annotations

from app.services.shadow_service import MIN_WORDS, Timed, align, compare


# Medicion real: «They breathe through those very thin leather things.»
MODELO = [
    Timed("They", 50, 150),
    Timed("breathe", 212, 300),
    Timed("through", 525, 162),
    Timed("those", 700, 250),
    Timed("very", 962, 287),
    Timed("thin", 1262, 275),
    Timed("leather", 1550, 275),
    Timed("things", 1837, 612),
]
TUYA = [
    Timed("they", 50, 320),
    Timed("breathe", 380, 210),
    Timed("through", 600, 210),
    Timed("those", 820, 210),
    Timed("very", 1040, 210),
    Timed("thin", 1260, 190),
    Timed("leather", 1460, 270),
    Timed("things", 1740, 490),
]


# --- El emparejado ---


def test_empareja_ignorando_mayusculas_y_puntuacion():
    pares = align(TUYA, MODELO)
    assert len(pares) == len(MODELO)
    assert [p[1].surface for p in pares] == [m.surface for m in MODELO]


def test_una_omision_no_desplaza_el_resto():
    """Alinear por indice convertiria la comparacion en basura sin avisar."""
    sin_very = [t for t in TUYA if t.surface != "very"]
    pares = align(sin_very, MODELO)
    assert len(pares) == len(MODELO) - 1
    # Cada par sigue siendo la misma palabra en los dos lados.
    assert all(p[0].surface.lower() == p[1].surface.lower() for p in pares)


def test_una_palabra_repetida_no_se_empareja_dos_veces():
    modelo = [Timed("the", 0, 100), Timed("the", 100, 100), Timed("end", 200, 300)]
    tuya = [Timed("the", 0, 120), Timed("the", 120, 120), Timed("end", 240, 260)]
    assert len(align(tuya, modelo)) == 3


# --- Lo que se mide ---


def test_detecta_que_aplanas_el_ritmo():
    """El hallazgo que motiva el modo entero."""
    d = compare(TUYA, MODELO)
    assert d["enough"]
    assert d["your_contrast"] < d["model_contrast"]
    assert d["contrast_ratio"] < 1


def test_el_tempo_se_reporta_aparte_del_contraste():
    # Ir mas rapido y aplanar son problemas distintos: uno se arregla solo.
    d = compare(TUYA, MODELO)
    assert 0.85 <= d["tempo"] <= 0.95


def test_ir_mas_lento_no_cuenta_como_error_de_ritmo():
    """Misma forma, todo al doble de lento: el contraste no debe moverse."""
    lento = [Timed(t.surface, t.start_ms * 2, t.duration_ms * 2) for t in MODELO]
    d = compare(lento, MODELO)
    assert d["tempo"] == 2.0
    assert d["contrast_ratio"] == 1.0
    assert all(w["verdict"] == "en su sitio" for w in d["words"])


def test_nombra_las_palabras_que_mas_se_desvian():
    d = compare(TUYA, MODELO)
    assert d["notable"]
    # «They» duro 320 ms donde el modelo puso 150: es la mas estirada.
    assert d["notable"][0]["surface"] == "They"
    assert d["notable"][0]["verdict"] == "estirada"


def test_una_lectura_identica_no_tiene_nada_que_senalar():
    d = compare(list(MODELO), MODELO)
    assert d["tempo"] == 1.0
    assert d["contrast_ratio"] == 1.0
    assert d["notable"] == []


# --- Cuando no hay con que ---


def test_con_pocas_palabras_no_se_opina():
    corto = MODELO[: MIN_WORDS - 1]
    d = compare(list(corto), corto)
    assert d["enough"] is False
    assert d["matched"] == MIN_WORDS - 1


def test_si_no_se_parecen_en_nada_tampoco():
    otra = [Timed("completely", 0, 200), Timed("different", 200, 200)]
    assert compare(otra, MODELO)["enough"] is False
