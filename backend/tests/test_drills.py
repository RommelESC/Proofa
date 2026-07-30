"""Pruebas del material de practica dirigida.

Todos los casos de aqui son reales: salieron como ejercicios en la primera
version, sobre el libro que el usuario esta leyendo. La calidad del material es
la mitad del valor de la funcion — una frase de practica que en realidad es una
entrada de indice hace perder el tiempo y desconfiar del resto.
"""

from __future__ import annotations

from collections import Counter

from app.services.drill_service import (
    Corpus,
    _pick_words,
    _usable_word,
    is_complete_sentence,
)


def corpus(words: dict[str, tuple[str, ...]], known=None, freq=None) -> Corpus:
    return Corpus(
        book_id=1,
        total_sentences=100,
        ipa=words,
        freq=Counter(freq or {w: 10 for w in words}),
        known=set(known if known is not None else words),
    )


# --- Que cuenta como frase ---


def test_acepta_prosa_de_verdad():
    assert is_complete_sentence("One of these must needs be.")
    assert is_complete_sentence("Then canst not thou truly be free?")


def test_rechaza_referencias_con_numeros():
    assert not is_complete_sentence("Salaminius, Book 7, XXXVII.")
    assert not is_complete_sentence('XII "Claudius Maximus" (15).')


def test_rechaza_fragmentos_sin_entonacion():
    # Trozos que dejaba la segmentacion: ni empiezan ni acaban donde deberian.
    assert not is_complete_sentence("his readiness to hear any man")
    assert not is_complete_sentence("neither absolutely requiring of his friends")


def test_rechaza_lo_vacio():
    assert not is_complete_sentence("")
    assert not is_complete_sentence("   ")


# --- Que cuenta como palabra practicable ---


def test_rechaza_restos_de_extraccion():
    c = corpus({"ii": ("i",), "e": ("i",), "'ee": ("i",), "easy": ("i", "z", "i")})
    assert not _usable_word(c, "e")  # una letra suelta
    assert not _usable_word(c, "'ee")  # apostrofo pegado
    assert _usable_word(c, "easy")


def test_rechaza_lo_que_el_diccionario_no_conoce():
    """A «xii» y «salaminius» el modelo les inventa una pronunciacion.

    Sin avisar, y plausible. Drilar eso es ensenar a decir mal algo que no es
    una palabra.
    """
    c = corpus({"xii": ("i",), "easy": ("i", "z", "i")}, known={"easy"})
    assert not _usable_word(c, "xii")
    assert _usable_word(c, "easy")


# --- Como se ordenan las palabras ---


def test_lo_que_ya_te_salio_mal_va_primero():
    c = corpus({"easy": ("i", "z", "i"), "very": ("v", "ɛ", "ɹ", "i")})
    out = _pick_words(c, "i", {"very": 74.3}, 5)
    assert out[0]["surface"] == "very"
    assert out[0]["your_mean"] == 74.3


def test_entre_dos_con_historial_gana_el_peor():
    c = corpus({"very": ("v", "ɛ", "ɹ", "i"), "breathe": ("b", "ɹ", "i", "ð")})
    out = _pick_words(c, "i", {"very": 74.3, "breathe": 100.0}, 5)
    assert [w["surface"] for w in out[:2]] == ["very", "breathe"]


def test_las_funcionales_entran_pero_contadas():
    """«he, be, we, me» es donde mas vive la /i/, y un drill de eso aburre."""
    palabras = {w: ("h", "i") for w in ("hee", "bee", "wee", "mee", "see")}
    palabras["easy"] = ("i", "z", "i")
    c = corpus(palabras, freq={**{w: 900 for w in palabras}, "easy": 8})
    out = _pick_words(c, "i", {}, 6)
    frecuentes = [w for w in out if c.freq[w["surface"]] >= 200]
    assert len(frecuentes) <= 2
    assert any(w["surface"] == "easy" for w in out)


def test_cuenta_las_apariciones_dentro_de_la_palabra():
    c = corpus({"easy": ("i", "z", "i")})
    assert _pick_words(c, "i", {}, 3)[0]["occurrences"] == 2
