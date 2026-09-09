"""Phase 2 reliability tests for ScriptWriter and classification.

Covers:
- Section classification routing (THEORETICAL, EXERCISE, INTRODUCTION, ACTIVITY, SUMMARY)
- Fallback scene minimum requirements (>=2 voiceover_lines, >=2 scene_steps)
- Markdown sanitization in prompts and fallbacks
- SectionType-aware prompt generation
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from textbook_pipeline.core.script.writer import ScriptWriter, _sanitize_text
from textbook_pipeline.models.chapter import ChapterNode, SectionNode, SectionType, Subject
from textbook_pipeline.models.script import SceneStepType, ScriptScene, VoiceoverLine


REPO_ROOT = Path(__file__).resolve().parents[3]
CHAPTER_JSON = REPO_ROOT / "packages/textbook-pipeline/projects/english_pipeline_output/chapter.json"


def _load_chapter() -> ChapterNode:
    data = json.loads(CHAPTER_JSON.read_text(encoding="utf-8"))
    return ChapterNode(**data)


class TestMarkdownSanitization:
    """Markdown artifacts must be stripped before narration/scene steps."""

    def test_removes_image_markdown(self):
        raw = "Hello ![](image.png) world ![]<other.jpg>"
        assert _sanitize_text(raw) == "Hello world"

    def test_removes_link_markdown_keeps_text(self):
        raw = "Click [here](http://example.com) now"
        assert _sanitize_text(raw) == "Click here now"

    def test_collapses_whitespace(self):
        raw = "Hello   world\n\n  foo\tbar  "
        assert _sanitize_text(raw) == "Hello world foo bar"

    def test_empty_input(self):
        assert _sanitize_text("") == ""

    def test_no_markdown(self):
        raw = "Plain text without markdown"
        assert _sanitize_text(raw) == raw


class TestFallbackSceneMinimums:
    """Fallback scenes must meet AGENTS.md minimum content requirements."""

    def test_fallback_has_minimum_voiceover_lines(self):
        chapter = _load_chapter()
        section = chapter.sections[0]
        writer = ScriptWriter(api_key="sk-test", model="test-model", base_url="http://localhost")
        scenes = writer._fallback_scene(section, SectionType.THEORETICAL.value)
        assert len(scenes) == 1
        assert len(scenes[0].voiceover_lines) >= 2
        for vl in scenes[0].voiceover_lines:
            assert vl.text.strip()

    def test_fallback_has_minimum_scene_steps(self):
        chapter = _load_chapter()
        section = chapter.sections[0]
        writer = ScriptWriter(api_key="sk-test", model="test-model", base_url="http://localhost")
        scenes = writer._fallback_scene(section, SectionType.EXERCISE.value)
        assert len(scenes[0].scene_steps) >= 2
        for ss in scenes[0].scene_steps:
            assert ss.text.strip()

    def test_fallback_sanitizes_markdown_content(self):
        chapter = _load_chapter()
        section = chapter.sections[0]
        section.content_text = "Look ![](image.png) and [click](http://test.com) here"
        writer = ScriptWriter(api_key="sk-test", model="test-model", base_url="http://localhost")
        scenes = writer._fallback_scene(section, SectionType.THEORETICAL.value)
        for vl in scenes[0].voiceover_lines:
            assert "![]" not in vl.text
            assert "](" not in vl.text

    def test_fallback_uses_exercise_steps_for_exercise_sections(self):
        chapter = _load_chapter()
        section = chapter.sections[0]
        writer = ScriptWriter(api_key="sk-test", model="test-model", base_url="http://localhost")
        scenes = writer._fallback_scene(section, SectionType.EXERCISE.value)
        step_types = {ss.type for ss in scenes[0].scene_steps}
        # Exercise fallback should use exercise-oriented step types
        assert any(st in step_types for st in (
            SceneStepType.QUESTION_CARD,
            SceneStepType.WORKED_STEP,
            SceneStepType.ANSWER_REVEAL,
        ))

    def test_fallback_uses_theory_steps_for_theoretical_sections(self):
        chapter = _load_chapter()
        section = chapter.sections[0]
        writer = ScriptWriter(api_key="sk-test", model="test-model", base_url="http://localhost")
        scenes = writer._fallback_scene(section, SectionType.THEORETICAL.value)
        step_types = {ss.type for ss in scenes[0].scene_steps}
        assert SceneStepType.TITLE in step_types
        assert SceneStepType.TEXT in step_types


class TestSectionTypeRouting:
    """ScriptWriter must route all SectionTypes to appropriate prompts."""

    def test_all_section_types_have_prompts(self):
        writer = ScriptWriter(api_key="sk-test", model="test-model", base_url="http://localhost")
        for section_type in SectionType:
            if section_type == SectionType.THEORETICAL:
                method_name = "_build_theory_prompt"
            else:
                method_name = f"_build_{section_type.value}_prompt"
            assert hasattr(writer, method_name), f"Missing prompt builder for {section_type.value}"

    def test_introduction_prompt_mentions_welcome(self):
        writer = ScriptWriter(api_key="sk-test", model="test-model", base_url="http://localhost")
        section = SectionNode(
            id="sec_test",
            type=SectionType.INTRODUCTION,
            title="Welcome",
            content_text="",
            page_range=(1, 1),
        )
        chapter = ChapterNode(
            id="ch_test",
            number=1,
            title="Test Chapter",
            textbook_id="test",
            subject=Subject.ENGLISH,
            grade=1,
            page_range=(1, 2),
            source_pdf="test.pdf",
            sections=[section],
        )
        prompt = writer._build_introduction_prompt(section, chapter)
        assert "introduction" in prompt.lower() or "welcome" in prompt.lower()

    def test_activity_prompt_mentions_instructions(self):
        writer = ScriptWriter(api_key="sk-test", model="test-model", base_url="http://localhost")
        section = SectionNode(
            id="sec_test",
            type=SectionType.ACTIVITY,
            title="Draw an Animal",
            content_text="",
            page_range=(1, 1),
        )
        chapter = ChapterNode(
            id="ch_test",
            number=1,
            title="Test Chapter",
            textbook_id="test",
            subject=Subject.ENGLISH,
            grade=1,
            page_range=(1, 2),
            source_pdf="test.pdf",
            sections=[section],
        )
        prompt = writer._build_activity_prompt(section, chapter)
        assert "activity" in prompt.lower() or "instructions" in prompt.lower()

    def test_summary_prompt_mentions_review(self):
        writer = ScriptWriter(api_key="sk-test", model="test-model", base_url="http://localhost")
        section = SectionNode(
            id="sec_test",
            type=SectionType.SUMMARY,
            title="Recap",
            content_text="",
            page_range=(1, 1),
        )
        chapter = ChapterNode(
            id="ch_test",
            number=1,
            title="Test Chapter",
            textbook_id="test",
            subject=Subject.ENGLISH,
            grade=1,
            page_range=(1, 2),
            source_pdf="test.pdf",
            sections=[section],
        )
        prompt = writer._build_summary_prompt(section, chapter)
        assert "review" in prompt.lower() or "summary" in prompt.lower()

    def test_prompts_sanitize_content(self):
        writer = ScriptWriter(api_key="sk-test", model="test-model", base_url="http://localhost")
        section = SectionNode(
            id="sec_test",
            type=SectionType.THEORETICAL,
            title="Test",
            content_text="Content ![](img.png) and [link](http://x.com)",
            page_range=(1, 1),
        )
        chapter = ChapterNode(
            id="ch_test",
            number=1,
            title="Test Chapter",
            textbook_id="test",
            subject=Subject.ENGLISH,
            grade=1,
            page_range=(1, 2),
            source_pdf="test.pdf",
            sections=[section],
        )
        prompt = writer._build_theory_prompt(section, chapter)
        assert "![]" not in prompt
        assert "](" not in prompt


class TestEnrichChapterClassification:
    """Verify dynamic markdown-based classification."""

    @pytest.fixture(scope="class")
    def _enrich_module(self):
        import importlib.util
        import sys
        spec = importlib.util.spec_from_file_location(
            "enrich_chapter",
            REPO_ROOT / "packages/textbook-pipeline/scripts/enrich_chapter.py",
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["enrich_chapter"] = mod
        spec.loader.exec_module(mod)
        return mod

    def test_enrich_chapter_reclassifies_misclassified_sections(self, _enrich_module):
        is_exercise_section = _enrich_module.is_exercise_section

        # These titles should be classified as exercise
        assert is_exercise_section("Warm Up", content="Look at the picture. Talk about any 3 of them.", heading_level=3)
        assert is_exercise_section("Begin by saying:", content="Hello, My name is _____.", heading_level=3)
        assert is_exercise_section("Read these lines. Colour one smiley to show how you feel:",
                                   content="- 1. read and enjoy a text", heading_level=3)

    def test_theoretical_sections_not_reclassified(self, _enrich_module):
        is_exercise_section = _enrich_module.is_exercise_section

        # These should remain theoretical
        assert not is_exercise_section("At the Beach 1", content="", heading_level=1)
        assert not is_exercise_section("Vowels and Consonants",
                                       content="There are 26 letters in the English alphabets.",
                                       heading_level=2)

    def test_content_analysis_prefers_theory_for_narrative(self, _enrich_module):
        is_exercise_section = _enrich_module.is_exercise_section

        narrative = (
            "Let us read what Varun and his sister do when they visit a beach with their family. "
            "It is a lovely day. Varun and Vidya are at a beach with their parents. "
            "Hey, let us build a sandcastle. Sure! I have a shovel and a bucket too. "
            "Glossary shovel : a tool for digging earth. basement : rooms below ground."
        )
        assert not is_exercise_section("Read and Enjoy", content=narrative, heading_level=4)

    def test_content_analysis_prefers_exercise_for_questions(self, _enrich_module):
        is_exercise_section = _enrich_module.is_exercise_section

        exercise_content = (
            "- a. What do Varun and Vidya do on the beach? _______\n"
            "- b. What do they use to build the sandcastle? _______\n"
            "- c. Where does the staircase go? _______"
        )
        assert is_exercise_section("Think and Answer", content=exercise_content, heading_level=4)
