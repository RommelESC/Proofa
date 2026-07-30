"""Politica de puntuacion de palabra. Un solo lugar, compartido por motores.

El promedio simple de fonemas es demasiado indulgente: en «think» un /θ/
convertido en /s/ queda diluido por tres fonemas correctos y la palabra pasa
como aceptable. Pero para quien escucha, esa palabra SI esta mal dicha.

Por eso el score combina la media con el peor fonema. El peso de 0.4 al
minimo es un parametro de calibracion: subirlo hace el sistema mas severo.
Ajustalo contra tus propias grabaciones de referencia, no a ojo.
"""

from __future__ import annotations

from app.schemas.assessment import PhonemeScore

MIN_WEIGHT = 0.4


def word_score(phonemes: list[PhonemeScore], *, default: float = 0.0) -> float:
    if not phonemes:
        return default
    scores = [p.score for p in phonemes]
    mean = sum(scores) / len(scores)
    worst = min(scores)
    return round((1 - MIN_WEIGHT) * mean + MIN_WEIGHT * worst, 1)
