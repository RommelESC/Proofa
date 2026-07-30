"""Pruebas de la medida de dificultad.

El contador de sílabas es la parte que hay que proteger: es donde falla casi
toda implementación de Flesch, porque cuenta grupos de vocales sobre las letras
en vez de mirar la pronunciación. Los casos de aquí son los que mi primera
versión falló — contaba «the» con cero sílabas y «philosophy» con dos, porque
comparaba por carácter y se dejaba fuera `ə` y `ʌ`.
"""

from __future__ import annotations

import pytest

from app.services.difficulty_service import Counts, band, flesch, is_archaic, syllables


@pytest.mark.parametrize(
    "palabra,esperado",
    [
        ("cat", 1),
        ("the", 1),          # /ð ə/ — la schwa faltaba y daba 0
        ("water", 2),
        ("rhythm", 2),       # sin vocal escrita en la segunda sílaba
        ("beautiful", 3),
        ("philosophy", 4),   # daba 2
        ("university", 5),
        ("extraordinary", 5),
        ("queue", 1),        # cinco vocales escritas, una sola sílaba
    ],
)
def test_cuenta_silabas_por_pronunciacion(palabra, esperado):
    assert syllables(palabra) == esperado


# --- La fórmula ---


def test_texto_sencillo_puntua_alto():
    # Oraciones cortas, palabras de una sílaba.
    score = flesch(Counts(sentences=10, words=60, syllables=70, unknown_words=0))
    assert score > 80


def test_texto_denso_puntua_bajo():
    # Oraciones largas y palabras polisílabas: lo que hace difícil un texto.
    score = flesch(Counts(sentences=10, words=250, syllables=500, unknown_words=0))
    assert score < 30


def test_mas_palabras_por_oracion_baja_la_puntuacion():
    corto = flesch(Counts(sentences=20, words=200, syllables=300, unknown_words=0))
    largo = flesch(Counts(sentences=10, words=200, syllables=300, unknown_words=0))
    assert largo < corto


def test_sin_texto_no_hay_puntuacion():
    assert flesch(Counts(sentences=0, words=0, syllables=0, unknown_words=0)) is None


# --- Las bandas ---


def test_las_bandas_van_de_facil_a_dificil():
    assert band(95)[0] == "muy fácil"
    assert band(65)[0] == "normal"
    assert band(10)[0] == "muy difícil"


def test_la_banda_cefr_sube_con_la_dificultad():
    facil = band(95)[1]
    dificil = band(10)[1]
    assert (facil, dificil) == ("A2", "C2")


def test_sin_puntuacion_no_se_inventa_banda():
    assert band(None) == (None, None)


# --- El punto ciego de Flesch ---


@pytest.mark.parametrize("palabra", ["thou", "hast", "whatsoever", "unto", "doth", "recordeth"])
def test_reconoce_lo_arcaico(palabra):
    assert is_archaic(palabra)


@pytest.mark.parametrize("palabra", ["teeth", "the", "philosophy", "breath", "seth"])
def test_no_marca_palabras_normales(palabra):
    """«-eth» tiene falsos amigos: dientes y alientos no son verbos del XVII."""
    assert not is_archaic(palabra)


def test_no_distingue_mayusculas():
    assert is_archaic("Thou") and is_archaic("UNTO")
