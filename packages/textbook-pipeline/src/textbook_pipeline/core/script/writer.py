"""Script writer: generates pedagogical scripts from ChapterNode blueprints.

Uses the OpenAI-compatible SDK so it works with Groq, AnyAPI, or any
OpenAI-compatible provider configured in lib.config_model.InkSpectrumConfig.
"""

from __future__ import annotations

import json
import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI
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
)

logger = logging.getLogger(__name__)


def _sanitize_text(text: str) -> str:
    """Remove markdown artifacts from text for clean narration/scene steps."""
    if not text:
        return ""
    # Remove markdown images: ![](url) or ![](<url>) or ![]<url>
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'!\[\]\(.*?\)', '', text)
    text = re.sub(r'!\[\]<.*?>', '', text)
    # Remove markdown links: [text](url) → keep text
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


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
    """Generates pedagogical scripts from ChapterNode blueprints.

    Uses InkSpectrumConfig (lib.config_model) for provider settings, so it
    works with Groq, AnyAPI, or any OpenAI-compatible backend.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        max_retries: int = 2,
    ):
        # Load config from config.yaml via InkSpectrumConfig
        try:
            from lib.config_model import InkSpectrumConfig
            self.cfg = InkSpectrumConfig.load()
            llm = self.cfg.llm
        except Exception as exc:
            logger.warning("Could not load InkSpectrumConfig (%s); using defaults", exc)
            from lib.config_model import LLMConfig
            llm = LLMConfig()

        self.api_key = api_key or os.environ.get(llm.api_key_env, "")
        if not self.api_key:
            raise ValueError(f"{llm.api_key_env} not found in environment")

        self.model = model or os.environ.get("MODEL_SCRIPTOR", llm.model)
        self.base_url = base_url or llm.base_url
        self.max_retries = max_retries if max_retries != 2 else llm.max_retries
        self.temperature = llm.temperature
        self.max_completion_tokens = llm.max_tokens

        logger.info("ScriptWriter: provider=%s model=%s base_url=%s", llm.provider, self.model, self.base_url)
        logger.info("API key loaded: %s (prefix: %s...)", bool(self.api_key), self.api_key[:12])

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    @lru_cache(maxsize=8)
    def _get_system_prompt(self, subject: str) -> str:
        """Build system prompt for a subject (cached per subject)."""
        prompts = SUBJECT_PROMPTS.get(subject, SUBJECT_PROMPTS["english"])
        return f"""You are an expert {prompts['teacher_persona']} creating educational video scripts.

SCENE STEP VOCABULARY (constrained primitives - ONLY these types allowed):
- Universal: title, subtitle, text, clear
- English/Humanities: word_highlight, sentence_token, vocabulary_card, pronunciation_guide, poem_card, dialogue_bubble, storyboard_frame
- Math: latex_inline, latex_block, polygon, circle, rectangle, triangle, angle_arc, axes_2d, axes_3d, plot_curve, number_line, fraction_bar, grid
- Social Studies: timeline, map_marker, cause_effect_chain, comparison_table, geographic_map, historical_figure, primary_source
- Exercises: question_card, worked_step, answer_reveal

OUTPUT FORMAT: Valid JSON array of ScriptScene objects matching the schema.

STYLE: {prompts['theory_style']}
FOCUS: {', '.join(prompts['key_focus'])}

HARD RULES:
1. Every ScriptScene MUST have at least 2 voiceover_lines with non-empty text.
2. Every ScriptScene MUST have at least 2 scene_steps with valid type and non-empty text.
3. Use ONLY SceneStepType enum values. NO arbitrary fields. Timing 'at' in seconds.
4. If you cannot generate 2+ lines and 2+ steps, return an empty array [] and the system will handle it.
5. JSON only. No markdown, no explanations outside the JSON array."""

    def _build_theory_prompt(self, section: SectionNode, chapter: ChapterNode) -> str:
        prompts = SUBJECT_PROMPTS.get(chapter.subject, SUBJECT_PROMPTS["english"])
        content_snippet = _sanitize_text(section.content_text) if section.content_text else ""
        if not content_snippet:
            content_snippet = f"[Section: {section.title} — no extracted text available. Generate a brief introductory scene based on the section title and grade level.]"
        return f"""Generate theory script for this section:

SECTION: {section.title}
TYPE: THEORETICAL
CONTENT: {content_snippet[:3000]}
GRADE: {chapter.grade}
SUBJECT: {chapter.subject}

Create a pedagogical script with:
1. Voiceover lines (text + estimated duration + pause_after)
2. Scene steps using ONLY the constrained vocabulary
3. Timing 'at' in seconds for each step

STRICT OUTPUT RULES:
- Return a JSON array with EXACTLY 1 ScriptScene object.
- The scene MUST contain at least 2 voiceover_lines and 2 scene_steps.
- Every voiceover_lines entry must have non-empty "text".
- Every scene_steps entry must have a valid "type" from the vocabulary and non-empty "text".
- NEVER return empty arrays or placeholder-only content.
- If content is missing, create original educational narration suitable for the section title.

Style: {prompts['theory_style']}
Focus: {', '.join(prompts['key_focus'])}

JSON output:"""

    def _build_exercise_prompt(self, section: SectionNode, chapter: ChapterNode) -> str:
        prompts = SUBJECT_PROMPTS.get(chapter.subject, SUBJECT_PROMPTS["english"])
        exercises_text = "\n".join([
            f"Q: {ex.question_text}" for ex in section.exercises
        ]) if section.exercises else _sanitize_text(section.content_text)[:2000]

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

    def _build_introduction_prompt(self, section: SectionNode, chapter: ChapterNode) -> str:
        prompts = SUBJECT_PROMPTS.get(chapter.subject, SUBJECT_PROMPTS["english"])
        content_snippet = _sanitize_text(section.content_text) if section.content_text else ""
        if not content_snippet:
            content_snippet = f"[Section: {section.title} — introductory content. Generate a brief welcome and overview scene.]"
        return f"""Generate introduction/warm-up script:

SECTION: {section.title}
TYPE: INTRODUCTION
CONTENT: {content_snippet[:3000]}
GRADE: {chapter.grade}
SUBJECT: {chapter.subject}

Create an engaging opening scene:
1. Welcome the student to the lesson
2. Preview what will be learned
3. Activate prior knowledge with a quick question

Style: {prompts['theory_style']}
Focus: {', '.join(prompts['key_focus'])}

Output: JSON array of ScriptScene objects."""

    def _build_activity_prompt(self, section: SectionNode, chapter: ChapterNode) -> str:
        prompts = SUBJECT_PROMPTS.get(chapter.subject, SUBJECT_PROMPTS["english"])
        content_snippet = _sanitize_text(section.content_text) if section.content_text else ""
        if not content_snippet:
            content_snippet = f"[Section: {section.title} — hands-on activity. Generate instructions and encouragement.]"
        return f"""Generate activity/hands-on script:

SECTION: {section.title}
TYPE: ACTIVITY
CONTENT: {content_snippet[:3000]}
GRADE: {chapter.grade}
SUBJECT: {chapter.subject}

Create an interactive activity scene:
1. Explain the activity clearly
2. Give step-by-step instructions
3. Encourage participation and praise effort

Style: {prompts['exercise_style']}
Focus: {', '.join(prompts['key_focus'])}

Output: JSON array of ScriptScene objects."""

    def _build_summary_prompt(self, section: SectionNode, chapter: ChapterNode) -> str:
        prompts = SUBJECT_PROMPTS.get(chapter.subject, SUBJECT_PROMPTS["english"])
        content_snippet = _sanitize_text(section.content_text) if section.content_text else ""
        if not content_snippet:
            content_snippet = f"[Section: {section.title} — review/summary. Generate a recap of key points.]"
        return f"""Generate review/summary script:

SECTION: {section.title}
TYPE: SUMMARY
CONTENT: {content_snippet[:3000]}
GRADE: {chapter.grade}
SUBJECT: {chapter.subject}

Create a review scene:
1. Recap the main ideas from the lesson
2. Use a quick-check question
3. End with positive reinforcement

Style: {prompts['theory_style']}
Focus: {', '.join(prompts['key_focus'])}

Output: JSON array of ScriptScene objects."""

    def _invoke(self, messages: List[Dict[str, str]]) -> str:
        """Invoke LLM with retry logic and rate-limit backoff."""
        import time

        last_error = None
        for attempt in range(self.max_retries):
            try:
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_completion_tokens=self.max_completion_tokens,
                    top_p=1,
                    stream=False,
                )
                content = completion.choices[0].message.content or ""
                if not content.strip():
                    # Empty body from provider - back off and retry
                    wait = min(2 ** attempt * 10, 60)
                    logger.warning("Empty response from provider, backing off %ds (attempt %d)", wait, attempt + 1)
                    time.sleep(wait)
                    last_error = ValueError("Empty LLM response")
                    continue
                return content
            except Exception as e:
                error_str = str(e)
                # Back off on rate limits
                if "429" in error_str or "rate_limit" in error_str.lower():
                    wait = min(2 ** attempt * 5, 60)
                    logger.warning("Rate limited, backing off %ds (attempt %d)", wait, attempt + 1)
                    time.sleep(wait)
                else:
                    logger.warning("LLM call attempt %d failed: %s", attempt + 1, e)
                last_error = e
                if attempt == self.max_retries - 1:
                    break
        if last_error:
            raise last_error
        return ""

    def _parse_script_response(
        self, response: str, section: SectionNode, section_type: str
    ) -> List[ScriptScene]:
        """Parse LLM response into ScriptScene objects with validation."""
        cleaned = (response or "").strip()
        if not cleaned:
            logger.warning("Empty response for section %s", section.id)
            raise ValueError("Empty LLM response")

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
            logger.error("JSON parse failed for section %s: %s", section.id, e)
            raise

        scenes = []
        for item in data:
            # Skip non-dict items (strings, nulls, etc.)
            if not isinstance(item, dict):
                logger.warning("Skipping non-dict scene item in section %s: %r", section.id, type(item).__name__)
                continue
            try:
                scene = ScriptScene(
                    id=item.get("id", f"scene_{section.id}_{len(scenes)}"),
                    title=item.get("title", section.title),
                    section_ref=section.id,
                    voiceover_lines=[
                        VoiceoverLine(**self._normalize_voiceover_line(vl)) for vl in self._ensure_list(item.get("voiceover_lines", []))
                    ],
                    scene_steps=[
                        SceneStep(**self._normalize_scene_step(ss)) for ss in self._ensure_list(item.get("scene_steps", []))
                    ],
                    duration_seconds=item.get("duration_seconds", item.get("estimated_duration", 10.0)),
                    notes=item.get("notes", ""),
                )
                # Reject scenes with no actual content - they are useless
                if not scene.voiceover_lines and not scene.scene_steps:
                    logger.warning(f"Rejecting empty scene for section {section.id}")
                    continue
                scenes.append(scene)
            except ValidationError as e:
                logger.warning(f"Scene validation failed for section {section.id}: {e}")
                continue

        # Enforce max 1 scene per section to prevent LLM over-generation
        if len(scenes) > 1:
            scenes = scenes[:1]

        return scenes or self._fallback_scene(section, section_type)

    def _ensure_list(self, value: Any) -> list:
        """Coerce value to a flat list of dicts. Filters out invalid items."""
        if value is None:
            return []
        if isinstance(value, list):
            # Flatten one level and keep only dicts
            result = []
            for item in value:
                if isinstance(item, dict):
                    result.append(item)
                elif isinstance(item, list):
                    # Flatten nested list (e.g. LLM returns [["text"]])
                    for sub in item:
                        if isinstance(sub, dict):
                            result.append(sub)
            return result
        # Skip strings/numbers/bools
        if isinstance(value, (str, int, float, bool)):
            return []
        # Single dict → wrap
        if isinstance(value, dict):
            return [value]
        return []

    def _normalize_scene_step(self, step: dict) -> dict:
        if "content" in step and "text" not in step:
            step = dict(step)
            step["text"] = step.pop("content")
        if "at" not in step:
            step = dict(step)
            step["at"] = 0.0
        return step

    def _normalize_voiceover_line(self, line: dict) -> dict:
        line = dict(line)
        if "estimated_duration" in line and "duration_seconds" not in line:
            line["duration_seconds"] = line.pop("estimated_duration")
        elif "duration" in line and "duration_seconds" not in line:
            line["duration_seconds"] = line.pop("duration")
        if "duration_seconds" not in line:
            line["duration_seconds"] = 5.0
        if "pause_after" not in line:
            line["pause_after"] = 0.5
        return line

    def _fallback_scene(self, section: SectionNode, section_type: str) -> List[ScriptScene]:
        """Create a robust fallback scene when LLM output is invalid.

        Ensures minimum requirements:
        - ≥2 voiceover_lines with non-empty text
        - ≥2 scene_steps with valid types
        - Markdown sanitization
        """
        import re

        # Sanitize content text
        raw_content = section.content_text or ""
        raw_content = re.sub(r'!\[.*?\]\(.*?\)', '', raw_content)
        raw_content = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', raw_content)
        raw_content = re.sub(r'\s+', ' ', raw_content).strip()

        # Build content-aware fallback
        if raw_content:
            # Split into at least 2 narration chunks
            sentences = raw_content.replace("\n", " ").split(". ")
            chunks = [s.strip() for s in sentences if s.strip()]
            while len(chunks) < 2:
                chunks.append(f"Let us learn more about {section.title}.")
            vo_texts = chunks[:3]  # Cap at 3 for fallback
        else:
            vo_texts = [
                f"Let us learn about {section.title}.",
                f"Pay attention to the key ideas in this section.",
            ]

        # Determine scene step types based on section type
        if section_type in ("exercise", "activity", "summary", "introduction"):
            step_types = ["question_card", "worked_step", "answer_reveal"]
            step_texts = [
                f"Look at this: {section.title}",
                "Think about what you already know.",
                "Great job! You are learning so much.",
            ]
        else:
            step_types = ["title", "text", "word_highlight", "text"]
            step_texts = [
                section.title,
                vo_texts[0][:120] if vo_texts else f"Welcome to {section.title}",
                "key",
                vo_texts[1][:120] if len(vo_texts) > 1 else f"Let us explore {section.title} together.",
            ]

        # Ensure ≥2 scene steps
        while len(step_texts) < 2:
            step_texts.append(f"More about {section.title}.")
        steps = step_texts[:4]  # Cap at 4

        # Build voiceover lines (≥2)
        vo_lines = []
        cumulative = 0.0
        for i, text in enumerate(vo_texts[:4]):
            duration = max(2.0, len(text.split()) / 2.5)
            pause = 0.5 if i < len(vo_texts[:4]) - 1 else 0.0
            vo_lines.append(VoiceoverLine(text=text, duration_seconds=duration, pause_after=pause))
            cumulative += duration + pause

        # Build scene steps (≥2)
        scene_steps = []
        for i, (step_type, step_text) in enumerate(zip(step_types, steps)):
            scene_steps.append(SceneStep(
                type=SceneStepType(step_type),
                text=step_text[:200],
                at=i * 3.0,
                duration=max(1.0, len(step_text.split()) / 3.0),
            ))

        # Ensure ≥2 scene steps
        while len(scene_steps) < 2:
            scene_steps.append(SceneStep(
                type=SceneStepType.TEXT,
                text=f"Remember: {section.title}",
                at=len(scene_steps) * 3.0,
                duration=2.0,
            ))

        total_duration = cumulative if cumulative > 0 else 5.0

        return [ScriptScene(
            id=f"scene_{section.id}_fallback",
            title=section.title,
            section_ref=section.id,
            voiceover_lines=vo_lines,
            scene_steps=scene_steps,
            duration_seconds=round(total_duration, 1),
            notes="Fallback due to generation error",
        )]

    def generate_chapter_script(self, chapter: ChapterNode) -> List[ScriptScene]:
        """Generate script for all sections in a chapter."""
        return self.generate_chapter_script_chunked(chapter, chunk_size=len(chapter.sections), delay_seconds=0)

    def generate_chapter_script_chunked(
        self,
        chapter: ChapterNode,
        chunk_size: int = 5,
        delay_seconds: float = 2.0,
        checkpoint_path: Optional[str] = None,
    ) -> List[ScriptScene]:
        """Generate script in chunks to avoid rate limits.

        Args:
            chapter: The chapter to process.
            chunk_size: Number of sections to process per batch.
            delay_seconds: Seconds to wait between batches.
            checkpoint_path: Optional path to save/load progress JSON.
        """
        import time

        all_scenes: List[ScriptScene] = []
        subject = chapter.subject
        sections = chapter.sections
        total = len(sections)

        # Load checkpoint if exists
        done_section_ids: set = set()
        checkpoint_data = {}
        if checkpoint_path:
            cp = Path(checkpoint_path)
            if cp.exists():
                try:
                    checkpoint_data = json.loads(cp.read_text(encoding="utf-8"))
                    done_section_ids = set(checkpoint_data.get("done_section_ids", []))
                    logger.info("Resuming from checkpoint: %d sections already done", len(done_section_ids))
                except Exception as exc:
                    logger.warning("Could not load checkpoint (%s); starting fresh", exc)

        for batch_start in range(0, total, chunk_size):
            batch_end = min(batch_start + chunk_size, total)
            batch = sections[batch_start:batch_end]
            logger.info(
                "Processing sections %d-%d of %d (chunk size %d)",
                batch_start + 1, batch_end, total, chunk_size,
            )

            for section in batch:
                # Skip already-done sections
                if section.id in done_section_ids:
                    logger.info("Skipping already-completed section %s", section.id)
                    # Rebuild scene from checkpoint data
                    saved = checkpoint_data.get("scenes", {}).get(section.id)
                    if saved:
                        try:
                            scene = ScriptScene(**saved)
                            all_scenes.append(scene)
                        except ValidationError:
                            logger.warning("Checkpoint scene invalid for %s; regenerating", section.id)
                            done_section_ids.discard(section.id)
                    else:
                        logger.info("No checkpoint scene data for %s; will regenerate", section.id)
                        done_section_ids.discard(section.id)
                    if section.id in done_section_ids:
                        continue

                if section.type == SectionType.THEORETICAL:
                    prompt = self._build_theory_prompt(section, chapter)
                elif section.type == SectionType.EXERCISE:
                    prompt = self._build_exercise_prompt(section, chapter)
                elif section.type == SectionType.INTRODUCTION:
                    prompt = self._build_introduction_prompt(section, chapter)
                elif section.type == SectionType.ACTIVITY:
                    prompt = self._build_activity_prompt(section, chapter)
                elif section.type == SectionType.SUMMARY:
                    prompt = self._build_summary_prompt(section, chapter)
                else:
                    # Fallback for unknown section types
                    prompt = self._build_theory_prompt(section, chapter)

                system_prompt = self._get_system_prompt(subject)

                scenes: Optional[List[ScriptScene]] = None
                for attempt in range(self.max_retries):
                    try:
                        response = self._invoke([
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ])
                        scenes = self._parse_script_response(response, section, section.type.value)
                        break
                    except Exception as e:
                        logger.error(f"Failed to generate script for section {section.id}: {e}")
                        if attempt == self.max_retries - 1:
                            scenes = self._fallback_scene(section, section.type.value)
                if scenes:
                    all_scenes.extend(scenes)
                    # Save to checkpoint
                    if checkpoint_path:
                        done_section_ids.add(section.id)
                        checkpoint_data.setdefault("scenes", {})[section.id] = scenes[0].model_dump(mode="json")
                        checkpoint_data["done_section_ids"] = list(done_section_ids)
                        cp = Path(checkpoint_path)
                        cp.parent.mkdir(parents=True, exist_ok=True)
                        cp.write_text(json.dumps(checkpoint_data, indent=2), encoding="utf-8")

            # Wait between chunks to avoid rate limits (skip after last chunk)
            if batch_end < total and delay_seconds > 0:
                logger.info("Sleeping %.1fs before next chunk...", delay_seconds)
                time.sleep(delay_seconds)

        return all_scenes
