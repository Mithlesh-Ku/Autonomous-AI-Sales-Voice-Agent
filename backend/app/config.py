"""Application configuration loaded from environment variables via Pydantic v2."""

from pathlib import Path
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    """Typed runtime settings with zero hardcoded secrets."""

    model_config = SettingsConfigDict(
        env_file=(str(ROOT_DIR / ".env"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # LLM configuration
    llm_provider: Literal["openai", "groq", "gemini", "mock"] = "openai"
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str = ""
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # Voice pipeline configuration
    stt_provider: Literal["deepgram", "browser"] = "browser"
    deepgram_api_key: str = ""

    tts_provider: Literal["openai", "elevenlabs", "browser"] = "browser"
    openai_tts_voice: str = "alloy"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"

    # Vector store & embeddings
    rag_backend: Literal["auto", "chroma", "local"] = "auto"
    chroma_persist_dir: str = str(DATA_DIR / "chroma_db")
    embedding_provider: Literal["openai", "local"] = "local"

    # Database
    database_url: str = f"sqlite:///{(DATA_DIR / 'sales_agent.db').as_posix()}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def resolved_llm_provider(self) -> str:
        """Return active LLM provider, gracefully falling back to mock if key is missing."""
        if self.llm_provider == "openai" and self.openai_api_key.strip():
            return "openai"
        if self.llm_provider == "groq" and self.groq_api_key.strip():
            return "groq"
        if self.llm_provider == "gemini" and self.gemini_api_key.strip():
            return "gemini"
        return "mock"

    def resolved_stt_provider(self) -> str:
        if self.stt_provider == "deepgram" and self.deepgram_api_key.strip():
            return "deepgram"
        return "browser"

    def resolved_tts_provider(self) -> str:
        if self.tts_provider == "openai" and self.openai_api_key.strip():
            return "openai"
        if self.tts_provider == "elevenlabs" and self.elevenlabs_api_key.strip():
            return "elevenlabs"
        return "browser"


settings = Settings()
