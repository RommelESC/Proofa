"""Compara modelos de Ollama en las tareas reales del proyecto.

Elegir modelo local es un balance entre calidad y latencia, y ninguna de las
dos se puede intuir: un modelo grande partido entre GPU y RAM puede ser diez
veces mas lento que uno chico que cabe entero en VRAM, y a veces sin mejorar
la respuesta. Esto lo mide con las mismas frases.

    python scripts/compare_llm.py qwen3:8b qwen3.6:latest
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.llm import LLMNotReady  # noqa: E402
from app.llm.ollama import OllamaProvider  # noqa: E402

# Casos donde un diccionario o una traduccion literal se equivocan.
GLOSSES = [
    ("gave", "He gave up smoking after twenty years."),
    ("run", "She used to run a small business in Queretaro."),
    ("pulling", "He was pulling my leg about the promotion."),
]

PARAGRAPH = [
    "Marcus was adopted by his grandfather, the consular Annius Verus.",
    "He took it as the highest of honours.",
    "The Emperor Hadrian divined the fine character of the lad.",
    "He advanced him to equestrian rank when six years of age.",
]


def build(model: str) -> OllamaProvider:
    provider = OllamaProvider()
    provider._model = model  # noqa: SLF001 - inyeccion deliberada para comparar
    return provider


def run(model: str) -> None:
    print(f"\n{'=' * 68}\n  {model}\n{'=' * 68}")
    provider = build(model)

    health = provider.health()
    if not health.ready:
        print(f"  no disponible: {health.detail}")
        return

    # Primera llamada aparte: incluye la carga del modelo en memoria y
    # falsearia la comparacion si se contara con las demas.
    print("\n  (calentando…)")
    try:
        started = time.time()
        provider.gloss("the", "The cat sat on the mat.")
        print(f"  carga inicial: {time.time() - started:.1f}s")
    except LLMNotReady as exc:
        print(f"  fallo: {exc}")
        return

    print("\n  GLOSAS EN CONTEXTO")
    times = []
    for word, sentence in GLOSSES:
        started = time.time()
        try:
            gloss = provider.gloss(word, sentence)
        except LLMNotReady as exc:
            print(f"    «{word}» -> fallo: {exc}")
            continue
        elapsed = time.time() - started
        times.append(elapsed)
        print(f"    «{word}» en «{sentence[:44]}…»  [{elapsed:.1f}s]")
        print(f"       {gloss.lemma} ({gloss.pos}) — {gloss.sense_es}")
        if gloss.note_es:
            print(f"       nota: {gloss.note_es[:96]}")

    if times:
        print(f"\n    promedio por glosa: {sum(times) / len(times):.1f}s")

    print("\n  TRADUCCION CON CONTEXTO DE PARRAFO")
    started = time.time()
    try:
        result = provider.translate_paragraphs([PARAGRAPH])
    except LLMNotReady as exc:
        print(f"    fallo: {exc}")
        return
    elapsed = time.time() - started

    for original, translated in zip(PARAGRAPH, result[0], strict=False):
        mark = " " if translated else "!"
        print(f"   {mark} {original[:52]}")
        print(f"     -> {translated or '(vacio)'}")

    faltantes = sum(1 for t in result[0] if not t)
    print(f"\n    {elapsed:.1f}s para {len(PARAGRAPH)} oraciones", end="")
    print(f" · {faltantes} sin traducir" if faltantes else " · todas traducidas")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("models", nargs="*", help="Tags de Ollama a comparar")
    args = parser.parse_args()

    models = args.models or [get_settings().ollama_model]
    if not any(models):
        print("Indica al menos un modelo, o define OLLAMA_MODEL en .env", file=sys.stderr)
        return 1

    for model in models:
        run(model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
