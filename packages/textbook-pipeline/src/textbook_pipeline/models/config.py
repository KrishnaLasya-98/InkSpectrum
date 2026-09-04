"""Subject and pipeline configuration schemas."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Terminology(BaseModel):
    """Subject-specific terminology settings."""
    highlight_keywords: List[str] = Field(default_factory=list)
    glossary_terms: List[str] = Field(default_factory=list)
    symbol_meanings: Dict[str, str] = Field(default_factory=dict)


class SubjectConfig(BaseModel):
    """Per-subject configuration."""
    model_config = ConfigDict(extra="forbid")

    subject: str = Field(description="Subject identifier from Subject values")
    display_name: str = Field(description="Human-readable subject name")
    grade: int = Field(ge=1, le=12, description="Target grade level")
    voice_id: str = Field(description="TTS voice identifier")
    tts_provider: str = Field(default="piper", description="TTS provider: piper, edge_tts, modelslab")
    palette: Dict[str, str] = Field(default_factory=dict, description="Color palette {role: hex}")
    scene_types: List[str] = Field(default_factory=list, description="Allowed SceneStepType values")
    narration_pattern: str = Field(default="standard", description="standard, storytelling, inquiry")
    reading_pace_wpm: int = Field(default=140, gt=0, description="Target words per minute")
    terminology: Terminology = Field(default_factory=Terminology)
    font_family: str = Field(default="Noto Serif", description="Primary font family")
    theme: Dict[str, Any] = Field(default_factory=dict, description="Subject-specific theme config")
    sub_themes: List[str] = Field(default_factory=list, description="Sub-topics or genres")


class PipelineConfig(BaseModel):
    """Global pipeline configuration."""
    model_config = ConfigDict(extra="forbid")

    max_workers: int = Field(default=4, ge=1, le=16)
    budget_cap_per_chapter: float = Field(default=5.00, ge=0.0)
    asset_cache_enabled: bool = Field(default=True)
    cache_dir: Path = Field(default=Path("cache"))
    output_dir: Path = Field(default=Path("output"))
    data_dir: Path = Field(default=Path("data"))
    remotion_fps: int = Field(default=30, gt=0)
    remotion_width: int = Field(default=1920, gt=0)
    remotion_height: int = Field(default=1080, gt=0)
    manim_timeout: int = Field(default=120, gt=0)
    default_image_model: str = Field(default="hidream-o1")
    default_video_model: str = Field(default="h3-minimax-start-end-frame")
    default_tts_voice: str = Field(default="en_IN-riya-medium")
    tts_provider: str = Field(default="piper")
    llm_provider: str = Field(default="groq")
    llm_model: str = Field(default="openai/gpt-oss-120b")
    llm_temperature: float = Field(default=0.3, ge=0.0, le=1.0)
    llm_max_tokens: int = Field(default=8192, gt=0)
    enable_qa: bool = Field(default=True)
    enable_checkpoint: bool = Field(default=True)
    verbose: bool = Field(default=False)
