"""Science subject plugin."""

from __future__ import annotations

from typing import List

from textbook_pipeline.core.subjects.base import SubjectPlugin
from textbook_pipeline.models.chapter import SectionNode
from textbook_pipeline.models.script import ScriptScene, SceneStep, SceneStepType


class SciencePlugin(SubjectPlugin):
    """Science plugin with diagram, cycle, and process support."""

    @property
    def subject_id(self) -> str:
        return "science"

    @property
    def display_name(self) -> str:
        return "Science"

    def allowed_scene_types(self) -> List[str]:
        return [
            SceneStepType.TITLE,
            SceneStepType.SUBTITLE,
            SceneStepType.TEXT,
            SceneStepType.LATEX_BLOCK,
            SceneStepType.DIAGRAM,
            SceneStepType.TEXT,
            SceneStepType.CLEAR,
        ]

    def system_prompt_suffix(self) -> str:
        return """SCIENCE-SPECIFIC RULES:
- Use LATEX_BLOCK for chemical formulas and physics equations
- Describe diagrams clearly: label all parts
- Use sequential scenes for processes (photosynthesis, digestion)
- Emphasize observation and hypothesis language"""

    def post_process_scene(self, scene: ScriptScene, section: SectionNode) -> ScriptScene:
        return scene

    def extract_key_terms(self, text: str) -> List[str]:
        science_terms = [
            "cell", "atom", "energy", "force", "gravity", "ecosystem",
            "photosynthesis", "experiment", "hypothesis", "observe",
        ]
        text_lower = text.lower()
        return [term for term in science_terms if term in text_lower]
