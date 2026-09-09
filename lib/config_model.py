"""Global Pydantic config model. Single source of truth for runtime settings.

All other modules read from `load_config()` rather than touching the env directly.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from lib.env_loader import load_env


# ───────────────────────────────────────────────────────────────────
# Sub-models
# ───────────────────────────────────────────────────────────────────

class LLMConfig(BaseModel):
    provider: str = "anyapi"
    base_url: str = "https://api.anyapi.ai/v1"
    model: str = "qwen3.8-27b"
    temperature: float = 0.3
    max_tokens: int = 8192
    max_retries: int = 3
    api_key_env: str = "ANYAPI_API_KEY"


class BudgetConfig(BaseModel):
    default_per_pipeline_usd: float = 2.00
    per_stage_cap_usd: float = 0.50
    per_call_reserve_usd: float = 0.05
    enforce_hard_cap: bool = True


class CheckpointConfig(BaseModel):
    root: Path = Path(".kilo/checkpoints")
    keep_history: int = 5
    auto_resume: bool = True


class OutputConfig(BaseModel):
    artifacts_root: Path = Path(".kilo/artifacts")
    video_root: Path = Path(".kilo/output/videos")
    audio_root: Path = Path(".kilo/output/audio")
    image_root: Path = Path(".kilo/output/images")


class ModelsLabConfig(BaseModel):
    base_url: str = "https://modelslab.com/api/v7"
    api_key_env: str = "MODELSLAB_API_KEY"
    image_model: str = "hidream-o1"
    tts_model: str = "text-to-speech"
    video_model_i2v: str = "h3-minimax-start-end-frame"
    video_model_r2v: str = "h3-minimax-r2v"


# ───────────────────────────────────────────────────────────────────
# Top-level config
# ───────────────────────────────────────────────────────────────────

class InkSpectrumConfig(BaseModel):
    """Global runtime config. Loaded once at process start."""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    checkpoint: CheckpointConfig = Field(default_factory=CheckpointConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    modelslab: ModelsLabConfig = Field(default_factory=ModelsLabConfig)
    project_root: Path = Path(".")

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "InkSpectrumConfig":
        """Load config from YAML if it exists, otherwise return defaults.

        Also loads `.env` so child processes and tools can pick up secrets.
        """
        load_env()
        if config_path is None:
            config_path = Path("config.yaml")
        if config_path.exists():
            import yaml
            data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            return cls.model_validate(data)
        return cls()


def get_api_key(env_var: str) -> Optional[str]:
    """Read an API key from the environment. Returns None if not set."""
    return os.environ.get(env_var)
