"""Data-driven subject classification and rendering profiles.

Chapter code consumes a profile instead of branching on individual subject
names. New subjects can therefore be added by editing the YAML registry rather
than changing the planner, renderer, and media-prompt code.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_PATH = _ROOT / "config" / "educational-subject-profiles.yaml"


@lru_cache(maxsize=4)
def load_subject_profiles(path: str | Path = _DEFAULT_PATH) -> dict[str, Any]:
    profile_path = Path(path).resolve()
    data = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("profiles"), dict):
        raise ValueError("Educational subject profile registry is invalid")
    default_id = str(data.get("default_profile") or "")
    if default_id not in data["profiles"]:
        raise ValueError("Educational subject profile registry has no valid default")
    return data


def resolve_subject_profile(
    subject: str | None,
    *,
    source_text: str = "",
    registry_path: str | Path = _DEFAULT_PATH,
) -> dict[str, Any]:
    """Resolve a subject label or source document to one configured profile."""

    registry = load_subject_profiles(registry_path)
    profiles = registry["profiles"]
    haystack = f"{subject or ''}\n{source_text}".casefold()
    normalized_subject = (subject or "").strip().casefold()
    best_id = str(registry["default_profile"])
    best_score = 0
    for profile_id, profile in profiles.items():
        aliases = [str(alias).strip().casefold() for alias in profile.get("aliases", [])]
        score = 0
        for alias in aliases:
            if not alias:
                continue
            if normalized_subject == alias:
                score += 100
            elif alias in normalized_subject:
                score += 25
            score += haystack.count(alias)
        if score > best_score:
            best_id, best_score = str(profile_id), score
    result = dict(profiles[best_id])
    result["profile_id"] = best_id
    result["requested_subject"] = subject or ""
    return result


def infer_subject_id(
    source_text: str,
    *,
    filename: str = "",
    explicit_subject: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Return a stable public subject ID and its resolved profile."""

    profile = resolve_subject_profile(
        explicit_subject,
        source_text=f"{filename}\n{source_text}",
    )
    requested = (explicit_subject or "").strip().lower().replace("_", "-")
    if requested:
        subject_id = requested.replace(" ", "-")
    else:
        preferred_ids = {
            "mathematics": "maths",
            "language_english": "english",
            "natural_science": "science",
            "social_science": "social-studies",
            "general_knowledge": "gk",
            "general_theory": "general",
        }
        subject_id = preferred_ids.get(profile["profile_id"], profile["profile_id"])
    return subject_id, profile


__all__ = [
    "infer_subject_id",
    "load_subject_profiles",
    "resolve_subject_profile",
]
