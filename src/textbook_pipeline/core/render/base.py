"""Abstract base for renderers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from textbook_pipeline.models.script import ScriptScene


class RendererProtocol(ABC):
    """Protocol for scene renderers."""

    @abstractmethod
    def render_scene(self, scene: ScriptScene, output_dir: Path) -> Path:
        """Render a single scene to video."""
        raise NotImplementedError

    @abstractmethod
    def render_chapter(self, scenes: List[ScriptScene], output_dir: Path) -> List[Path]:
        """Render all scenes in a chapter."""
        raise NotImplementedError
