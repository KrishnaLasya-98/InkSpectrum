"""Script writer: generates pedagogical scripts from ChapterNode blueprints."""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, ValidationError

from textbook_pipeline.models.chapter import (
    ChapterNode,
    SectionNode,
    SectionType,
)
from textbook_pipeline.models.script import (
    ScriptScene,
    SceneStep,
    SceneStepType,
    VoiceoverLine,
    SceneStepType,
)

load_dotenv()
logger = logging.getLogger(__name__)


# Subject-specific prompts (centralized, validated)
SUBJECT_PROMPTS: Dict[str, Dict[str, Any]] = {
    "english": {
        "teacher_persona": "warm, encouraging primary teacher who makes phonics and reading fun",
        "theory_style": "interactive storytelling with clear pronunciation modeling",
        "exercise_style": "guided practice with positive reinforcement",
        "key_focus": ["phonics sounds", "vocabulary", "comprehension", "speaking"],
    },
    "math": {
        "teacher_persona": "patient, logical math teacher who builds concepts step by step",
        "theory_style": "concrete-to-abstract with visual manipulatives",
        "exercise_style": "worked examples with thinking aloud",
        "key_focus": ["number sense", "operations", "problem solving", "reasoning"],
    },
    "science": {
        "teacher_persona": "curious science guide who encourages observation and questioning",
        "theory_style": "phenomenon-based with real-world connections",
        "exercise_style": "inquiry-based with prediction and explanation",
        "key_focus": ["observation", "experimentation", "vocabulary", "concepts"],
    },
    "social": {
        "teacher_persona": "engaging storyteller who connects past to present",
        "theory_style": "narrative-driven with maps, timelines, and perspectives",
        "exercise_style": "critical thinking with evidence-based answers",
        "key_focus": ["chronology", "geography", "civics", "empathy"],
    },
    "humanities": {
        "teacher_persona": "thoughtful literature guide exploring human experience",
        "theory_style": "theme-based discussion with textual evidence",
        "exercise_style": "interpretive analysis with creative response",
        "key_focus": ["theme", "character", "narrative", "context"],
    },
}


class ScriptWriter:
    """Generates pedagogical scripts from ChapterNode blueprints."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: int = 2,
    ):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found")

        self.model = model or os.environ.get("MODEL_SCRIPTOR_GROQ", "openai/gpt-oss-120b")
        self.max_retries = max_retries

        self.client = ChatOpenAI(
            api_key=self.api_key,
            base_url="https://api.groq.com/openai/v1",
            model=self.model,
            temperature=0.3,
        )
        logger.info(f"ScriptWriter initialized with model: {self.model}")

    @lru_cache(maxsize=8)
    def _get_system_prompt(self, subject: str) -> str:
        """Build system prompt for a subject (cached per subject)."""
        prompts = SUBJECT_PROMPTS.get(subject, SUBJECT_PROMPTS["english"])
        return f"""You are an expert {prompts['teacher_persona']} creating educational video scripts.

SCENE STEP VOCABULARY (constrained primitives - ONLY these types allowed):
- Universal: TITLE, SUBTITLE, TEXT, CLEAR
- English/Humanities: WORD_HIGHLIGHT, SENTENCE_TOKEN, VOCABULARY_CARD, PRONUNCIATION_GUIDE, POEM_CARD, DIALOGUE_BUBBLE, STORYBOARD_FRAME
- Math: LATEX_INLINE, LATEX_BLOCK, POLYGON, CIRCLE, RECTANGLE, TRIANGLE, ANGLE_ARC, AXES_2D, AXES_3D, PLOT_CURVE, NUMBER_LINE, FRACTION_BAR, GRID
- Social Studies: TIMELINE, MAP_MARKER, CAUSE_EFFECT_CHAIN, COMPARISON_TABLE, GEOGRAPHIC_MAP, HISTORICAL_FIGURE, PRIMARY_SOURCE
- Exercises: QUESTION_CARD, WORKED_STEP, ANSWER_REVEAL

OUTPUT FORMAT: Valid JSON array of ScriptScene objects matching the schema.

STYLE: {prompts['theory_style']}
FOCUS: {', '.join(prompts['key_focus'])}

CRITICAL: Use ONLY SceneStepType enum values. NO arbitrary fields. Timing 'at' in seconds."""

    def _build_theory_prompt(self, section: SectionNode, chapter: ChapterNode) -> str:
        prompts = SUBJECT_PROMPTS.get(chapter.subject, SUBJECT_PROMPTS["english"])
        return f"""Generate theory script for this section:

SECTION: {section.title}
TYPE: THEORETICAL
CONTENT: {section.content_text[:3000]}
GRADE: {chapter.grade}
SUBJECT: {chapter.subject}

Create a pedagogical script with:
1. Voiceover lines (text + estimated duration + pause_after)
2. Scene steps using ONLY the constrained vocabulary
3. Timing 'at' in seconds for each step

Style: {prompts['theory_style']}
Focus: {', '.join(prompts['key_focus'])}

Output: JSON array of ScriptScene objects."""

    def _build_exercise_prompt(self, section: SectionNode, chapter: ChapterNode) -> str:
        prompts = SUBJECT_PROMPTS.get(chapter.subject, SUBJECT_PROMPTS["english"])
        exercises_text = "\n".join([
            f"Q: {ex.question_text}" for ex in section.exercises
        ]) if section.exercises else section.content_text[:2000]

        return f"""Generate exercise walkthrough script:

SECTION: {section.title}
TYPE: EXERCISE
EXERCISES: {exercises_text[:3000]}
GRADE: {chapter.grade}
SUBJECT: {chapter.subject}

Create a step-by-step walkthrough:
1. Voiceover reads question clearly
2. WORKED_STEP for each solution step
3. ANSWER_REVEAL for final answer
4. QUESTION_CARD for MCQ

Style: {prompts['exercise_style']}
Focus: {', '.join(prompts['key_focus'])}

Output: JSON array of ScriptScene objects."""

    def _invoke(self, messages: List) -> str:
        """Invoke LLM with retry logic."""
        for attempt in range(self.max_retries):
            try:
                response = self.client.invoke(messages)
                return response.content
            except Exception as e:
                logger.warning(f"LLM call attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    raise
        return ""

    def _parse_script_response(
        self, response: str, section: SectionNode, section_type: str
    ) -> List[ScriptScene]:
        """Parse LLM response into ScriptScene objects with validation."""
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
            if "```" in cleaned:
                cleaned = cleaned.split("```")[0]
            cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                data = [data]
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse failed: {e}")
            raise

        scenes = []
        for item in data:
            try:
                scene = ScriptScene(
                    id=item.get("id", f"scene_{section.id}_{len(scenes)}"),
                    section_id=section.id,
                    section_type=section_type,
                    title=item.get("title", section.title),
                    voiceover_lines=[
                        VoiceoverLine(**vl) for vl in item.get("voiceover_lines", [])
                    ],
                    scene_steps=[
                        SceneStep(**ss) for ss in item.get("scene_steps", [])
                    ],
                    estimated_duration=item.get("estimated_duration", 10.0),
                    render_mode=item.get("render_mode", "remotion"),
                    visual_style=item.get("visual_style", "cinematic"),
                    docling_refs=item.get("docling_refs", []),
                )
                scenes.append(scene)
            except ValidationError as e:
                logger.warning(f"Scene validation failed: {e}")
                continue

        return scenes or [self._fallback_scene(section, section_type)]

    def _fallback_scene(self, section: SectionNode, section_type: str) -> List[ScriptScene]:
        """Create a minimal fallback scene when LLM output is invalid."""
        return [ScriptScene(
            id=f"scene_{section.id}_fallback",
            section_id=section.id,
            section_type=section_type,
            title=section.title,
            voiceover_lines=[VoiceoverLine(
                id="vl_001",
                text=section.content_text[:200] or "Lesson content",
                start_time=0.0,
                end_time=5.0,
            )],
            scene_steps=[SceneStep(
                id="ss_001",
                type=SceneStepType.TEXT,
                at=0.0,
                duration=5.0,
                content=section.content_text[:200] or "Lesson content",
            )],
            estimated_duration=5.0,
        )]

    def generate_chapter_script(self, chapter: ChapterNode) -> List[ScriptScene]:
        """Generate script for all sections in a chapter."""
        all_scenes: List[ScriptScene] = []
        subject = chapter.subject

        for section in chapter.sections:
            if section.type == SectionType.THEORETICAL:
                prompt = self._build_theory_prompt(section, chapter)
            else:
                prompt = self._build_exercise_prompt(section, chapter)

            system_prompt = self._get_system_prompt(subject)

            for attempt in range(self.max_retries):
                try:
                    response = self._invoke([
                        SystemMessage(content=system_prompt),
                        HumanMessage(content=prompt),
                    ])
                    scenes = self._parse_script_response(response, section, section.type)
                    all_scenes.extend(scenes)
                    break
                except Exception as e:
                    logger.error(f"Failed to generate script for section {section.id}: {e}")
                    if attempt == self.max_retries - 1:
                        all_scenes.append(self._fallback_scene(section, section.type))

        return all_scenes
