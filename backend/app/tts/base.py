"""Sintesis de voz para el modelo de pronunciacion.

No es narracion de libros: es escuchar UNA palabra que acabas de fallar, y
el par minimo que la contrasta. Oir la diferencia es como se aprende a
percibir un contraste que tu idioma no distingue — no sirve de nada que te
digan «pronuncia /θ/» si no puedes oir en que se diferencia de /s/.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class WordMark(BaseModel):
    """Cuándo suena cada palabra dentro del audio.

    `text_offset` y `length` apuntan al texto ORIGINAL, no al audio: así el
    resaltado se hace sobre los mismos caracteres que ya renderiza el lector,
    sin volver a tokenizar ni adivinar correspondencias.
    """

    text_offset: int
    length: int
    audio_ms: int
    duration_ms: int


class TTSHealth(BaseModel):
    name: str
    ready: bool
    detail: str = ""
    marks: bool = False


class TTSProvider(ABC):
    name: str = "base"
    media_type: str = "audio/mpeg"
    extension: str = "mp3"

    @abstractmethod
    def synthesize(self, text: str, *, ipa: str | None = None, slow: bool = False) -> bytes:
        """Devuelve el audio de `text`.

        `ipa` fuerza la pronunciacion exacta en vez de dejar que el motor
        adivine: importa en palabras cuya grafia enganya, y garantiza que el
        alumno oiga justo el fonema que fallo.

        `slow` baja la velocidad sin cambiar el tono, que es lo que permite
        percibir un sonido dentro de un grupo consonantico.
        """

    def synthesize_marked(
        self, text: str, *, ipa: str | None = None, slow: bool = False
    ) -> tuple[bytes, list[WordMark]]:
        """Audio + tiempos por palabra, para el resaltado tipo karaoke.

        La implementacion por defecto devuelve el audio sin marcas: un
        proveedor que no las soporte sigue sirviendo para escuchar, solo que
        sin resaltado. Degradar es mejor que no funcionar.
        """
        return self.synthesize(text, ipa=ipa, slow=slow), []

    @abstractmethod
    def health(self) -> TTSHealth: ...


class TTSNotReady(RuntimeError):
    pass
