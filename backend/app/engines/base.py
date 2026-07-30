"""Interfaz unica de los motores de pronunciacion.

Nota de arquitectura: Claude NO es la oreja. Un motor convierte audio en
fonemas y scores; Claude consume ese JSON y ensena. Mantener las dos capas
separadas es lo que permite empezar con un motor de pago para validar la UX
y cambiarlo despues por uno local sin tocar nada mas.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.schemas.assessment import AssessmentResult, EngineHealth


class PronunciationEngine(ABC):
    name: str = "base"
    version: str = "0"

    @abstractmethod
    def assess(
        self,
        audio_path: Path,
        expected_text: str,
        *,
        locale: str = "en-US",
    ) -> AssessmentResult:
        """Evalua `audio_path` contra `expected_text`.

        Sincrono a proposito: tanto el SDK de Azure como torch bloquean.
        La API lo invoca en un threadpool.
        """

    @abstractmethod
    def health(self) -> EngineHealth:
        """Puede este motor atender peticiones ahora mismo."""


class EngineNotReady(RuntimeError):
    pass
