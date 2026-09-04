"""Asset schemas for generated media."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AssetType(str):
    """Type of media asset."""
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    SUBTITLE = "subtitle"
    FONT = "font"
    MODEL = "model"


class ImageAsset(BaseModel):
    """Generated or retrieved image asset."""
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str = Field(default="image", pattern="^image$")
    path: Path = Field(description="Absolute path to image file")
    prompt: str = Field(description="Prompt used to generate this image")
    model: str = Field(description="Model used (e.g., hidream-o1)")
    seed: Optional[int] = Field(default=None, description="Random seed for reproducibility")
    width: int = Field(ge=1, description="Width in pixels")
    height: int = Field(ge=1, description="Height in pixels")
    format: str = Field(default="png", pattern="^(png|jpg|jpeg|webp)$")
    file_size_bytes: Optional[int] = Field(default=None, ge=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    content_hash: Optional[str] = Field(default=None, description="SHA256 hash for cache key")


class VideoAsset(BaseModel):
    """Generated or retrieved video asset."""
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str = Field(default="video", pattern="^video$")
    path: Path = Field(description="Absolute path to video file")
    prompt: str = Field(description="Prompt used to generate this video")
    start_frame_prompt: Optional[str] = Field(default=None, description="Start frame description")
    end_frame_prompt: Optional[str] = Field(default=None, description="End frame description")
    model: str = Field(description="Model used (e.g., h3-minimax-start-end-frame)")
    seed: Optional[int] = Field(default=None)
    duration: float = Field(gt=0.0, description="Duration in seconds")
    fps: int = Field(default=30, gt=0)
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    format: str = Field(default="mp4", pattern="^(mp4|webm|mov)$")
    file_size_bytes: Optional[int] = Field(default=None, ge=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    content_hash: Optional[str] = None


class AudioAsset(BaseModel):
    """Generated or retrieved audio asset."""
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str = Field(default="audio", pattern="^audio$")
    path: Path = Field(description="Absolute path to audio file")
    text: str = Field(description="Text that was spoken")
    voice: str = Field(description="TTS voice identifier")
    provider: str = Field(description="TTS provider (piper, edge_tts, modelslab)")
    duration: float = Field(gt=0.0, description="Duration in seconds")
    format: str = Field(default="wav", pattern="^(wav|mp3|ogg)$")
    sample_rate: int = Field(default=22050, gt=0)
    file_size_bytes: Optional[int] = Field(default=None, ge=0)
    word_timestamps: Optional[list[dict[str, float]]] = Field(
        default=None, description="Word-level timestamps [{word, start, end}]"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    content_hash: Optional[str] = None
