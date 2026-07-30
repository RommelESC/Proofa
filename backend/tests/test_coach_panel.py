"""Pruebas del panel de corrección.

Las dos partes con lógica propia son la detección de pausas y el contexto de
una palabra omitida. El resto es leer la base y juntarlo.

El umbral de pausa no es a ojo: sale de medir los huecos reales entre palabras
en las grabaciones del usuario. Leyendo seguido son de 10-30 ms; en una lectura
lenta deliberada, la mediana sube a 510. Los casos de aquí usan esos números.
"""

from __future__ import annotations

from app.services.coach_panel_service import LONG_PAUSE_MS, Timed, context_of, long_pauses


def hablando(*duraciones_y_huecos):
    """Construye una secuencia de palabras con los huecos que se le pasen."""
    palabras, t = [], 0
    for i, (dur, hueco) in enumerate(duraciones_y_huecos):
        palabras.append(Timed(f"w{i}", t, t + dur))
        t += dur + hueco
    return palabras


# --- Pausas ---


def test_leer_seguido_no_produce_pausas():
    # Huecos de 10 ms: lo que mide una lectura normal.
    assert long_pauses(hablando((200, 10), (200, 10), (200, 0))) == []


def test_un_silencio_real_se_detecta():
    p = long_pauses(hablando((200, 10), (200, 700), (200, 0)))
    assert len(p) == 1
    assert p[0]["ms"] == 700
    assert (p[0]["after"], p[0]["before"]) == ("w1", "w2")


def test_el_umbral_esta_donde_dice_la_constante():
    assert long_pauses(hablando((100, LONG_PAUSE_MS - 1), (100, 0))) == []
    assert len(long_pauses(hablando((100, LONG_PAUSE_MS), (100, 0)))) == 1


def test_una_sola_palabra_no_tiene_huecos():
    assert long_pauses(hablando((300, 0))) == []


def test_sin_palabras_no_revienta():
    assert long_pauses([]) == []


# --- Contexto de la omisión ---


def test_situa_la_palabra_en_su_frase():
    """Dos palabras a cada lado: justo el contexto de la propuesta de diseño."""
    texto = "and to forbear not only to do, but to intend any evil."
    assert context_of(texto, "any") == "to intend any evil"


def test_no_distingue_mayusculas():
    assert "The" in context_of("The fame and memory of him", "the")


def test_al_principio_de_la_frase_no_se_sale():
    assert context_of("His father, Annius Verus, had held", "His").startswith("His")


def test_una_palabra_que_no_esta_devuelve_vacio():
    assert context_of("nothing to see here", "elephant") == ""


def test_se_queda_con_la_primera_aparicion():
    # Suficiente para situarla: el objetivo es que reconozcas cuál fue, no
    # resolver a cuál de tres repeticiones se refiere.
    assert context_of("the cat and the dog", "the").startswith("the cat")
