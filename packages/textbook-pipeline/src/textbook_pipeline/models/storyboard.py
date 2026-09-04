"""Storyboard + audio schemas (rendering layer).

After the script writer produces ScriptScene objects and TTS generates
audio with word-level timestamps, the storyboard builder links scenes
to audio with precise timing. The renderer (Remotion) consumes this.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from .chapter import ChapterNode
from .script import ScriptScene


class WordTimestamp(BaseModel):
    """A single word's timing within a TTS audio segment."""

    word: str
    start_seconds: float
    end_seconds: float


class AudioManifest(BaseModel):
    """Audio output for a single script scene."""

    scene_id: str
    audio_path: Path
    duration_seconds: float
    word_timestamps: list[WordTimestamp] = Field(default_factory=list)
    voice: str                                  # e.g. "en-US-AriaNeural"
    rate: str = "+0%"


class StoryboardScene(BaseModel):
    """A scene with synced audio + visual plan, ready for rendering."""

    id: str
    title: str
    script_scene: ScriptScene
    audio: Optional[AudioManifest] = None      # populated after TTS
    start_time: float = 0.0                     # absolute start in final video
    end_time: float = 0.0                       # absolute end in final video
    chapter_id: Optional[str] = None


class ChapterStoryboard(BaseModel):
    """Complete storyboard for a chapter: ordered scenes + total duration."""

    chapter: ChapterNode
    scenes: list[StoryboardScene]
    total_duration_seconds: float = 0.0
    output_video_path: Optional[Path] = None    # set after render

    def scene_at_time(self, t: float) -> Optional[StoryboardScene]:
        """Find the scene playing at time t (useful for debugging)."""
        for scene in self.scenes:
            if scene.start_time <= t < scene.end_time:
                return scene
        return None