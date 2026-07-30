from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://ingles:ingles@localhost:5431/ingles"

    pronunciation_engine: str = "mock"
    azure_speech_key: str = ""
    azure_speech_region: str = "eastus"
    local_w2v2_model: str = "facebook/wav2vec2-lv-60-espeak-cv-ft"

    # Sintesis de voz: escuchar como deberia sonar una palabra fallada.
    # Usa la misma llave que la evaluacion — no hace falta otro recurso.
    tts_provider: str = "azure"
    azure_tts_voice: str = "en-US-JennyNeural"

    # Capa LLM: traduccion paralela ES/EN y glosas en contexto.
    llm_provider: str = "none"
    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-5"
    translation_batch_size: int = 25

    # Modelos locales via Ollama: sin llaves, sin costo, sin que el texto salga
    # de la maquina.
    ollama_base_url: str = "http://localhost:11434"
    # Modelo para traduccion masiva: corre desatendido, asi que puede ser
    # grande y lento a cambio de mejor interpretacion.
    ollama_model: str = ""
    # Modelo para glosas: es interactivo — tocas una palabra y esperas — asi
    # que aqui manda la latencia. Vacio = usar el mismo de arriba.
    ollama_gloss_model: str = ""
    # Ollama usa 4096 por defecto y recorta en silencio lo que no cabe.
    ollama_num_ctx: int = 8192
    # None = no mandar el parametro. NO lo pongas en false para traduccion:
    # medido contra Ollama 0.30.7 con qwen3.6, mandar `think: false` ANULA la
    # restriccion de esquema JSON y el modelo responde prosa libre. Ahorrar
    # tokens de razonamiento no vale romper la alineacion bilingue.
    ollama_think: bool | None = None
    # Las glosas son otra cosa, y esto SI esta medido con el modelo de glosas
    # (qwen3:8b): razonando tarda entre 5 y 14 segundos y produce 1500-2100
    # caracteres de pensamiento para definir una palabra; con `think: false`
    # tarda 0.8s, el JSON sigue siendo valido y la definicion es igual de
    # buena — en algunos casos mejor. Tocas una palabra y esperas mirando, asi
    # que aqui la latencia es la funcion.
    #
    # Si tu modelo de glosas se comporta como qwen3.6 y rompe el esquema, hay
    # reintento automatico sin el parametro; ponlo en None para desactivarlo.
    ollama_gloss_think: bool | None = False
    # Ollama descarga el modelo tras 5 minutos de inactividad, y volver a
    # cargarlo costaba 3.6s en la siguiente palabra que tocaras. Mantenerlo en
    # memoria es lo que hace que la primera consulta no se sienta distinta.
    ollama_keep_alive: str = "30m"

    assets_dir: Path = REPO_ROOT / "data" / "assets"
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def resolve_paths(self) -> None:
        """Ancla las rutas relativas a la raiz del repo, no al CWD.

        `ASSETS_DIR=./data/assets` se resolvia contra el directorio desde el
        que arrancabas uvicorn: lanzarlo desde backend/ mandaba las
        grabaciones a backend/data/assets/. Con dos formas de arrancar el
        servidor, el historial de audio terminaba partido en dos carpetas.
        """
        if not self.assets_dir.is_absolute():
            self.assets_dir = (REPO_ROOT / self.assets_dir).resolve()

    def ensure_dirs(self) -> None:
        self.resolve_paths()
        self.assets_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
