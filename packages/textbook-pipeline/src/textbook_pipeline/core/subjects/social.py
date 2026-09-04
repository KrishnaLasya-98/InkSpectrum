"""Social Studies subject plugin."""

from __future__ import annotations

from typing import List

from textbook_pipeline.core.subjects.base import SubjectPlugin
from textbook_pipeline.models.chapter import SectionNode
from textbook_pipeline.models.script import ScriptScene, SceneStep, SceneStepType


class SocialPlugin(SubjectPlugin):
    """Social Studies plugin with timeline, map, and comparison support."""

    @property
    def subject_id(self) -> str:
        return "social"

    @property
    def display_name(self) -> str:
        return "Social Studies"

    def allowed_scene_types(self) -> List[str]:
        return [
            SceneStepType.TITLE,
            SceneStepType.SUBTITLE,
            SceneStepType.TEXT,
            SceneStepType.TIMELINE,
            SceneStepType.MAP_MARKER,
            SceneStepType.CAUSE_EFFECT_CHAIN,
            SceneStepType.COMPARISON_TABLE,
            SceneStepType.GEOGRAPHIC_MAP,
            SceneStepType.HISTORICAL_FIGURE,
            SceneStepType.PRIMARY_SOURCE,
            SceneStepType.CLEAR,
        ]

    def system_prompt_suffix(self) -> str:
        return """SOCIAL STUDIES-SPECIFIC RULES:
- Use TIMELINE for chronological events
- Use MAP_MARKER for geographic locations
- Use CAUSE_EFFECT_CHAIN for historical causality
- Use COMPARISON_TABLE for comparing civilizations/ideas
- Use HISTORICAL_FIGURE for portraits with key facts
- Use PRIMARY_SOURCE for direct quotes with context"""

    def post_process_scene(self, scene: ScriptScene, section: SectionNode) -> ScriptScene:
        return scene

    def extract_key_terms(self, text: str) -> List[str]:
        social_terms = [
            "history", "geography", "civics", "government", "democracy",
            "citizen", "civilization", "culture", "economy", "map",
        ]
        text_lower = text.lower()
        return [term for term in social_terms if term in text_lower]
