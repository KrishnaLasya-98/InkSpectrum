"""Subject-specific plugins for extraction, prompts, and rendering."""

from __future__ import annotations

from textbook_pipeline.core.subjects.base import SubjectPlugin
from textbook_pipeline.core.subjects.english import EnglishPlugin
from textbook_pipeline.core.subjects.math import MathPlugin
from textbook_pipeline.core.subjects.science import SciencePlugin
from textbook_pipeline.core.subjects.social import SocialPlugin
from textbook_pipeline.core.subjects.humanities import HumanitiesPlugin

__all__ = [
    "SubjectPlugin",
    "EnglishPlugin",
    "MathPlugin",
    "SciencePlugin",
    "SocialPlugin",
    "HumanitiesPlugin",
]


def get_plugin(subject: str) -> SubjectPlugin:
    """Return the appropriate plugin for a subject string."""
    plugins = {
        "english": EnglishPlugin,
        "math": MathPlugin,
        "science": SciencePlugin,
        "social": SocialPlugin,
        "humanities": HumanitiesPlugin,
    }
    plugin_cls = plugins.get(subject.lower())
    if not plugin_cls:
        raise ValueError(f"No plugin for subject: {subject}")
    return plugin_cls()
