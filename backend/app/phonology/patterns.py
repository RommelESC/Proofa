"""Taxonomia de errores de pronunciacion tipicos de un hispanohablante.

Esta es la capa que diferencia el proyecto. Un motor generico dice
"esta palabra: 42/100". Esto dice "convertiste /θ/ en /s/, es tu error #1
de la semana, y aqui tienes pares minimos para practicarlo".

Diseno deliberado: los detectores son DERIVADOS, no fuente de verdad.
Se ejecutan sobre `phoneme_scores`, que a su vez se derivan del `raw` del
motor. Si manana afinas una regla, recalculas `pattern_hits` sobre todo tu
historial sin volver a grabar nada.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from app.schemas.assessment import PatternHit, PhonemeScore, WordScore

# Umbral bajo el cual un fonema cuenta como fallado. Deliberadamente
# permisivo: un falso positivo destruye la confianza del alumno mucho mas
# rapido de lo que un falso negativo retrasa su avance.
PHONEME_FAIL = 55.0

FULL_VOWELS = set("aeiouɑæɔɛɪʊ")
CONSONANTS = set("bdfɡhjklmnŋpɹstvwzðθʃʒ")


@dataclass(frozen=True)
class ErrorPattern:
    code: str
    label_es: str
    explanation_es: str
    minimal_pairs: tuple[str, ...] = ()
    detector: Callable[[WordScore], list[PatternHit]] = field(repr=False, default=lambda w: [])


def _pairs(word: WordScore) -> list[tuple[int, PhonemeScore]]:
    return list(enumerate(word.phonemes))


def _substitution(word: WordScore, expected: str, produced: set[str]) -> list[PatternHit]:
    """Detecta que /expected/ fallo, con o sin saber por que se sustituyo.

    Medido contra Azure: el motor identifica de forma fiable QUE un fonema
    salio mal, pero rara vez CON QUE lo cambiaste. En una lectura donde se
    dijo «sink» por «think» a proposito, la /θ/ cayo de 100 a 60 y aun asi
    vino reportada como /θ/.

    Por eso hay dos niveles de confianza. Exigir la sustitucion explicita
    dejaba mudos a la mitad de los detectores; afirmarla sin evidencia seria
    inventar. Decir «tu /θ/ salio mal» con confianza media es lo que de
    verdad se sabe.
    """
    hits = []
    for i, ph in _pairs(word):
        if ph.expected_ipa != expected:
            continue

        got = (ph.produced_ipa or "").strip()
        if got in produced:
            confidence, detail = 0.9, f"/{expected}/ -> /{got}/ en «{word.surface}»"
        elif not got:
            confidence, detail = 0.5, f"/{expected}/ no se articulo en «{word.surface}»"
        elif ph.score < PHONEME_FAIL:
            confidence, detail = 0.55, f"/{expected}/ impreciso en «{word.surface}» ({ph.score:.0f}/100)"
        else:
            continue

        hits.append(
            PatternHit(
                code="",  # lo rellena `detect`
                word_index=word.index,
                phoneme_index=i,
                confidence=confidence,
                detail=detail,
            )
        )
    return hits


def _detect_th_to_s(w: WordScore) -> list[PatternHit]:
    return _substitution(w, "θ", {"s", "t", "f"})


def _detect_dh_to_d(w: WordScore) -> list[PatternHit]:
    return _substitution(w, "ð", {"d", "z", "t"})


def _detect_b_v_merge(w: WordScore) -> list[PatternHit]:
    return _substitution(w, "v", {"b", "β"})


def _detect_z_to_s(w: WordScore) -> list[PatternHit]:
    return _substitution(w, "z", {"s"})


def _detect_y_to_jh(w: WordScore) -> list[PatternHit]:
    return _substitution(w, "j", {"dʒ", "ʒ"})


def _detect_ng_to_n(w: WordScore) -> list[PatternHit]:
    return _substitution(w, "ŋ", {"n", "nɡ"})


def _detect_vowel_iy_ih(w: WordScore) -> list[PatternHit]:
    """ship/sheep. El espanol tiene una sola /i/, asi que el contraste
    largo/corto simplemente no se percibe hasta que se entrena."""
    hits = []
    for i, ph in _pairs(w):
        exp, got = ph.expected_ipa, (ph.produced_ipa or "")
        if {exp, got} == {"i", "ɪ"}:
            hits.append(PatternHit(code="", word_index=w.index, phoneme_index=i,
                                   confidence=0.9, detail=f"/{exp}/ -> /{got}/ en «{w.surface}»"))
        elif exp in {"i", "ɪ"} and not got and ph.score < PHONEME_FAIL:
            hits.append(PatternHit(code="", word_index=w.index, phoneme_index=i,
                                   confidence=0.4, detail=f"vocal /{exp}/ imprecisa en «{w.surface}»"))
    return hits


def _detect_schwa_full(w: WordScore) -> list[PatternHit]:
    """No reducir la schwa. Es el error que mas afecta al ritmo global
    aunque cada sonido aislado sea correcto."""
    hits = []
    for i, ph in _pairs(w):
        if ph.expected_ipa not in {"ə", "ɚ"}:
            continue
        got = (ph.produced_ipa or "")
        if got and got in FULL_VOWELS:
            hits.append(PatternHit(code="", word_index=w.index, phoneme_index=i,
                                   confidence=0.85,
                                   detail=f"schwa sin reducir: /ə/ -> /{got}/ en «{w.surface}»"))
    return hits


_S_CLUSTER = re.compile(r"^s[ptkbdgmnflw]", re.IGNORECASE)


def _detect_epenthetic_e(w: WordScore) -> list[PatternHit]:
    """'espeak' por 'speak'. El espanol no admite grupos s+consonante en
    inicio de palabra, asi que se inserta una /e/ de apoyo."""
    if not _S_CLUSTER.match(w.surface):
        return []
    if not w.phonemes:
        return []

    first = w.phonemes[0]
    got = (first.produced_ipa or "")
    if first.expected_ipa == "s" and got in {"e", "ɛ", "ə"}:
        return [PatternHit(code="", word_index=w.index, phoneme_index=0, confidence=0.95,
                           detail=f"/e/ insertada antes de /s/ en «{w.surface}»")]
    if first.expected_ipa == "s" and first.score < PHONEME_FAIL:
        return [PatternHit(code="", word_index=w.index, phoneme_index=0, confidence=0.45,
                           detail=f"arranque de «{w.surface}» inestable (posible /e/ de apoyo)")]
    return []


def _detect_ed_ending(w: WordScore) -> list[PatternHit]:
    """-ed suena /t/, /d/ o /ɪd/ segun el sonido anterior. Casi nadie lo
    aprende explicitamente y se nota en cada verbo en pasado."""
    if not w.surface.lower().endswith("ed") or len(w.surface) < 4:
        return []
    if not w.phonemes:
        return []
    last = w.phonemes[-1]
    if last.expected_ipa in {"t", "d"} and last.score < PHONEME_FAIL:
        return [PatternHit(code="", word_index=w.index, phoneme_index=len(w.phonemes) - 1,
                           confidence=0.8,
                           detail=f"terminacion -ed: esperado /{last.expected_ipa}/ en «{w.surface}»")]
    return []


def _detect_final_cluster(w: WordScore) -> list[PatternHit]:
    """'asked', 'texts', 'worlds'. El espanol casi no tiene grupos
    consonanticos finales, asi que se simplifican.

    Un grupo exige consonantes ADYACENTES. Contar simplemente cuantas
    consonantes hay en la cola marcaba «spanish» (/s p æ n ɪ ʃ/) como grupo
    final, cuando su /n/ y su /ʃ/ estan separadas por una vocal. El
    diagnostico salia con nombre y explicacion equivocados.
    """
    if len(w.phonemes) < 3:
        return []

    # Consonantes finales consecutivas, de atras hacia adelante.
    cluster: list[PhonemeScore] = []
    for ph in reversed(w.phonemes):
        if ph.expected_ipa not in CONSONANTS:
            break
        cluster.append(ph)
    if len(cluster) < 2:
        return []

    dropped = [p for p in reversed(cluster) if not p.produced_ipa or p.score < PHONEME_FAIL]
    if not dropped:
        return []

    return [PatternHit(code="", word_index=w.index, phoneme_index=dropped[0].index,
                       confidence=0.7,
                       detail=f"grupo consonantico final simplificado en «{w.surface}»")]


def _detect_sh_to_ch(w: WordScore) -> list[PatternHit]:
    return _substitution(w, "ʃ", {"tʃ", "s"})


def _detect_word_stress(w: WordScore) -> list[PatternHit]:
    if w.stress_ok is False:
        return [PatternHit(code="", word_index=w.index, confidence=0.8,
                           detail=f"acento de palabra desplazado en «{w.surface}»")]
    return []


PATTERNS: tuple[ErrorPattern, ...] = (
    ErrorPattern("TH_TO_S", "/θ/ se vuelve /s/",
                 "La 'th' sorda no existe en español y se sustituye por /s/, /t/ o /f/. "
                 "Saca la punta de la lengua entre los dientes y sopla.",
                 ("think / sink", "thin / sin", "bath / bass", "three / free"),
                 _detect_th_to_s),
    ErrorPattern("DH_TO_D", "/ð/ se vuelve /d/",
                 "La 'th' sonora es como la 'd' de 'nada', no como la 'd' de 'donde'. "
                 "Es más suave y con la lengua más adelante.",
                 ("they / day", "then / den", "breathe / breed"),
                 _detect_dh_to_d),
    ErrorPattern("EPENTHETIC_E", "/e/ de apoyo antes de s-",
                 "En español no hay palabras que empiecen con s+consonante, así que se "
                 "agrega una /e/. Arranca directo con la /s/, sin vocal previa.",
                 ("speak (no 'espeak')", "school", "student", "stop"),
                 _detect_epenthetic_e),
    ErrorPattern("VOWEL_IY_IH", "/i/ vs /ɪ/",
                 "El español tiene una sola /i/. En inglés son dos vocales distintas: "
                 "/i/ es larga y tensa, /ɪ/ es corta y relajada.",
                 ("sheep / ship", "beach / bitch", "leave / live", "feel / fill"),
                 _detect_vowel_iy_ih),
    ErrorPattern("SCHWA_FULL", "Schwa sin reducir",
                 "El inglés reduce las sílabas átonas a /ə/. Pronunciar todas las vocales "
                 "completas es lo que produce el ritmo 'silabeado'.",
                 ("about", "banana", "computer", "problem"),
                 _detect_schwa_full),
    ErrorPattern("B_V_MERGE", "/v/ se vuelve /b/",
                 "En español 'b' y 'v' suenan igual. En inglés /v/ se hace con los "
                 "dientes superiores sobre el labio inferior, vibrando.",
                 ("very / berry", "vote / boat", "vest / best"),
                 _detect_b_v_merge),
    ErrorPattern("Z_TO_S", "/z/ se vuelve /s/",
                 "El español no tiene /z/. Es una /s/ con vibración de las cuerdas vocales. "
                 "Afecta casi todos los plurales.",
                 ("zoo / sue", "buzz / bus", "prize / price"),
                 _detect_z_to_s),
    ErrorPattern("ED_ENDING", "Terminación -ed",
                 "Suena /t/ tras sonido sordo (worked), /d/ tras sonoro (played) y "
                 "/ɪd/ solo tras /t/ o /d/ (wanted). Nunca es una sílaba extra.",
                 ("worked", "played", "wanted", "asked"),
                 _detect_ed_ending),
    ErrorPattern("FINAL_CLUSTER", "Grupo consonántico final",
                 "El español simplifica los grupos finales. En inglés hay que producir "
                 "todas las consonantes, aunque sea rápido.",
                 ("asked", "texts", "worlds", "months"),
                 _detect_final_cluster),
    ErrorPattern("Y_TO_JH", "/j/ se vuelve /dʒ/",
                 "El yeísmo rioplatense y de varias zonas convierte 'y' en /dʒ/. "
                 "En inglés 'yellow' arranca suave, como 'hielo'.",
                 ("yellow / jello", "year / jeer", "yet / jet"),
                 _detect_y_to_jh),
    ErrorPattern("SH_TO_CH", "/ʃ/ se vuelve /tʃ/ o /s/",
                 "El español no tiene /ʃ/ (salvo en algunas variantes), así que se "
                 "sustituye por la 'ch'. Es un sonido continuo: el aire fluye sin "
                 "el golpe inicial de /tʃ/.",
                 ("she / chee", "ship / chip", "wash / watch", "shoe / chew"),
                 _detect_sh_to_ch),
    ErrorPattern("NG_TO_N", "/ŋ/ se vuelve /n/ o /nɡ/",
                 "La 'ng' final es un solo sonido nasal, sin /ɡ/ audible al final.",
                 ("sing", "running", "thing", "long"),
                 _detect_ng_to_n),
    ErrorPattern("WORD_STRESS", "Acento de palabra",
                 "Aplicar las reglas de acentuación del español a palabras inglesas cambia "
                 "la sílaba tónica y dificulta mucho la comprensión.",
                 ("PHOtograph / phoTOgrapher", "REcord / reCORD"),
                 _detect_word_stress),
)

PATTERNS_BY_CODE: dict[str, ErrorPattern] = {p.code: p for p in PATTERNS}


def detect(words: list[WordScore]) -> list[PatternHit]:
    """Corre toda la taxonomia sobre las palabras evaluadas."""
    out: list[PatternHit] = []
    for pattern in PATTERNS:
        for word in words:
            for hit in pattern.detector(word):
                out.append(hit.model_copy(update={"code": pattern.code}))
    return out
