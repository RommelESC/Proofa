"""Grafema -> fonema para ingles, con salida en IPA.

Por que existe: para saber si pronunciaste mal una palabra hay que saber
primero como *deberia* sonar. Como siempre lees un texto conocido, esto es
un problema resuelto (no hay que adivinar que dijiste, solo verificarlo).

Camino principal: g2p_en (CMUdict + modelo neuronal para OOV) -> ARPAbet,
que traducimos a IPA. Si g2p_en no esta disponible o falta la data de nltk,
caemos a un g2p por reglas: peor, pero nunca revienta.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache

log = logging.getLogger(__name__)

# ARPAbet (CMUdict) -> IPA. Las vocales llevan digito de acento: 0=atono, 1=primario, 2=secundario.
ARPABET_TO_IPA: dict[str, str] = {
    "AA": "ɑ", "AE": "æ", "AH": "ʌ", "AO": "ɔ", "AW": "aʊ", "AY": "aɪ",
    "EH": "ɛ", "ER": "ɝ", "EY": "eɪ", "IH": "ɪ", "IY": "i", "OW": "oʊ",
    "OY": "ɔɪ", "UH": "ʊ", "UW": "u",
    "B": "b", "CH": "tʃ", "D": "d", "DH": "ð", "F": "f", "G": "ɡ",
    "HH": "h", "JH": "dʒ", "K": "k", "L": "l", "M": "m", "N": "n",
    "NG": "ŋ", "P": "p", "R": "ɹ", "S": "s", "SH": "ʃ", "T": "t",
    "TH": "θ", "V": "v", "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ",
}

VOWELS_IPA = set("ɑæʌɔɛɝɚɪiʊuəaeo") | {"aʊ", "aɪ", "eɪ", "oʊ", "ɔɪ"}

_STRESS_RE = re.compile(r"([A-Z]+)([0-2])?$")


def arpabet_to_ipa(symbol: str) -> tuple[str, int | None]:
    """Devuelve (ipa, acento). acento es None en consonantes.

    La regla que mas importa aqui: AH0 -> schwa. El espanol no tiene schwa,
    y no reducirla es la causa principal de sonar 'silabeado' aunque cada
    sonido individual este bien.
    """
    m = _STRESS_RE.match(symbol.strip().upper())
    if not m:
        return symbol.lower(), None

    base, stress_digit = m.group(1), m.group(2)
    stress = int(stress_digit) if stress_digit is not None else None

    if base == "AH" and stress == 0:
        return "ə", 0
    if base == "ER" and stress == 0:
        return "ɚ", 0

    return ARPABET_TO_IPA.get(base, base.lower()), stress


class G2P:
    """Interfaz minima. `phonemize` devuelve la secuencia IPA esperada."""

    name = "base"

    def phonemize(self, word: str) -> list[str]:  # pragma: no cover - interfaz
        raise NotImplementedError

    def stress_pattern(self, word: str) -> list[int]:
        """Indices (sobre la lista IPA) que llevan acento primario."""
        return []

    def knows(self, word: str) -> bool:
        """Si la pronunciacion viene del diccionario o esta adivinada.

        Importa para elegir material de practica. Un EPUB deja tokens como
        «xii» o «salaminius», y el modelo les inventa una pronunciacion
        plausible sin avisar; drilar eso seria ensenar a decir mal algo que
        no es una palabra. Quien no puede distinguirlo devuelve True y deja
        la decision a quien llame.
        """
        return True


class CmudictG2P(G2P):
    name = "g2p_en"

    def __init__(self) -> None:
        from g2p_en import G2p  # import perezoso: pesa y baja data de nltk

        self._g2p = G2p()

    @lru_cache(maxsize=8192)
    def _arpabet(self, word: str) -> tuple[str, ...]:
        return tuple(p for p in self._g2p(word) if p.strip() and p != " ")

    def phonemize(self, word: str) -> list[str]:
        out = []
        for sym in self._arpabet(word):
            ipa, _ = arpabet_to_ipa(sym)
            if ipa and ipa.isalpha() is not False:
                out.append(ipa)
        return [p for p in out if p and not p.isspace()]

    def stress_pattern(self, word: str) -> list[int]:
        idx = []
        for i, sym in enumerate(self._arpabet(word)):
            _, stress = arpabet_to_ipa(sym)
            if stress == 1:
                idx.append(i)
        return idx

    def knows(self, word: str) -> bool:
        return word.lower() in self._g2p.cmu


class FallbackG2P(G2P):
    """G2P por reglas. Degradado a proposito, pero sin dependencias.

    Cubre bien los digrafos que importan para la taxonomia L1-espanol
    (th, sh, ch, ng) y aproxima el resto. No confies en el para feedback
    fino: es una red de seguridad para que la app nunca deje de arrancar.
    """

    name = "fallback-rules"

    _DIGRAPHS = [
        ("tch", "tʃ"), ("sch", "sk"), ("ough", "ʌf"),
        ("th", "θ"), ("sh", "ʃ"), ("ch", "tʃ"), ("ph", "f"),
        ("wh", "w"), ("ng", "ŋ"), ("ck", "k"), ("qu", "kw"),
        ("ee", "i"), ("ea", "i"), ("oo", "u"), ("ou", "aʊ"),
        ("ai", "eɪ"), ("ay", "eɪ"), ("oa", "oʊ"), ("oi", "ɔɪ"),
        ("oy", "ɔɪ"), ("au", "ɔ"), ("aw", "ɔ"),
    ]
    _SINGLES = {
        "a": "æ", "b": "b", "c": "k", "d": "d", "e": "ɛ", "f": "f",
        "g": "ɡ", "h": "h", "i": "ɪ", "j": "dʒ", "k": "k", "l": "l",
        "m": "m", "n": "n", "o": "ɑ", "p": "p", "r": "ɹ", "s": "s",
        "t": "t", "u": "ʌ", "v": "v", "w": "w", "x": "ks", "y": "j",
        "z": "z",
    }

    def phonemize(self, word: str) -> list[str]:
        w = re.sub(r"[^a-z]", "", word.lower())
        if not w:
            return []
        # 'e' final muda: cake -> keɪk, no keɪkɛ
        if len(w) > 2 and w.endswith("e") and w[-2] not in "aeiou":
            w = w[:-1]

        out: list[str] = []
        i = 0
        while i < len(w):
            for gr, ipa in self._DIGRAPHS:
                if w.startswith(gr, i):
                    out.append(ipa)
                    i += len(gr)
                    break
            else:
                out.append(self._SINGLES.get(w[i], w[i]))
                i += 1
        return out


def _ensure_nltk_data() -> None:
    """g2p_en descarga los recursos con sus nombres antiguos.

    nltk >= 3.8.2 renombro el tagger a `averaged_perceptron_tagger_eng`, asi
    que g2p_en baja el paquete viejo y luego falla al buscar el nuevo. Lo
    pedimos explicitamente aqui.
    """
    try:
        import nltk
    except ImportError:
        return

    for resource, path in (
        ("averaged_perceptron_tagger_eng", "taggers/averaged_perceptron_tagger_eng"),
        ("averaged_perceptron_tagger", "taggers/averaged_perceptron_tagger"),
        ("cmudict", "corpora/cmudict"),
    ):
        try:
            nltk.data.find(path)
        except LookupError:
            try:
                nltk.download(resource, quiet=True)
            except Exception as exc:  # noqa: BLE001 - sin red, degradamos
                log.warning("nltk: no se pudo descargar %s (%s)", resource, exc)


@lru_cache(maxsize=1)
def get_g2p() -> G2P:
    try:
        _ensure_nltk_data()
        g2p = CmudictG2P()
        g2p.phonemize("think")  # fuerza la carga de data ahora, no en la primera peticion
        log.info("g2p: usando g2p_en (CMUdict)")
        return g2p
    except Exception as exc:  # noqa: BLE001 - cualquier fallo debe degradar, no tumbar
        log.warning("g2p: g2p_en no disponible (%s). Usando reglas de respaldo.", exc)
        return FallbackG2P()


def phonemize_sentence(text: str) -> list[tuple[str, list[str]]]:
    """[(palabra, [ipa, ...]), ...] conservando el orden del texto."""
    g2p = get_g2p()
    words = re.findall(r"[A-Za-z']+", text)
    return [(w, g2p.phonemize(w)) for w in words]
