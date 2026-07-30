"""Comparacion de ritmo entre tu lectura y el modelo.

Shadowing no se corrige con fonemas: para eso ya esta Coach. Lo que entrena es
el RITMO, y hay una forma de medirlo que significa algo.

El ingles es de ritmo acentual: las silabas tonicas se alargan y las atonas se
comprimen, y la diferencia entre unas y otras es grande. El espanol es de ritmo
silabico: todas duran parecido. Un hispanohablante leyendo ingles tiende a
APLANAR — pronuncia todo con duraciones parejas — y eso suena a acento incluso
cuando cada fonema esta bien.

Medido en una lectura real: el modelo repartia sus palabras entre 150 y 612 ms;
la misma frase leida por el usuario, entre 190 y 490. Los fonemas puntuaban
79-97. El problema no estaba en los sonidos.

Asi que se miden dos cosas distintas y se reportan por separado:

- **tempo**: si vas mas rapido o mas lento en total. Es lo menos interesante y
  lo mas facil de arreglar.
- **contraste**: cuanto varian tus duraciones frente a las suyas. Es el que
  delata el ritmo silabico, y no se arregla yendo mas despacio.

Los dos lados salen de mediciones reales: tus tiempos por palabra los da el
motor de pronunciacion, los del modelo vienen de las marcas del sintetizador.
Nada de esto es estimado.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

# Por debajo de esto la comparacion es anecdota: con tres palabras, una pausa
# para respirar ya cambia todas las cifras.
MIN_WORDS = 4

# Cuanto tiene que desviarse una palabra para nombrarla. Por debajo, la
# diferencia cabe en el margen del propio motor y senalarla seria ruido.
NOTABLE_RATIO = 1.35


@dataclass(frozen=True)
class Timed:
    """Una palabra con su duracion medida, venga de donde venga."""

    surface: str
    start_ms: int
    duration_ms: int


def _normalize(word: str) -> str:
    return "".join(c for c in word.lower() if c.isalpha() or c == "'")


def align(yours: list[Timed], model: list[Timed]) -> list[tuple[Timed, Timed]]:
    """Empareja palabra con palabra por su forma, en orden.

    No por posicion: si te saltaste una palabra, alinear por indice desplazaria
    todas las siguientes y la comparacion de ritmo se volveria basura sin que
    nada avisara. Avanzando por coincidencia de forma, una omision se queda
    fuera y el resto sigue emparejado donde debe.
    """
    pairs: list[tuple[Timed, Timed]] = []
    i = 0
    for m in model:
        target = _normalize(m.surface)
        j = i
        while j < len(yours) and _normalize(yours[j].surface) != target:
            j += 1
        if j < len(yours):
            pairs.append((yours[j], m))
            i = j + 1
    return pairs


def _contrast(durations: list[int]) -> float | None:
    """Cuanto varian las duraciones entre si.

    Coeficiente de variacion (desviacion / media) y no max/min: con max/min una
    sola palabra final alargada decide el numero entero. Esto describe el
    reparto completo, que es lo que se oye como ritmo.
    """
    if len(durations) < 2:
        return None
    media = statistics.mean(durations)
    if media <= 0:
        return None
    return statistics.pstdev(durations) / media


def compare(yours: list[Timed], model: list[Timed]) -> dict:
    pairs = align(yours, model)
    if len(pairs) < MIN_WORDS:
        return {
            "enough": False,
            "matched": len(pairs),
            "expected": len(model),
        }

    tus_dur = [p[0].duration_ms for p in pairs]
    mod_dur = [p[1].duration_ms for p in pairs]

    tu_total = sum(tus_dur)
    mod_total = sum(mod_dur)

    tu_contraste = _contrast(tus_dur)
    mod_contraste = _contrast(mod_dur)

    words = []
    for mine, m in pairs:
        # Relativo al tempo de cada uno: si vas al 90% de su velocidad, TODAS
        # tus palabras salen mas cortas y eso no es un error de ritmo. Lo que
        # importa es como repartes el tiempo que usas.
        tuyo_rel = mine.duration_ms / tu_total if tu_total else 0
        modelo_rel = m.duration_ms / mod_total if mod_total else 0
        ratio = (tuyo_rel / modelo_rel) if modelo_rel else 1.0
        words.append(
            {
                "surface": m.surface,
                "yours_ms": mine.duration_ms,
                "model_ms": m.duration_ms,
                "yours_share": round(tuyo_rel, 4),
                "model_share": round(modelo_rel, 4),
                "ratio": round(ratio, 2),
                "verdict": "estirada" if ratio >= NOTABLE_RATIO
                else "comprimida" if ratio <= 1 / NOTABLE_RATIO
                else "en su sitio",
            }
        )

    notables = sorted(
        (w for w in words if w["verdict"] != "en su sitio"),
        key=lambda w: abs(1 - w["ratio"]),
        reverse=True,
    )

    return {
        "enough": True,
        "matched": len(pairs),
        "expected": len(model),
        "tempo": round(tu_total / mod_total, 2) if mod_total else None,
        "your_contrast": round(tu_contraste, 3) if tu_contraste is not None else None,
        "model_contrast": round(mod_contraste, 3) if mod_contraste is not None else None,
        # <1 significa que aplanas: repartes el tiempo mas parejo que el modelo.
        "contrast_ratio": (
            round(tu_contraste / mod_contraste, 2)
            if tu_contraste is not None and mod_contraste not in (None, 0)
            else None
        ),
        "words": words,
        "notable": notables[:3],
    }
