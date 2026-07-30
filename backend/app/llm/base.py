"""Interfaz de la capa LLM: traduccion y glosas contextuales.

Mismo patron que los motores de pronunciacion: una interfaz, varias
implementaciones. Sin llave de API el lector sigue funcionando (solo en
ingles) en lugar de no arrancar.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class Gloss(BaseModel):
    """Definicion EN CONTEXTO, no la primera acepcion del diccionario.

    Es la diferencia entre traducir «run» en «run a business» como 'correr'
    o como 'dirigir'. Un diccionario se equivoca; un LLM con la oracion
    delante, no.
    """

    lemma: str
    pos: str = ""
    sense_es: str
    note_es: str = ""


class ProviderHealth(BaseModel):
    name: str
    ready: bool
    detail: str = ""


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def translate_paragraphs(self, paragraphs: list[list[str]]) -> list[list[str]]:
        """Traduce EN -> ES conservando la estructura de parrafos.

        La entrada es una lista de parrafos, cada uno con sus oraciones; la
        salida tiene exactamente la misma forma.

        Las dos cosas a la vez, y ninguna es negociable:

        - **Alineacion**: una traduccion por oracion de entrada, en orden.
          Es lo que permite mostrar ambos idiomas emparejados sin recurrir a
          alineadores automaticos.
        - **Contexto**: el modelo ve el parrafo COMPLETO al traducir cada
          oracion. Sin eso la traduccion se vuelve literal — «He took it» no
          se puede traducir bien si no sabes que es «it», y el antecedente
          casi nunca esta en la misma oracion.
        """

    @abstractmethod
    def gloss(self, word: str, sentence: str) -> Gloss:
        """Que significa `word` en esta oracion concreta."""

    @abstractmethod
    def health(self) -> ProviderHealth: ...

    def prewarm(self) -> None:
        """Deja el proveedor listo para la primera consulta interactiva.

        Existe por los modelos locales: la primera palabra que tocas paga la
        carga del modelo desde disco — medido, 8.5 segundos — y esa espera cae
        justo en el momento en que abres un libro y quieres leer. Hacerla al
        arrancar la mueve a un rato en el que nadie esta esperando.

        No hace nada por defecto: un proveedor por API no tiene nada que
        precalentar, y esto no debe obligar a los demas a implementarlo.
        """


class LLMNotReady(RuntimeError):
    pass
