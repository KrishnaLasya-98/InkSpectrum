"""Loader for per-subject configuration.

Reads `data/subjects/<subject>/config.json` and returns a typed
SubjectConfig object. Centralizes the location so adding a new subject
later (Phase 2: GK) is just adding one JSON file.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from textbook_pipeline.models.chapter import Subject, SubjectConfig

# Resolve to repo_root/data/subjects/
_DATA_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=None)
def load_subject_config(subject: Subject) -> SubjectConfig:
    """Load the SubjectConfig for a given subject.

    Cached because the JSON files don't change at runtime.

    Raises:
        FileNotFoundError: if no config.json exists for the subject
        ValidationError: if the JSON doesn't match the SubjectConfig schema
    """
    config_path = _DATA_DIR / subject.value / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(
            f"No config.json for subject '{subject.value}' at {config_path}. "
            f"Available subjects with configs: {available_subjects()}"
        )

    raw = json.loads(config_path.read_text(encoding="utf-8"))

    # Allow JSON to omit template dir; default to subject dir
    raw.setdefault("scene_template_dir", f"data/subjects/{subject.value}/templates")

    return SubjectConfig.model_validate(raw)


def available_subjects() -> list[str]:
    """List subjects that have a config.json on disk."""
    if not _DATA_DIR.exists():
        return []
    return sorted(
        p.name
        for p in _DATA_DIR.iterdir()
        if p.is_dir() and (p / "config.json").exists()
    )


def is_subject_available(subject: Subject) -> bool:
    """Check whether a subject has a config available (Phase 1 only by default)."""
    return subject.value in available_subjects()


def reset_cache() -> None:
    """Clear the lru_cache. Useful in tests after modifying config files."""
    load_subject_config.cache_clear()
