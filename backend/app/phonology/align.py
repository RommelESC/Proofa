"""Alineacion de secuencias de fonemas (Needleman-Wunsch).

Necesaria porque lo que produjiste y lo que se esperaba tienen distinta
longitud: omites fonemas, insertas otros. Sin alinear, comparar posicion a
posicion produce basura despues del primer error.
"""

from __future__ import annotations

GAP_PENALTY = -1.0
MATCH = 1.0
MISMATCH = -0.5

# Sustituciones foneticamente cercanas: penalizarlas como un error total
# infla los falsos positivos.
NEAR: dict[frozenset[str], float] = {
    frozenset({"i", "ɪ"}): 0.3,
    frozenset({"u", "ʊ"}): 0.3,
    frozenset({"ə", "ʌ"}): 0.5,
    frozenset({"ɛ", "æ"}): 0.2,
    frozenset({"θ", "s"}): 0.0,
    frozenset({"ð", "d"}): 0.0,
    frozenset({"v", "b"}): 0.0,
    frozenset({"z", "s"}): 0.0,
    frozenset({"ɹ", "r"}): 0.6,
    frozenset({"ɡ", "g"}): 0.9,
}


def _score(a: str, b: str) -> float:
    if a == b:
        return MATCH
    return NEAR.get(frozenset({a, b}), MISMATCH)


def align(
    expected: list[str], produced: list[str]
) -> list[tuple[int | None, int | None]]:
    """Devuelve pares (idx_esperado, idx_producido).

    None en la primera posicion = insercion (dijiste algo de mas).
    None en la segunda = omision (te comiste un fonema).
    """
    n, m = len(expected), len(produced)
    if n == 0:
        return [(None, j) for j in range(m)]
    if m == 0:
        return [(i, None) for i in range(n)]

    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = dp[i - 1][0] + GAP_PENALTY
    for j in range(1, m + 1):
        dp[0][j] = dp[0][j - 1] + GAP_PENALTY

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            dp[i][j] = max(
                dp[i - 1][j - 1] + _score(expected[i - 1], produced[j - 1]),
                dp[i - 1][j] + GAP_PENALTY,
                dp[i][j - 1] + GAP_PENALTY,
            )

    pairs: list[tuple[int | None, int | None]] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + _score(expected[i - 1], produced[j - 1]):
            pairs.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + GAP_PENALTY:
            pairs.append((i - 1, None))
            i -= 1
        else:
            pairs.append((None, j - 1))
            j -= 1

    pairs.reverse()
    return pairs


def similarity_score(expected_ph: str, produced_ph: str | None) -> float:
    """Score 0..100 para un par alineado."""
    if produced_ph is None:
        return 15.0
    raw = _score(expected_ph, produced_ph)
    return round(max(0.0, min(1.0, (raw + 0.5) / 1.5)) * 100, 1)
