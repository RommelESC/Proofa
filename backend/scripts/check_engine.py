"""Prueba un motor de pronunciacion contra un WAV real.

Sirve para dos cosas: confirmar que la conexion funciona, y calibrar. El
flag --raw vuelca el payload integro del motor, que es lo que hay que mirar
cuando un score no cuadra con lo que oiste.

    python scripts/check_engine.py grabacion.wav "I think so"
    python scripts/check_engine.py grabacion.wav "I think so" --engine azure --raw

Las grabaciones que haces desde la interfaz quedan en data/assets/recordings/,
asi que puedes reevaluar una vieja con otro motor y comparar directamente.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.engines import EngineNotReady, get_engine  # noqa: E402
from app.phonology import PATTERNS_BY_CODE, detect  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path, help="WAV PCM 16 kHz mono")
    parser.add_argument("text", help="Texto que se esperaba leer")
    parser.add_argument("--engine", default=None, help="mock | azure | local")
    parser.add_argument("--raw", action="store_true", help="Volcar el payload del motor")
    args = parser.parse_args()

    if not args.audio.exists():
        print(f"No existe: {args.audio}", file=sys.stderr)
        return 1

    name = args.engine or get_settings().pronunciation_engine
    engine = get_engine(name)

    health = engine.health()
    print(f"motor: {health.name} v{health.version} — {health.detail}")
    if not health.ready:
        print("\nEl motor no esta listo. Revisa .env y las dependencias.", file=sys.stderr)
        return 2

    try:
        result = engine.assess(args.audio, args.text)
    except EngineNotReady as exc:
        print(f"\nFallo: {exc}", file=sys.stderr)
        return 2

    result.patterns = detect(result.words)

    print(f"\nglobal: {result.overall}")
    p = result.prosody
    print(
        f"fluidez: {p.fluency}  completitud: {p.completeness}  "
        f"prosodia: {p.prosody_score}  wpm: {p.wpm}"
    )

    print("\npalabras:")
    for word in result.words:
        mark = " " if word.score >= 70 else "!"
        detail = " ".join(
            f"{ph.expected_ipa}->{ph.produced_ipa}"
            if ph.produced_ipa and ph.produced_ipa != ph.expected_ipa
            else (ph.expected_ipa if ph.produced_ipa else f"{ph.expected_ipa}->_")
            for ph in word.phonemes
        )
        print(f" {mark} {word.surface:<16} {word.score:>5}  {detail}")

    if result.patterns:
        print("\npatrones detectados:")
        for hit in result.patterns:
            label = PATTERNS_BY_CODE[hit.code].label_es
            print(f"  {hit.code:<15} conf {hit.confidence:<5} {label} — {hit.detail}")
    else:
        print("\nsin patrones de la taxonomia L1-espanol")

    if args.raw:
        print("\npayload crudo:")
        print(json.dumps(result.raw, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
