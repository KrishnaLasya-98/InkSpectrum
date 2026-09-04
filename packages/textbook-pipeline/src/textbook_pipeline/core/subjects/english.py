"""English Language Arts subject plugin."""

from __future__ import annotations

from typing import List

from textbook_pipeline.core.subjects.base import SubjectPlugin
from textbook_pipeline.models.chapter import SectionNode
from textbook_pipeline.models.script import ScriptScene, SceneStep, SceneStepType


class EnglishPlugin(SubjectPlugin):
    """English Language Arts plugin with phonics, vocabulary, and storytelling support."""

    @property
    def subject_id(self) -> str:
        return "english"

    @property
    def display_name(self) -> str:
        return "English Language Arts"

    def allowed_scene_types(self) -> List[str]:
        return [
            SceneStepType.TITLE,
            SceneStepType.SUBTITLE,
            SceneStepType.TEXT,
            SceneStepType.WORD_HIGHLIGHT,
            SceneStepType.SENTENCE_TOKEN,
            SceneStepType.VOCABULARY_CARD,
            SceneStepType.PRONUNCIATION_GUIDE,
            SceneStepType.POEM_CARD,
            SceneStepType.DIALOGUE_BUBBLE,
            SceneStepType.STORYBOARD_FRAME,
            SceneStepType.CLEAR,
        ]

    def system_prompt_suffix(self) -> str:
        return """ENGLISH-SPECIFIC RULES:
- Use WORD_HIGHLIGHT for phonics and spelling patterns
- Use SENTENCE_TOKEN for sentence structure analysis
- Use VOCABULARY_CARD for new words with definition + example sentence
- Use PRONUNCIATION_GUIDE for phonetic breakdowns
- Use POEM_CARD for poetry with stanza breaks
- Use DIALOGUE_BUBBLE for character speech in stories
- Use STORYBOARD_FRAME for narrative scenes"""

    def post_process_scene(self, scene: ScriptScene, section: SectionNode) -> ScriptScene:
        """Enforce English-specific scene constraints."""
        # Ensure vocabulary cards have definitions
        for step in scene.scene_steps:
            if step.type == SceneStepType.VOCABULARY_CARD:
                if not step.content or len(step.content) < 5:
                    step.content = "Vocabulary term"
        return scene

    def extract_key_terms(self, text: str) -> List[str]:
        """Extract English-specific key terms."""
        # Simple heuristic: capitalized words not at sentence start
        import re
        words = text.split()
        key_terms = []
        for i, word in enumerate(words):
            if i > 0 and word[0].isupper() and word.lower() not in ("the", "a", "an"):
                key_terms.append(word.strip('.,!?;:"'))
        return list(set(key_terms))[:10]
