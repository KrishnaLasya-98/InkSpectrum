"""Script + scene schemas.

Defines the LLM output contract: when the script writer generates a chapter
video, it produces ScriptScene + SceneStep objects. The SceneStep vocabulary
is the constrained primitive set — see SceneStepType for the full list.

Phase 1 subjects: ENGLISH, MATH, SOCIAL
- Math uses: latex_inline, latex_block, polygon, circle, axes_2d, etc.
- English uses: word_highlight, vocabulary_card, sentence_token
- Social uses: timeline, map_marker, comparison_table
- All subjects use: title, subtitle, text, clear
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field


# ───────────────────────────────────────────────────────────────────
# Scene vocabulary (constrained primitives — LLM output contract)
# ───────────────────────────────────────────────────────────────────

class SceneStepType(str, Enum):
    """Constrained scene primitive vocabulary.

    LLMs output SceneStep objects using these types. Each type maps to
    a deterministic Remotion component. NO arbitrary SVG/React code.

    Why constrained? Because arbitrary code from LLMs requires scope-repair
    loops (Code2Video's pain). Constrained vocabulary → predictable output
    → zero scope errors.
    """

    # ── Universal (all subjects) ──
    TITLE = "title"                            # big centered title card
    SUBTITLE = "subtitle"                      # smaller secondary text
    TEXT = "text"                              # body text
    CLEAR = "clear"                            # wipe everything before next step

    # ── Math ──
    LATEX_INLINE = "latex_inline"              # inline equation (KaTeX-rendered)
    LATEX_BLOCK = "latex_block"                # display equation (centered, larger)
    POLYGON = "polygon"                        # n-gon shape
    CIRCLE = "circle"
    RECTANGLE = "rectangle"
    TRIANGLE = "triangle"
    ANGLE_ARC = "angle_arc"                    # angle indicator
    AXES_2D = "axes_2d"                        # 2D coordinate system
    AXES_3D = "axes_3d"                        # 3D coordinate system
    PLOT_CURVE = "plot_curve"                  # function plot on axes
    NUMBER_LINE = "number_line"                # 1D number line with marks
    FRACTION_BAR = "fraction_bar"              # visual fraction representation
    GRID = "grid"                              # grid background

    # ── English / Humanities ──
    WORD_HIGHLIGHT = "word_highlight"          # highlight a word in a sentence
    SENTENCE_TOKEN = "sentence_token"          # break sentence into tokens
    VOCABULARY_CARD = "vocabulary_card"        # word + definition + example
    PRONUNCIATION_GUIDE = "pronunciation_guide"  # phonetic guide
    POEM_CARD = "poem_card"                    # poem stanza card
    DIALOGUE_BUBBLE = "dialogue_bubble"        # comic-style speech bubble
    STORYBOARD_FRAME = "storyboard_frame"      # sequential story panel

    # ── Social / EVS ──
    TIMELINE = "timeline"                      # horizontal date markers
    MAP_MARKER = "map_marker"                  # location pin on map
    CAUSE_EFFECT_CHAIN = "cause_effect_chain"  # linked boxes
    COMPARISON_TABLE = "comparison_table"      # X vs Y table
    GEOGRAPHIC_MAP = "geographic_map"          # regional/national map
    HISTORICAL_FIGURE = "historical_figure"    # person card with dates/role
    PRIMARY_SOURCE = "primary_source"          # excerpt/document panel

    # ── Exercise (universal, any subject) ──
    QUESTION_CARD = "question_card"            # question text + options
    WORKED_STEP = "worked_step"                # numbered solution step
    ANSWER_REVEAL = "answer_reveal"            # final answer with highlight

    # ── GK (Phase 2 — DEFERRED) ──
    # FACT_CARD = "fact_card"
    # IMAGE_GRID = "image_grid"
    # QUIZ_PROMPT = "quiz_prompt"
    # PERSON_BIO = "person_bio"
    # PLACE_CARD = "place_card"
    # DID_YOU_KNOW = "did_you_know"
    # COMPARE_TWO = "compare_two"


class Vec2(BaseModel):
    """2D coordinate in SVG viewBox (or Remotion absolute coords)."""

    x: float
    y: float


class SceneStep(BaseModel):
    """A single scene step — one visual element at one moment in time.

    The LLM outputs a list of these. The renderer reads them as a deterministic
    timeline. Steps with the same `at` time appear simultaneously.

    Example:
        SceneStep(at=0, type=SceneStepType.TITLE, text="Photosynthesis", color="saffron")
        SceneStep(at=3, type=SceneStepType.LATEX_BLOCK, latex="6CO_2 + 6H_2O \\rightarrow ...", x=160, y=100)
    """

    at: float = Field(ge=0, description="Time in seconds when this step appears")
    duration: Optional[float] = Field(None, ge=0, description="How long it stays (default: until next clear)")

    type: SceneStepType

    # Text content (varies by type)
    text: Optional[str] = None                  # for title/subtitle/text
    latex: Optional[str] = None                 # for latex_inline/latex_block

    # Position (varies by type)
    x: Optional[float] = None
    y: Optional[float] = None
    cx: Optional[float] = None                  # for circle
    cy: Optional[float] = None
    r: Optional[float] = None                   # for circle
    w: Optional[float] = None                   # for rectangle
    h: Optional[float] = None
    points: Optional[list[Vec2]] = None         # for polygon

    # Style
    color: Optional[str] = None                 # "saffron" | "indigo" | "teal" | "white" | "muted" | hex
    fill: Optional[bool] = None
    size: Optional[str] = None                  # "sm" | "md" | "lg" | "xl"

    # Annotations
    label: Optional[str] = None                 # e.g. "right angle", "P", "F"
    highlight: Optional[bool] = None           # for word_highlight

    # Subject-specific extras
    steps: Optional[list[str]] = None          # for worked_step
    options: Optional[list[str]] = None        # for question_card (MCQ)
    correct_index: Optional[int] = None         # for question_card
    timeline_events: Optional[list[dict]] = None  # for timeline: [{"year": 1947, "event": "..."}]

    # Free-form extra (subject-specific)
    extra: Optional[dict] = None


# ───────────────────────────────────────────────────────────────────
# Script layer (narration + scene plan)
# ───────────────────────────────────────────────────────────────────

class VoiceoverLine(BaseModel):
    """A single line of narration with timing metadata."""

    text: str
    duration_seconds: float                     # estimated (filled in by TTS later)
    scene_id: Optional[str] = None              # which SceneStep group this belongs to
    pause_after: float = 0.5                    # silence after this line (seconds)


class ScriptScene(BaseModel):
    """A scene in the video script: voiceover + visual plan."""

    id: str                                     # e.g. "sec1_intro", "ex3_q1"
    title: str                                  # human-readable label
    voiceover_lines: list[VoiceoverLine]
    scene_steps: list[SceneStep]                # the visual plan
    duration_seconds: float                     # total (voiceover + pauses)
    section_ref: Optional[str] = None           # SectionNode.id this came from
    notes: str = ""                             # pedagogical notes for QA