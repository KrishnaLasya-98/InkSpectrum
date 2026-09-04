"""Centralized configuration management using Pydantic Settings."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "textbook-pipeline"
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    # Paths
    project_root: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent.parent
    )
    data_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "data"
    )
    output_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "output"
    )
    cache_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "cache"
    )

    # API Keys
    anyapi_api_key: Optional[str] = Field(default=None, validation_alias="ANYAPI_API_KEY")
    groq_api_key: Optional[str] = Field(default=None, validation_alias="GROQ_API_KEY")
    modelslab_api_key: Optional[str] = Field(default=None, validation_alias="MODELSLAB_API_KEY")
    openrouter_api_key: Optional[str] = Field(default=None, validation_alias="OPENROUTER_API_KEY")

    # LLM Defaults
    default_llm_provider: str = Field(default="groq", validation_alias="DEFAULT_LLM_PROVIDER")
    default_model: str = Field(default="openai/gpt-oss-120b", validation_alias="DEFAULT_MODEL")
    llm_temperature: float = Field(default=0.3, validation_alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=8192, validation_alias="LLM_MAX_TOKENS")

    # Asset Generation
    default_image_model: str = Field(default="hidream-o1", validation_alias="DEFAULT_IMAGE_MODEL")
    default_video_model: str = Field(default="h3-minimax-start-end-frame", validation_alias="DEFAULT_VIDEO_MODEL")
    default_tts_voice: str = Field(default="en_IN-riya-medium", validation_alias="DEFAULT_TTS_VOICE")
    tts_provider: str = Field(default="piper", validation_alias="TTS_PROVIDER")

    # Rendering
    remotion_fps: int = Field(default=30, validation_alias="REMOTION_FPS")
    remotion_width: int = Field(default=1920, validation_alias="REMOTION_WIDTH")
    remotion_height: int = Field(default=1080, validation_alias="REMOTION_HEIGHT")
    manim_timeout: int = Field(default=120, validation_alias="MANIM_TIMEOUT")

    # Pipeline
    max_workers: int = Field(default=4, validation_alias="MAX_WORKERS")
    budget_cap_per_chapter: float = Field(default=5.00, validation_alias="BUDGET_CAP_PER_CHAPTER")
    asset_cache_enabled: bool = Field(default=True, validation_alias="ASSET_CACHE_ENABLED")

    @model_validator(mode="after")
    def validate_dirs(self) -> "Settings":
        """Ensure critical directories exist."""
        for dir_field in ["data_dir", "output_dir", "cache_dir"]:
            path = getattr(self, dir_field)
            path.mkdir(parents=True, exist_ok=True)
        return self


# Singleton settings instance
settings = Settings()


def get_settings() -> Settings:
    """Return the global settings instance."""
    return settings
