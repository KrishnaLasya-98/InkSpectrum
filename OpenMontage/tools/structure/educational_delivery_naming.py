"""Canonical final-delivery naming for educational chapter videos."""
from __future__ import annotations

import re
from pathlib import Path


_PART_RE = re.compile(
    r"\b(?:volume|vol\.?|part|book)\s*[-_:]?\s*(\d+)\b",
    re.IGNORECASE,
)


def infer_book_part(source: str | Path) -> int | None:
    """Read a book part only from an explicit Volume/Part/Book token.

    Names such as ``chapter-pages-2.pdf`` intentionally return ``None``;
    page-extraction suffixes are not book-part metadata.
    """

    match = _PART_RE.search(Path(source).stem)
    return int(match.group(1)) if match else None


def _safe_component(value: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", str(value))
    return "-".join(words) or "Untitled"


def canonical_subject_label(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "", str(value).lower())
    fixed = {
        "evs": "EVS",
        "environmentalstudies": "EVS",
        "gk": "GK",
        "generalknowledge": "GK",
        "math": "Maths",
        "maths": "Maths",
        "mathematics": "Maths",
        "english": "English",
    }
    if normalized in fixed:
        return fixed[normalized]
    return "-".join(word.capitalize() for word in _safe_component(value).split("-"))


def delivery_folder_name(grade: int, subject_label: str) -> str:
    """Return ``Class-4-English`` style delivery folder names."""

    return f"Class-{int(grade)}-{canonical_subject_label(subject_label)}"


def delivery_video_name(
    *,
    grade: int,
    subject_label: str,
    chapter: int,
    chapter_title: str,
    book_part: int | None = None,
) -> str:
    """Return a stable, collision-safe final MP4 filename."""

    prefix = delivery_folder_name(grade, subject_label)
    part = f"-Part-{int(book_part):02d}" if book_part is not None else ""
    title = _safe_component(chapter_title)
    return f"{prefix}{part}-Chapter-{int(chapter):02d}-{title}.mp4"
