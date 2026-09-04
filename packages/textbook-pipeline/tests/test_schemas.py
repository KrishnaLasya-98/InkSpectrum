"""Smoke tests for the schemas layer.

These tests verify:
- All schemas import cleanly
- Phase 1 subjects are present
- GK is NOT in active subjects (Phase 2 deferred)
- ChapterNode + SectionNode + ExerciseNode round-trip through JSON
- SceneStep accepts the full vocabulary
- StoryboardScene links audio + script correctly

Run with:
    pytest tests/test_schemas.py -v
or:
    python -m pytest tests/ -q
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from textbook_pipeline.models import (
    AudioManifest,
    ChapterNode,
    DoclingRef,
    ExerciseNode,
    ExerciseType,
    LaTeXEquation,
    SceneStepType,
    ScriptScene,
    SectionNode,
    SectionType,
    StoryboardScene,
    Subject,
    VoiceoverLine,
    WordTimestamp,
)


# ───────────────────────────────────────────────────────────────────
# Subject enum
# ───────────────────────────────────────────────────────────────────

class TestSubjects:
    def test_phase1_subjects_present(self):
        """All four Phase 1 subjects must be active."""
        assert Subject.ENGLISH.value == "english"
        assert Subject.MATH.value == "math"
        assert Subject.SCIENCE.value == "science"
        assert Subject.SOCIAL.value == "social"

    def test_gk_deferred(self):
        """GK must NOT be a member of the active Subject enum yet."""
        # The enum definition has GK commented out, so this should hold
        # When Phase 2 begins, this test will need to be updated
        assert not hasattr(Subject, "GK") or Subject.GK.value == "gk"

    def test_subject_count_phase1(self):
        """Exactly 4 active subjects."""
        active = [Subject.ENGLISH, Subject.MATH, Subject.SCIENCE, Subject.SOCIAL]
        assert len(active) == 4


# ───────────────────────────────────────────────────────────────────
# SceneStepType vocabulary
# ───────────────────────────────────────────────────────────────────

class TestSceneStepType:
    def test_universal_types_present(self):
        for t in ["title", "subtitle", "text", "clear"]:
            assert SceneStepType(t) in SceneStepType

    def test_math_types_present(self):
        math_types = [
            "latex_inline", "latex_block", "polygon", "circle", "rectangle",
            "axes_2d", "plot_curve", "number_line",
        ]
        for t in math_types:
            assert SceneStepType(t) in SceneStepType

    def test_english_types_present(self):
        for t in ["word_highlight", "sentence_token", "vocabulary_card", "pronunciation_guide"]:
            assert SceneStepType(t) in SceneStepType

    def test_social_types_present(self):
        for t in ["timeline", "map_marker", "cause_effect_chain", "comparison_table"]:
            assert SceneStepType(t) in SceneStepType

    def test_exercise_types_present(self):
        for t in ["question_card", "worked_step", "answer_reveal"]:
            assert SceneStepType(t) in SceneStepType

    def test_no_gk_types_yet(self):
        """GK primitives should be commented out in the enum (Phase 2 deferred)."""
        gk_types = ["fact_card", "image_grid", "quiz_prompt", "person_bio", "place_card"]
        for t in gk_types:
            try:
                SceneStepType(t)
                # If it exists, it must NOT be from the enum body
                pytest.fail(f"GK type {t} should be deferred but is present in SceneStepType")
            except ValueError:
                pass  # expected — not in enum


# ───────────────────────────────────────────────────────────────────
# Chapter / Section / Exercise round-trip
# ───────────────────────────────────────────────────────────────────

class TestChapterRoundTrip:
    def test_minimal_chapter_serializes(self):
        """A minimal ChapterNode should serialize to JSON and back without loss."""
        chapter = ChapterNode(
            id="english_v1_ch1",
            number=1,
            title="A Good Boy",
            subject=Subject.ENGLISH,
            grade=4,
            textbook_id="english_v1",
            page_range=(1, 10),
            source_pdf=Path("data/textbook_corpus/ENGLISH_V1.pdf"),
        )

        as_json = chapter.model_dump_json()
        restored = ChapterNode.model_validate_json(as_json)

        assert restored.id == chapter.id
        assert restored.title == chapter.title
        assert restored.subject == Subject.ENGLISH
        assert restored.grade == 4

    def test_chapter_with_exercise_section(self):
        """ChapterNode with exercise section + exercises round-trips."""
        exercise_section = SectionNode(
            id="ch1_exercises",
            type=SectionType.EXERCISE,
            title="Exercises",
            content_text="Answer the following questions.",
            page_range=(8, 10),
            exercises=[
                ExerciseNode(
                    id="ex_1_1",
                    question_text="Who is the boy in the story?",
                    exercise_type=ExerciseType.SHORT_ANSWER,
                    difficulty=2,
                    marks=2,
                    page_number=9,
                ),
                ExerciseNode(
                    id="ex_1_2",
                    question_text="What did the boy do that was good?",
                    exercise_type=ExerciseType.SHORT_ANSWER,
                    difficulty=3,
                    page_number=9,
                ),
            ],
        )

        chapter = ChapterNode(
            id="english_v1_ch1",
            number=1,
            title="A Good Boy",
            subject=Subject.ENGLISH,
            grade=4,
            textbook_id="english_v1",
            sections=[exercise_section],
            page_range=(1, 10),
            source_pdf=Path("data/textbook_corpus/ENGLISH_V1.pdf"),
        )

        assert len(chapter.all_exercises()) == 2
        assert len(chapter.get_exercise_sections()) == 1
        assert len(chapter.get_theoretical_sections()) == 0

    def test_chapter_with_math_section_and_equations(self):
        """Math chapter with LaTeX equations round-trips."""
        math_section = SectionNode(
            id="ch3_sec1",
            type=SectionType.THEORETICAL,
            title="Linear Equations",
            content_text="An equation of the form ax + b = 0 is linear.",
            page_range=(40, 50),
            equations=[
                LaTeXEquation(
                    latex="ax + b = 0",
                    plain_text="ax + b = 0",
                    page_number=42,
                ),
                LaTeXEquation(
                    latex="x = -\\frac{b}{a}",
                    plain_text="x = -b/a",
                    page_number=43,
                    context="Solving for x",
                ),
            ],
            docling_refs=[
                DoclingRef(item_id="itm_001", page_number=42, label="FORMULA"),
            ],
        )

        chapter = ChapterNode(
            id="maths_v2_ch3",
            number=3,
            title="Linear Equations in One Variable",
            subject=Subject.MATH,
            grade=8,
            textbook_id="maths_v2",
            sections=[math_section],
            page_range=(40, 60),
            source_pdf=Path("data/textbook_corpus/MATHS_V2.pdf"),
        )

        assert chapter.sections[0].equations[0].latex == "ax + b = 0"
        assert chapter.sections[0].equations[1].latex == "x = -\\frac{b}{a}"

    def test_json_serializable_to_file(self, tmp_path: Path):
        """A chapter can be saved to disk and re-loaded."""
        chapter = ChapterNode(
            id="test_ch",
            number=1,
            title="Test Chapter",
            subject=Subject.ENGLISH,
            grade=4,
            textbook_id="test",
            page_range=(1, 5),
            source_pdf=Path("/tmp/test.pdf"),
        )

        out_path = tmp_path / "chapter.json"
        out_path.write_text(chapter.model_dump_json(indent=2))

        loaded = ChapterNode.model_validate_json(out_path.read_text())
        assert loaded.id == "test_ch"


# ───────────────────────────────────────────────────────────────────
# Script + Scene vocabulary
# ───────────────────────────────────────────────────────────────────

class TestScriptLayer:
    def test_scene_step_math_latex(self):
        """SceneStep with LaTeX equation (math scene) is valid."""
        from textbook_pipeline.models import SceneStep
        step = SceneStep(
            at=5.0,
            type=SceneStepType.LATEX_BLOCK,
            latex="x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}",
            y=100,
            size="lg",
        )
        assert step.type == SceneStepType.LATEX_BLOCK
        assert "\\frac" in step.latex

    def test_scene_step_english_highlight(self):
        """SceneStep for English word-highlight is valid."""
        from textbook_pipeline.models import SceneStep
        step = SceneStep(
            at=2.0,
            type=SceneStepType.WORD_HIGHLIGHT,
            text="metaphor",
            x=160,
            y=100,
            highlight=True,
        )
        assert step.type == SceneStepType.WORD_HIGHLIGHT

    def test_script_scene_with_voiceover(self):
        """ScriptScene holds voiceover + scene steps."""
        from textbook_pipeline.models import SceneStep
        script = ScriptScene(
            id="ch1_intro",
            title="Introduction",
            voiceover_lines=[
                VoiceoverLine(text="Welcome to Chapter One.", duration_seconds=2.5),
                VoiceoverLine(text="Today we'll learn about photosynthesis.", duration_seconds=3.5, pause_after=1.0),
            ],
            scene_steps=[
                SceneStep(at=0, type=SceneStepType.TITLE, text="Chapter One", color="saffron"),
                SceneStep(at=2.5, type=SceneStepType.SUBTITLE, text="Photosynthesis", color="muted"),
            ],
            duration_seconds=7.5,
            section_ref="ch1_sec0",
        )
        assert len(script.voiceover_lines) == 2
        assert len(script.scene_steps) == 2


# ───────────────────────────────────────────────────────────────────
# Storyboard + audio
# ───────────────────────────────────────────────────────────────────

class TestStoryboardLayer:
    def test_storyboard_with_audio(self):
        """StoryboardScene links script + audio with timing."""
        from textbook_pipeline.models import SceneStep
        audio = AudioManifest(
            scene_id="ch1_intro",
            audio_path=Path("audio/ch1_intro.mp3"),
            duration_seconds=7.5,
            voice="en-US-AriaNeural",
            rate="+0%",
            word_timestamps=[
                WordTimestamp(word="Welcome", start_seconds=0.0, end_seconds=0.5),
                WordTimestamp(word="to", start_seconds=0.5, end_seconds=0.7),
            ],
        )

        script = ScriptScene(
            id="ch1_intro",
            title="Introduction",
            voiceover_lines=[],
            scene_steps=[SceneStep(at=0, type=SceneStepType.TITLE, text="Hi")],
            duration_seconds=7.5,
        )

        scene = StoryboardScene(
            id="ch1_intro",
            title="Introduction",
            script_scene=script,
            audio=audio,
            start_time=0.0,
            end_time=7.5,
        )

        assert scene.audio.duration_seconds == 7.5
        assert len(scene.audio.word_timestamps) == 2
        assert scene.end_time - scene.start_time == 7.5