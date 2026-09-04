"""Pydantic schemas for textbook-pipeline.

Defines the canonical data structures that flow through the pipeline:
- ChapterNode, SectionNode, ExerciseNode (ingestion layer)
- ScriptScene, SceneStep (script + visual plan)
- StoryboardScene, AudioManifest (rendering layer)

All schemas use Pydantic v2 for validation and serialization.
"""

from .chapter import (
    ChapterNode,
    DoclingRef,
    ExerciseNode,
    ExerciseType,
    ImageAsset,
    LaTeXEquation,
    SectionNode,
    SectionType,
    Subject,
    SubjectConfig,
    TableData,
)
from .script import (
    ScriptScene,
    SceneStep,
    SceneStepType,
    VoiceoverLine,
)
from .storyboard import (
    AudioManifest,
    StoryboardScene,
    WordTimestamp,
)

__all__ = [
    # Chapter / textbook layer
    "Subject",
    "SubjectConfig",
    "ChapterNode",
    "SectionNode",
    "SectionType",
    "ExerciseNode",
    "ExerciseType",
    "DoclingRef",
    "LaTeXEquation",
    "TableData",
    "ImageAsset",
    # Script layer
    "ScriptScene",
    "SceneStep",
    "SceneStepType",
    "VoiceoverLine",
    # Storyboard / render layer
    "StoryboardScene",
    "AudioManifest",
    "WordTimestamp",
]