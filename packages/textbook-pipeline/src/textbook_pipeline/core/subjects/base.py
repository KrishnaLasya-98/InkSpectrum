"""Abstract base class for subject plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from textbook_pipeline.models.chapter import ChapterNode, SectionNode
from textbook_pipeline.models.script import ScriptScene, SceneStep, SceneStepType


class SubjectPlugin(ABC):
    """Base class for subject-specific behavior."""

    @property
    @abstractmethod
    def subject_id(self) -> str:
        """Return the subject identifier string."""
        raise NotImplementedError

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Return human-readable subject name."""
        raise NotImplementedError

    @abstractmethod
    def allowed_scene_types(self) -> List[str]:
        """Return allowed SceneStepType values for this subject."""
        raise NotImplementedError

    @abstractmethod
    def system_prompt_suffix(self) -> str:
        """Return additional instructions for the LLM system prompt."""
        raise NotImplementedError

    @abstractmethod
    def post_process_scene(self, scene: ScriptScene, section: SectionNode) -> ScriptScene:
        """Apply subject-specific transformations to a scene."""
        raise NotImplementedError

    def extract_key_terms(self, text: str) -> List[str]:
        """Extract subject-specific key terms from text."""
        return []

    def validate_scene_step(self, step: SceneStep) -> bool:
        """Validate that a SceneStep is appropriate for this subject."""
        return step.type in self.allowed_scene_types()
