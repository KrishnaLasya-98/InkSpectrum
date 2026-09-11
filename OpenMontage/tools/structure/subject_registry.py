"""Subject registry — single source of truth for all supported subjects.

To add a new subject (e.g., Science, General Knowledge):
  1. Add an entry to SUBJECT_REGISTRY below
  2. Copy the extracted .md to opendataloader_output/ (or set md_path override)
  3. Run: python -m tools.structure.subject_pipeline_runner --subject <id>

No other code changes are required. The pipeline is subject-agnostic.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_ODL_DIR = Path(
    os.environ.get(
        "OPENDATALOADER_OUTPUT_DIR",
        r"C:\Users\user\Downloads\opendataloader_output",
    )
)

# ---------------------------------------------------------------------------
# Registry — add new subjects here
# ---------------------------------------------------------------------------
SUBJECT_REGISTRY: dict[str, dict[str, Any]] = {
    # ── Existing subjects (Class 1, RPS curriculum) ─────────────────────────
    "evs": {
        "label":        "Environmental Science",
        "chapter":      8,
        "title":        "Animal Life",
        "subject_type": "theory",
        "complexity":   "elementary",
        "audience":     "Class 1, ages 5-7",
        "duration_s":   480,
        "md_filename":  "RPS - EVS - CLASS 1 - INDIVIDUAL - B (2026) PRINTFILE-pages-2.md",
    },
    "english": {
        "label":        "English",
        "chapter":      1,
        "title":        "At the Beach",
        "subject_type": "mixed",
        "complexity":   "elementary",
        "audience":     "Class 1, ages 5-7",
        "duration_s":   360,
        "md_filename":  "RPS - ENGLISH - CLASS 1 - INDIVIDUAL - A (2026) PRINTFILE (2)-pages-2.md",
    },
    "maths": {
        "label":        "Mathematics",
        "chapter":      8,
        "title":        "2-Digit Numbers 51 to 100",
        "subject_type": "mathematics",
        "complexity":   "elementary",
        "audience":     "Class 1, ages 5-7",
        "duration_s":   480,
        "md_filename":  "RPS - MATHS - CLASS 1 - INDIVIDUAL - B (2026) PRINTFILE-pages-2.md",
    },

    # ── Extensible — add new subjects below ─────────────────────────────────
    # "science": {
    #     "label":        "Science",
    #     "chapter":      1,
    #     "title":        "Plants Around Us",
    #     "subject_type": "theory",
    #     "complexity":   "elementary",
    #     "audience":     "Class 1, ages 5-7",
    #     "duration_s":   480,
    #     "md_filename":  "<filename>.md",   # place in opendataloader_output/
    # },
    # "gk": {
    #     "label":        "General Knowledge",
    #     "chapter":      1,
    #     "title":        "My Country",
    #     "subject_type": "mixed",
    #     "complexity":   "elementary",
    #     "audience":     "Class 1, ages 5-7",
    #     "duration_s":   360,
    #     "md_filename":  "<filename>.md",
    # },
}


def get_subject(subject_id: str) -> dict[str, Any]:
    """Return registry entry; raises KeyError with clear message if not found."""
    if subject_id not in SUBJECT_REGISTRY:
        available = ", ".join(sorted(SUBJECT_REGISTRY))
        raise KeyError(
            f"Subject '{subject_id}' not registered. "
            f"Available: {available}\n"
            f"Add it to tools/structure/subject_registry.py to enable it."
        )
    return SUBJECT_REGISTRY[subject_id]


def md_path(subject_id: str) -> Path:
    """Return the Path to the extracted markdown for this subject."""
    reg = get_subject(subject_id)
    return _ODL_DIR / reg["md_filename"]


def all_subject_ids() -> list[str]:
    return sorted(SUBJECT_REGISTRY)
