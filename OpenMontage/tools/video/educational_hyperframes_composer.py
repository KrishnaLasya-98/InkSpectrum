"""Deterministic, source-aware HyperFrames educational workspace composer.

This module is intentionally independent of ``subject_pipeline_runner``.  It is
the composition boundary for already-approved educational artifacts:

* a locked educational UI template contract,
* an educational plan,
* a rendered clip manifest,
* a measured narration manifest,
* an authoritative multimedia sync plan, and
* word-level captions.

The composer does not plan lessons, generate media, estimate timings, or repair
missing assets.  It fails closed when those upstream artifacts disagree.  Its
only side effect is a self-contained HyperFrames workspace with statically
registered muted videos, separate narration audio, source-aware teaching
panels, word-highlight captions, and a deterministic GSAP timeline.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml
from tools.video.exercise_visuals import prepare_visual, visual_html
from tools.video.class5_social_v4_presentation import CSS as CLASS5_SOCIAL_V4_CSS, VARIANT as CLASS5_SOCIAL_V4_VARIANT

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)


_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_TEMPLATE = _ROOT / "styles" / "hyperframes-educational-v1.yaml"
_TEMPLATE_PACKAGE_FILES = (
    _ROOT / "styles" / "hyperframes-educational-v1.yaml",
    Path(__file__).resolve(),
    _ROOT / "tools" / "video" / "exercise_visuals.py",
    _ROOT / "tools" / "structure" / "educational_pre_render_receipt.py",
    _ROOT / "tools" / "structure" / "educational_regression_gates.py",
)
_REQUIRED_COMPONENTS = {
    "opening_frame",
    "we_learn",
    "lesson_highlights",
    "concept_card",
    "recall",
    "glossary",
    "assessment",
    "subtitle_lane",
}
_STABLE_TYPES = {
    "recall",
    "glossary",
    "qa_item",
    "assessment",
    "mcq",
    "fill_blank",
    "activity",
    "life_skills",
    "worked_example",
    "table",
    "we_learn",
    "lesson_highlights",
}
_PATH_KEYS = ("output_path", "video_path", "clip_path", "audio_path", "path", "asset_path")
_WORDS_PER_CAPTION = 6
_TRANSITION_SECONDS = 0.55
_MOVING_SECTION_TRANSITION_SECONDS = 0.10


class EducationalCompositionError(ValueError):
    """Raised when an upstream artifact cannot produce a faithful workspace."""


@dataclass(frozen=True)
class _Artifact:
    data: Any
    base_dir: Path


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _sha256_value(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def educational_template_package_sha256() -> str:
    """Hash every file that defines the locked educational presentation.

    The YAML describes the approved slots and tokens; this compiler owns the
    actual HTML, CSS, and seekable GSAP implementation. Locking both prevents a
    chapter from silently changing component geometry while retaining the same
    YAML identity.
    """

    digest = hashlib.sha256()
    for path in _TEMPLATE_PACKAGE_FILES:
        relative = path.relative_to(_ROOT).as_posix()
        digest.update(f"{relative}\n".encode("utf-8"))
        digest.update(path.read_bytes())
        digest.update(b"\n")
    return digest.hexdigest()


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "section"


def _seconds(value: Any) -> float:
    try:
        return round(float(value), 3)
    except (TypeError, ValueError) as exc:
        raise EducationalCompositionError(f"Invalid timeline value: {value!r}") from exc


def _fmt_seconds(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".") or "0"


def _read_artifact(value: Any, *, base_dir: Path | None = None) -> _Artifact:
    if isinstance(value, (str, Path)):
        path = Path(value).expanduser().resolve()
        if not path.is_file():
            raise EducationalCompositionError(f"Artifact does not exist: {path}")
        if path.suffix.lower() in {".yaml", ".yml"}:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
        return _Artifact(data=data, base_dir=path.parent)
    return _Artifact(data=value, base_dir=(base_dir or Path.cwd()).resolve())


def _unwrap_list(value: Any, keys: Iterable[str]) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in keys:
            candidate = value.get(key)
            if isinstance(candidate, list):
                return candidate
    raise EducationalCompositionError(f"Expected a list artifact ({', '.join(keys)})")


def _resolve_asset(record: dict[str, Any], base_dir: Path) -> Path | None:
    for key in _PATH_KEYS:
        raw = record.get(key)
        if not raw:
            continue
        path = Path(str(raw)).expanduser()
        if not path.is_absolute():
            candidates = (
                (base_dir / path).resolve(),
                (_ROOT / path).resolve(),
                (Path.cwd() / path).resolve(),
            )
            path = next((candidate for candidate in candidates if candidate.is_file()), candidates[0])
        else:
            path = path.resolve()
        return path
    return None


def _source_ids(section: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("source_block_ids", "source_line_ids", "source_refs"):
        raw = section.get(key)
        if isinstance(raw, str):
            values.append(raw)
        elif isinstance(raw, list):
            values.extend(str(item) for item in raw if item)
    metadata = section.get("metadata")
    if isinstance(metadata, dict):
        for key in ("source_block_ids", "source_line_ids", "source_refs"):
            raw = metadata.get(key)
            if isinstance(raw, str):
                values.append(raw)
            elif isinstance(raw, list):
                values.extend(str(item) for item in raw if item)
    return list(dict.fromkeys(values))


def _section_type(section: dict[str, Any]) -> str:
    raw = str(
        section.get("source_block_type")
        or section.get("section_type")
        or section.get("type")
        or "concept"
    ).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "intro": "opening",
        "title": "opening",
        "opening_frame": "opening",
        "welearn": "we_learn",
        "learning_objectives": "we_learn",
        "highlights": "lesson_highlights",
        "lesson_highlight": "lesson_highlights",
        "quiz": "assessment",
        "question": "assessment",
        "true_false": "assessment",
        "fill_in_the_blanks": "fill_blank",
        "life_skill": "life_skills",
    }
    return aliases.get(raw, raw)


def _native_visual_theme(section: dict[str, Any]) -> str:
    """Choose a deterministic animated teaching visual from source wording.

    Native visuals are used when a chapter intentionally routes a concept to
    HyperFrames instead of a paid video provider.  They contain no invented
    labels or embedded prose: the source-faithful teaching panel and captions
    remain the only text surfaces.
    """
    text = " ".join(
        str(section.get(key) or "")
        for key in ("title", "description", "source_text", "narration_script")
    ).casefold()
    if "greenwich" in text or "time zone" in text or " gmt" in text:
        return "time"
    if "international date line" in text or " idl" in text or "180°" in text:
        return "date-line"
    if "longitude" in text or "meridian" in text or "eastern hemisphere" in text or "western hemisphere" in text:
        return "longitude"
    if "latitude" in text or "equator" in text or "parallel" in text or "climate" in text:
        return "latitude"
    if "ocean" in text:
        return "ocean"
    if "continent" in text or "country" in text or "map" in text:
        return "continents"
    if "coordinate" in text or "locate" in text or "location" in text:
        return "coordinates"
    return "globe"


def _native_visual_html(theme: str, sid: str) -> str:
    meridians = "".join(
        f'<span class="native-meridian native-meridian-{index}"></span>'
        for index in range(1, 6)
    )
    parallels = "".join(
        f'<span class="native-parallel native-parallel-{index}"></span>'
        for index in range(1, 6)
    )
    land = "".join(
        f'<span class="native-land native-land-{index}"></span>'
        for index in range(1, 5)
    )
    clocks = "".join(
        f'<span class="native-clock native-clock-{index}"><i></i><b></b></span>'
        for index in range(1, 4)
    ) if theme == "time" else ""
    pin = '<span class="native-pin"></span>' if theme == "coordinates" else ""
    return (
        f'<div id="native-{sid}" class="native-visual native-theme-{theme}" '
        'data-layout-ignore aria-hidden="true">'
        '<div class="native-orbit native-orbit-back"></div>'
        '<div class="native-globe">'
        f'{land}{meridians}{parallels}'
        '<span class="native-date-line"></span>'
        '</div>'
        '<div class="native-orbit native-orbit-front"></div>'
        f'{clocks}{pin}'
        '</div>'
    )


def _list_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        output: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                output.append(item.strip())
            elif isinstance(item, dict):
                text = item.get("text") or item.get("label") or item.get("question")
                if text:
                    output.append(str(text).strip())
        return output
    return []


def _source_fragments(section: dict[str, Any]) -> list[dict[str, str]]:
    """Return non-empty source fragments without changing their text."""

    fragments: list[dict[str, str]] = []
    for raw in section.get("source_fragments") or []:
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("source_text") or "").strip()
        if text:
            fragments.append({
                "text": text,
                "block_type": str(raw.get("block_type") or ""),
            })
    return fragments


def _source_lines(section: dict[str, Any]) -> list[str]:
    fragments = _source_fragments(section)
    if fragments:
        # Figure alt text describes an asset for routing and accessibility.
        # It is not textbook teaching prose, including in Recall/Remember.
        return [fragment["text"] for fragment in fragments if fragment["block_type"] != "figure"]
    return [
        line.strip()
        for line in str(section.get("source_text") or "").splitlines()
        if line.strip()
    ]


def _strip_exact_heading(lines: list[str], title: str) -> list[str]:
    if lines and title and lines[0].casefold() == title.casefold():
        return lines[1:]
    return lines


def _complete_source_line(section: dict[str, Any], displayed_chunk: str) -> str:
    """Expand a timed chunk to its complete, exact source line when possible."""

    needle = " ".join(displayed_chunk.split()).casefold()
    if not needle:
        return displayed_chunk
    matches = [
        fragment["text"]
        for fragment in _source_fragments(section)
        if needle in " ".join(fragment["text"].split()).casefold()
        and fragment["block_type"] not in {"section_heading", "heading", "title"}
    ]
    return min(matches, key=len) if matches else displayed_chunk


def _source_fragments_for_chunk(
    section: dict[str, Any], displayed_chunk: str
) -> list[dict[str, str]]:
    """Map a timed chunk back to every exact source line it overlaps."""

    needle = " ".join(displayed_chunk.split()).casefold()
    fragments = _source_fragments(section)
    if not needle or not fragments:
        return []
    normalized = [" ".join(fragment["text"].split()).casefold() for fragment in fragments]
    combined_parts: list[str] = []
    ranges: list[tuple[int, int]] = []
    cursor = 0
    for value in normalized:
        if combined_parts:
            combined_parts.append(" ")
            cursor += 1
        start = cursor
        combined_parts.append(value)
        cursor += len(value)
        ranges.append((start, cursor))
    combined = "".join(combined_parts)
    start = combined.find(needle)
    if start < 0:
        return []
    end = start + len(needle)
    matched = []
    for fragment, (fragment_start, fragment_end) in zip(fragments, ranges):
        if fragment_start >= end or fragment_end <= start:
            continue
        # Preserve a short source sentence (including decimal values), but do
        # not expand a spoken excerpt into an entire page-long paragraph.
        # Select complete overlapping sentences, never an ellipsis or summary.
        if fragment["block_type"] == "paragraph" and len(fragment["text"].split()) > 60:
            value = " ".join(fragment["text"].split())
            local_start = max(0, start - fragment_start)
            local_end = min(len(value), end - fragment_start)
            boundaries = [0] + [m.end() for m in re.finditer(r"(?<=[.!?])\s+(?=[A-Z])", value)] + [len(value)]
            sentences = [value[a:b].strip() for a, b in zip(boundaries, boundaries[1:])
                         if a < local_end and b > local_start]
            matched.append({**fragment, "text": " ".join(sentences)})
        else:
            matched.append(fragment)
    return matched


def _panel_content(
    section: dict[str, Any],
    plan: dict[str, Any],
) -> tuple[str, str, list[str]]:
    """Return source-aware heading, body and list items without invented copy."""
    kind = _section_type(section)
    title = str(section.get("title") or section.get("source_heading") or plan.get("title") or "").strip()
    body = ""
    items: list[str] = []
    source_lines = _source_lines(section)

    if kind == "opening":
        body = str(section.get("opening_tagline") or "").strip()
    elif kind == "we_learn":
        items = _list_strings(section.get("source_questions"))
        if not items or not _source_ids(section):
            raise EducationalCompositionError("We Learn requires PDF-linked source_questions; do not invent an opening box")
    elif kind == "lesson_highlights":
        items = _list_strings(section.get("source_topics"))
        if not items or not _source_ids(section):
            raise EducationalCompositionError("Highlights require PDF-linked source_topics; do not invent an opening box")
    elif kind == "glossary":
        term = str(section.get("source_term") or section.get("term") or title).strip()
        definition = str(section.get("source_definition") or section.get("definition") or "").strip()
        title, body = term, definition
    elif kind in {"assessment", "mcq", "fill_blank", "qa_item"}:
        exact_lines = _strip_exact_heading(source_lines, title)
        if exact_lines:
            items = exact_lines
        else:
            body = str(
                section.get("source_prompt")
                or section.get("question")
                or section.get("current_source_item")
                or section.get("description")
                or ""
            ).strip()
            items = _list_strings(section.get("source_options") or section.get("choices") or section.get("options"))
    elif kind == "table":
        # The structured cells are rendered separately. Never show the raw
        # Markdown pipes as a paragraph inside the teaching panel.
        body = ""
    elif kind in {"recall", "activity", "life_skills", "worked_example"}:
        exact_lines = _strip_exact_heading(source_lines, title)
        if exact_lines:
            body = exact_lines[0]
            items = exact_lines[1:]
        else:
            body = str(
                section.get("current_source_item")
                or section.get("source_instruction")
                or section.get("current_source_idea")
                or section.get("description")
                or ""
            ).strip()
            items = _list_strings(section.get("source_items"))
    else:
        source_content = [
            fragment["text"]
            for fragment in _source_fragments(section)
            if fragment["block_type"] not in {
                "chapter_title", "section_heading", "heading", "title", "figure"
            }
        ]
        source_headings = [
            fragment["text"]
            for fragment in _source_fragments(section)
            if fragment["block_type"] in {"section_heading", "heading", "title"}
        ]
        authored_source_idea = str(section.get("current_source_idea") or "").strip()
        # ``description`` is a production direction in educational plans, not
        # textbook copy. Never display it when PDF-linked content is present.
        if not authored_source_idea and source_content:
            return source_headings[-1] if source_headings else title, source_content[0], source_content[1:]
        body = str(
            authored_source_idea
            or section.get("source_text")
            or section.get("narration_script")
            or section.get("description")
            or ""
        ).strip()
        matched = _source_fragments_for_chunk(section, body)
        if matched:
            headings = [
                fragment["text"]
                for fragment in matched
                if fragment["block_type"] in {"section_heading", "heading", "title"}
            ]
            content = [
                fragment["text"]
                for fragment in matched
                if fragment["block_type"] not in {"section_heading", "heading", "title"}
            ]
            if headings:
                title = headings[-1]
            body = content[0] if content else ""
            items = content[1:]
        else:
            # Also avoid echoing a heading when legacy source fragments are not
            # available.  Equality is checked before punctuation trimming so a
            # source title like "Do You Know?" never degenerates to just "?".
            if title and body.casefold() == title.casefold():
                body = ""
            else:
                title_prefix = title.strip().rstrip(".:;!?")
                if title_prefix and body.casefold().startswith(title_prefix.casefold()):
                    remainder = body[len(title_prefix) :].lstrip(" .:;!?-\u2013\u2014")
                    if remainder:
                        body = remainder
            body = _complete_source_line(section, body)
        concepts = _list_strings(section.get("key_concepts"))
        if not body and concepts:
            body = concepts[0]

    return title, body, items


def _normalise_source_table(value: Any) -> dict[str, Any] | None:
    """Validate and normalize a source table without altering cell text."""

    if value in (None, {}):
        return None
    if not isinstance(value, dict):
        raise EducationalCompositionError("source_table must be an object")
    try:
        row_count = int(value.get("row_count"))
        column_count = int(value.get("column_count"))
        header_rows = int(value.get("header_rows") or 0)
    except (TypeError, ValueError) as exc:
        raise EducationalCompositionError("source_table dimensions must be integers") from exc
    if row_count <= 0 or column_count <= 0:
        raise EducationalCompositionError("source_table must contain at least one row and column")
    if not 0 <= header_rows <= row_count:
        raise EducationalCompositionError("source_table header_rows is outside the table")

    cells: list[dict[str, Any]] = []
    positions: set[tuple[int, int]] = set()
    for index, raw in enumerate(value.get("cells") or []):
        if not isinstance(raw, dict):
            raise EducationalCompositionError(f"source_table cell {index} must be an object")
        try:
            row = int(raw["row"])
            column = int(raw["column"])
            row_span = int(raw.get("row_span") or 1)
            column_span = int(raw.get("column_span") or 1)
        except (KeyError, TypeError, ValueError) as exc:
            raise EducationalCompositionError(
                f"source_table cell {index} has invalid coordinates"
            ) from exc
        if not (0 <= row < row_count and 0 <= column < column_count):
            raise EducationalCompositionError(
                f"source_table cell {index} is outside the declared dimensions"
            )
        if row_span < 1 or column_span < 1:
            raise EducationalCompositionError(
                f"source_table cell {index} has a non-positive span"
            )
        if (row, column) in positions:
            raise EducationalCompositionError(
                f"source_table contains duplicate cell position {row},{column}"
            )
        positions.add((row, column))
        cells.append({
            "row": row,
            "column": column,
            "text": str(raw.get("text") or ""),
            "row_span": row_span,
            "column_span": column_span,
            "is_header": bool(raw.get("is_header") or row < header_rows),
        })
    if not cells:
        raise EducationalCompositionError("source_table has no cells")
    return {
        "row_count": row_count,
        "column_count": column_count,
        "header_rows": header_rows,
        "cells": sorted(cells, key=lambda cell: (cell["row"], cell["column"])),
    }


def _panel_record(section: dict[str, Any], plan: dict[str, Any], kind: str) -> dict[str, Any]:
    """Build one source-only panel record shared by authoring and repair."""

    heading, body, items = _panel_content(section, plan)
    source_table = _normalise_source_table(section.get("source_table"))
    if kind == "table" and source_table is None:
        raise EducationalCompositionError(
            f"Table section {section.get('section_id') or '<unknown>'} is missing its structured source_table"
        )
    explicit_label = str(
        section.get("section_label") or section.get("source_label") or ""
    ).strip()
    if explicit_label:
        section_label = explicit_label
        panel_heading = "" if explicit_label.casefold() == heading.casefold() else heading
    elif body or items:
        section_label = heading
        panel_heading = ""
    else:
        section_label = ""
        panel_heading = heading
    return {
        "section_label": section_label,
        "heading": panel_heading,
        "body": body,
        "items": items,
        "table": source_table,
    }


def _normalise_word(raw: dict[str, Any], index: int) -> dict[str, Any]:
    word = str(raw.get("word") or raw.get("text") or "").strip()
    if not word:
        raise EducationalCompositionError(f"Caption word {index} is empty")
    if "startMs" in raw:
        start_ms = int(round(float(raw["startMs"])))
        end_ms = int(round(float(raw.get("endMs", raw["startMs"]))))
    elif "start_ms" in raw:
        start_ms = int(round(float(raw["start_ms"])))
        end_ms = int(round(float(raw.get("end_ms", raw["start_ms"]))))
    else:
        start_ms = int(round(float(raw.get("start", 0)) * 1000))
        end_ms = int(round(float(raw.get("end", raw.get("start", 0))) * 1000))
    if start_ms < 0 or end_ms <= start_ms:
        raise EducationalCompositionError(
            f"Caption word {index} has invalid timing {start_ms}-{end_ms} ms"
        )
    return {
        "word": word,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "page_break_after": bool(raw.get("pageBreakAfter") or raw.get("page_break_after")),
        "section_id": str(raw.get("section_id") or ""),
    }


def _caption_groups(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    for word in words:
        # Acoustic forced alignment excludes quiet consonant/word gaps. A
        # 180 ms threshold turned natural delivery into one-word fragments.
        # Keep readable phrases; sentence/page boundaries still take priority.
        if current and (
            word["start_ms"] - current[-1]["end_ms"] >= 650
            or word.get("section_id") != current[-1].get("section_id")
        ):
            groups.append({"words": current})
            current = []
        current.append(word)
        boundary = word["page_break_after"] or bool(re.search(r"[.!?][\"')\]]?$", word["word"]))
        if boundary or len(current) >= _WORDS_PER_CAPTION:
            groups.append({"words": current})
            current = []
    if current:
        groups.append({"words": current})

    result: list[dict[str, Any]] = []
    for index, group in enumerate(groups):
        group_words = group["words"]
        result.append({
            "group_id": f"caption-{index + 1:04d}",
            "start_seconds": round(group_words[0]["start_ms"] / 1000, 3),
            "end_seconds": round(group_words[-1]["end_ms"] / 1000, 3),
            "text": " ".join(item["word"] for item in group_words),
            "words": group_words,
        })
    # Keep the current phrase readable through natural punctuation pauses.
    # The active word still follows measured speech timings, but the lane no
    # longer flashes empty between adjacent phrases.
    if result:
        result[0]["start_seconds"] = 0.0
        for index in range(len(result) - 1):
            result[index]["end_seconds"] = result[index + 1]["start_seconds"]
    return result


class EducationalHyperFramesComposer(BaseTool):
    """Materialize a locked, source-faithful educational HyperFrames workspace."""

    name = "educational_hyperframes_composer"
    version = "1.0.0"
    tier = ToolTier.CORE
    capability = "educational_video_composition"
    provider = "hyperframes"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL
    dependencies = ["python:yaml"]
    install_instructions = "Install PyYAML. Rendering additionally requires the HyperFrames CLI."
    agent_skills = ["hyperframes", "gsap"]
    capabilities = [
        "locked_educational_template",
        "static_timed_media",
        "word_highlight_captions",
        "source_aware_teaching_panels",
        "crossfade_transitions",
    ]
    side_effects = ["writes a self-contained HyperFrames workspace"]
    user_visible_verification = [
        "Run npx hyperframes lint in the emitted workspace",
        "Run npx hyperframes validate and inspect before rendering",
        "Verify the encoded MP4 with contact sheets and ffprobe",
    ]

    input_schema = {
        "type": "object",
        "required": [
            "workspace_path",
            "template_contract",
            "educational_plan",
            "clip_manifest",
            "narration_manifest",
            "multimedia_sync_plan",
            "word_captions",
        ],
        "properties": {
            "workspace_path": {"type": "string"},
            "template_contract": {"type": ["object", "string"]},
            "educational_plan": {"type": ["object", "string"]},
            "clip_manifest": {"type": ["array", "object", "string"]},
            "narration_manifest": {"type": ["object", "string"]},
            "multimedia_sync_plan": {"type": ["object", "string"]},
            "word_captions": {"type": ["array", "object", "string"]},
            "asset_base_dir": {"type": "string"},
            "template_package_sha256": {"type": "string"},
            "strict_educational_regression": {"type": "boolean"},
            "pre_render_regression_receipt": {"type": "string"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "workspace_path": {"type": "string"},
            "index_html": {"type": "string"},
            "design_md": {"type": "string"},
            "timeline_json": {"type": "string"},
            "hyperframes_json": {"type": "string"},
            "template_sha256": {"type": "string"},
            "template_package_sha256": {"type": "string"},
            "duration_seconds": {"type": "number"},
        },
    }

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 0.03 * len(inputs.get("clip_manifest", [])) if isinstance(inputs.get("clip_manifest"), list) else 0.2

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.monotonic()
        try:
            data = self.compose(inputs)
            return ToolResult(
                success=True,
                data=data,
                artifacts=["index.html", "DESIGN.md", "timeline.json", "hyperframes.json"],
                duration_seconds=time.monotonic() - started,
            )
        except (EducationalCompositionError, OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
            return ToolResult(
                success=False,
                error=str(exc),
                duration_seconds=time.monotonic() - started,
            )

    def compose(self, inputs: dict[str, Any]) -> dict[str, Any]:
        base_dir = Path(inputs.get("asset_base_dir") or Path.cwd()).expanduser().resolve()
        receipt_path = str(inputs.get("pre_render_regression_receipt") or "").strip()
        if inputs.get("strict_educational_regression") and not receipt_path:
            raise EducationalCompositionError(
                "Strict educational composition requires a hash-bound pre-render regression receipt"
            )
        if receipt_path:
            from tools.structure.educational_pre_render_receipt import verify_pre_render_receipt
            try:
                verify_pre_render_receipt(receipt_path)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                raise EducationalCompositionError(
                    f"Pre-render regression receipt verification failed: {exc}"
                ) from exc
        template_artifact = _read_artifact(inputs.get("template_contract", _DEFAULT_TEMPLATE), base_dir=base_dir)
        template, template_sha = self._load_template(template_artifact)
        package_sha = educational_template_package_sha256()
        expected_package_sha = str(inputs.get("template_package_sha256") or "").strip()
        if expected_package_sha and expected_package_sha != package_sha:
            raise EducationalCompositionError(
                "Educational template package SHA-256 mismatch: expected "
                f"{expected_package_sha}, found {package_sha}"
            )
        plan_artifact = _read_artifact(inputs["educational_plan"], base_dir=base_dir)
        clip_artifact = _read_artifact(inputs["clip_manifest"], base_dir=base_dir)
        narration_artifact = _read_artifact(inputs["narration_manifest"], base_dir=base_dir)
        sync_artifact = _read_artifact(inputs["multimedia_sync_plan"], base_dir=base_dir)
        captions_artifact = _read_artifact(inputs["word_captions"], base_dir=base_dir)

        plan = plan_artifact.data
        if not isinstance(plan, dict):
            raise EducationalCompositionError("educational_plan must be an object")
        sections = _unwrap_list(plan.get("sections"), ("sections",))
        section_map = {str(item.get("section_id") or ""): item for item in sections}
        if "" in section_map or len(section_map) != len(sections):
            raise EducationalCompositionError("Educational section IDs must be present and unique")

        clips = _unwrap_list(clip_artifact.data, ("clips", "clip_manifest", "items"))
        clip_map = {str(item.get("section_id") or ""): item for item in clips}
        narration = narration_artifact.data
        if not isinstance(narration, dict):
            raise EducationalCompositionError("narration_manifest must be an object")
        narration_segments = _unwrap_list(narration.get("segments"), ("segments",))
        narration_map = {str(item.get("section_id") or ""): item for item in narration_segments}

        sync = sync_artifact.data
        if isinstance(sync, dict) and isinstance(sync.get("sync_plan"), dict):
            sync = sync["sync_plan"]
        if not isinstance(sync, dict):
            raise EducationalCompositionError("multimedia_sync_plan must be an object")
        self._validate_sync_plan(sync)
        timeline_items = _unwrap_list(sync.get("timeline"), ("timeline",))
        total_duration = _seconds(sync.get("total_duration_seconds") or timeline_items[-1]["end_seconds"])

        raw_captions = _unwrap_list(captions_artifact.data, ("word_captions", "captions", "words"))
        words = [_normalise_word(item, index) for index, item in enumerate(raw_captions)]
        words.sort(key=lambda item: (item["start_ms"], item["end_ms"]))
        if not words:
            raise EducationalCompositionError("word_captions must not be empty")
        if words[-1]["end_ms"] > int(round(total_duration * 1000)) + 150:
            raise EducationalCompositionError("Word captions extend beyond the authoritative timeline")
        groups = _caption_groups(words)
        if groups:
            groups[-1]["end_seconds"] = total_duration

        workspace = Path(inputs["workspace_path"]).expanduser().resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        video_dir = workspace / "assets" / "video"
        audio_dir = workspace / "assets" / "audio"
        image_dir = workspace / "assets" / "images"
        video_dir.mkdir(parents=True, exist_ok=True)
        audio_dir.mkdir(parents=True, exist_ok=True)
        image_dir.mkdir(parents=True, exist_ok=True)

        built_sections = self._build_sections(
            timeline_items=timeline_items,
            total_duration=total_duration,
            section_map=section_map,
            clip_map=clip_map,
            narration_map=narration_map,
            clip_base_dir=clip_artifact.base_dir,
            narration_base_dir=narration_artifact.base_dir,
            video_dir=video_dir,
            audio_dir=audio_dir,
            image_dir=image_dir,
            workspace=workspace,
            plan=plan,
        )
        self._validate_caption_coverage(words, built_sections)
        from tools.analysis.narration_text_syncer import _build_qa_card_props
        for section in built_sections:
            source_section = section_map[section["section_id"]]
            questions = (source_section.get("teaching_contract") or {}).get("questions") or source_section.get("qa_pairs", [])
            if not questions:
                continue
            start_ms = round(section["start_seconds"] * 1000)
            end_ms = round(section["end_seconds"] * 1000)
            section_words = [w for w in words if start_ms <= w["start_ms"] and w["end_ms"] <= end_ms]
            try:
                cards = _build_qa_card_props([{"words": section_words}], questions, start_ms)
            except ValueError as exc:
                raise EducationalCompositionError(f"Exercise timing for {section['section_id']}: {exc}") from exc
            if not cards:
                raise EducationalCompositionError(f"Exercise words missing for {section['section_id']}")
            for index, (question, card) in enumerate(zip(questions, cards)):
                latest = cards[index+1]["question_start_seconds"] if index+1 < len(cards) else section["duration_seconds"]
                try:
                    card["visual"] = prepare_visual(question, section_words, section["start_seconds"],
                        card["thinking_end_seconds"], latest, plan_artifact.base_dir,
                        workspace / "assets" / "exercises")
                except (ValueError, OSError) as exc:
                    raise EducationalCompositionError(f"Exercise visual for {section['section_id']}: {exc}") from exc
            section["exercise_cards"] = cards

        timeline = {
            "version": "1.0",
            "composition_id": "educational-main",
            "duration_seconds": total_duration,
            "fps": int(template["canvas"]["frame_rate"]),
            "audio_is_timing_authority": True,
            "template": {
                "id": template["id"],
                "version": template["version"],
                "status": template["status"],
                "presentation_contract": template["presentation_contract"],
                "sha256": template_sha,
                "package_sha256": package_sha,
            },
            "transition": {"type": "crossfade", "duration_seconds": _TRANSITION_SECONDS},
            "sections": built_sections,
            "caption_groups": groups,
        }

        presentation_variant = str(inputs.get("presentation_variant") or "").strip()
        if presentation_variant and presentation_variant != CLASS5_SOCIAL_V4_VARIANT:
            raise EducationalCompositionError(f"Unknown presentation variant: {presentation_variant}")
        if presentation_variant:
            timeline["presentation_variant"] = presentation_variant
        design_text = self._render_design(template, template_sha)
        if presentation_variant:
            design_text += (
                "\n## Approved Class 5 Social Chapter 1 presentation\n\n"
                "Use the verified Chapter 1 revision-v4 mint canvas, cream cards, "
                "left heading label, source figure layout, and bottom word-highlight lane. "
                "No dark-navy empty backgrounds or red hanging tabs.\n"
            )
        # DESIGN.md is deliberately written before index.html: visual identity is
        # an authored prerequisite, not documentation inferred after the fact.
        design_path = workspace / "DESIGN.md"
        design_path.write_text(design_text, encoding="utf-8", newline="\n")
        html_text = self._render_html(template, plan, timeline, presentation_variant)
        index_path = workspace / "index.html"
        index_path.write_text(html_text, encoding="utf-8", newline="\n")
        timeline_path = workspace / "timeline.json"
        timeline_path.write_text(
            json.dumps(timeline, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        config_path = workspace / "hyperframes.json"
        config_path.write_text(
            json.dumps(
                {
                    "version": 3,
                    "name": str(plan.get("title") or "Educational chapter"),
                    "width": int(template["canvas"]["width_px"]),
                    "height": int(template["canvas"]["height_px"]),
                    "fps": int(template["canvas"]["frame_rate"]),
                    "duration": total_duration,
                    "media": {"autoProxy": True},
                },
                indent=2,
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return {
            "workspace_path": str(workspace),
            "index_html": str(index_path),
            "design_md": str(design_path),
            "timeline_json": str(timeline_path),
            "hyperframes_json": str(config_path),
            "template_sha256": template_sha,
            "template_package_sha256": package_sha,
            "duration_seconds": total_duration,
            "section_count": len(built_sections),
            "caption_group_count": len(groups),
            "video_count": sum(
                len(item.get("videos") or []) or bool(item.get("video"))
                for item in built_sections
            ),
            "audio_count": len(built_sections),
        }

    def refresh_existing_workspace(
        self,
        *,
        workspace_path: str | Path,
        educational_plan: str | Path | dict[str, Any],
        template_contract: str | Path | dict[str, Any] = _DEFAULT_TEMPLATE,
    ) -> dict[str, Any]:
        """Rebuild authored text/layout while preserving measured media timing."""

        workspace = Path(workspace_path).expanduser().resolve()
        timeline_path = workspace / "timeline.json"
        if not timeline_path.is_file():
            raise EducationalCompositionError(f"Existing timeline is missing: {timeline_path}")
        timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
        plan = _read_artifact(educational_plan).data
        if not isinstance(plan, dict):
            raise EducationalCompositionError("educational_plan must be an object")
        template, template_sha = self._load_template(_read_artifact(template_contract))
        section_map = {
            str(section.get("section_id") or ""): section
            for section in _unwrap_list(plan.get("sections"), ("sections",))
        }
        for authored in timeline.get("sections") or []:
            section_id = str(authored.get("section_id") or "")
            source = section_map.get(section_id)
            if source is None:
                raise EducationalCompositionError(
                    f"Existing timeline section {section_id!r} is absent from the educational plan"
                )
            kind = _section_type(source)
            authored["kind"] = kind
            authored["panel"] = _panel_record(source, plan, kind)
        timeline["template"].update({
            "sha256": template_sha,
            "package_sha256": educational_template_package_sha256(),
        })
        design_path = workspace / "DESIGN.md"
        index_path = workspace / "index.html"
        design_path.write_text(
            self._render_design(template, template_sha), encoding="utf-8", newline="\n"
        )
        index_path.write_text(
            self._render_html(template, plan, timeline), encoding="utf-8", newline="\n"
        )
        timeline_path.write_text(
            json.dumps(timeline, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return {
            "workspace_path": str(workspace),
            "index_html": str(index_path),
            "design_md": str(design_path),
            "timeline_json": str(timeline_path),
            "duration_seconds": float(timeline["duration_seconds"]),
            "section_count": len(timeline.get("sections") or []),
        }

    @staticmethod
    def _load_template(artifact: _Artifact) -> tuple[dict[str, Any], str]:
        candidate = artifact.data
        declared_sha = None
        if isinstance(candidate, dict) and "palette" not in candidate and candidate.get("path"):
            declared_sha = candidate.get("sha256")
            path = Path(str(candidate["path"]))
            if not path.is_absolute():
                project_path = (_ROOT / path).resolve()
                artifact_path = (artifact.base_dir / path).resolve()
                path = project_path if project_path.is_file() else artifact_path
            loaded = _read_artifact(path)
            candidate = loaded.data
        if not isinstance(candidate, dict):
            raise EducationalCompositionError("template_contract must be a YAML/JSON object")
        required_values = {
            "status": "locked",
            "runtime": "hyperframes",
            "presentation_contract": "source-faithful-book-v1",
        }
        for key, expected in required_values.items():
            if candidate.get(key) != expected:
                raise EducationalCompositionError(
                    f"Template contract {key} must be {expected!r}; found {candidate.get(key)!r}"
                )
        if not candidate.get("id") or not candidate.get("version"):
            raise EducationalCompositionError("Template contract requires id and version")
        canvas = candidate.get("canvas") or {}
        if (canvas.get("width_px"), canvas.get("height_px"), canvas.get("frame_rate")) != (1920, 1080, 30):
            raise EducationalCompositionError("Educational template canvas is locked to 1920x1080 at 30 fps")
        override = candidate.get("override_policy") or {}
        for key in ("chapter_css_overrides", "chapter_layout_overrides", "chapter_palette_overrides"):
            if override.get(key) is not False:
                raise EducationalCompositionError(f"Template override policy {key} must remain false")
        components = set((candidate.get("component_contract") or {}).keys())
        missing = sorted(_REQUIRED_COMPONENTS - components)
        if missing:
            raise EducationalCompositionError(
                "Template contract is missing locked components: " + ", ".join(missing)
            )
        digest = _sha256_value(candidate)
        if declared_sha and declared_sha != digest:
            raise EducationalCompositionError(
                f"Template SHA-256 mismatch: expected {declared_sha}, found {digest}"
            )
        return candidate, digest

    @staticmethod
    def _validate_sync_plan(sync: dict[str, Any]) -> None:
        if sync.get("status") not in (None, "pass"):
            raise EducationalCompositionError("Multimedia sync plan is blocked")
        critical = [
            item for item in sync.get("issues", [])
            if str(item.get("severity", "critical")).lower() == "critical"
        ]
        if critical:
            raise EducationalCompositionError(
                "Multimedia sync plan contains critical issues: "
                + ", ".join(str(item.get("code") or "unknown") for item in critical)
            )
        items = _unwrap_list(sync.get("timeline"), ("timeline",))
        cursor = 0.0
        seen: set[str] = set()
        for index, item in enumerate(items):
            section_id = str(item.get("section_id") or "")
            if not section_id or section_id in seen:
                raise EducationalCompositionError("Sync timeline section IDs must be present and unique")
            seen.add(section_id)
            start = _seconds(item.get("start_seconds"))
            end = _seconds(item.get("end_seconds"))
            if end <= start:
                raise EducationalCompositionError(f"Section {section_id} has non-positive duration")
            if index == 0 and abs(start) > 0.01:
                raise EducationalCompositionError(
                    "The first narrated section must begin at 0 seconds; use an explicit opening section"
                )
            if abs(start - cursor) > 0.05:
                raise EducationalCompositionError(
                    f"Timeline gap or overlap before {section_id}: expected {cursor:.3f}, found {start:.3f}"
                )
            policy = str(item.get("visual_duration_policy") or "as_is")
            if policy in {"missing", "regenerate_motion_coverage"}:
                raise EducationalCompositionError(
                    f"Section {section_id} is not composition-ready: {policy}"
                )
            cursor = end

    def _build_sections(
        self,
        *,
        timeline_items: list[dict[str, Any]],
        total_duration: float,
        section_map: dict[str, dict[str, Any]],
        clip_map: dict[str, dict[str, Any]],
        narration_map: dict[str, dict[str, Any]],
        clip_base_dir: Path,
        narration_base_dir: Path,
        video_dir: Path,
        audio_dir: Path,
        image_dir: Path,
        workspace: Path,
        plan: dict[str, Any],
    ) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        used_videos: dict[Path, str] = {}
        voices: set[str] = set()
        for index, timing in enumerate(timeline_items):
            section_id = str(timing["section_id"])
            section = section_map.get(section_id)
            clip = clip_map.get(section_id)
            narration = narration_map.get(section_id)
            if section is None:
                raise EducationalCompositionError(f"Missing educational-plan section {section_id}")
            if clip is None:
                raise EducationalCompositionError(f"Missing clip-manifest record for {section_id}")
            if narration is None:
                raise EducationalCompositionError(f"Missing narration-manifest segment for {section_id}")
            if clip.get("success") is False:
                raise EducationalCompositionError(f"Clip generation failed for {section_id}")

            start = _seconds(timing["start_seconds"])
            end = _seconds(timing["end_seconds"])
            duration = round(end - start, 3)
            narration_duration = _seconds(narration.get("duration_seconds") or duration)
            body_offset = float(narration.get("body_start_seconds") or 0)
            heading_duration = float(narration.get("heading_duration_seconds") or 0)
            inline_title_pause = narration.get("heading_pause_presentation") == "inline"
            if abs(narration_duration - duration) > 0.15:
                raise EducationalCompositionError(
                    f"Narration duration disagrees with sync plan for {section_id}: "
                    f"{narration_duration:.3f}s vs {duration:.3f}s"
                )
            voice = str(narration.get("voice_used") or narration.get("voice_id") or "").strip()
            if voice:
                voices.add(voice)

            audio_source = _resolve_asset(narration, narration_base_dir)
            if audio_source is None or not audio_source.is_file():
                raise EducationalCompositionError(f"Narration audio is missing for {section_id}")
            audio_name = f"{index + 1:03d}-{_slug(section_id)}{audio_source.suffix.lower()}"
            audio_target = audio_dir / audio_name
            if audio_source != audio_target:
                shutil.copyfile(audio_source, audio_target)
            audio_rel = audio_target.relative_to(workspace).as_posix()

            kind = _section_type(section)
            visual_segments = clip.get("visual_segments")
            if visual_segments is not None and not isinstance(visual_segments, list):
                raise EducationalCompositionError(
                    f"visual_segments must be a list for {section_id}"
                )
            if visual_segments and _resolve_asset(clip, clip_base_dir) is not None:
                raise EducationalCompositionError(
                    f"{section_id} cannot mix a legacy visual clip with visual_segments"
                )
            video_source = None if visual_segments else _resolve_asset(clip, clip_base_dir)
            video_data: dict[str, Any] | None = None
            video_segments_data: list[dict[str, Any]] = []
            for segment_index, visual in enumerate(visual_segments or []):
                if not isinstance(visual, dict):
                    raise EducationalCompositionError(
                        f"visual_segments[{segment_index}] must be an object for {section_id}"
                    )
                source = _resolve_asset(visual, clip_base_dir)
                if source is None or not source.is_file():
                    raise EducationalCompositionError(
                        f"Visual segment is missing for {section_id} at index {segment_index}"
                    )
                prior = used_videos.get(source)
                if prior is not None:
                    raise EducationalCompositionError(
                        f"Visual asset reuse is forbidden by default: {section_id} reuses {prior}"
                    )
                offset = _seconds(visual.get("offset_seconds"))
                segment_duration = _seconds(visual.get("duration_seconds"))
                segment_transition = str(visual.get("transition") or "crossfade")
                if segment_transition not in {"crossfade", "cut"}:
                    raise EducationalCompositionError(
                        f"Unsupported visual transition for {section_id}: {segment_transition}"
                    )
                if offset < 0 or segment_duration <= 0 or offset + segment_duration > duration + 0.02:
                    raise EducationalCompositionError(
                        f"Visual segment timing exceeds {section_id}: "
                        f"offset={offset:.3f}, duration={segment_duration:.3f}, section={duration:.3f}"
                    )
                used_videos[source] = section_id
                video_name = f"{index + 1:03d}-{_slug(section_id)}-{segment_index + 1:02d}{source.suffix.lower()}"
                video_target = video_dir / video_name
                if source != video_target:
                    shutil.copyfile(source, video_target)
                video_segments_data.append({
                    "path": video_target.relative_to(workspace).as_posix(),
                    "sha256": _sha256_file(video_target),
                    "start_seconds": round(start + offset, 3),
                    "duration_seconds": round(segment_duration, 3),
                    "track_index": 1000 + index * 100 + segment_index,
                    "muted": True,
                    "transition": segment_transition,
                })
            if video_source is not None:
                if not video_source.is_file():
                    raise EducationalCompositionError(f"Visual clip is missing for {section_id}: {video_source}")
                prior = used_videos.get(video_source)
                if prior is not None:
                    raise EducationalCompositionError(
                        f"Visual asset reuse is forbidden by default: {section_id} reuses {prior}"
                    )
                used_videos[video_source] = section_id
                video_name = f"{index + 1:03d}-{_slug(section_id)}{video_source.suffix.lower()}"
                video_target = video_dir / video_name
                if video_source != video_target:
                    shutil.copyfile(video_source, video_target)
                media_start = 0.0 if index == 0 else max(0.0, start - _TRANSITION_SECONDS)
                if body_offset and kind != "opening":
                    media_start = start + body_offset
                media_end = end
                video_data = {
                    "path": video_target.relative_to(workspace).as_posix(),
                    "sha256": _sha256_file(video_target),
                    "start_seconds": round(media_start, 3),
                    "duration_seconds": round(media_end - media_start, 3),
                    "track_index": index % 2,
                    "muted": True,
                }
            elif not video_segments_data and kind not in _STABLE_TYPES and str(clip.get("render_mode") or section.get("render_mode")) not in {"hyperframes", "remotion"}:
                raise EducationalCompositionError(
                    f"Motion section {section_id} requires a rendered visual clip"
                )
            native_visual_theme = (
                _native_visual_theme(section)
                if video_data is None and not video_segments_data and kind not in _STABLE_TYPES
                else ""
            )

            panel = _panel_record(section, plan, kind)
            panel_pages: list[dict[str, Any]] = []
            raw_pages = clip.get("teaching_pages") or []
            if raw_pages:
                if not isinstance(raw_pages, list):
                    raise EducationalCompositionError(f"teaching_pages must be a list for {section_id}")
                expected_text = " ".join([panel["body"], *panel["items"]]).split()
                actual_text: list[str] = []
                previous_end = 0.0
                for page_index, raw_page in enumerate(raw_pages):
                    if not isinstance(raw_page, dict):
                        raise EducationalCompositionError(f"Invalid teaching page {page_index} for {section_id}")
                    page_text = str(raw_page.get("text") or "").strip()
                    page_start = _seconds(raw_page.get("start_offset_seconds"))
                    page_end = _seconds(raw_page.get("end_offset_seconds"))
                    if not page_text or abs(page_start - previous_end) > 0.02 or page_end <= page_start or page_end > duration + 0.02:
                        raise EducationalCompositionError(f"Invalid teaching page timing/text for {section_id} page {page_index}")
                    actual_text.extend(page_text.split())
                    panel_pages.append({
                        "text": page_text,
                        "start_seconds": round(start + page_start, 3),
                        "end_seconds": round(start + page_end, 3),
                    })
                    previous_end = page_end
                if abs(previous_end - duration) > 0.02 or actual_text != expected_text:
                    raise EducationalCompositionError(f"Teaching pages must preserve all source panel text and cover {section_id}")
            figures: list[dict[str, Any]] = []
            for figure_index, figure in enumerate(clip.get("source_figure_overlays") or []):
                if not isinstance(figure, dict):
                    raise EducationalCompositionError(f"Invalid source figure for {section_id}")
                raw_path = str(figure.get("path") or "").strip()
                path = Path(raw_path)
                candidates = ([path] if path.is_absolute() else [
                    clip_base_dir / path,
                    clip_base_dir / "assets" / "images" / path,
                    clip_base_dir / "artifacts" / "images" / path,
                ])
                source = next((candidate.resolve() for candidate in candidates if candidate.is_file()), None)
                if source is None or source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                    raise EducationalCompositionError(f"Missing or unsupported source figure for {section_id}: {raw_path}")
                offset = _seconds(figure.get("offset_seconds"))
                figure_duration = _seconds(figure.get("duration_seconds"))
                if offset < 0 or figure_duration <= 0 or offset + figure_duration > duration + 0.02:
                    raise EducationalCompositionError(f"Source figure timing exceeds {section_id}")
                target = image_dir / f"{index + 1:03d}-{_slug(section_id)}-{figure_index + 1:02d}{source.suffix.lower()}"
                if source != target:
                    shutil.copyfile(source, target)
                figures.append({
                    "path": target.relative_to(workspace).as_posix(),
                    "sha256": _sha256_file(target),
                    "authored_caption": str(figure.get("authored_caption") or "Original textbook figure").strip(),
                    "start_seconds": round(start + offset, 3),
                    "end_seconds": round(start + offset + figure_duration, 3),
                })
            output.append({
                "section_id": section_id,
                "kind": kind,
                "start_seconds": start,
                "end_seconds": end,
                "duration_seconds": duration,
                "heading_hold": {
                    "start_seconds": start + heading_duration,
                    "end_seconds": start + body_offset,
                    "title": str(section.get("title") or ""),
                } if body_offset > heading_duration and not inline_title_pause else None,
                "inline_title_pause": {
                    "start_seconds": start + heading_duration,
                    "end_seconds": start + body_offset,
                } if body_offset > heading_duration and inline_title_pause else None,
                "heading_holds": [dict(hold, start_seconds=start + hold["start_seconds"],
                                       end_seconds=start + hold["end_seconds"])
                                  for hold in narration.get("heading_holds", [])],
                "topic_pause_start": end - float(narration.get("topic_end_pause_seconds") or 0),
                "source_block_ids": _source_ids(section),
                "source_document_block_type": str(
                    section.get("source_document_block_type") or ""
                ),
                "source_semantic_role": str(
                    section.get("source_semantic_role") or ""
                ),
                "source_page_number": section.get("source_page_number"),
                "source_bbox": list(section.get("source_bbox") or []),
                "panel": panel,
                "panel_pages": panel_pages,
                "figures": figures,
                "video": video_data,
                "videos": video_segments_data,
                "native_visual_theme": native_visual_theme,
                "audio": {
                    "path": audio_rel,
                    "sha256": _sha256_file(audio_target),
                    "start_seconds": start,
                    "duration_seconds": duration,
                    # Alternate narration tracks so sub-frame media-duration
                    # rounding cannot be misreported as same-track overlap.
                    "track_index": 10 + (index % 2),
                    "volume": 1,
                },
                "visual_duration_policy": str(timing.get("visual_duration_policy") or "as_is"),
            })
        if len(voices) > 1:
            raise EducationalCompositionError(
                "Narrator identity changes within the chapter: " + ", ".join(sorted(voices))
            )
        if output[-1]["end_seconds"] != total_duration:
            raise EducationalCompositionError("Sync-plan total duration does not match its final section")
        return output

    @staticmethod
    def _validate_caption_coverage(words: list[dict[str, Any]], sections: list[dict[str, Any]]) -> None:
        for section in sections:
            start_ms = int(round(section["start_seconds"] * 1000))
            end_ms = int(round(section["end_seconds"] * 1000))
            if not any(word["start_ms"] < end_ms and word["end_ms"] > start_ms for word in words):
                raise EducationalCompositionError(
                    f"No word captions overlap narrated section {section['section_id']}"
                )

    @staticmethod
    def _render_design(template: dict[str, Any], template_sha: str) -> str:
        palette = template["palette"]
        return f"""# Educational HyperFrames Design Contract

## Template Lock

- ID: `{template['id']}`
- Version: `{template['version']}`
- Status: `{template['status']}`
- Presentation contract: `{template['presentation_contract']}`
- Canonical SHA-256: `{template_sha}`

## Style Prompt

A warm, source-faithful classroom film for young learners. Full-frame motion carries the story while compact cream teaching panels explain only the current textbook idea. The frame has clear edge anchors, generous safe areas, readable hierarchy, and one stable word-highlight subtitle lane.

## Colors

- Cream `{palette['cream']}`: teaching panels and subtitle lane
- Ink `{palette['ink']}`: primary text
- Teaching accent `{palette['teaching_accent']}`: headings and rules
- Active word `{palette['highlight_active']}`: currently spoken word
- Inactive word `{palette['highlight_inactive']}`: surrounding subtitle words

## Typography

- Source reading voice: Georgia, 400 and 700 weights
- Labels and subtitle voice: Nunito, Segoe UI, 400 and 700 weights
- Body text is never smaller than 28 px; display titles are at least 64 px.

## Motion

- Gentle 0.55-second crossfades connect related sections.
- Every section label and teaching panel receives a deterministic entrance.
- No pre-transition exits; the crossfade performs the visual handoff.
- Captions enter gently, highlight the measured active word, and receive a hard timed kill.

## Fixed Layout

- Source-derived label attached to its teaching panel
- Compact cream teaching panel in the top-right safe area for story scenes
- Full-frame animated teaching footage where motion is required
- Stable cream word-highlight subtitle lane in the bottom safe area
- Source-faithful centered reading treatment for recall, glossary, and assessment content

## What NOT to Do

- Do not override the chapter palette, spacing, component positions, or typography.
- Do not add invented labels, decorative copy, watermarks, or embedded media text.
- Do not play generated-video audio or place narration inside a video element.
- Do not loop or reuse story clips to fill missing motion.
- Do not cover faces or textbook prompts with the subtitle lane.
"""

    def _render_html(
        self,
        template: dict[str, Any],
        plan: dict[str, Any],
        timeline: dict[str, Any],
        presentation_variant: str = "",
    ) -> str:
        palette = template["palette"]
        canvas = template["canvas"]
        safe = int(canvas["safe_margin_px"])
        duration = float(timeline["duration_seconds"])
        sections = timeline["sections"]
        groups = timeline["caption_groups"]
        chapter1_style = bool(presentation_variant)
        plan_sections = {
            str(item.get("section_id")): item
            for item in plan.get("sections", []) if isinstance(item, dict)
        }

        media_html: list[str] = []
        for index, section in enumerate(sections):
            sid = _slug(section["section_id"])
            video = section.get("video")
            if video:
                media_html.append(
                    f'    <video id="video-{sid}" class="media-clip" '
                    f'data-start="{_fmt_seconds(video["start_seconds"])}" '
                    f'data-duration="{_fmt_seconds(video["duration_seconds"])}" '
                    f'data-track-index="{video["track_index"]}" '
                    f'src="{html.escape(video["path"], quote=True)}" muted playsinline preload="auto"></video>'
                )
            for segment_index, segment in enumerate(section.get("videos") or []):
                media_html.append(
                    f'    <video id="video-{sid}-seg-{segment_index + 1}" class="media-clip" '
                    f'data-start="{_fmt_seconds(segment["start_seconds"])}" '
                    f'data-duration="{_fmt_seconds(segment["duration_seconds"])}" '
                    f'data-track-index="{segment["track_index"]}" '
                    f'src="{html.escape(segment["path"], quote=True)}" muted playsinline preload="auto"></video>'
                )
            audio = section["audio"]
            media_html.append(
                f'    <audio id="audio-{sid}" class="narration-clip" '
                f'data-start="{_fmt_seconds(audio["start_seconds"])}" '
                f'data-duration="{_fmt_seconds(audio["duration_seconds"])}" '
                f'data-track-index="{audio["track_index"]}" data-volume="1" '
                f'src="{html.escape(audio["path"], quote=True)}" preload="auto"></audio>'
            )

        scenes_html: list[str] = []
        for index, section in enumerate(sections):
            sid = _slug(section["section_id"])
            panel = section["panel"]
            source_ids = " ".join(section["source_block_ids"])
            kind = section["kind"]
            stable_class = " stable-teaching" if ((not section.get("video") and not section.get("videos") and not section.get("native_visual_theme")) or any(
                c.get("visual") for c in section.get("exercise_cards", []))) else ""
            if chapter1_style and (kind in _STABLE_TYPES or sid in {"s02-objectives", "s07-do-you-know", "s09-day-length", "s13-recall", "s14-remember", "s15-wordbank"}):
                stable_class = " stable-teaching"
            native_visual_html = (
                _native_visual_html(section["native_visual_theme"], sid)
                if section.get("native_visual_theme")
                else ""
            )
            figures_html = "".join(
                f'<figure id="source-figure-{sid}-{figure_index}" class="source-figure">'
                f'<img src="{html.escape(figure["path"], quote=True)}" '
                f'alt="{html.escape(figure["authored_caption"], quote=True)}" />'
                f'<figcaption class="source-figure-caption">'
                f'{html.escape(figure["authored_caption"])}</figcaption></figure>'
                for figure_index, figure in enumerate(section.get("figures") or [])
            )
            section_label = html.escape(panel["section_label"])
            heading = html.escape(panel["heading"])
            body = html.escape(panel["body"])
            items = panel["items"]
            list_html = ""
            if items:
                list_html = '<div class="panel-lines">' + "".join(
                    f'<p class="panel-line">{html.escape(item)}</p>' for item in items
                ) + "</div>"
            text_length = len(panel["body"]) + sum(len(item) for item in items)
            length_class = " text-long" if text_length > 240 else (" text-medium" if text_length > 140 else "")
            body_html = f'<p class="panel-body{length_class}">{body}</p>' if body else ""
            if section.get("panel_pages"):
                body_html = '<div class="panel-pages">' + ''.join(
                    f'<p id="panel-page-{sid}-{page_index}" class="panel-body panel-page">'
                    f'{html.escape(page["text"])}</p>'
                    for page_index, page in enumerate(section["panel_pages"])
                ) + '</div>'
                list_html = ""
            structured_list = str(plan_sections.get(section["section_id"], {}).get("title") or "").casefold().strip() in {"learning objectives", "let's remember", "let’s remember"}
            if chapter1_style and (structured_list or sid in {"s02-objectives", "s14-remember"}):
                fragments = plan_sections.get(section["section_id"], {}).get("source_fragments") or []
                reading_lines = []
                for fragment in fragments:
                    if fragment.get("block_type") == "section_heading":
                        continue
                    value = str(fragment.get("source_text") or "").strip()
                    if not value:
                        continue
                    klass = "source-reading bullet-reading" if fragment.get("block_type") == "bullet" else "source-reading"
                    block_id = html.escape(str(fragment.get("block_id") or ""), quote=True)
                    reading_lines.append(
                        f'<p class="{klass}" data-source-block="{block_id}">{html.escape(value)}</p>'
                    )
                if not reading_lines:
                    raise EducationalCompositionError(f"Missing source reading lines for {sid}")
                body_html = '<div class="v4-reading-list">' + ''.join(reading_lines) + '</div>'
                list_html = ""
            if chapter1_style and sid == "s15-wordbank":
                fragments = plan_sections.get(section["section_id"], {}).get("source_fragments") or []
                word_rows = []
                for fragment in fragments:
                    if fragment.get("block_type") == "section_heading":
                        continue
                    value = str(fragment.get("source_text") or "").strip()
                    term, separator, meaning = value.partition(" – ")
                    if not separator or not term.strip() or not meaning.strip():
                        raise EducationalCompositionError(f"Invalid source Word Bank row: {value}")
                    block_id = html.escape(str(fragment.get("block_id") or ""), quote=True)
                    word_rows.append(
                        f'<tr data-source-block="{block_id}"><td>{html.escape(term)}</td>'
                        f'<td>{html.escape(meaning)}</td></tr>'
                    )
                if not word_rows:
                    raise EducationalCompositionError("Word Bank has no source rows")
                body_html = '<table class="v4-wordbank"><thead><tr><th>Word</th><th>Meaning</th></tr></thead><tbody>' + ''.join(word_rows) + '</tbody></table>'
                list_html = ""
            table_html = ""
            source_table = panel.get("table")
            if source_table:
                rows: list[str] = []
                cells_by_row: dict[int, list[dict[str, Any]]] = {}
                for cell in source_table["cells"]:
                    cells_by_row.setdefault(int(cell["row"]), []).append(cell)
                for row_index in range(int(source_table["row_count"])):
                    row_cells: list[str] = []
                    for cell in sorted(
                        cells_by_row.get(row_index, []),
                        key=lambda value: int(value["column"]),
                    ):
                        tag = "th" if cell["is_header"] else "td"
                        attributes = (
                            f' rowspan="{int(cell["row_span"])}"'
                            f' colspan="{int(cell["column_span"])}"'
                            f' data-source-row="{int(cell["row"])}"'
                            f' data-source-column="{int(cell["column"])}"'
                        )
                        row_cells.append(
                            f"<{tag}{attributes}>{html.escape(cell['text'])}</{tag}>"
                        )
                    rows.append("<tr>" + "".join(row_cells) + "</tr>")
                table_html = (
                    '<div class="source-table-wrap"><table class="' + ('source-table v4-wordbank' if chapter1_style else 'source-table') + '">'
                    + "".join(rows)
                    + "</table></div>"
                )
            is_opening = kind == "opening" or (chapter1_style and index == 0)
            panel_class = "opening-card" if is_opening else "teaching-panel"
            label_html = (
                f'<div class="panel-label">{section_label}</div>'
                if section_label and not is_opening and not chapter1_style else ""
            )
            if chapter1_style and not is_opening and section_label:
                label_html = f'<h1 class="heading-label">{section_label}</h1>'
            if chapter1_style and is_opening:
                metadata = plan.get("metadata") or {}
                subject = html.escape(str(metadata.get("subject_label") or "Social Studies").upper())
                grade = html.escape(str(metadata.get("grade") or 5))
                lesson = html.escape(str(metadata.get("chapter") or 2))
                title = html.escape(str(plan.get("title") or section_label))
                body_html = f'<p class="panel-body">{subject} · CLASS {grade}</p><p class="lesson-number">Lesson {lesson}</p>'
                heading = title
            if kind == "opening":
                heading_html_prefix = ""
            else:
                heading_html_prefix = ""
            heading_html = (
                f'<h1 class="panel-heading">{heading}</h1>' if heading else ""
            )
            if section.get("exercise_cards"):
                cards_html = []
                for card_index, card in enumerate(section["exercise_cards"]):
                    card_id = f"exercise-{sid}-{card_index}"
                    options = ''.join(f'<li>{html.escape(str(option))}</li>' for option in card.get("choices", []))
                    answer = card.get("answer_text", "") or ' '.join(card.get("blanks", []))
                    steps_html = ''.join(
                        f'<p id="{card_id}-step-{step_index}" class="exercise-step">{html.escape(step["text"])}</p>'
                        for step_index, step in enumerate(card.get("solution_beats", [])))
                    cards_html.append(
                        f'<div id="{card_id}" class="exercise-card">'
                        f'<p class="panel-body">{html.escape(card["question"])}</p>'
                        + visual_html(card.get("visual"), card_id)
                        + (f'<ul class="panel-list">{options}</ul>' if options else '')
                        + f'<p id="{card_id}-think" class="exercise-think">Think about your answer.</p>'
                        + f'<div class="exercise-stack">{steps_html}</div>'
                        + f'<p id="{card_id}-answer" class="exercise-answer">{html.escape(answer)}</p></div>')
                body_html = '<div class="exercise-stack">' + ''.join(cards_html) + '</div>'
                list_html = table_html = ""
            panel_content = (
                body_html + heading_html + list_html + table_html
                if chapter1_style and is_opening else
                heading_html_prefix + heading_html + body_html + list_html + table_html
            )
            scenes_html.append(
                f'    <section id="scene-{sid}" class="scene{stable_class}" '
                f'data-section-id="{html.escape(section["section_id"], quote=True)}" '
                f'data-section-type="{html.escape(kind, quote=True)}" '
                f'data-source-block-ids="{html.escape(source_ids, quote=True)}">\n'
                f"      {native_visual_html}\n"
                f"      {figures_html}\n"
                f'      <div class="{panel_class}">\n'
                f"        {'' if chapter1_style else label_html}\n"
                f'        <div class="panel-content">{panel_content}</div>\n'
                f"      </div>\n"
                f"      {label_html if chapter1_style else ''}\n"
                f"    </section>"
            )

        captions_html: list[str] = []
        for group_index, group in enumerate(groups):
            word_spans = []
            for word_index, word in enumerate(group["words"]):
                word_spans.append(
                    f'<span id="cw-{group_index}-{word_index}" class="caption-word">{html.escape(word["word"])}</span>'
                )
            captions_html.append(
                f'      <div id="cg-{group_index}" class="caption-group" '
                f'data-caption-start="{_fmt_seconds(group["start_seconds"])}" '
                f'data-caption-end="{_fmt_seconds(group["end_seconds"])}">'
                + " ".join(word_spans)
                + "</div>"
            )

        js: list[str] = [
            "    window.__timelines = window.__timelines || {};",
            "    var tl = gsap.timeline({ paused: true });",
        ]
        for index, section in enumerate(sections):
            sid = _slug(section["section_id"])
            start = float(section["start_seconds"])
            entrance = start + 0.18
            if index > 0:
                previous = _slug(sections[index - 1]["section_id"])
                transition_start = start
                if chapter1_style:
                    incoming_video = bool(section.get("videos") or section.get("video"))
                    scene_fade = (_MOVING_SECTION_TRANSITION_SECONDS if incoming_video
                                  else _TRANSITION_SECONDS)
                    # Stable incoming teaching scenes can dissolve during the
                    # preceding pause, so their text is ready for the heading.
                    # Moving scenes start at their measured video time; an
                    # earlier fade would show an empty video slot.
                    if not incoming_video:
                        transition_start = max(0.0, start - _TRANSITION_SECONDS)
                    entrance = transition_start + (0.01 if incoming_video else 0.10)
                    js.extend([
                        f'    tl.to("#scene-{previous} .teaching-panel, #scene-{previous} .opening-card, #scene-{previous} .heading-label", {{ opacity: 0, duration: {_fmt_seconds(min(.15, scene_fade))}, ease: "sine.in" }}, {_fmt_seconds(transition_start)});',
                        f'    tl.to("#scene-{previous}", {{ opacity: 0, duration: {_fmt_seconds(scene_fade)}, ease: "sine.inOut" }}, {_fmt_seconds(transition_start)});',
                        f'    tl.set("#scene-{sid}", {{ opacity: 0 }}, {_fmt_seconds(transition_start)});',
                        f'    tl.to("#scene-{sid}", {{ opacity: 1, duration: {_fmt_seconds(scene_fade)}, ease: "sine.inOut" }}, {_fmt_seconds(transition_start)});',
                    ])
                else:
                    entrance = transition_start + 0.04
                    js.extend([
                        f'    tl.to("#scene-{previous}", {{ opacity: 0, duration: {_TRANSITION_SECONDS}, ease: "sine.inOut" }}, {_fmt_seconds(transition_start)});',
                        f'    tl.set("#scene-{sid}", {{ opacity: 0 }}, {_fmt_seconds(transition_start)});',
                        f'    tl.to("#scene-{sid}", {{ opacity: 1, duration: {_TRANSITION_SECONDS}, ease: "sine.inOut" }}, {_fmt_seconds(transition_start)});',
                    ])
                if section.get("video"):
                    js.append(
                        f'    tl.fromTo("#video-{sid}", {{ opacity: 0 }}, {{ opacity: 1, duration: {_TRANSITION_SECONDS}, ease: "sine.inOut" }}, {_fmt_seconds(transition_start)});'
                    )
                if sections[index - 1].get("video"):
                    js.append(
                        f'    tl.to("#video-{previous}", {{ opacity: 0, duration: {_TRANSITION_SECONDS}, ease: "sine.inOut" }}, {_fmt_seconds(transition_start)});'
                    )
            if chapter1_style and index > 0 and section["panel"]["section_label"]:
                js.append(
                    f'    tl.from("#scene-{sid} .heading-label", {{ x: -24, opacity: 0, duration: 0.36, ease: "power3.out" }}, {_fmt_seconds(entrance)});'
                )
            elif not chapter1_style and section["panel"]["section_label"] and section["kind"] != "opening":
                js.append(
                    f'    tl.from("#scene-{sid} .panel-label", {{ x: -28, opacity: 0, duration: 0.48, ease: "power3.out" }}, {_fmt_seconds(entrance)});'
                )
            if chapter1_style and index > 0 and not (section.get("videos") or section.get("video")):
                js.extend([
                    f'    tl.from("#scene-{sid} .teaching-panel, #scene-{sid} .opening-card", {{ x: 54, scale: 0.96, opacity: 0, duration: 0.35, ease: "back.out(1.18)" }}, {_fmt_seconds(entrance + 0.08)});',
                    f'    tl.from("#scene-{sid} .panel-content", {{ y: 18, opacity: 0, duration: 0.32, ease: "circ.out" }}, {_fmt_seconds(entrance + 0.10)});',
                ])
            else:
                js.extend([
                    f'    tl.from("#scene-{sid} .teaching-panel, #scene-{sid} .opening-card", {{ x: 54, scale: 0.96, opacity: 0, duration: 0.66, ease: "back.out(1.18)" }}, {_fmt_seconds(entrance + 0.08)});',
                    f'    tl.from("#scene-{sid} .panel-content", {{ y: 18, opacity: 0, duration: 0.54, ease: "circ.out" }}, {_fmt_seconds(entrance + 0.24)});',
                ])
            if section.get("native_visual_theme"):
                cycle = max(4.0, min(9.0, float(section["duration_seconds"]) / 2.0))
                repeats = max(0, int(float(section["duration_seconds"]) / cycle) - 1)
                js.extend([
                    f'    tl.from("#native-{sid}", {{ opacity: 0, scale: 1.04, duration: 0.72, ease: "power2.out" }}, {_fmt_seconds(entrance)});',
                    f'    tl.from("#native-{sid} .native-globe", {{ rotation: -8, scale: 0.88, duration: 0.92, ease: "back.out(1.12)" }}, {_fmt_seconds(entrance + 0.06)});',
                    f'    tl.to("#native-{sid} .native-globe", {{ rotation: 6, duration: {_fmt_seconds(cycle)}, ease: "sine.inOut", yoyo: true, repeat: {repeats} }}, {_fmt_seconds(entrance + 1.02)});',
                    f'    tl.from("#native-{sid} .native-meridian, #native-{sid} .native-parallel", {{ opacity: 0, scale: 0.72, duration: 0.68, stagger: 0.045, ease: "expo.out" }}, {_fmt_seconds(entrance + 0.18)});',
                    f'    tl.from("#native-{sid} .native-land, #native-{sid} .native-clock, #native-{sid} .native-pin", {{ opacity: 0, y: 22, duration: 0.62, stagger: 0.09, ease: "circ.out" }}, {_fmt_seconds(entrance + 0.26)});',
                ])
            for segment_index, segment in enumerate(section.get("videos") or []):
                segment_id = f"video-{sid}-seg-{segment_index + 1}"
                segment_start = float(segment["start_seconds"])
                segment_end = segment_start + float(segment["duration_seconds"])
                if segment.get("transition") == "cut":
                    # Concept changes over a persistent scientific background
                    # must not dissolve three unrelated objects together.
                    js.extend([
                        f'    tl.set("#{segment_id}", {{ opacity: 1 }}, {_fmt_seconds(segment_start)});',
                        f'    tl.set("#{segment_id}", {{ opacity: 0 }}, {_fmt_seconds(segment_end)});',
                    ])
                    continue
                fade = min(_TRANSITION_SECONDS, float(segment["duration_seconds"]) / 3)
                js.append(
                    f'    tl.fromTo("#{segment_id}", {{ opacity: 0 }}, '
                    f'{{ opacity: 1, duration: {_fmt_seconds(fade)}, ease: "sine.inOut" }}, '
                    f'{_fmt_seconds(segment_start)});'
                )
                # Keep the outgoing layer opaque while the next layer fades
                # over it. Fading both stacked videos simultaneously exposes
                # the pale scene base and washes out captions/panels.
                js.append(
                    f'    tl.set("#{segment_id}", {{ opacity: 0 }}, {_fmt_seconds(segment_end)});'
                )
            source_title = str(plan_sections.get(section["section_id"], {}).get("title") or "").casefold().strip()
            structured_source_scene = chapter1_style and (source_title in {"learning objectives", "let's remember", "let’s remember", "word bank"} or sid in {
                "s02-objectives", "s14-remember", "s15-wordbank"
            })
            for page_index, page in enumerate(
                [] if structured_source_scene else (section.get("panel_pages") or [])
            ):
                page_id = f"panel-page-{sid}-{page_index}"
                js.append(
                    f'    tl.set("#{page_id}", {{ opacity: 1 }}, '
                    f'{_fmt_seconds(page["start_seconds"])});'
                )
                js.append(
                    f'    tl.set("#{page_id}", {{ opacity: 0 }}, '
                    f'{_fmt_seconds(page["end_seconds"])});'
                )
            for figure_index, figure in enumerate(section.get("figures") or []):
                figure_id = f"source-figure-{sid}-{figure_index}"
                js.append(
                    f'    tl.fromTo("#{figure_id}", {{ opacity: 0, scale: 0.96 }}, '
                    f'{{ opacity: 1, scale: 1, duration: 0.45, ease: "sine.out" }}, '
                    f'{_fmt_seconds(figure["start_seconds"])});'
                )
                js.append(
                    f'    tl.to("#{figure_id}", {{ opacity: 0, duration: 0.35, ease: "sine.in" }}, '
                    f'{_fmt_seconds(figure["end_seconds"] - 0.35)});'
                )
        for group_index, group in enumerate(groups):
            start = float(group["start_seconds"])
            end = float(group["end_seconds"])
            js.extend([
                # Caption visibility is deliberately deterministic.  Parent-level
                # opacity tweens can conflict when HyperFrames seeks directly to
                # a frame, leaving a correctly timed phrase invisible.  The
                # spoken word still animates below, while the complete phrase
                # remains readable until the next phrase begins.
                f'    tl.set("#cg-{group_index}", {{ opacity: 1, visibility: "visible", y: 0 }}, {_fmt_seconds(start)});',
            ])
            for word_index, word in enumerate(group["words"]):
                word_start = float(word["start_ms"]) / 1000
                word_end = float(word["end_ms"]) / 1000
                word_duration = max(0.02, word_end - word_start)
                highlight_duration = min(0.05, word_duration / 2)
                reset_duration = min(0.05, word_duration / 2)
                reset_start = max(
                    word_start + highlight_duration,
                    word_end - reset_duration,
                )
                js.extend([
                    f'    tl.set("#cw-{group_index}-{word_index}", {{ color: "{palette["cream"]}", backgroundColor: "{palette["highlight_active"]}", scale: 1.04 }}, {_fmt_seconds(word_start)});',
                    f'    tl.set("#cw-{group_index}-{word_index}", {{ color: "{palette["highlight_inactive"]}", backgroundColor: "transparent", scale: 1 }}, {_fmt_seconds(reset_start)});',
                ])
            js.extend([
                f'    tl.set("#cg-{group_index}", {{ opacity: 0, visibility: "hidden" }}, {_fmt_seconds(end)});',
            ])

        for section in sections:
            sid = _slug(section["section_id"])
            cards = section.get("exercise_cards", [])
            for card_index, card in enumerate(cards):
                card_id = f"exercise-{sid}-{card_index}"
                base = section["start_seconds"]
                show = base + card["question_start_seconds"]
                end = (base + cards[card_index + 1]["question_start_seconds"]
                       if card_index + 1 < len(cards) else section["end_seconds"])
                js.append(f'tl.set("#{card_id}", {{opacity:1}}, {_fmt_seconds(show)});')
                js.append(f'tl.set("#{card_id}", {{opacity:0}}, {_fmt_seconds(end)});')
                js.append(f'tl.set("#{card_id}-answer", {{opacity:1}}, {_fmt_seconds(base + card["reveal_delay_seconds"])});')
                for reveal_index, reveal in enumerate((card.get("visual") or {}).get("reveals", [])):
                    js.append(f'tl.set("#{card_id}-visual-{reveal_index}", {{opacity:1}}, {_fmt_seconds(base + reveal["reveal_seconds"])});')
                for step_index, step in enumerate(card.get("solution_beats", [])):
                    at = base + step["start_seconds"]
                    if step_index:
                        js.append(f'tl.set("#{card_id}-step-{step_index-1}", {{opacity:0}}, {_fmt_seconds(at)});')
                    js.append(f'tl.set("#{card_id}-step-{step_index}", {{opacity:1}}, {_fmt_seconds(at)});')
                if card["thinking_end_seconds"] > card["thinking_start_seconds"]:
                    js.append(f'tl.set("#{card_id}-think", {{opacity:1}}, {_fmt_seconds(base + card["thinking_start_seconds"])});')
                    js.append(f'tl.set("#{card_id}-think", {{opacity:0}}, {_fmt_seconds(base + card["thinking_end_seconds"])});')

        # These masks are above both media and captions. During the requested
        # silent heading pause the only visible content is the chapter heading.
        for section in sections:
            hold = section.get("heading_hold")
            holds = section.get("heading_holds") or ([hold] if hold else [])
            for hold_index, hold in enumerate(holds):
                hold_id = "heading-hold-" + _slug(section["section_id"]) + "-" + str(hold_index)
                scenes_html.append(
                    f'<div id="{hold_id}" class="heading-hold" data-layout-allow-overlap data-layout-allow-occlusion><h1>{html.escape(hold["title"])}</h1></div>'
                )
                js.append(f'tl.set("#{hold_id}", {{opacity:1}}, {_fmt_seconds(hold["start_seconds"])});')
                # A heading pause is title-only: hide the underlying scene as
                # well as covering it, so no source text can leak through.
                js.append(f'tl.set("#scene-{_slug(section["section_id"])}", {{opacity:0}}, {_fmt_seconds(hold["start_seconds"])});')
                js.append(f'tl.set("#{hold_id}", {{opacity:0}}, {_fmt_seconds(hold["end_seconds"])});')
                js.append(f'tl.set("#scene-{_slug(section["section_id"])}", {{opacity:1}}, {_fmt_seconds(hold["end_seconds"])});')
            pause_start = float(section.get("topic_pause_start", section["end_seconds"]))
            if pause_start < float(section["end_seconds"]):
                js.append(f'tl.set(".subtitle-lane", {{opacity:0}}, {_fmt_seconds(pause_start)});')
                js.append(f'tl.set(".subtitle-lane", {{opacity:1}}, {_fmt_seconds(section["end_seconds"])});')
        js.append('    window.__timelines["educational-main"] = tl;')

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=1920, initial-scale=1" />
  <title>{html.escape(str(plan.get('title') or 'Educational chapter'))}</title>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <style>
    @font-face {{ font-family: "Classroom Sans"; src: local("Nunito"), local("Segoe UI"); font-style: normal; font-weight: 400 800; }}
    @font-face {{ font-family: "Classroom Serif"; src: local("Georgia"); font-style: normal; font-weight: 400 700; }}
    * {{ box-sizing: border-box; }}
    .heading-hold {{ position:absolute; inset:0; z-index:50; opacity:0; background:{palette['cream']}; display:grid; place-items:center; padding:120px; text-align:center; pointer-events:none; }}
    .heading-hold h1 {{ color:{palette['ink']}; font-family:"Classroom Serif",serif; font-size:82px; line-height:1.15; max-width:1500px; }}
    html, body {{ margin: 0; width: {canvas['width_px']}px; height: {canvas['height_px']}px; overflow: hidden; background-color: {palette['ink']}; }}
    body {{ font-family: "Classroom Sans", sans-serif; color: {palette['ink']}; }}
    #educational-main {{ position: relative; width: 100%; height: 100%; overflow: hidden; background-color: {palette['ink']}; }}
    .media-clip {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; z-index: 0; will-change: opacity; }}
    .scene {{ position: absolute; inset: 0; width: 100%; height: 100%; padding: {safe}px; overflow: hidden; z-index: 3; background-color: rgba(255,249,237,0); }}
    .scene:not(:first-of-type) {{ opacity: 0; }}
    .native-visual {{ position:absolute; inset:0; overflow:hidden; background-color:#0B3148; }}
    .native-visual::before, .native-visual::after {{ content:""; position:absolute; border-radius:50%; background-color:rgba(255,249,237,.12); }}
    .native-visual::before {{ width:18px; height:18px; left:15%; top:20%; box-shadow:300px 70px 0 3px rgba(255,249,237,.07), 620px -48px 0 1px rgba(255,249,237,.12), 980px 180px 0 2px rgba(255,249,237,.08), 1240px 18px 0 2px rgba(255,249,237,.1); }}
    .native-visual::after {{ width:520px; height:130px; left:100px; bottom:96px; border-radius:50%; background-color:rgba(7,29,43,.42); }}
    .native-globe {{ position:absolute; left:170px; top:122px; width:650px; height:650px; border-radius:50%; overflow:hidden; background-color:#237F9E; border:10px solid rgba(255,249,237,.88); box-shadow:inset -52px -40px 90px rgba(7,29,43,.42), inset 34px 22px 54px rgba(162,232,211,.28), 0 46px 90px rgba(0,0,0,.3); transform-origin:center; }}
    .native-land {{ position:absolute; z-index:2; display:block; background-color:#83BE65; border:5px solid rgba(18,50,71,.2); border-radius:48% 52% 44% 56% / 58% 42% 58% 42%; box-shadow:inset -12px -10px 20px rgba(18,50,71,.16); }}
    .native-land-1 {{ width:210px; height:135px; left:78px; top:92px; transform:rotate(-16deg); }}
    .native-land-2 {{ width:145px; height:215px; left:236px; top:210px; transform:rotate(14deg); }}
    .native-land-3 {{ width:180px; height:120px; right:46px; top:155px; transform:rotate(19deg); }}
    .native-land-4 {{ width:105px; height:74px; right:118px; bottom:87px; transform:rotate(-12deg); }}
    .native-meridian, .native-parallel {{ position:absolute; z-index:4; display:block; pointer-events:none; border:3px solid rgba(255,249,237,.52); }}
    .native-meridian {{ top:13px; bottom:13px; left:50%; width:42%; border-top-color:rgba(255,249,237,.2); border-bottom-color:rgba(255,249,237,.2); border-radius:50%; transform:translateX(-50%); }}
    .native-meridian-1 {{ width:18%; }} .native-meridian-2 {{ width:42%; }} .native-meridian-3 {{ width:70%; }} .native-meridian-4 {{ width:94%; }} .native-meridian-5 {{ width:128%; }}
    .native-parallel {{ left:26px; right:26px; top:50%; height:18%; border-left-color:rgba(255,249,237,.18); border-right-color:rgba(255,249,237,.18); border-radius:50%; transform:translateY(-50%); }}
    .native-parallel-1 {{ top:22%; width:70%; left:15%; right:auto; }} .native-parallel-2 {{ top:36%; }} .native-parallel-3 {{ top:50%; height:24%; }} .native-parallel-4 {{ top:64%; }} .native-parallel-5 {{ top:78%; width:70%; left:15%; right:auto; }}
    .native-orbit {{ position:absolute; z-index:5; left:112px; top:384px; width:760px; height:190px; border:5px solid rgba(255,211,99,.7); border-radius:50%; transform:rotate(-11deg); }}
    .native-orbit-back {{ border-bottom-color:rgba(255,211,99,.08); }} .native-orbit-front {{ border-top-color:rgba(255,211,99,.08); }}
    .native-date-line {{ display:none; position:absolute; z-index:8; left:50%; top:12px; bottom:12px; border-left:8px dashed #FFCF5C; }}
    .native-theme-latitude .native-meridian {{ opacity:.2; }}
    .native-theme-latitude .native-parallel-3 {{ border-color:#FFCF5C; border-width:8px; }}
    .native-theme-longitude .native-parallel {{ opacity:.22; }}
    .native-theme-longitude .native-meridian-2 {{ border-color:#FFCF5C; border-width:8px; }}
    .native-theme-date-line .native-date-line {{ display:block; }}
    .native-theme-ocean .native-land {{ transform:scale(.78); opacity:.78; }}
    .native-theme-ocean .native-globe {{ background-color:#0F9EC1; }}
    .native-theme-continents .native-land {{ background-color:#A4C95F; }}
    .native-clock {{ position:absolute; z-index:7; width:126px; height:126px; border-radius:50%; background-color:{palette['cream']}; border:8px solid #FFCF5C; box-shadow:0 20px 38px rgba(0,0,0,.24); }}
    .native-clock-1 {{ left:90px; top:82px; }} .native-clock-2 {{ left:770px; top:90px; }} .native-clock-3 {{ left:750px; top:650px; }}
    .native-clock i, .native-clock b {{ position:absolute; left:50%; top:50%; display:block; width:5px; border-radius:4px; background-color:{palette['ink']}; transform-origin:center bottom; }}
    .native-clock i {{ height:38px; transform:translate(-50%,-100%) rotate(32deg); }} .native-clock b {{ height:27px; transform:translate(-50%,-100%) rotate(128deg); }}
    .native-pin {{ position:absolute; z-index:8; left:420px; top:300px; width:68px; height:68px; border:12px solid #FFCF5C; border-radius:50% 50% 50% 0; transform:rotate(-45deg); box-shadow:0 12px 14px rgba(0,0,0,.32); }}
    .native-theme-coordinates .native-globe {{ background-image:repeating-linear-gradient(0deg, rgba(255,255,255,.14) 0 3px, rgba(255,255,255,0) 3px 46px), repeating-linear-gradient(90deg, rgba(255,255,255,.14) 0 3px, rgba(255,255,255,0) 3px 46px); }}
    .scene.stable-teaching {{ background-color: {palette['cream']}; }}
    .scene.stable-teaching::before {{ content: ""; position: absolute; inset: 0; background-color: rgba(18,50,71,0.035); border-top: 12px solid rgba(182,65,50,0.13); }}
    .teaching-panel, .opening-card {{ position: absolute; top: 86px; right: 62px; width: 650px; max-height: 720px; padding: 42px 34px 31px; border-left: 8px solid {palette['teaching_accent']}; border-radius: 9px 22px 22px 9px; background-color: rgba(255,249,237,0.97); box-shadow: 0 24px 68px rgba(18,50,71,0.24); overflow: visible; }}
    .panel-label {{ position:absolute; top:-34px; left:-8px; min-width:190px; max-width:600px; padding:10px 24px 11px; border-radius:13px 13px 0 0; background-color:{palette['teaching_accent']}; color:{palette['cream']}; box-shadow:0 9px 22px rgba(18,50,71,.18); font-family:"Classroom Sans",sans-serif; font-size:24px; font-weight:800; line-height:1.05; }}
    .opening-card {{ top: 230px; right: auto; bottom: auto; left: 100px; width: 820px; background: rgba(18,50,71,0.88); border: 1px solid rgba(255,249,237,0.3); }}
    .opening-card .panel-heading, .opening-card .panel-body {{ color: #FFF9ED; }}
    .stable-teaching .teaching-panel {{ top:205px; right:245px; left:245px; width:auto; min-height:545px; max-height:675px; transform:none; display:flex; flex-direction:column; justify-content:center; padding:58px 72px 54px; border-left-width:0; border-radius:22px; }}
    .stable-teaching .panel-label {{ left:-1px; top:-42px; min-width:230px; font-size:26px; padding:12px 28px 13px; }}
    .panel-heading {{ margin: 0; font-family: "Classroom Serif", serif; font-size: 52px; font-weight: 700; line-height: 1.08; letter-spacing: -0.025em; color: {palette['ink']}; overflow-wrap: anywhere; }}
    .opening-card .panel-heading {{ font-size: 82px; max-width: 680px; }}
    .panel-body {{ margin: 18px 0 0; font-family:"Classroom Serif",serif; font-size: 31px; font-weight: 400; line-height: 1.34; color: {palette['ink']}; overflow-wrap: anywhere; }}
    .panel-pages {{ display:grid; margin-top:18px; }}
    .panel-pages .panel-page {{ grid-area:1 / 1; margin:0; opacity:0; }}
    .source-figure {{ position:absolute; left:62px; top:140px; z-index:2; width:1040px; height:680px; margin:0; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:8px; padding:20px; border-radius:22px; background:{palette['cream']}; box-shadow:0 20px 55px rgba(0,0,0,.22); opacity:0; }}
    .source-figure img {{ display:block; width:100%; height:calc(100% - 46px); object-fit:contain; }}
    .source-figure-caption {{ flex:0 0 auto; max-width:100%; height:38px; overflow:hidden; color:#332b20; font-family:Nunito,sans-serif; font-size:24px; font-weight:700; line-height:38px; text-align:center; white-space:nowrap; }}
    .panel-body.text-medium {{ font-size:29px; }}
    .panel-body.text-long {{ font-size:26px; line-height:1.28; }}
    .stable-teaching .panel-body {{ font-size:39px; line-height:1.32; }}
    .stable-teaching .panel-body.text-medium {{ font-size:35px; }}
    .stable-teaching .panel-body.text-long {{ font-size:31px; }}
    .panel-lines {{ margin-top:20px; display:grid; gap:14px; }}
    .panel-line {{ margin:0; padding:0; font-family:"Classroom Serif",serif; font-size:36px; font-weight:400; line-height:1.28; color:{palette['ink']}; overflow-wrap:anywhere; }}
    .panel-list {{ margin: 22px 0 0; padding-left: 1.2em; display: grid; gap: 10px; font-size: 29px; font-weight: 700; line-height: 1.24; }}
    .panel-list li::marker {{ color: {palette['teaching_accent']}; }}
    .source-table-wrap {{ width: 100%; margin-top: 22px; overflow: hidden; border: 2px solid rgba(18,50,71,0.24); border-radius: 18px; background-color: rgba(255,249,237,0.98); }}
    .source-table {{ width: 100%; border-collapse: collapse; table-layout: fixed; font-size: 28px; line-height: 1.22; }}
    .source-table th, .source-table td {{ padding: 15px 18px; border-right: 1px solid rgba(18,50,71,0.18); border-bottom: 1px solid rgba(18,50,71,0.18); vertical-align: middle; text-align: left; overflow-wrap: anywhere; }}
    .source-table th {{ color: {palette['cream']}; background-color: {palette['ink']}; font-weight: 700; }}
    .source-table td {{ color: {palette['ink']}; background-color: rgba(255,249,237,0.98); font-weight: 400; }}
    .source-table tr:last-child > * {{ border-bottom: 0; }}
    .source-table tr > *:last-child {{ border-right: 0; }}
    .subtitle-lane {{ position: absolute; left: {safe + 80}px; right: {safe + 80}px; bottom: 42px; height: 118px; z-index: 20; display: grid; place-items: center; padding: 12px 30px; border-radius: 25px; background-color: rgba(255,249,237,0.97); box-shadow: 0 18px 55px rgba(18,50,71,0.28); overflow: visible; }}
    .caption-group {{ position: absolute; left: 0; right: 0; height: 88px; display: flex; align-items: center; justify-content: center; flex-wrap: wrap; gap: 4px 8px; padding: 0 26px; opacity: 0; visibility: hidden; color: {palette['highlight_inactive']}; font-size: 36px; font-weight: 700; line-height: 1.12; text-align: center; overflow: visible; }}
    .caption-word {{ display: inline-block; padding:5px 8px; border-radius:10px; transform-origin: center bottom; will-change: transform, color, background-color; }}
    .exercise-stack {{ display:grid; }}
    .exercise-card {{ grid-area:1 / 1; opacity:0; min-width:0; }}
    .exercise-think, .exercise-answer {{ opacity:0; font-size:36px; line-height:1.3; }}
    .exercise-answer {{ color:{palette['highlight_active']}; font-weight:700; }}
    .exercise-step {{ grid-area:1 / 1; opacity:0; font-size:32px; line-height:1.3; }}
    .exercise-visual {{ display:block; width:100%; height:260px; color:{palette['ink']}; }}
    .exercise-reveal {{ opacity:0; color:{palette['highlight_active']}; }}
    .grammar-visual {{ height:auto; min-height:150px; display:flex; flex-wrap:wrap; align-content:center; gap:14px; font-size:42px; line-height:1.35; }}
    .grammar-token {{ display:inline-flex; position:relative; padding:6px 8px; }}
    .grammar-target {{ min-width:110px; border-bottom:3px solid {palette['teaching_accent']}; }}
    .grammar-correction {{ position:absolute; left:8px; top:6px; padding:0 4px; background:{palette['cream']}; font-weight:800; }}
    .table-visual {{ height:auto; max-height:330px; overflow:visible; }}
    .table-visual table {{ width:100%; border-collapse:collapse; table-layout:fixed; font-size:27px; }}
    .table-visual th, .table-visual td {{ position:relative; padding:12px 14px; border:2px solid rgba(18,50,71,.24); text-align:center; overflow-wrap:anywhere; }}
    .table-visual th {{ background:{palette['ink']}; color:{palette['cream']}; }}
    .table-answer {{ display:inline-block; margin-left:8px; font-weight:800; }}
    .math-visual {{ height:auto; min-height:220px; display:grid; grid-template-columns:1fr 1.35fr; gap:28px; align-items:center; }}
    .math-expression {{ padding:22px; border-radius:18px; background:rgba(18,50,71,.08); font-family:"Classroom Serif",serif; font-size:50px; font-weight:900; text-align:center; }}
    .math-steps {{ display:grid; gap:10px; font-size:30px; line-height:1.28; }}
    .math-visual-step {{ padding:8px 14px; border-left:5px solid {palette['teaching_accent']}; }}
    {CLASS5_SOCIAL_V4_CSS if chapter1_style else ''}
  </style>
</head>
<body>
  <div id="educational-main" data-composition-id="educational-main" data-width="{canvas['width_px']}" data-height="{canvas['height_px']}" data-start="0" data-duration="{_fmt_seconds(duration)}" data-template-id="{html.escape(str(template['id']), quote=True)}" data-template-version="{html.escape(str(template['version']), quote=True)}" data-template-sha256="{html.escape(str(timeline['template']['sha256']), quote=True)}" data-template-package-sha256="{html.escape(str(timeline['template']['package_sha256']), quote=True)}">
{chr(10).join(media_html)}
{chr(10).join(scenes_html)}
    <div class="subtitle-lane" aria-label="Word-highlight subtitles" data-layout-allow-caption-zone>
{chr(10).join(captions_html)}
    </div>
  </div>
  <script>
{chr(10).join(js)}
  </script>
</body>
</html>
"""


__all__ = [
    "EducationalCompositionError",
    "EducationalHyperFramesComposer",
    "educational_template_package_sha256",
]
