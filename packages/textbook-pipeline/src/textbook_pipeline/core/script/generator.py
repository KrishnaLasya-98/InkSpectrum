"""Script Writer for Textbook Pipeline - Phase 2.

Generates pedagogical scripts from ChapterNode blueprints.
Uses Groq (gpt-oss-120b) - FREE, unlimited daily quota.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from textbook_pipeline.models.chapter import (
    ChapterNode,
    SectionNode,
    SectionType,
    Subject,
)
from textbook_pipeline.models.script import (
    ScriptScene,
    SceneStep,
    SceneStepType,
    VoiceoverLine,
    ExerciseType,
)

load_dotenv()
logger = logging.getLogger(__name__)

SUBJECT_PROMPTS = {
    Subject.ENGLISH: {
        "teacher_persona": "warm, encouraging primary teacher who makes phonics and reading fun",
        "theory_style": "interactive storytelling with clear pronunciation modeling",
        "exercise_style": "guided practice with positive reinforcement",
        "key_focus": ["phonics sounds", "vocabulary", "comprehension", "speaking"],
    },
    Subject.MATH: {
        "teacher_persona": "patient, logical math teacher who builds concepts step by step",
        "theory_style": "concrete-to-abstract with visual manipulatives",
        "exercise_style": "worked examples with thinking aloud",
        "key_focus": ["number sense", "operations", "problem solving", "reasoning"],
    },
    Subject.SCIENCE: {
        "teacher_persona": "curious science guide who encourages observation and questioning",
        "theory_style": "phenomenon-based with real-world connections",
        "exercise_style": "inquiry-based with prediction and explanation",
        "key_focus": ["observation", "experimentation", "vocabulary", "concepts"],
    },
    Subject.SOCIAL: {
        "teacher_persona": "engaging storyteller who connects past to present",
        "theory_style": "narrative-driven with maps, timelines, and perspectives",
        "exercise_style": "critical thinking with evidence-based answers",
        "key_focus": ["chronology", "geography", "civics", "empathy"],
    },
}

class ScriptWriter:
    """Generates pedagogical scripts from ChapterNode blueprints using Groq (FREE)."""

    def __init__(
        self,
        groq_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.groq_key = groq_key or os.getenv("GROQ_API_KEY")
        
        if not self.groq_key:
            raise ValueError("GROQ_API_KEY not found")

        self.model = model or os.getenv("MODEL_SCRIPTOR_GROQ", "openai/gpt-oss-120b")
        
        self.client = ChatOpenAI(
            api_key=self.groq_key,
            base_url="https://api.groq.com/openai/v1",
            model=self.model,
            temperature=0.3,
        )
        logger.info(f"ScriptWriter initialized with Groq model: {self.model}")

    def _invoke(self, messages: List) -> str:
        """Invoke Groq client."""
        response = self.client.invoke(messages)
        return response.content

    def generate_chapter_script(self, chapter: ChapterNode) -> List[ScriptScene]:
        subject_config = SUBJECT_PROMPTS.get(chapter.subject, SUBJECT_PROMPTS[Subject.ENGLISH])
        
        all_scenes = []
        
        for section in chapter.sections:
            if section.type == SectionType.THEORETICAL:
                scenes = self._generate_theory_scenes(section, chapter, SUBJECT_PROMPTS.get(chapter.subject))
            else:
                scenes = self._generate_exercise_scenes(section, chapter, SUBJECT_PROMPTS.get(chapter.subject))
            all_scenes.extend(scenes)

        return all_scenes

    def _generate_theory_scenes(
        self,
        section: SectionNode,
        chapter: ChapterNode,
        subject_config: Dict,
    ) -> List[ScriptScene]:
        prompt = self._build_theory_prompt(section, chapter, SUBJECT_PROMPTS.get(chapter.subject))
        response = self._invoke([
            SystemMessage(content=self._get_system_prompt(SUBJECT_PROMPTS.get(chapter.subject))),
            HumanMessage(content=prompt)
        ])
        return self._parse_script_response(response, section, SectionType.THEORETICAL)

    def _generate_exercise_scenes(
        self,
        section: SectionNode,
        chapter: ChapterNode,
        subject_config: Dict,
    ) -> List[ScriptScene]:
        prompt = self._build_exercise_prompt(section, chapter, SUBJECT_PROMPTS.get(chapter.subject))
        response = self._invoke([
            SystemMessage(content=self._get_system_prompt(SUBJECT_PROMPTS.get(chapter.subject))),
            HumanMessage(content=prompt)
        ])
        return self._parse_script_response(response, section, SectionType.EXERCISE)

    def _get_system_prompt(self, subject_config: Dict) -> str:
        return f"""You are an expert {subject_config['teacher_persona']} creating educational video scripts.

SCENE STEP VOCABULARY (constrained primitives - ONLY these types allowed):
- TITLE, SUBTITLE, TEXT, CLEAR
- WORD_HIGHLIGHT, SENTENCE_TOKEN, VOCABULARY_CARD, PRONUNCIATION_GUIDE
- QUESTION_CARD, WORKED_STEP, ANSWER_REVEAL
- TITLE, SUBTITLE, TEXT, CLEAR (universal)

OUTPUT FORMAT: Valid JSON array of ScriptScene objects matching this schema:
{{
  "id": "sec1_intro",
  "title": "Introduction",
  "voiceover_lines": [
    {{"text": "Welcome to Lesson 1...", "duration_seconds": 5.0, "pause_after": 0.5}}
  ],
  "scene_steps": [
    {{"at": 0, "type": "TITLE", "text": "Lesson 1", "size": "xl", "color": "saffron"}},
    {{"at": 3, "type": "TEXT", "text": "Learning phonics...", "size": "md"}}
  ],
  "duration_seconds": 10.0,
  "section_ref": "sec_1",
  "notes": "Pedagogical notes for QA"
}}

STYLE: {SUBJECT_PROMPTS.get(Subject.ENGLISH, {}).get('theory_style', 'clear and engaging')}
FOCUS: Phonics, vocabulary, comprehension, speaking for Grade 1 English.

CRITICAL: Use ONLY SceneStepType enum values. NO arbitrary fields. Timing 'at' in seconds."""

    def _build_theory_prompt(self, section: SectionNode, chapter: ChapterNode, subject_config: Dict) -> str:
        return f"""Generate theory script for this section:

SECTION: {section.title}
TYPE: THEORETICAL
CONTENT: {section.content_text[:3000]}
GRADE: {chapter.grade}
SUBJECT: {chapter.subject.value}

Create a pedagogical script with:
1. Voiceover lines (text + estimated duration + pause_after)
2. Scene steps using ONLY the constrained vocabulary
3. Timing 'at' in seconds for each step

For Grade 1 English phonics/reading:
- Use TITLE for lesson name
- Use VOCABULARY_CARD for phonics sounds
- Use WORD_HIGHLIGHT for pronunciation
- Use TEXT for explanations
- Use CLEAR between concepts

Output: JSON array of ScriptScene objects."""

    def _build_exercise_prompt(self, section: SectionNode, chapter: ChapterNode, subject_config: Dict) -> str:
        exercises_text = "\n".join([
            f"Q: {ex.question_text}" for ex in section.exercises
        ]) if section.exercises else section.content_text[:2000]

        return f"""Generate exercise walkthrough script:

SECTION: {section.title}
TYPE: EXERCISE
EXERCISES: {exercises_text[:3000]}
GRADE: {chapter.grade}
SUBJECT: {chapter.subject.value}

Create a step-by-step walkthrough:
1. Voiceover reads question clearly
2. WORKED_STEP for each solution step
3. ANSWER_REVEAL for final answer
4. QUESTION_CARD for MCQ

Use encouraging tone. Sync voiceover with visual steps.
Output: JSON array of ScriptScene objects."""

    def _parse_script_response(self, response: str, section: SectionNode, section_type: SectionType) -> List[ScriptScene]:
        try:
            # Strip markdown code fences if present
            cleaned = response.strip()
            if cleaned.startswith("```"):
                # Remove opening fence (```json, ``` etc)
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
                # Find and remove closing fence
                if "```" in cleaned:
                    cleaned = cleaned.split("```")[0]
                cleaned = cleaned.strip()
            
            data = json.loads(cleaned)
            if isinstance(data, dict):
                data = [data]
            
            scenes = []
            for i, scene_data in enumerate(data):
                voiceover_lines = []
                for vol in scene_data.get("voiceover_lines", []):
                    voiceover_lines.append(VoiceoverLine(
                        text=vol.get("text", ""),
                        duration_seconds=vol.get("duration_seconds", 3.0),
                        pause_after=vol.get("pause_after", 0.5)
                    ))
                
                scene_steps = []
                for step_data in scene_data.get("scene_steps", []):
                    step_type_str = step_data.get("type", "TEXT")
                    try:
                        step_type = SceneStepType(step_type_str)
                    except ValueError:
                        step_type = SceneStepType.TEXT
                    
                    scene_steps.append(SceneStep(
                        at=step_data.get("at", 0),
                        duration=step_data.get("duration"),
                        type=step_type,
                        text=step_data.get("text"),
                        latex=step_data.get("latex"),
                        x=step_data.get("x"),
                        y=step_data.get("y"),
                        size=step_data.get("size"),
                        color=step_data.get("color"),
                        highlight=step_data.get("highlight"),
                        extra=step_data.get("extra"),
                    ))
                
                scene = ScriptScene(
                    id=scene_data.get("id", f"{section.id}_scene_{i+1}"),
                    title=scene_data.get("title", f"{section.title} Scene {i+1}"),
                    voiceover_lines=voiceover_lines,
                    scene_steps=scene_steps,
                    duration_seconds=scene_data.get("duration_seconds", 10.0),
                    section_ref=section.id,
                    notes=scene_data.get("notes", ""),
                )
                scenes.append(scene)
            return scenes
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse script response: {e}")
            return [self._fallback_scene(section, section_type)]

    def _fallback_scene(self, section: SectionNode, section_type: SectionType) -> ScriptScene:
        return ScriptScene(
            id=f"{section.id}_fallback",
            title=f"{section.title} (Fallback)",
            voiceover_lines=[VoiceoverLine(text=f"Content for {section.title}", duration_seconds=5.0)],
            scene_steps=[SceneStep(at=0, type=SceneStepType.TEXT, text=f"Content for {section.title}", size="md")],
            duration_seconds=5.0,
            section_ref=section.id,
            notes="Fallback due to generation error",
        )


def generate_chapter_script(chapter: ChapterNode) -> List[ScriptScene]:
    """Convenience function for pipeline."""
    writer = ScriptWriter()
    return writer.generate_chapter_script(chapter)

