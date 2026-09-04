"""Chapter-level schemas: Subject, ChapterNode, SectionNode, ExerciseNode.

These schemas represent the output of the ingestion layer — a textbook PDF
parsed into a structured, pedagogy-aware chapter tree.

Phase 1 subjects: ENGLISH, MATH, SCIENCE, SOCIAL (EVS)
Phase 2 (deferred): GK
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field


class Subject(str, Enum):
    """Subject classification for K-10 textbooks.

    Phase 1 (active): ENGLISH, MATH, SCIENCE, SOCIAL
    Phase 2 (deferred): GK
    """

    ENGLISH = "english"
    MATH = "math"
    SCIENCE = "science"
    SOCIAL = "social"      # Social Studies / EVS / Environmental Studies
    # GK = "gk"            # Phase 2 (deferred)


class SubjectConfig(BaseModel):
    """Per-subject configuration: TTS voice, palette, scene templates."""

    subject: Subject
    display_name: str                              # e.g. "Mathematics"
    default_voice: str                             # e.g. "en-US-AriaNeural"
    primary_color: str                             # hex, e.g. "#3D3BDB"
    secondary_color: str
    background_color: str = "#FFFFFF"
    tts_rate: str = "+0%"                          # e.g. "-15%" for slower narration
    reading_level_adjustment: float = 1.0          # multiplier for vocab complexity
    scene_template_dir: Path                       # path to subject-specific Remotion templates

    # Optional extensions (from JSON config files)
    scene_types: Optional[list[str]] = None       # allowed SceneStepType values for this subject
    narration_pattern: Optional[dict] = None      # pedagogical narration templates per
    terminology: Optional[dict] = None               # subject-specific vocabulary
    equation_detection_patterns: Optional[list[str]] = None  # math only
    exercise_detection_patterns: Optional[list[str]] = None
    tts_voice_alternatives: Optional[list[str]] = None
    reading_pace_wpm: Optional[dict] = None       # english only
    sub_themes: Optional[dict] = None             # social: history/geography/civics vs env/ecology


class SectionType(str, Enum):
    """Discriminates theoretical content from exercises/activities."""

    THEORETICAL = "theoretical"
    EXERCISE = "exercise"
    ACTIVITY = "activity"
    SUMMARY = "summary"
    INTRODUCTION = "introduction"


class ExerciseType(str, Enum):
    """Type of exercise question. Determines scene template + narration pattern."""

    MCQ = "mcq"
    SHORT_ANSWER = "short_answer"
    NUMERICAL = "numerical"
    ESSAY = "essay"
    FILL_BLANK = "fill_blank"
    MATCHING = "matching"
    TRUE_FALSE = "true_false"            # common in GK (Phase 2)


class LaTeXEquation(BaseModel):
    """An equation extracted from a textbook, with LaTeX source + page reference."""

    latex: str                                   # e.g. "6CO_2 + 6H_2O \\rightarrow ..."
    plain_text: str                              # e.g. "6CO2 + 6H2O → ..."
    page_number: int
    context: Optional[str] = None                # surrounding sentence for narration


class TableData(BaseModel):
    """A table extracted from a textbook."""

    page_number: int
    headers: list[str]
    rows: list[list[str]]
    caption: Optional[str] = None


class ImageAsset(BaseModel):
    """An image extracted from a textbook (figure, diagram, photo)."""

    page_number: int
    file_path: Path                              # local path on disk
    caption: Optional[str] = None
    alt_text: Optional[str] = None               # for accessibility
    classification: Optional[str] = None         # e.g. "diagram", "photo", "map"


class DoclingRef(BaseModel):
    """Reference to a source item in Docling's DoclingDocument.

    We keep the reference (rather than copy) so we can trace back
    to the original PDF page/section for citation tracking.
    """

    item_id: str
    page_number: int
    label: str                                   # Docling's DocItemLabel value


class ExerciseNode(BaseModel):
    """A single exercise question."""

    id: str                                      # e.g. "ex_3_1" (chapter 3, question 1)
    question_text: str
    exercise_type: ExerciseType
    difficulty: int = Field(ge=1, le=5)
    marks: Optional[int] = None
    options: Optional[list[str]] = None          # for MCQ
    correct_answer: Optional[str] = None
    worked_solution: Optional[list[str]] = None  # step-by-step if available
    hint: Optional[str] = None
    visual_assets: list[ImageAsset] = Field(default_factory=list)
    page_number: int
    docling_refs: list[DoclingRef] = Field(default_factory=list)


class SectionNode(BaseModel):
    """A section within a chapter (theoretical OR exercise OR activity)."""

    id: str                                      # e.g. "ch3_sec1", "ch3_exercises"
    type: SectionType
    title: str
    content_text: str                            # plain text content (LLM-friendly)
    page_range: tuple[int, int]
    docling_refs: list[DoclingRef] = Field(default_factory=list)
    equations: list[LaTeXEquation] = Field(default_factory=list)
    tables: list[TableData] = Field(default_factory=list)
    figures: list[ImageAsset] = Field(default_factory=list)
    exercises: list[ExerciseNode] = Field(default_factory=list)
    estimated_duration_seconds: int = 0          # set by script writer


class ChapterNode(BaseModel):
    """A complete chapter extracted from a textbook PDF."""

    id: str                                      # e.g. "english_v1_ch3"
    number: int
    title: str
    subject: Subject
    grade: int = Field(ge=1, le=10)
    textbook_id: str                             # e.g. "english_v1"
    learning_objectives: list[str] = Field(default_factory=list)
    sections: list[SectionNode] = Field(default_factory=list)
    page_range: tuple[int, int]
    source_pdf: Path
    total_estimated_duration_seconds: int = 0     # computed
    metadata: dict[str, Any] = Field(default_factory=dict)

    def get_exercise_sections(self) -> list[SectionNode]:
        """Return only the EXERCISE-type sections."""
        return [s for s in self.sections if s.type == SectionType.EXERCISE]

    def get_theoretical_sections(self) -> list[SectionNode]:
        """Return only the THEORETICAL-type sections (excluding intro/summary/activity)."""
        return [
            s for s in self.sections
            if s.type in (SectionType.THEORETICAL, SectionType.INTRODUCTION)
        ]

    def all_exercises(self) -> list[ExerciseNode]:
        """Flatten all exercises from all exercise sections."""
        exercises = []
        for section in self.sections:
            exercises.extend(section.exercises)
        return exercises

    def total_pages(self) -> int:
        return self.page_range[1] - self.page_range[0] + 1