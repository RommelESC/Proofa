"""Verifica el mapeo del JSON de Azure al contrato AssessmentResult.

No necesita llave ni red: alimenta `AzureEngine._parse` con un payload con la
forma real que devuelve el servicio. Eso cubre la parte del motor que mas
facil se rompe en silencio — los nombres de campo — y deja para la prueba con
llave solo el viaje de ida y vuelta.

Correr:  ./.venv/Scripts/python.exe -m pytest tests/ -v
"""

from __future__ import annotations

from app.engines.azure import AzureEngine
from app.phonology import detect
from app.schemas.assessment import WordErrorType

# Respuesta de Azure para «I think so» pronunciado «I sink so»:
# la /θ/ falla y NBestPhonemes revela que en su lugar sono /s/.
AZURE_PAYLOAD = {
    "RecognitionStatus": "Success",
    "Offset": 500000,
    "Duration": 21000000,
    "DisplayText": "I think so.",
    "NBest": [
        {
            "Confidence": 0.97,
            "Lexical": "i think so",
            "PronunciationAssessment": {
                "AccuracyScore": 78.0,
                "FluencyScore": 85.0,
                "ProsodyScore": 71.0,
                "CompletenessScore": 100.0,
                "PronScore": 76.0,
            },
            "Words": [
                {
                    "Word": "I",
                    "Offset": 500000,
                    "Duration": 2000000,
                    "PronunciationAssessment": {"AccuracyScore": 96.0, "ErrorType": "None"},
                    "Phonemes": [
                        {
                            "Phoneme": "aɪ",
                            "Offset": 500000,
                            "Duration": 2000000,
                            "PronunciationAssessment": {"AccuracyScore": 96.0},
                        }
                    ],
                },
                {
                    "Word": "think",
                    "Offset": 2500000,
                    "Duration": 5000000,
                    "PronunciationAssessment": {
                        "AccuracyScore": 42.0,
                        "ErrorType": "Mispronunciation",
                    },
                    "Phonemes": [
                        {
                            "Phoneme": "θ",
                            "Offset": 2500000,
                            "Duration": 1200000,
                            "PronunciationAssessment": {
                                "AccuracyScore": 18.0,
                                "NBestPhonemes": [
                                    {"Phoneme": "s", "Score": 91.0},
                                    {"Phoneme": "θ", "Score": 18.0},
                                ],
                            },
                        },
                        {
                            "Phoneme": "ɪ",
                            "Offset": 3700000,
                            "Duration": 1100000,
                            "PronunciationAssessment": {"AccuracyScore": 88.0},
                        },
                        {
                            "Phoneme": "ŋ",
                            "Offset": 4800000,
                            "Duration": 1400000,
                            "PronunciationAssessment": {"AccuracyScore": 90.0},
                        },
                        {
                            "Phoneme": "k",
                            "Offset": 6200000,
                            "Duration": 1300000,
                            "PronunciationAssessment": {"AccuracyScore": 84.0},
                        },
                    ],
                },
                {
                    "Word": "so",
                    "Offset": 7500000,
                    "Duration": 2500000,
                    "PronunciationAssessment": {"AccuracyScore": 93.0, "ErrorType": "None"},
                    "Phonemes": [
                        {
                            "Phoneme": "s",
                            "Offset": 7500000,
                            "Duration": 1200000,
                            "PronunciationAssessment": {"AccuracyScore": 95.0},
                        },
                        {
                            "Phoneme": "oʊ",
                            "Offset": 8700000,
                            "Duration": 1300000,
                            "PronunciationAssessment": {"AccuracyScore": 91.0},
                        },
                    ],
                },
            ],
        }
    ],
}


def _parsed():
    return AzureEngine.__new__(AzureEngine)._parse(AZURE_PAYLOAD, "en-US")


def test_scores_globales():
    r = _parsed()
    assert r.engine == "azure"
    assert r.overall == 76.0  # PronScore, no AccuracyScore
    assert r.prosody.fluency == 85.0
    assert r.prosody.completeness == 100.0
    assert r.prosody.prosody_score == 71.0


def test_palabras_y_tiempos():
    r = _parsed()
    assert [w.surface for w in r.words] == ["I", "think", "so"]

    think = r.words[1]
    assert think.score == 42.0
    assert think.error_type == WordErrorType.MISPRONUNCIATION
    # Offsets en unidades de 100 ns -> milisegundos.
    assert think.start_ms == 250
    assert think.end_ms == 750


def test_nbest_revela_el_fonema_producido():
    """Azure puntua el fonema esperado pero no dice cual se dijo.

    `NBestPhonemes[0]` es la mejor pista disponible: si difiere del esperado
    y el score es bajo, ese es el sonido que realmente se produjo.
    """
    theta = _parsed().words[1].phonemes[0]
    assert theta.expected_ipa == "θ"
    assert theta.produced_ipa == "s"
    assert theta.score == 18.0

    # Un fonema correcto no debe inventar sustitucion.
    assert _parsed().words[1].phonemes[1].produced_ipa == "ɪ"


def test_la_taxonomia_dispara_sobre_datos_de_azure():
    """La deteccion corre sobre el contrato normalizado, no sobre el motor:
    si funciona con Azure sin tocar nada, el desacople es real."""
    r = _parsed()
    hits = detect(r.words)
    codes = {h.code for h in hits}
    assert "TH_TO_S" in codes

    th = next(h for h in hits if h.code == "TH_TO_S")
    assert th.word_index == 1
    assert th.phoneme_index == 0
    assert th.confidence == 0.9  # sustitucion explicita, no inferida
    assert "think" in th.detail


def test_peores_palabras():
    assert [w.surface for w in _parsed().worst_words] == ["think"]


# --- Casos medidos contra el servicio real -----------------------------------
# Capturados evaluando «They breathe through those very thin leather things.»
# con dos voces de Windows: una nativa (en-US) y una espanola (es-ES) leyendo
# el mismo texto en ingles. Son la red de seguridad contra falsos positivos.

_prod = AzureEngine._produced_phoneme


def test_no_inventa_sustitucion_cuando_el_esperado_va_segundo():
    """El caso que casi produce un falso positivo.

    /b/ real en «breathe»: AccuracyScore 60, pero NBest[0] es /ʊ/ con 100 y
    /b/ va segundo con 95. La /b/ SI se pronuncio — ese /ʊ/ es la vocal
    contigua filtrandose. Con la regla vieja («NBest[0] != esperado y score
    < 60») bastaba con que el accuracy cayera un punto para reportar
    «dijiste /ʊ/ donde iba /b/».
    """
    candidates = [
        {"Phoneme": "ʊ", "Score": 100.0},
        {"Phoneme": "b", "Score": 95.0},
        {"Phoneme": "w", "Score": 59.0},
        {"Phoneme": "v", "Score": 53.0},
        {"Phoneme": "ə", "Score": 50.0},
    ]
    assert _prod("b", 60.0, candidates) == "b"
    # Incluso forzando un accuracy bajo: el margen de 5 puntos es un empate
    # tecnico, no una sustitucion.
    assert _prod("b", 30.0, candidates) == "b"


def test_fonema_bien_pronunciado_se_reporta_tal_cual():
    """Voz nativa: el esperado encabeza el ranking y no se toca."""
    assert _prod("ð", 83.0, [
        {"Phoneme": "ð", "Score": 100.0},
        {"Phoneme": "n", "Score": 76.0},
        {"Phoneme": "d", "Score": 26.0},
    ]) == "ð"
    assert _prod("θ", 78.0, [
        {"Phoneme": "θ", "Score": 100.0},
        {"Phoneme": "ə", "Score": 90.0},
        {"Phoneme": "t", "Score": 5.0},
    ]) == "θ"


def test_sustitucion_clara_si_se_reporta():
    """Las tres condiciones se cumplen: accuracy baja, otro candidato arriba,
    margen amplio."""
    assert _prod("θ", 18.0, [
        {"Phoneme": "s", "Score": 91.0},
        {"Phoneme": "θ", "Score": 18.0},
    ]) == "s"


def test_omision_solo_sin_candidatos():
    assert _prod("θ", 12.0, []) is None
    # Con accuracy pesima pero el esperado aun al frente: fallo, no ausencia.
    assert _prod("θ", 12.0, [{"Phoneme": "θ", "Score": 100.0}]) is None
