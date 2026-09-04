"""Scene planner: dual-mode routing and timing."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from textbook_pipeline.models.chapter import ChapterNode, SectionNode, SectionType
from textbook_pipeline.models.script import ScriptScene, SceneStep, SceneStepType

logger = logging.getLogger(__name__)


class ScenePlanner:
    """Plans scenes from sections with dual-mode routing."""

    def __init__(self, wpm: int = 140):
        self.wpm = wpm

    def plan_chapter(self, chapter: ChapterNode) -> List[ScriptScene]:
        """Plan all scenes for a chapter."""
        scenes = []
        for section in chapter.sections:
            section_scenes = self.plan_section(section, chapter)
            scenes.extend(section_scenes)
        return scenes

    def plan_section(
        self,
        section: SectionNode,
        chapter: ChapterNode,
    ) -> List[ScriptScene]:
        """Plan scenes for a single section."""
        if section.type in (SectionType.THEORETICAL, SectionType.INTRODUCTION):
            return self._plan_theory(section, chapter)
        else:
            return self._plan_exercise(section, chapter)

    def _plan_theory(
        self,
        section: SectionNode,
        chapter: ChapterNode,
    ) -> List[ScriptScene]:
        """Plan theory scenes with Remotion or Manim routing."""
        word_count = len(section.content_text.split())
        duration = self._duration_from_words(word_count)

        # Determine render mode
        render_mode = self._determine_render_mode(chapter.subject, section)

        scene = ScriptScene(
            id=f"scene_{section.id}_theory",
            section_id=section.id,
            section_type=section.type,
            title=section.title,
            voiceover_lines=[],  # Filled by ScriptWriter
            scene_steps=[],  # Filled by ScriptWriter
            estimated_duration=duration,
            render_mode=render_mode,
            visual_style="cinematic",
            docling_refs=[ref.item_id for ref in section.docling_refs],
        )

        return [scene]

    def _plan_exercise(
        self,
        section: SectionNode,
        chapter: ChapterNode,
    ) -> List[ScriptScene]:
        """Plan exercise scenes (always Remotion for deterministic UI)."""
        scenes = []

        for idx, exercise in enumerate(section.exercises):
            duration = self._duration_from_words(len(exercise.question_text.split()))
            scene = ScriptScene(
                id=f"scene_{section.id}_ex_{idx+1}",
                section_id=section.id,
                section_type=section.type,
                title=f"Exercise {idx + 1}",
                voiceover_lines=[],
                scene_steps=[],
                estimated_duration=duration + 5.0,  # Extra time for answer reveal
                render_mode="remotion",
                visual_style="minimal",
                docling_refs=[ref.item_id for ref in exercise.docling_refs],
            )
            scenes.append(scene)

        return scenes or [ScriptScene(
            id=f"scene_{section.id}_exercise",
            section_id=section.id,
            section_type=section.type,
            title=section.title,
            voiceover_lines=[],
            scene_steps=[],
            estimated_duration=10.0,
            render_mode="remotion",
            visual_style="minimal",
        )]

    def _determine_render_mode(self, subject: str, section: SectionNode) -> str:
        """Determine render mode based on subject and content."""
        math_science_subjects = {"math", "science"}
        has_math_content = any(
            kw in section.content_text.lower()
            for kw in ["equation", "formula", "solve", "calculate", "latex"]
        )

        if subject in math_science_subjects and has_math_content:
            return "manim"
        return "remotion"

    def _duration_from_words(self, word_count: int) -> float:
        """Calculate duration from word count at target WPM."""
        return max(2.0, (word_count / self.wpm) * 60.0 + 0.5)
