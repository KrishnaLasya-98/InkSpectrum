"""Educational content generator — agent-driven, no LLM API calls.

The AI agent (Claude / Kiro / Cursor / Kilo) IS the content generator.
This tool's job is:
  1. Accept either a pre-built educational_plan dict (agent wrote it) OR
     a source_content string (agent will write the plan after reading the
     EduGen 6-step prompt from the skill file)
  2. Validate the plan against the schema
  3. Enforce render_mode on every section
  4. Persist the plan to artifacts/educational_plan.json

There are NO LLM API calls here. The agent reads
  skills/edustream/content-director.md
and follows the 6-step + Step 7 (render_mode) prompt to produce the
educational_plan JSON, then passes it back as an input to this tool.

render_mode values
------------------
  manim        — concept diagrams, equations, number lines, classification trees
  hyperframes  — Q&A cards, fill-blank, MCQ, glossary, recall
  hyperframes  — chapter title cards and transition bumpers only
  video_gen    — narrative / story scenes requiring animation
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)
from tools.structure.subject_profiles import resolve_subject_profile

# ---------------------------------------------------------------------------
# render_mode inference — used when the agent omits the field
# ---------------------------------------------------------------------------

_MANIM_KW = re.compile(
    r"equation|formula|number\s*line|place\s*value|skip\s*count|diagram"
    r"|classif|concept\s*(wheel|tree|map)|worked\s*example|tens|ones",
    re.I,
)
_REMOTION_KW = re.compile(
    r"q&a|question|fill.in|blank|multiple.choice|glossary|recall|assess"
    r"|vocabulary|define|summary",
    re.I,
)
_HF_KW   = re.compile(r"chapter\s*title|title\s*card|bumper|transition|intro\s*card", re.I)
_VID_KW  = re.compile(r"story|narrative|scene|video|illustrat|animation", re.I)

def _infer_render_mode(section: dict[str, Any], subject: str) -> str:
    title = (section.get("title") or "") + " " + (section.get("description") or "")
    btype = section.get("source_block_type", "")
    if _HF_KW.search(title):      return "hyperframes"
    if _REMOTION_KW.search(title): return "hyperframes"
    if _MANIM_KW.search(title):   return "manim"
    if _VID_KW.search(title):     return "video_gen"
    profile = resolve_subject_profile(subject)
    mode_map = profile.get("render_modes") or {}
    return str(mode_map.get(btype) or profile.get("default_render_mode") or "video_gen")


# ---------------------------------------------------------------------------
# Plan defaults and enforcement
# ---------------------------------------------------------------------------

def _enforce_plan(
    plan: dict[str, Any],
    subject: str,
    delivery_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fill defaults and enforce render_mode on every section."""
    valid_rm = {"manim", "remotion", "hyperframes", "video_gen"}
    plan.setdefault("version", "1.0")
    plan.setdefault("subject_classification", "theory")
    plan.setdefault("complexity_level", "elementary")
    plan.setdefault("target_audience", "Class 1, ages 5-7")
    plan.setdefault("total_duration_seconds", 480)
    plan.setdefault("learning_objectives", [])
    plan.setdefault("sections", [])
    plan.setdefault("assessment", {})
    plan.setdefault("metadata", {})
    delivery = dict(delivery_profile or {})
    wpm_min = int(delivery.get("wpm_min", 105))
    wpm_max = int(delivery.get("wpm_max", 125))
    wpm_target = round((wpm_min + wpm_max) / 2)
    plan["metadata"]["children_design_system"] = "sunshine-classroom"
    plan["metadata"]["narration_wpm_target"] = wpm_target
    plan["metadata"]["grade_delivery"] = {
        "wpm_min": wpm_min,
        "wpm_max": wpm_max,
        "sentence_words_target": int(
            delivery.get("sentence_words_target", 12)
        ),
        "subtitle_words_max": int(delivery.get("subtitle_words_max", 7)),
        "subtitle_lines_max": int(delivery.get("subtitle_lines_max", 2)),
    }
    plan["metadata"]["max_concept_hold_seconds"] = 5
    plan["metadata"]["orchestrator"]           = "agent"

    for section in plan.get("sections", []):
        rm = section.get("render_mode", "")
        if rm not in valid_rm:
            section["render_mode"] = _infer_render_mode(section, subject)

    return plan


def _source_block_type(block: dict[str, Any], subject: str) -> str:
    """Map normalized document roles to the legacy educational-plan taxonomy."""

    block_type = str(block.get("block_type", "concept"))
    semantic_role = str(block.get("semantic_role", ""))
    concept_family = str(resolve_subject_profile(subject).get("concept_family") or "")
    if semantic_role == "we_learn":
        return "we_learn"
    if semantic_role == "highlights":
        return "lesson_highlights"
    if semantic_role == "recall" or block_type == "recall":
        return "recall"
    if semantic_role == "glossary" or block_type == "glossary":
        return "glossary"
    if semantic_role == "assessment" or block_type in {
        "assessment", "mcq", "fill_blank", "true_false", "matching",
    }:
        return "qa_item"
    if semantic_role in {"activity", "life_skill"} or block_type in {
        "activity", "life_skill",
    }:
        return "activity"
    if block_type in {"chapter_title", "section_heading"}:
        return "intro"
    if block_type == "table":
        return "table"
    if concept_family == "mathematics" and block_type in {"equation", "paragraph"}:
        return "worked_example"
    if concept_family == "language" and block_type in {"paragraph", "caption"}:
        return "story_section"
    return str(resolve_subject_profile(subject).get("paragraph_block_type") or "concept")


def _source_render_mode(source_block_type: str, subject: str) -> str:
    if source_block_type in {
        "qa_item", "recall", "glossary", "activity", "table",
        "we_learn", "lesson_highlights",
    }:
        # These are stable teaching/read-and-think scenes authored directly by
        # the locked HyperFrames template. Generative video must not attempt to
        # draw textbook text, and no intermediate Remotion clip is required.
        return "hyperframes"
    profile = resolve_subject_profile(subject)
    mode_map = profile.get("render_modes") or {}
    return str(
        mode_map.get(source_block_type)
        or profile.get("default_render_mode")
        or "video_gen"
    )


def _motion_narration_chunks(text: str, max_words: int = 18) -> list[str]:
    """Keep complete teaching sentences; shot duration must not truncate prose.

    ``max_words`` is retained for caller compatibility, not a hard text limit.
    A long sentence needs multiple timed shots, not dangling subtitle clauses.
    Decimal points, initials and common abbreviations are not sentence ends.
    """
    compact = " ".join(text.split())
    protected = re.sub(r"(?<=\d)\.(?=\d)", "\uE000", compact)
    protected = re.sub(
        r"\b(?:Mr|Mrs|Ms|Dr|Prof|St|No|e\.g|i\.e)\.|\b[A-Z]\.(?=\s+[A-Z])",
        lambda match: match.group().replace(".", "\uE000"),
        protected,
    )
    return [
        part.replace("\uE000", ".").strip()
        for part in re.split(r"(?<=[.!?])\s+", protected)
        if part.strip()
    ] or [compact]


def _table_spoken_text(table: dict[str, Any], fallback: str) -> str:
    """Convert a structured textbook table to complete, TTS-friendly prose."""

    row_count = int(table.get("row_count") or 0)
    column_count = int(table.get("column_count") or 0)
    if row_count <= 0 or column_count <= 0:
        return fallback
    grid = [["" for _ in range(column_count)] for _ in range(row_count)]
    for cell in table.get("cells") or []:
        try:
            row = int(cell["row"])
            column = int(cell["column"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= row < row_count and 0 <= column < column_count:
            grid[row][column] = str(cell.get("text") or "").strip()

    header_rows = max(0, min(row_count, int(table.get("header_rows") or 0)))
    headers = grid[0] if header_rows else []
    spoken_rows: list[str] = []
    for row_number, row in enumerate(grid[header_rows:], start=header_rows + 1):
        values: list[str] = []
        for column, value in enumerate(row):
            if not value:
                continue
            label = headers[column] if column < len(headers) else ""
            values.append(f"{label}: {value}" if label else value)
        if values:
            spoken_rows.append(f"Row {row_number}. " + ". ".join(values) + ".")
    if spoken_rows:
        return "Let us read the table. " + " ".join(spoken_rows)
    return fallback


def _split_source_table(
    table: dict[str, Any], *, max_body_rows: int = 6
) -> list[dict[str, Any]]:
    """Paginate a table for 1080p teaching panels while preserving every cell."""

    row_count = int(table.get("row_count") or 0)
    header_rows = max(0, min(row_count, int(table.get("header_rows") or 0)))
    if row_count <= header_rows + max_body_rows:
        return [table]
    header_cells = [
        dict(cell) for cell in table.get("cells") or []
        if int(cell.get("row", -1)) < header_rows
    ]
    body_rows = list(range(header_rows, row_count))
    chunks: list[dict[str, Any]] = []
    for start in range(0, len(body_rows), max_body_rows):
        selected_rows = body_rows[start:start + max_body_rows]
        row_map = {
            old_row: new_row
            for new_row, old_row in enumerate(
                list(range(header_rows)) + selected_rows
            )
        }
        cells: list[dict[str, Any]] = []
        for raw in header_cells + [
            dict(cell) for cell in table.get("cells") or []
            if int(cell.get("row", -1)) in selected_rows
        ]:
            cell = dict(raw)
            cell["row"] = row_map[int(raw["row"])]
            cells.append(cell)
        chunks.append({
            "row_count": header_rows + len(selected_rows),
            "column_count": int(table.get("column_count") or 0),
            "header_rows": header_rows,
            "cells": cells,
        })
    return chunks or [table]


def _callout_items(text: str) -> list[str]:
    """Split source callout copy without inventing or rewriting its wording."""

    values = [
        " ".join(part.split()).strip(" -\t")
        for part in re.split(r"[•●▪◦]\s*|\n+", str(text or ""))
    ]
    return [
        value for value in values
        if value and not re.fullmatch(r"[_\-–—.\s]{4,}", value)
    ]


def _group_textbook_callouts(
    blocks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Combine each We Learn/Highlights box into one source-linked scene."""

    roles = {"we_learn", "highlights"}
    groups: dict[tuple[int, str, str], list[dict[str, Any]]] = {}
    keys: list[tuple[int, str, str] | None] = []
    for block in blocks:
        role = str(block.get("semantic_role") or "")
        if role not in roles:
            keys.append(None)
            continue
        key = (
            int(block.get("page_number") or 1),
            role,
            str(block.get("heading") or block.get("source_text") or role).strip(),
        )
        groups.setdefault(key, []).append(block)
        keys.append(key)

    output: list[dict[str, Any]] = []
    emitted: set[tuple[int, str, str]] = set()
    for block, key in zip(blocks, keys):
        if key is None:
            output.append(block)
            continue
        if key in emitted:
            continue
        emitted.add(key)
        members = groups[key]
        heading = key[2]
        items: list[str] = []
        source_ids: list[str] = []
        for member in members:
            source_id = str(member.get("block_id") or "")
            if source_id:
                source_ids.append(source_id)
            text = str(member.get("source_text") or "").strip()
            if (
                member.get("block_type") in {"chapter_title", "section_heading"}
                and text.casefold() == heading.casefold()
            ):
                continue
            items.extend(_callout_items(text))
        synthetic = dict(members[0])
        synthetic.update({
            "block_id": source_ids[0],
            "source_block_ids": source_ids,
            "block_type": "callout",
            "semantic_role": key[1],
            "heading": heading,
            "source_text": " ".join(items).strip(),
        })
        if key[1] == "we_learn":
            synthetic["source_questions"] = items
        else:
            synthetic["source_topics"] = items
        output.append(synthetic)
    return output


def _coalesce_planning_blocks(
    blocks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Create readable teaching units while retaining lossless source links.

    PDF-to-Markdown converters commonly emit every visual line as a separate
    heading or paragraph. Treating those lines as scenes creates hundreds of
    tiny clips and patchwork pacing. This pass groups adjacent compatible
    blocks on the same page. Every original block id and verbatim fragment is
    retained, so coverage QA remains exact and reversible.
    """

    structured_types = {"table", "figure", "equation"}
    special_roles = {
        "we_learn",
        "highlights",
        "recall",
        "glossary",
        "assessment",
        "activity",
        "life_skill",
    }

    def ids(block: dict[str, Any]) -> list[str]:
        values = block.get("source_block_ids") or [block.get("block_id")]
        return [str(value) for value in values if value]

    def fragments(block: dict[str, Any]) -> list[dict[str, Any]]:
        existing = block.get("source_fragments")
        if isinstance(existing, list) and existing:
            return [dict(value) for value in existing if isinstance(value, dict)]
        return [{
            "block_id": value,
            "page_number": block.get("page_number"),
            "block_type": str(block.get("block_type") or ""),
            "semantic_role": str(block.get("semantic_role") or "lesson_content"),
            "source_text": str(block.get("source_text") or ""),
            "bbox": list(block.get("bbox") or []),
        } for value in ids(block)]

    def word_limit(role: str) -> int:
        if role in {"assessment", "activity", "life_skill"}:
            return 65
        if role in {"we_learn", "highlights", "recall", "glossary"}:
            return 85
        return 95

    def word_count(block: dict[str, Any]) -> int:
        return len(str(block.get("source_text") or "").split())

    def can_merge(left: dict[str, Any], right: dict[str, Any]) -> bool:
        if int(left.get("page_number") or 1) != int(right.get("page_number") or 1):
            return False
        left_type = str(left.get("block_type") or "")
        right_type = str(right.get("block_type") or "")
        if left_type in structured_types or right_type in structured_types:
            return False
        if left_type == "chapter_title" or right_type == "chapter_title":
            return False
        left_role = str(left.get("semantic_role") or "lesson_content")
        right_role = str(right.get("semantic_role") or "lesson_content")
        if left_role != right_role:
            return False
        # A named pedagogical box starts a new unit, then absorbs its items.
        if right_type == "section_heading" and right_role in special_roles:
            return False
        return word_count(left) + word_count(right) <= word_limit(left_role)

    def merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        result = dict(left)
        left_text = str(left.get("source_text") or "").strip()
        right_text = str(right.get("source_text") or "").strip()
        result["source_text"] = "\n".join(
            value for value in (left_text, right_text) if value
        )
        result["source_block_ids"] = list(dict.fromkeys(ids(left) + ids(right)))
        result["source_fragments"] = fragments(left) + fragments(right)
        types = {
            str(fragment.get("block_type") or "")
            for fragment in result["source_fragments"]
        }
        if "paragraph" in types or "callout" in types:
            result["block_type"] = "paragraph"
        elif len(result["source_block_ids"]) > 1:
            result["block_type"] = "grouped_content"
        return result

    output: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in blocks:
        if raw.get("required_for_coverage") is False or raw.get("block_type") == "decorative":
            continue
        block = dict(raw)
        block["source_block_ids"] = ids(block)
        block["source_fragments"] = fragments(block)
        if current is None:
            current = block
        elif can_merge(current, block):
            current = merge(current, block)
        else:
            output.append(current)
            current = block
    if current is not None:
        output.append(current)
    return output


def build_source_grounded_plan(
    blocks: list[dict[str, Any]],
    *,
    subject: str,
    subject_type: str,
    complexity_level: str,
    target_audience: str,
    title: str | None = None,
    delivery_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic zero-shot plan without replacing source text.

    This is the non-agent fallback used by the one-command pipeline.  It makes
    the source-to-section mapping explicit so completeness can be checked
    before media generation.  An agent-authored plan may still improve the
    delivery, but it must preserve these source block mappings.
    """

    sections: list[dict[str, Any]] = []
    section_index = 0
    grouped_blocks = _coalesce_planning_blocks(_group_textbook_callouts(blocks))
    for block_index, block in enumerate(grouped_blocks, 1):
        if (
            block.get("required_for_coverage") is False
            or block.get("block_type") == "decorative"
        ):
            continue
        source_text = str(
            block.get("source_text") or block.get("body_text") or ""
        ).strip()
        heading = str(block.get("heading") or "").strip()
        if block.get("block_type") in {"chapter_title", "section_heading"}:
            heading = source_text or heading
        if not source_text and not heading:
            continue
        block_id = str(block.get("block_id") or f"source-block-{block_index:04d}")
        source_block_ids = [
            str(value) for value in block.get("source_block_ids") or [block_id]
        ]
        block_type = _source_block_type(block, subject)
        source_table = block.get("table") if isinstance(block.get("table"), dict) else None
        render_mode = _source_render_mode(block_type, subject)
        table_chunks = _split_source_table(source_table) if source_table else [None]
        narration = source_text or heading
        narration_chunks = (
            [_table_spoken_text(table_chunk, narration) for table_chunk in table_chunks]
            if source_table is not None
            else _motion_narration_chunks(narration)
            if render_mode == "video_gen"
            else _motion_narration_chunks(narration, max_words=30)
            if render_mode == "manim"
            else [narration]
        )
        for chunk_index, (chunk, table_chunk) in enumerate(
            zip(narration_chunks, table_chunks if source_table is not None else [None] * len(narration_chunks)),
            1,
        ):
            section_index += 1
            word_count = max(1, len(chunk.split()))
            duration = max(3.0, round(word_count / 2.0 + 0.8, 2))
            section = {
                "section_id": f"section-{section_index:04d}",
                "title": heading or semantic_title(block, block_index),
                "description": chunk,
                "narration_script": chunk,
                "duration_seconds": duration,
                "equations": list(block.get("equations") or []),
                "key_concepts": [],
                "source_block_type": block_type,
                "source_block_ids": source_block_ids,
                "source_text": source_text,
                "source_document_block_type": str(block.get("block_type") or ""),
                "source_semantic_role": str(block.get("semantic_role") or "lesson_content"),
                "source_page_number": block.get("page_number"),
                "source_bbox": list(block.get("bbox") or []),
                "source_layout": dict(block.get("source_layout") or {}),
                "source_table": table_chunk,
                "source_table_page_index": chunk_index if source_table is not None else None,
                "source_table_page_count": len(table_chunks) if source_table is not None else None,
                "source_media": dict(block.get("media") or {}),
                "source_questions": list(block.get("source_questions") or []),
                "source_topics": list(block.get("source_topics") or []),
                "source_fragments": list(block.get("source_fragments") or []),
                "source_chunk_index": chunk_index,
                "source_chunk_count": len(narration_chunks),
                "render_mode": render_mode,
                "visual_elements": {
                    "diagrams": [],
                    "animations": [],
                    "color_scheme": [],
                },
                "transition_to_next": "crossfade",
            }
            sections.append(section)

    detected_title = title or next(
        (
            str(block.get("source_text") or block.get("heading"))
            for block in blocks
            if block.get("block_type") == "chapter_title"
            and (block.get("source_text") or block.get("heading"))
        ),
        "Educational Chapter",
    )
    plan = {
        "version": "1.0",
        "title": detected_title,
        "subject_classification": subject_type,
        "complexity_level": complexity_level,
        "target_audience": target_audience,
        "total_duration_seconds": round(
            sum(section["duration_seconds"] for section in sections), 2
        ),
        "learning_objectives": [],
        "sections": sections,
        "assessment": {},
        "metadata": {
            "plan_origin": "deterministic-source-contract",
            "source_block_count": len(blocks),
            "planning_group_count": len(grouped_blocks),
        },
    }
    return _enforce_plan(plan, subject, delivery_profile)


def semantic_title(block: dict[str, Any], index: int) -> str:
    source_text = " ".join(str(block.get("source_text") or "").split())
    if source_text:
        if len(source_text) <= 72:
            return source_text
        words = source_text.split()
        return " ".join(words[:8]).rstrip(".,;:") + "..."
    role = str(block.get("semantic_role") or block.get("block_type") or "concept")
    return role.replace("_", " ").title() or f"Section {index}"


# ---------------------------------------------------------------------------
# Dry-run fixture — three subjects
# ---------------------------------------------------------------------------

_DRY_RUN_FIXTURE: dict[str, Any] = {
    "version": "1.0",
    "title": "Animal Life — Chapter 8",
    "subject_classification": "theory",
    "complexity_level": "elementary",
    "target_audience": "Class 1, ages 5-7",
    "total_duration_seconds": 480,
    "learning_objectives": [
        "Identify water and land animals",
        "Name three types of birds",
        "Distinguish domestic from wild animals",
        "Match animals to their homes",
    ],
    "sections": [
        {
            "section_id":        "s00",
            "title":             "Chapter Title Card",
            "description":       "Animated chapter title intro",
            "narration_script":  "Today we learn about Animal Life!",
            "duration_seconds":  3,
            "equations":         [],
            "key_concepts":      [],
            "source_block_type": "intro",
            "visual_elements":   {"diagrams": [], "animations": ["bounce-in title"],
                                  "color_scheme": ["#FF8C42", "#FFD93D"]},
            "render_mode":       "hyperframes",
            "transition_to_next": "fade",
        },
        {
            "section_id":        "s01",
            "title":             "Animals Around Us",
            "description":       "Animals need food, shelter, air, water",
            "narration_script":  (
                "Animals live all around us. Like us, they need food. "
                "They need water. They need air. And they need a safe home. "
                "Can you name an animal you have seen today?"
            ),
            "duration_seconds":  30,
            "equations":         [],
            "key_concepts":      ["animals", "food", "shelter", "air", "water"],
            "source_block_type": "concept",
            "visual_elements":   {"diagrams": ["needs wheel"], "animations": [],
                                  "color_scheme": ["#FF8C42", "#6BCB77"]},
            "render_mode":       "manim",
            "transition_to_next": "slide",
        },
        {
            "section_id":        "s14",
            "title":             "Assessment — Questions",
            "description":       "Short-answer and fill-in-blank questions",
            "narration_script":  "Now let us test what we learned! Are you ready?",
            "duration_seconds":  40,
            "equations":         [],
            "key_concepts":      [],
            "source_block_type": "qa_item",
            "visual_elements":   {"diagrams": [], "animations": ["card flip"],
                                  "color_scheme": ["#FF6B9D", "#FFFDF0"]},
            "render_mode":       "hyperframes",
            "transition_to_next": "fade",
        },
    ],
    "assessment": {
        "quiz_questions": [
            {"question": "Name any two pet animals.",
             "type": "short_answer",
             "correct_answer": "dog, parrot, rabbit (any two)",
             "explanation": "Pet animals are kept at home."},
            {"question": "Fish live in ___.",
             "type": "fill_blank",
             "correct_answer": "water",
             "explanation": "Fish are aquatic animals."},
            {"question": "Butterfly is a ___.",
             "type": "mcq",
             "choices": ["a) bird", "b) insect", "c) animal"],
             "correct_answer": "b) insect",
             "explanation": "Insects have six legs."},
        ],
        "thought_experiments": ["What would happen if animals had no homes?"],
        "interactive_elements": ["Draw your favourite animal"],
    },
    "metadata": {
        "orchestrator":            "agent",
        "children_design_system":  "sunshine-classroom",
        "narration_wpm_target":    120,
        "max_concept_hold_seconds": 5,
    },
}


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

class EducationalContentGenerator(BaseTool):
    """Validate, enforce, and persist an agent-authored educational_plan.

    The agent produces the JSON plan content by following the EduGen 6-step
    prompt in skills/edustream/content-director.md. This tool validates and
    saves the result — it does not call any LLM API.
    """

    name = "educational_content_generator"
    version = "2.0.0"
    tier = ToolTier.CORE
    capability = "content_generation"
    provider = "openmontage"
    stability = ToolStability.PRODUCTION
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL     # local only — no API calls

    dependencies: list[str] = []   # no external dependencies
    install_instructions = "No setup required."
    agent_skills = ["edu-gen", "pedagogy"]
    capabilities = ["plan_validation", "render_mode_enforcement", "plan_persistence"]

    input_schema = {
        "type": "object",
        "properties": {
            # Option A: agent passes a pre-built plan dict
            "educational_plan": {
                "type": "object",
                "description": "Complete educational_plan JSON authored by the agent.",
            },
            # Option B: minimal fields — tool builds a shell, agent fills sections
            "source_content": {
                "type": "string",
                "description": "Raw source text (used to infer title/subject if plan omitted).",
            },
            "content_blocks": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Ordered normalized source blocks with stable block IDs.",
            },
            "title": {"type": "string"},
            "subject_type": {
                "type": "string",
                "enum": ["theory", "mathematics", "mixed"],
                "default": "mixed",
            },
            "complexity_level": {
                "type": "string",
                "enum": ["elementary", "middle_school", "high_school"],
                "default": "elementary",
            },
            "target_audience":        {"type": "string", "default": "Class 1, ages 5-7"},
            "delivery_profile":       {"type": "object"},
            "total_duration_seconds": {"type": "number", "default": 480},
            "subject":                {"type": "string", "default": "evs"},
            "output_dir":             {"type": "string"},
            "seed":                   {"type": "integer"},
            "dry_run":                {"type": "boolean", "default": False},
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "educational_plan": {"type": "object"},
            "output_path":      {"type": "string"},
        },
    }

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0   # no API calls

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 1.0   # local validation only

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        dry_run  = inputs.get("dry_run", False)
        subject  = inputs.get("subject", "evs")
        seed     = inputs.get("seed")
        out_dir  = Path(inputs.get("output_dir", "."))
        start    = time.monotonic()

        content_blocks = list(inputs.get("content_blocks") or [])
        if content_blocks and not inputs.get("educational_plan"):
            plan = build_source_grounded_plan(
                content_blocks,
                subject=subject,
                subject_type=inputs.get("subject_type", "mixed"),
                complexity_level=inputs.get("complexity_level", "elementary"),
                target_audience=inputs.get("target_audience", "Class 1, ages 5-7"),
                title=inputs.get("title"),
                delivery_profile=inputs.get("delivery_profile"),
            )
            if len(plan.get("sections", [])) < 2:
                return ToolResult(
                    success=False,
                    error=(
                        "Source extraction produced fewer than two usable blocks; "
                        "the chapter cannot be planned safely."
                    ),
                )
            if not dry_run:
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / "educational_plan.json"
                out_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
            else:
                out_path = Path()
            return ToolResult(
                success=True,
                data={"educational_plan": plan, "output_path": str(out_path)},
                artifacts=["educational_plan", "decision_log"],
                cost_usd=0.0,
                duration_seconds=time.monotonic() - start,
                seed=seed,
            )

        if dry_run:
            plan = _enforce_plan(
                dict(_DRY_RUN_FIXTURE), subject, inputs.get("delivery_profile")
            )
            return ToolResult(
                success=True,
                data={"educational_plan": plan, "output_path": ""},
                artifacts=["educational_plan", "decision_log"],
                cost_usd=0.0,
                duration_seconds=time.monotonic() - start,
                seed=seed,
            )

        # Use agent-provided plan if present
        plan = inputs.get("educational_plan")

        if not plan:
            # Build a minimal shell — agent must have provided sections via
            # educational_plan input; if they didn't, return a clear error
            return ToolResult(
                success=False,
                error=(
                    "educational_plan not provided. "
                    "The agent must author the plan by following "
                    "skills/edustream/content-director.md and pass it as "
                    "the 'educational_plan' input field."
                ),
            )

        # Enforce defaults and render_mode
        plan = _enforce_plan(plan, subject, inputs.get("delivery_profile"))
        plan.setdefault("title", inputs.get("source_content", "")[:60] or "Educational Video")
        plan.setdefault("subject_classification", inputs.get("subject_type", "theory"))
        plan.setdefault("total_duration_seconds", inputs.get("total_duration_seconds", 480))
        plan.setdefault("target_audience", inputs.get("target_audience", "Class 1, ages 5-7"))

        # Validate section count
        if len(plan.get("sections", [])) < 2:
            return ToolResult(
                success=False,
                error=f"educational_plan needs at least 2 sections, got {len(plan.get('sections', []))}",
            )

        # Persist
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "educational_plan.json"
        out_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")

        return ToolResult(
            success=True,
            data={"educational_plan": plan, "output_path": str(out_path)},
            artifacts=["educational_plan", "decision_log"],
            cost_usd=0.0,
            duration_seconds=time.monotonic() - start,
            seed=seed,
        )

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {
            "tool":                      self.name,
            "estimated_cost_usd":        0.0,
            "estimated_runtime_seconds": 1.0,
            "status":                    self.get_status().value,
            "would_execute":             True,
        }
