"""Constrained SceneStepType vocabulary registry."""

from __future__ import annotations

from typing import Dict, Set

from textbook_pipeline.models.script import SceneStepType


class SceneVocabularyRegistry:
    """Registry mapping SceneStepType values to renderer components."""

    def __init__(self):
        self._registry: Dict[str, str] = {}
        self._subject_restrictions: Dict[str, Set[str]] = {}
        self._build_default_registry()

    def _build_default_registry(self) -> None:
        """Build default mappings."""
        # Universal types
        universal = {
            SceneStepType.TITLE: "TitleCard",
            SceneStepType.SUBTITLE: "SubtitleCard",
            SceneStepType.TEXT: "TextCard",
            SceneStepType.CLEAR: "Clear",
        }
        self._registry.update(universal)

        # English types
        english_types = {
            SceneStepType.WORD_HIGHLIGHT: "WordHighlight",
            SceneStepType.SENTENCE_TOKEN: "SentenceToken",
            SceneStepType.VOCABULARY_CARD: "VocabularyCard",
            SceneStepType.PRONUNCIATION_GUIDE: "PronunciationGuide",
            SceneStepType.POEM_CARD: "PoemCard",
            SceneStepType.DIALOGUE_BUBBLE: "DialogueBubble",
            SceneStepType.STORYBOARD_FRAME: "StoryboardFrame",
        }
        self._registry.update(english_types)

        # Math types
        math_types = {
            SceneStepType.LATEX_INLINE: "LatexInline",
            SceneStepType.LATEX_BLOCK: "LatexBlock",
            SceneStepType.POLYGON: "Polygon",
            SceneStepType.CIRCLE: "Circle",
            SceneStepType.RECTANGLE: "Rectangle",
            SceneStepType.TRIANGLE: "Triangle",
            SceneStepType.ANGLE_ARC: "AngleArc",
            SceneStepType.AXES_2D: "Axes2D",
            SceneStepType.AXES_3D: "Axes3D",
            SceneStepType.PLOT_CURVE: "PlotCurve",
            SceneStepType.NUMBER_LINE: "NumberLine",
            SceneStepType.FRACTION_BAR: "FractionBar",
            SceneStepType.GRID: "Grid",
        }
        self._registry.update(math_types)

        # Social types
        social_types = {
            SceneStepType.TIMELINE: "Timeline",
            SceneStepType.MAP_MARKER: "MapMarker",
            SceneStepType.CAUSE_EFFECT_CHAIN: "CauseEffectChain",
            SceneStepType.COMPARISON_TABLE: "ComparisonTable",
            SceneStepType.GEOGRAPHIC_MAP: "GeographicMap",
            SceneStepType.HISTORICAL_FIGURE: "HistoricalFigure",
            SceneStepType.PRIMARY_SOURCE: "PrimarySource",
        }
        self._registry.update(social_types)

        # Exercise types
        exercise_types = {
            SceneStepType.QUESTION_CARD: "QuestionCard",
            SceneStepType.WORKED_STEP: "WorkedStep",
            SceneStepType.ANSWER_REVEAL: "AnswerReveal",
        }
        self._registry.update(exercise_types)

    def get_component(self, step_type: str) -> str:
        """Get the renderer component name for a SceneStepType."""
        if step_type not in SceneStepType.values():
            raise ValueError(f"Unknown SceneStepType: {step_type}")
        return self._registry.get(step_type, "UnknownComponent")

    def is_valid_for_subject(self, step_type: str, subject: str) -> bool:
        """Check if a SceneStepType is valid for a given subject."""
        allowed = self._subject_restrictions.get(subject.lower())
        if allowed is None:
            return True  # No restrictions defined
        return step_type in allowed

    def register_subject_restriction(self, subject: str, allowed_types: Set[str]) -> None:
        """Register allowed SceneStepTypes for a subject."""
        self._subject_restrictions[subject.lower()] = allowed_types
