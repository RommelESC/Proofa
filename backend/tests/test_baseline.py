"""Pruebas del baseline personal.

Lo que se protege aqui no es que el numero salga bonito, sino que el sistema
se calle cuando no sabe. Un baseline que declara debilidades con siete
muestras ruidosas manda a practicar lo que no toca, y eso es peor que la
version con umbrales absolutos que al menos no pretendia conocerte.
"""

from __future__ import annotations

import math

from app.services.baseline_service import (
    MIN_SAMPLES,
    OK,
    UNCLEAR,
    WEAK,
    Tally,
    attempts_to_resolve,
    build_baselines,
    focus_in_attempt,
)


def tally(ipa: str, n: int, mean: float, sd: float) -> Tally:
    """Construye los recuentos que producirian esa media y desviacion."""
    total = n * mean
    total_sq = (n - 1) * sd * sd + n * mean * mean if n > 1 else mean * mean
    return Tally(ipa, n, total, total_sq)


def by_ipa(baselines):
    return {b.ipa: b for b in baselines}


def solid_rest() -> list[Tally]:
    """Un cuerpo de fonemas sanos que sirva de vara estable."""
    return [tally(f"r{i}", 60, 85.0, 12.0) for i in range(6)]


# --- Lo que si debe detectar ---


def test_debilidad_clara_con_datos_suficientes():
    b = by_ipa(build_baselines([tally("i", 80, 70.0, 12.0), *solid_rest()]))["i"]
    assert b.verdict == WEAK
    assert b.gap == 15.0
    assert b.samples_needed is None  # ya esta resuelto


def test_fonema_por_encima_de_tu_media_es_ok():
    b = by_ipa(build_baselines([tally("m", 80, 93.0, 10.0), *solid_rest()]))["m"]
    assert b.verdict == OK
    assert b.gap < 0


def test_la_vara_excluye_al_propio_fonema():
    # Con 600 muestras en 60, incluir el fonema en la referencia la hundiria
    # y el hueco se encogeria hasta desaparecer.
    b = by_ipa(build_baselines([tally("t", 600, 60.0, 12.0), *solid_rest()]))["t"]
    assert b.reference == 85.0
    assert b.verdict == WEAK


# --- Lo que NO debe detectar ---


def test_muestra_pequena_no_produce_veredicto():
    b = by_ipa(build_baselines([tally("z", MIN_SAMPLES - 1, 60.0, 5.0), *solid_rest()]))["z"]
    assert b.verdict == UNCLEAR
    assert b.stdev is None


def test_ruido_alto_no_se_declara_debilidad():
    """El caso real: /ʃ/ con n=7 y desviacion 26.3 parecia un punto debil."""
    b = by_ipa(build_baselines([tally("ʃ", 7, 72.9, 26.3), *solid_rest()]))["ʃ"]
    assert b.verdict == UNCLEAR
    assert b.samples_needed is not None  # pero dice cuanto falta


def test_diferencia_minuscula_es_irresoluble():
    # Medio punto por debajo de la vara: ninguna cantidad util de muestras
    # lo vuelve significativo, y prometer un objetivo seria mentir.
    b = by_ipa(build_baselines([tally("d", 40, 84.5, 20.0), *solid_rest()]))["d"]
    assert b.verdict == UNCLEAR
    assert b.samples_needed is None


# --- Como se comporta el objetivo ---


def test_hacen_falta_menos_muestras_cuanto_mayor_es_el_hueco():
    rest = solid_rest()
    poco = by_ipa(build_baselines([tally("a", 8, 80.0, 20.0), *rest]))["a"]
    mucho = by_ipa(build_baselines([tally("a", 8, 74.0, 20.0), *rest]))["a"]
    assert poco.samples_needed > mucho.samples_needed


def test_hacen_falta_menos_muestras_cuanto_menor_es_el_ruido():
    # Hueco pequeño a proposito: con uno grande el caso limpio ya seria
    # significativo con estas 8 muestras y no pediria ninguna mas.
    rest = solid_rest()
    ruidoso = by_ipa(build_baselines([tally("a", 8, 82.0, 24.0), *rest]))["a"]
    limpio = by_ipa(build_baselines([tally("a", 8, 82.0, 12.0), *rest]))["a"]
    assert ruidoso.verdict == limpio.verdict == UNCLEAR
    assert ruidoso.samples_needed > limpio.samples_needed


def test_menos_ruido_resuelve_antes():
    """Con el mismo hueco, bajar el ruido cierra el veredicto sin mas datos."""
    rest = solid_rest()
    ruidoso = by_ipa(build_baselines([tally("a", 8, 78.0, 24.0), *rest]))["a"]
    limpio = by_ipa(build_baselines([tally("a", 8, 78.0, 8.0), *rest]))["a"]
    assert ruidoso.verdict == UNCLEAR
    assert limpio.verdict == WEAK


def test_el_objetivo_es_alcanzable():
    """Reunir las muestras prometidas debe cerrar realmente el veredicto."""
    rest = solid_rest()
    b = by_ipa(build_baselines([tally("a", 8, 76.0, 18.0), *rest]))["a"]
    logrado = by_ipa(build_baselines([tally("a", b.samples_needed, 76.0, 18.0), *rest]))["a"]
    assert logrado.verdict == WEAK


# --- Cuanto cuesta salir de dudas ---


def test_el_coste_usa_el_ritmo_del_propio_fonema():
    """El caso real que casi se cuela: /j/ salio 5 veces en 16 grabaciones.

    Al ritmo general (345 muestras / 16 grabaciones) las 14 muestras que le
    faltan parecian UNA grabacion. A su ritmo real son cuarenta y cinco.
    """
    assert attempts_to_resolve(14, 5, 16) == 45


def test_un_fonema_frecuente_se_resuelve_antes():
    frecuente = attempts_to_resolve(40, 37, 16)  # /s/: dos por grabacion
    raro = attempts_to_resolve(40, 5, 16)
    assert frecuente < raro


def test_un_horizonte_absurdo_no_es_un_objetivo():
    """El caso real: /ɛɹ/ pedia 2240 lecturas. Eso no es una meta."""
    assert attempts_to_resolve(980, 7, 16) is None


def test_sin_historial_no_se_puede_estimar():
    assert attempts_to_resolve(20, 0, 16) is None
    assert attempts_to_resolve(20, 5, 0) is None


# --- Del informe al corrector ---


def test_solo_se_señalan_tus_debilidades_conocidas():
    focos = focus_in_attempt({"i": 70.0}, [("i", 62.0), ("s", 40.0), ("t", 88.0)])
    # /s/ salio fatal, pero eso ya lo cubre el umbral absoluto. Aqui va lo tuyo.
    assert [f["ipa"] for f in focos] == ["i"]


def test_promedia_las_apariciones_del_intento():
    focos = focus_in_attempt({"i": 70.0}, [("i", 60.0), ("i", 80.0)])
    assert focos[0]["now"] == 70.0
    assert focos[0]["occurrences"] == 2


def test_tambien_reconoce_la_mejora():
    """Comparar contra tu historial permite dar buenas noticias, no solo malas."""
    focos = focus_in_attempt({"i": 60.0}, [("i", 78.0)])
    assert focos[0]["delta"] == 18.0


def test_una_debilidad_que_no_aparecio_no_se_menciona():
    assert focus_in_attempt({"i": 70.0}, [("t", 88.0)]) == []


def test_sin_debilidades_confirmadas_no_hay_nada_que_decir():
    assert focus_in_attempt({}, [("i", 30.0)]) == []


def test_lo_peor_de_lo_tuyo_va_primero():
    focos = focus_in_attempt({"i": 70.0, "ʃ": 72.0}, [("i", 80.0), ("ʃ", 55.0)])
    assert [f["ipa"] for f in focos] == ["ʃ", "i"]


# --- Bordes ---


def test_sin_datos():
    assert build_baselines([]) == []


def test_un_solo_fonema_no_tiene_con_que_compararse():
    b = build_baselines([tally("i", 50, 70.0, 10.0)])[0]
    assert b.verdict == UNCLEAR


def test_varianza_cero_no_revienta():
    b = by_ipa(build_baselines([tally("i", 30, 70.0, 0.0), *solid_rest()]))["i"]
    assert b.stdev == 0.0
    assert b.verdict == WEAK


def test_orden_de_peor_a_mejor():
    out = build_baselines([tally("a", 30, 90.0, 5.0), tally("b", 30, 60.0, 5.0), *solid_rest()])
    assert [b.ipa for b in out[:2]] == ["b"] + [out[1].ipa]
    assert out[0].mean <= out[1].mean <= out[2].mean


def test_el_intervalo_dibujado_coincide_con_el_veredicto():
    """La barra no puede contradecir al fallo.

    El grafico pinta media ± margen contra la vara. Si ese intervalo cruza la
    vara pero el veredicto dice «debil», el usuario ve una cosa y lee otra —
    y la que se cree es la imagen.
    """
    casos = [
        tally("a", 80, 70.0, 12.0),  # debilidad clara
        tally("b", 7, 72.9, 26.3),  # ruidoso
        tally("c", 30, 84.0, 10.0),  # justo por debajo
        tally("d", 80, 93.0, 10.0),  # por encima
    ]
    for b in build_baselines([*casos, *solid_rest()]):
        if b.margin is None:
            assert b.verdict == UNCLEAR
            continue
        separado = b.mean + b.margin < b.reference
        assert separado == (b.verdict == WEAK), f"/{b.ipa}/ dibuja algo distinto de lo que dice"


def test_los_recuentos_reproducen_media_y_desviacion():
    """Si el helper miente, todas las demas pruebas miden otra cosa."""
    b = build_baselines([tally("x", 40, 77.0, 13.0), *solid_rest()])[0]
    assert math.isclose(b.mean, 77.0, abs_tol=0.05)
    assert math.isclose(b.stdev, 13.0, abs_tol=0.05)
