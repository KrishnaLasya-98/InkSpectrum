"""Humanities / ELA subject plugin."""

from __future__ import annotations

from typing import List

from textbook_pipeline.core.subjects.base import SubjectPlugin
from textbook_pipeline.models.chapter import SectionNode
from textbook_pipeline.models.script import ScriptScene, SceneStep, SceneStepType


class HumanitiesPlugin(SubjectPlugin):
    """Humanities plugin for stories, poems, and primary sources."""

    @property
    def subject_id(self) -> str:
        return "humanities"

    @property
    def display_name(self) -> str:
        return "Humanities"

    def allowed_scene_types(self) -> List[str]:
        return [
            SceneStepType.TITLE,
            SceneStepType.SUBTITLE,
            SceneStepType.TEXT,
            SceneStepType.WORD_HIGHLIGHT,
            SceneStepType.VOCABULARY_CARD,
            SceneStepType.POEM_CARD,
            SceneStepType.DIALOGUE_BUBBLE,
            SceneStepType.STORYBOARD_FRAME,
            SceneStepType.PRIMARY_SOURCE,
            SceneStepType.CLEAR,
        ]

    def system_prompt_suffix(self) -> str:
        return """HUMANITIES-SPECIFIC RULES:
- Use POEM_CARD for poems with stanza breaks and line emphasis
- Use DIALOGUE_BUBBLE for character conversations
- Use STORYBOARD_FRAME for narrative panels
- Use PRIMARY_SOURCE for historical documents with annotations
- Emphasize themes, character motivations, and literary devices"""

    def post_process_scene(self, scene: ScriptScene, section: SectionNode) -> ScriptScene:
        return scene

    def extract_key_terms(self, text: str) -> List[str]:
        humanities_terms = [
            "theme", "character", "plot", "setting", "motif", "symbol",
            "narrative", "perspective", "cultural", "ethical",
        ]
        text_lower = text.lower()
        return [term for term in humanities_terms if term in text_lower]
