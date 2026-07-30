"""Sintesis con voz neuronal de Azure.

Usa la MISMA llave que la evaluacion de pronunciacion — no hace falta otro
recurso. El tier F0 incluye 0.5 M de caracteres al mes de voz neuronal, y
una palabra son ~6 caracteres: para este uso es efectivamente ilimitado.

Lo que aporta sobre el TTS del navegador es SSML con `<phoneme>`: se puede
forzar la pronunciacion exacta en IPA en vez de esperar que el motor acierte
al leer la grafia. Para ensenar un fonema concreto, eso no es un lujo.
"""

from __future__ import annotations

import logging
from xml.sax.saxutils import escape

from app.config import get_settings
from app.tts.base import TTSHealth, TTSNotReady, TTSProvider, WordMark

log = logging.getLogger(__name__)

SLOW_RATE = "-45%"
TICKS_PER_MS = 10_000  # Azure reporta offsets en unidades de 100 ns


class AzureTTS(TTSProvider):
    name = "azure"
    media_type = "audio/mpeg"
    extension = "mp3"

    def __init__(self) -> None:
        settings = get_settings()
        self._key = settings.azure_speech_key
        self._region = settings.azure_speech_region
        self._voice = settings.azure_tts_voice

    def _sdk(self):
        try:
            import azure.cognitiveservices.speech as speechsdk
        except ImportError as exc:
            raise TTSNotReady(
                "Falta el SDK. Instala: pip install -r requirements-azure.txt"
            ) from exc
        if not self._key:
            raise TTSNotReady("AZURE_SPEECH_KEY vacia en .env")
        return speechsdk

    def _ssml(self, text: str, ipa: str | None, slow: bool) -> str:
        body = escape(text)
        if ipa:
            body = f'<phoneme alphabet="ipa" ph="{escape(ipa)}">{body}</phoneme>'
        if slow:
            body = f'<prosody rate="{SLOW_RATE}">{body}</prosody>'
        return (
            '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
            'xml:lang="en-US">'
            f'<voice name="{self._voice}">{body}</voice>'
            "</speak>"
        )

    def synthesize(self, text: str, *, ipa: str | None = None, slow: bool = False) -> bytes:
        return self.synthesize_marked(text, ipa=ipa, slow=slow)[0]

    def synthesize_marked(
        self, text: str, *, ipa: str | None = None, slow: bool = False
    ) -> tuple[bytes, list[WordMark]]:
        speechsdk = self._sdk()

        config = speechsdk.SpeechConfig(subscription=self._key, region=self._region)
        config.speech_synthesis_voice_name = self._voice
        config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio24Khz96KBitRateMonoMp3
        )

        # audio_config=None es obligatorio: el valor por defecto reproduce el
        # audio por las bocinas de la MAQUINA DEL SERVIDOR en vez de
        # devolverlo. Con None, el resultado llega en `audio_data`.
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)

        # Los tiempos por palabra los emite el propio motor mientras sintetiza,
        # asi que el resaltado va pegado al audio real. Estimarlos en el
        # navegador se desincroniza en cuanto hay una pausa o un numero leido
        # en voz.
        marks: list[WordMark] = []

        def on_boundary(evt) -> None:  # noqa: ANN001
            if evt.boundary_type != speechsdk.SpeechSynthesisBoundaryType.Word:
                return
            marks.append(
                WordMark(
                    text_offset=evt.text_offset,
                    length=evt.word_length,
                    audio_ms=evt.audio_offset // TICKS_PER_MS,
                    duration_ms=int(evt.duration.total_seconds() * 1000)
                    if hasattr(evt.duration, "total_seconds")
                    else int(evt.duration) // TICKS_PER_MS,
                )
            )

        synthesizer.synthesis_word_boundary.connect(on_boundary)
        result = synthesizer.speak_ssml_async(self._ssml(text, ipa, slow)).get()

        if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
            details = getattr(result, "cancellation_details", None)
            raise TTSNotReady(
                f"Azure no sintetizo el audio: {result.reason}"
                + (f" — {details.error_details}" if details else "")
            )

        # Los offsets de SSML incluyen las etiquetas; el lector solo tiene el
        # texto plano. Se corrigen restando el desplazamiento del cuerpo.
        shift = self._ssml(text, ipa, slow).find(escape(text))
        if shift > 0:
            marks = [m.model_copy(update={"text_offset": max(0, m.text_offset - shift)}) for m in marks]

        return bytes(result.audio_data), marks

    def health(self) -> TTSHealth:
        try:
            self._sdk()
        except TTSNotReady as exc:
            return TTSHealth(name=self.name, ready=False, detail=str(exc))
        return TTSHealth(name=self.name, ready=True, detail=f"voz={self._voice}")
