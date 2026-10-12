"""Canonical source-document and coverage contracts for educational videos.

The supplied textbook remains authoritative. This module turns extracted
Markdown into stable source blocks and a coverage ledger. Downstream stages
may enrich these artifacts, but must not silently delete required blocks.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_IMAGE_RE = re.compile(r"^!\[([^\]]*)\]\((.+?)\)\s*$")
_BULLET_RE = re.compile(r"^\s*[-*+]\s+(.+?)\s*$")
_NUMBERED_RE = re.compile(r"^\s*(\d+)[.)]\s+(.+?)\s*$")
_PAGE_MARKER_RE = re.compile(
    r"^\s*<!--\s*(?:page|page_number)\s*[:=]\s*(\d+)\s*-->\s*$", re.I
)
_TABLE_SEPARATOR_RE = re.compile(
    r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$"
)

_SECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("we_learn", re.compile(r"\bwe\s+learn\b", re.I)),
    ("highlights", re.compile(r"\b(?:lesson\s+)?highlights?\b", re.I)),
    ("recall", re.compile(r"\b(?:let.?s\s+)?recall\b|\blet.?s\s+remember\b|\bsummary\b", re.I)),
    ("glossary", re.compile(r"\bglossary\b|\bvocabulary\b|\bnew\s+words?\b|\bword\s+bank\b", re.I)),
    (
        "assessment",
        re.compile(
            r"answer\s+the\s+following|fill\s+in\s+the\s+blanks?|"
            r"choose\s+the\s+correct|true\s+or\s+false|match\s+the\s+following|"
            r"exercises?|questions?\s+and\s+answers?",
            re.I,
        ),
    ),
    ("activity", re.compile(r"\bactivity\b|\bproject\b|\btry\s+this\b", re.I)),
    ("life_skill", re.compile(r"\blife\s*skills?\b|\bvalue\s+education\b", re.I)),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _is_page_furniture(value: str) -> bool:
    """Identify running page furniture that must never become narration/UI."""

    normalized = " ".join(str(value or "").split()).strip()
    if not normalized:
        return False
    return bool(
        re.fullmatch(r"(?:page\s*)?\d{1,4}", normalized, re.I)
        or re.search(r"\b(?:isbn|copyright|all rights reserved)\b", normalized, re.I)
        or re.fullmatch(
            r"\d+\s+(?:sv\s+)?rockland\b.*\b(?:class|book)\s*-?\s*\d+.*",
            normalized,
            re.I,
        )
        or re.fullmatch(
            r"(?:sv\s+)?rockland\b.*\b(?:class|book)\s*-?\s*\d+.*\d+",
            normalized,
            re.I,
        )
    )


def _text_match_score(left: str, right: str) -> float:
    """Return conservative similarity so a shared word cannot hide a box."""
    left = _normalized_text(left)
    right = _normalized_text(right)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    substring_score = 0.0
    if left in right or right in left:
        substring_score = min(len(left), len(right)) / max(len(left), len(right))
    left_tokens = set(re.findall(r"[a-z0-9]+", left))
    right_tokens = set(re.findall(r"[a-z0-9]+", right))
    token_score = len(left_tokens & right_tokens) / max(
        len(left_tokens), len(right_tokens), 1
    )
    return max(substring_score, token_score)


def _load_layout_pages(extraction_artifact_path: Path | None) -> list[dict[str, Any]]:
    if not extraction_artifact_path:
        return []
    try:
        artifact = json.loads(Path(extraction_artifact_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    pages = artifact.get("layout_pages", [])
    return list(pages) if isinstance(pages, list) else []


def _apply_pdf_geometry(
    blocks: list[dict[str, Any]], layout_pages: list[dict[str, Any]]
) -> int:
    """Attach the best matching PDF bounding box to normalized blocks."""

    text_candidates: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    image_candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
    table_candidates: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    for page in layout_pages:
        for item in page.get("blocks", []):
            if item.get("kind") == "image":
                image_candidates.append((page, item))
            else:
                text = _normalized_text(str(item.get("text", "")))
                if text:
                    text_candidates.append((page, item, text))
        for table in page.get("tables", []):
            text = _normalized_text(
                " ".join(str(cell) for row in table.get("rows", []) for cell in row)
            )
            if text:
                table_candidates.append((page, table, text))

    matched = 0
    image_index = 0
    for block in blocks:
        source_text = _normalized_text(str(block.get("source_text", "")))
        match: tuple[dict[str, Any], dict[str, Any], str] | None = None
        candidates = table_candidates if block.get("block_type") == "table" else text_candidates
        best_score = 0.0
        for candidate in candidates:
            candidate_text = candidate[2]
            if not source_text or not candidate_text:
                continue
            score = _text_match_score(source_text, candidate_text)
            if score >= 0.6 and score > best_score:
                match, best_score = candidate, score

        if match is None and block.get("block_type") == "figure" and image_candidates:
            page, item = image_candidates[min(image_index, len(image_candidates) - 1)]
            image_index += 1
            match = (page, item, "")

        if match is None:
            continue
        page, item, _candidate_text = match
        bbox = item.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        block["page_number"] = int(page.get("page_number", block["page_number"]))
        block["bbox"] = [float(value) for value in bbox]
        page_width = float(page.get("width") or 0.0)
        page_height = float(page.get("height") or 0.0)
        normalized_bbox = []
        if page_width > 0 and page_height > 0:
            normalized_bbox = [
                round(float(bbox[0]) / page_width, 6),
                round(float(bbox[1]) / page_height, 6),
                round(float(bbox[2]) / page_width, 6),
                round(float(bbox[3]) / page_height, 6),
            ]
        block["source_layout"] = {
            "kind": str(item.get("kind") or (
                "table" if block.get("block_type") == "table" else "text"
            )),
            "reading_order": int(item.get("reading_order") or block["reading_order"]),
            "bbox": [float(value) for value in bbox],
            "normalized_bbox": normalized_bbox,
            "page_width": page_width,
            "page_height": page_height,
            "unit": str(page.get("unit") or "points"),
            "text_styles": list(item.get("text_styles") or []),
        }
        if block["provenance"].get("extraction_mode") != "pdf-layout-recovery":
            block["provenance"]["extraction_mode"] = "pdf-layout-match"
        matched += 1

    # IDs and reading order encode final page geometry deterministically.
    blocks.sort(key=lambda item: (
        int(item.get("page_number") or 1),
        float((item.get("bbox") or [0.0, float("inf")])[1]),
        int(item.get("reading_order") or 0),
    ))
    per_page: dict[int, int] = {}
    active_heading = ""
    for reading_order, block in enumerate(blocks, 1):
        block["reading_order"] = reading_order
        page_number = int(block["page_number"])
        per_page[page_number] = per_page.get(page_number, 0) + 1
        block["block_id"] = f"p{page_number:04d}-b{per_page[page_number]:04d}"
        if block.get("block_type") in {"chapter_title", "section_heading"}:
            active_heading = str(block.get("source_text") or "").strip()
            block["heading"] = active_heading
        elif active_heading and not block.get("heading"):
            block["heading"] = active_heading
    return matched


def _assign_spatial_callout_roles(
    blocks: list[dict[str, Any]], layout_pages: list[dict[str, Any]]
) -> None:
    """Resolve side-by-side textbook cards by geometry instead of text order.

    PDF extraction is usually top-to-bottom. When ``We Learn`` and
    ``Highlights`` cards share the same row, that order interleaves their
    contents and causes one heading to absorb the other card and the body text.
    This pass assigns only compact, nearby column content to each card.
    """

    page_sizes = {
        int(page.get("page_number") or 0): (
            float(page.get("width") or 0.0),
            float(page.get("height") or 0.0),
        )
        for page in layout_pages
    }
    special_roles = {"we_learn", "highlights"}
    by_page: dict[int, list[dict[str, Any]]] = {}
    for block in blocks:
        by_page.setdefault(int(block.get("page_number") or 1), []).append(block)

    for page_number, page_blocks in by_page.items():
        headings = [
            block for block in page_blocks
            if block.get("block_type") in {"chapter_title", "section_heading"}
            and block.get("semantic_role") in special_roles
            and len(block.get("bbox") or []) == 4
        ]
        if len(headings) < 2:
            continue
        heading_tops = [float(block["bbox"][1]) for block in headings]
        if max(heading_tops) - min(heading_tops) > 60:
            continue
        page_width, page_height = page_sizes.get(page_number, (0.0, 0.0))
        if page_width <= 0 or page_height <= 0:
            continue

        for block in page_blocks:
            if block in headings or block.get("block_type") == "decorative":
                continue
            if block.get("semantic_role") in special_roles:
                block["semantic_role"] = "lesson_content"
                block.pop("heading", None)

        for heading in headings:
            hx0, _hy0, hx1, hy1 = [float(value) for value in heading["bbox"]]
            center_x = (hx0 + hx1) / 2.0
            current_bottom = hy1
            assigned = 0
            for block in sorted(page_blocks, key=lambda item: float((item.get("bbox") or [0, float("inf")])[1])):
                if block in headings or block.get("block_type") == "decorative":
                    continue
                bbox = block.get("bbox") or []
                if len(bbox) != 4:
                    continue
                x0, y0, x1, y1 = [float(value) for value in bbox]
                if y0 < hy1:
                    continue
                width = x1 - x0
                candidate_center = (x0 + x1) / 2.0
                if width > page_width * 0.58:
                    if assigned:
                        break
                    continue
                if abs(candidate_center - center_x) > page_width * 0.30:
                    continue
                if y0 - current_bottom > 52:
                    if assigned:
                        break
                    continue
                if y1 - hy1 > page_height * 0.25:
                    break
                block["semantic_role"] = heading["semantic_role"]
                block["heading"] = heading["source_text"]
                current_bottom = max(current_bottom, y1)
                assigned += 1

        for block in page_blocks:
            if re.fullmatch(r"[_\-–—.\s]{4,}", str(block.get("source_text") or "")):
                block["block_type"] = "decorative"
                block["required_for_coverage"] = False


def _section_role(text: str) -> str:
    for role, pattern in _SECTION_PATTERNS:
        if pattern.search(text):
            return role
    return "lesson_content"


def _split_table_row(line: str) -> list[str]:
    value = line.strip()
    if value.startswith("|"):
        value = value[1:]
    if value.endswith("|"):
        value = value[:-1]
    return [cell.strip() for cell in value.split("|")]


def _table_payload(lines: list[str]) -> dict[str, Any]:
    rows = [_split_table_row(line) for line in lines]
    has_header = len(rows) > 1 and _TABLE_SEPARATOR_RE.match(lines[1]) is not None
    if has_header:
        rows.pop(1)
    cells: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows):
        for column_index, text in enumerate(row):
            cells.append({
                "row": row_index,
                "column": column_index,
                "text": text,
                "row_span": 1,
                "column_span": 1,
                "is_header": bool(has_header and row_index == 0),
            })
    return {
        "row_count": len(rows),
        "column_count": max((len(row) for row in rows), default=0),
        "header_rows": 1 if has_header else 0,
        "cells": cells,
    }


def _table_payload_from_rows(rows: list[list[Any]]) -> dict[str, Any]:
    normalized = [
        [str(cell or "").strip() for cell in row]
        for row in rows
        if isinstance(row, list)
    ]
    cells: list[dict[str, Any]] = []
    for row_index, row in enumerate(normalized):
        for column_index, text in enumerate(row):
            cells.append({
                "row": row_index,
                "column": column_index,
                "text": text,
                "row_span": 1,
                "column_span": 1,
                "is_header": bool(row_index == 0),
            })
    return {
        "row_count": len(normalized),
        "column_count": max((len(row) for row in normalized), default=0),
        "header_rows": 1 if normalized else 0,
        "cells": cells,
    }


def _recover_unrepresented_layout_blocks(
    blocks: list[dict[str, Any]], layout_pages: list[dict[str, Any]]
) -> int:
    """Recover PDF tables/callouts omitted by the Markdown conversion."""
    known = [
        _normalized_text(str(block.get("source_text") or ""))
        for block in blocks
        if block.get("source_text")
    ]
    recovered = 0
    next_order = max((int(block.get("reading_order", 0)) for block in blocks), default=0)

    def represented(text: str) -> bool:
        normalized = _normalized_text(text)
        if not normalized:
            return True
        return any(
            _text_match_score(normalized, existing) >= 0.7
            for existing in known if existing
        )

    for page in layout_pages:
        page_number = int(page.get("page_number") or 1)
        for item in page.get("blocks", []):
            if item.get("kind") != "text":
                continue
            text = str(item.get("text") or "").strip()
            if represented(text):
                continue
            normalized = _normalized_text(text)
            decorative = _is_page_furniture(text)
            next_order += 1
            block = _make_block(
                page_number=page_number,
                index=next_order,
                reading_order=next_order,
                block_type="decorative" if decorative else "callout",
                source_text=text,
                source_line_start=1,
                source_line_end=1,
                semantic_role=_section_role(text),
            )
            block["provenance"]["extraction_mode"] = "pdf-layout-recovery"
            blocks.append(block)
            known.append(normalized)
            recovered += 1

        for table in page.get("tables", []):
            rows = table.get("rows") or []
            flat_text = " ".join(
                str(cell or "") for row in rows if isinstance(row, list) for cell in row
            ).strip()
            if not flat_text or represented(flat_text):
                continue
            next_order += 1
            source_text = "\n".join(
                " | ".join(str(cell or "").strip() for cell in row)
                for row in rows if isinstance(row, list)
            )
            block = _make_block(
                page_number=page_number,
                index=next_order,
                reading_order=next_order,
                block_type="table",
                source_text=source_text,
                source_line_start=1,
                source_line_end=1,
                semantic_role="lesson_content",
                extra={"table": _table_payload_from_rows(rows)},
            )
            block["provenance"]["extraction_mode"] = "pdf-layout-recovery"
            blocks.append(block)
            known.append(_normalized_text(flat_text))
            recovered += 1
    return recovered


def _make_block(
    *,
    page_number: int,
    index: int,
    reading_order: int,
    block_type: str,
    source_text: str,
    source_line_start: int,
    source_line_end: int,
    semantic_role: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    block = {
        "block_id": f"p{page_number:04d}-b{index:04d}",
        "page_number": page_number,
        "reading_order": reading_order,
        "block_type": block_type,
        "semantic_role": semantic_role,
        "source_text": source_text,
        "required_for_coverage": block_type != "decorative",
        "provenance": {
            "source_line_start": source_line_start,
            "source_line_end": source_line_end,
            "extraction_mode": "markdown_fallback",
        },
    }
    if extra:
        block.update(extra)
    return block


def normalize_markdown_document(
    source_path: Path,
    *,
    source_pdf: str | None = None,
    source_input: str | None = None,
    extraction_artifact_path: Path | None = None,
) -> dict[str, Any]:
    """Normalize Markdown while explicitly recording missing PDF geometry."""
    source_path = Path(source_path).resolve()
    lines = source_path.read_text(encoding="utf-8").splitlines()
    blocks: list[dict[str, Any]] = []
    page_number = 1
    page_block_index = 0
    reading_order = 0
    current_role = "lesson_content"
    current_heading = ""
    i = 0

    def append_block(
        block_type: str,
        text: str,
        start_line: int,
        end_line: int,
        *,
        role: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        nonlocal page_block_index, reading_order
        page_block_index += 1
        reading_order += 1
        payload = dict(extra or {})
        if current_heading and "heading" not in payload:
            payload["heading"] = current_heading
        blocks.append(_make_block(
            page_number=page_number,
            index=page_block_index,
            reading_order=reading_order,
            block_type=block_type,
            source_text=text,
            source_line_start=start_line,
            source_line_end=end_line,
            semantic_role=role or current_role,
            extra=payload,
        ))

    while i < len(lines):
        raw = lines[i]
        line = raw.strip()
        line_number = i + 1
        i += 1
        if not line:
            continue

        page_match = _PAGE_MARKER_RE.match(line)
        if page_match:
            page_number = int(page_match.group(1))
            page_block_index = 0
            continue

        heading_match = _HEADING_RE.match(line)
        if heading_match:
            heading_text = heading_match.group(2)
            if _is_page_furniture(heading_text):
                append_block(
                    "decorative",
                    heading_text,
                    line_number,
                    line_number,
                    role="lesson_content",
                )
                continue
            current_role = _section_role(heading_text)
            current_heading = heading_text
            append_block(
                "chapter_title" if heading_match.group(1) == "#" else "section_heading",
                heading_text,
                line_number,
                line_number,
                role=current_role,
                extra={"heading_level": len(heading_match.group(1))},
            )
            continue

        image_match = _IMAGE_RE.match(line)
        if image_match:
            alt_text, source = image_match.groups()
            append_block(
                "figure",
                alt_text,
                line_number,
                line_number,
                extra={"media": {"source": source, "alt_text": alt_text}},
            )
            continue

        # Keep a table as one structured block so planning cannot split cells.
        if "|" in line and i < len(lines) and _TABLE_SEPARATOR_RE.match(lines[i]):
            table_lines = [raw, lines[i]]
            i += 1
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                table_lines.append(lines[i])
                i += 1
            append_block(
                "table",
                "\n".join(table_lines),
                line_number,
                line_number + len(table_lines) - 1,
                extra={"table": _table_payload(table_lines)},
            )
            continue

        bullet_match = _BULLET_RE.match(line)
        numbered_match = _NUMBERED_RE.match(line)
        if bullet_match and not re.search(r"[A-Za-z0-9]", bullet_match.group(1)):
            # A maths worksheet may place an operator row such as "+ =" in a
            # separate PDF text box. It is not a Markdown bullet. Preserve the
            # full symbolic expression so geometry matching and Manim routing
            # retain the source exercise instead of reducing it to "=".
            append_block(
                "equation",
                line,
                line_number,
                line_number,
            )
            continue
        if bullet_match or numbered_match:
            text = (bullet_match or numbered_match).group(1 if bullet_match else 2)
            kind = {
                "recall": "recall",
                "glossary": "glossary",
                "assessment": "assessment",
                "activity": "activity",
                "life_skill": "life_skill",
            }.get(current_role, "bullet")
            extra: dict[str, Any] = {}
            if numbered_match:
                extra["list_ordinal"] = numbered_match.group(1)
            append_block(kind, text, line_number, line_number, extra=extra)
            continue

        if _is_page_furniture(line):
            append_block(
                "decorative",
                line,
                line_number,
                line_number,
                role="lesson_content",
            )
            continue

        kind = {
            "recall": "recall",
            "glossary": "glossary",
            "assessment": "assessment",
            "activity": "activity",
            "life_skill": "life_skill",
        }.get(current_role, "paragraph")
        append_block(kind, line, line_number, line_number)

    layout_pages = _load_layout_pages(extraction_artifact_path)
    recovered_layout_blocks = (
        _recover_unrepresented_layout_blocks(blocks, layout_pages)
        if layout_pages else 0
    )
    geometry_matches = _apply_pdf_geometry(blocks, layout_pages) if layout_pages else 0
    if layout_pages:
        _assign_spatial_callout_roles(blocks, layout_pages)
    layout_by_number = {
        int(page.get("page_number", 0)): page for page in layout_pages
    }
    page_numbers = sorted({block["page_number"] for block in blocks}) or [1]
    pages = []
    for number in page_numbers:
        page = {
            "page_number": number,
            "block_ids": [
                block["block_id"] for block in blocks if block["page_number"] == number
            ],
        }
        layout_page = layout_by_number.get(number, {})
        if layout_page.get("width") and layout_page.get("height"):
            page.update({
                "width": float(layout_page["width"]),
                "height": float(layout_page["height"]),
                "unit": layout_page.get("unit", "points"),
            })
        pages.append(page)
    required_blocks = [block for block in blocks if block["required_for_coverage"]]
    unmatched_required = sum("bbox" not in block for block in required_blocks)
    return {
        "version": "1.0",
        "source": {
            "path": source_pdf or source_input or str(source_path),
            "format": (
                "pdf"
                if source_pdf
                else Path(source_input).suffix.lstrip(".").lower()
                if source_input
                else source_path.suffix.lstrip(".").lower()
            ),
            "text_artifact": str(source_path),
            "text_sha256": _sha256(source_path),
            "extraction_artifact": (
                str(Path(extraction_artifact_path).resolve())
                if extraction_artifact_path else None
            ),
        },
        "layout_fidelity": {
            "reading_order": "preserved",
            "tables": "structured_when_markdown_table_present",
            "geometry": (
                "pdf_bounding_boxes_complete"
                if required_blocks and unmatched_required == 0
                else "pdf_bounding_boxes_partial"
                if geometry_matches
                else "unavailable"
            ),
            "text_boxes": (
                "positions_and_text_style_preserved"
                if required_blocks and unmatched_required == 0
                else "partial_geometry_requires_visual_audit"
                if geometry_matches
                else "semantic_heading_inference_only"
            ),
            "requires_visual_pdf_audit": bool(unmatched_required),
        },
        "pages": pages,
        "blocks": blocks,
        "validation": {
            "block_count": len(blocks),
            "required_block_count": sum(bool(block["required_for_coverage"]) for block in blocks),
            "page_count_represented": len(pages),
            "semantic_roles": sorted({block["semantic_role"] for block in blocks}),
            "duplicate_block_ids": len({block["block_id"] for block in blocks}) != len(blocks),
            "recovered_layout_blocks": recovered_layout_blocks,
        },
    }


def coverage_summary(entries: Iterable[dict[str, Any]]) -> dict[str, Any]:
    entries = list(entries)
    required = [entry for entry in entries if entry.get("required", True)]
    mapped = [entry for entry in required if entry.get("status") == "mapped"]
    omitted = [entry for entry in required if entry.get("status") == "omitted"]
    pending = [entry for entry in required if entry.get("status") == "pending"]
    invalid_omissions = [
        entry["source_block_id"] for entry in omitted
        if not str(entry.get("omission_reason") or "").strip()
    ]
    coverage_ratio = len(mapped) / len(required) if required else 1.0
    blocking = [entry["source_block_id"] for entry in pending] + invalid_omissions
    return {
        "total_blocks": len(entries),
        "required_blocks": len(required),
        "mapped_blocks": len(mapped),
        "pending_blocks": len(pending),
        "omitted_required_blocks": len(omitted),
        "coverage_ratio": round(coverage_ratio, 6),
        "render_ready": not blocking and coverage_ratio == 1.0,
        "blocking_source_block_ids": blocking,
    }


def build_coverage_contract(chapter_document: dict[str, Any]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for block in chapter_document["blocks"]:
        required = bool(block.get("required_for_coverage", True))
        entries.append({
            "source_block_id": block["block_id"],
            "page_number": block["page_number"],
            "block_type": block["block_type"],
            "semantic_role": block["semantic_role"],
            "source_text_sha256": hashlib.sha256(
                block.get("source_text", "").encode("utf-8")
            ).hexdigest(),
            "required": required,
            "status": "pending" if required else "omitted",
            "mappings": {
                "narration_segment_ids": [], "screen_ids": [], "visual_cue_ids": [],
            },
            "omission_reason": None if required else "decorative_source_block",
        })
    return {
        "version": "1.0",
        "source_document_sha256": chapter_document["source"]["text_sha256"],
        "source_document_path": chapter_document["source"]["text_artifact"],
        "entries": entries,
        "summary": coverage_summary(entries),
    }


def validate_coverage_contract(
    contract: dict[str, Any], *, require_complete: bool = True
) -> dict[str, Any]:
    """Recalculate coverage and fail closed when required mappings are absent."""
    block_ids = [entry["source_block_id"] for entry in contract.get("entries", [])]
    duplicates = sorted({block_id for block_id in block_ids if block_ids.count(block_id) > 1})
    if duplicates:
        raise ValueError(f"Duplicate coverage entries: {', '.join(duplicates)}")
    for entry in contract.get("entries", []):
        if entry.get("status") == "mapped":
            mappings = entry.get("mappings", {})
            if not mappings.get("narration_segment_ids") and not mappings.get("screen_ids"):
                raise ValueError(
                    f"Mapped source block {entry['source_block_id']} has no narration or screen mapping"
                )
    summary = coverage_summary(contract.get("entries", []))
    if require_complete and not summary["render_ready"]:
        raise ValueError(
            "Source coverage is incomplete; blocking blocks: "
            + ", ".join(summary["blocking_source_block_ids"][:20])
        )
    return summary


def validate_final_source_coverage(
    contract: dict[str, Any],
    *,
    educational_plan: dict[str, Any],
    narration_manifest: dict[str, Any],
    clip_manifest: list[dict[str, Any]],
    composition_timeline: dict[str, Any],
    require_complete: bool = True,
) -> dict[str, Any]:
    """Prove that mapped textbook blocks survive every production artifact.

    Planning coverage alone is insufficient: a later orchestration, audio,
    rendering, or composition stage could silently drop a section. This gate
    verifies each mapped screen/narration ID against the final authored
    HyperFrames timeline before the expensive encode begins.
    """

    plan_sections = {
        str(section.get("section_id") or ""): section
        for section in educational_plan.get("sections", [])
    }
    narration_segments = {
        str(segment.get("section_id") or ""): segment
        for segment in narration_manifest.get("segments", [])
    }
    clips = {
        str(clip.get("section_id") or ""): clip
        for clip in clip_manifest
    }
    composed_sections = {
        str(section.get("section_id") or ""): section
        for section in composition_timeline.get("sections", [])
    }

    issues: list[dict[str, str]] = []
    verified_blocks = 0
    required_entries = [
        entry for entry in contract.get("entries", []) if entry.get("required", True)
    ]
    for entry in required_entries:
        block_id = str(entry.get("source_block_id") or "")
        block_issues: list[dict[str, str]] = []
        if entry.get("status") != "mapped":
            block_issues.append({
                "source_block_id": block_id,
                "code": "not_mapped",
                "detail": "required source block is not mapped by the educational plan",
            })
        mappings = entry.get("mappings") or {}
        screen_ids = [str(value) for value in mappings.get("screen_ids") or []]
        narration_ids = [
            str(value) for value in mappings.get("narration_segment_ids") or []
        ]
        if not screen_ids:
            block_issues.append({
                "source_block_id": block_id,
                "code": "missing_screen_mapping",
                "detail": "required source block has no authored screen IDs",
            })
        for section_id in screen_ids:
            if section_id not in plan_sections:
                block_issues.append({
                    "source_block_id": block_id,
                    "code": "missing_plan_section",
                    "detail": section_id,
                })
            if section_id not in composed_sections:
                block_issues.append({
                    "source_block_id": block_id,
                    "code": "missing_composition_section",
                    "detail": section_id,
                })
            else:
                composed_source_ids = {
                    str(value)
                    for value in composed_sections[section_id].get("source_block_ids", [])
                }
                if block_id not in composed_source_ids:
                    block_issues.append({
                        "source_block_id": block_id,
                        "code": "composition_lost_source_provenance",
                        "detail": section_id,
                    })
            clip = clips.get(section_id)
            if clip is None:
                block_issues.append({
                    "source_block_id": block_id,
                    "code": "missing_clip_record",
                    "detail": section_id,
                })
            elif clip.get("success") is False:
                block_issues.append({
                    "source_block_id": block_id,
                    "code": "failed_clip",
                    "detail": section_id,
                })
        for section_id in narration_ids:
            segment = narration_segments.get(section_id)
            if segment is None:
                block_issues.append({
                    "source_block_id": block_id,
                    "code": "missing_narration_segment",
                    "detail": section_id,
                })
            elif not str(segment.get("text") or "").strip():
                block_issues.append({
                    "source_block_id": block_id,
                    "code": "empty_narration_segment",
                    "detail": section_id,
                })
        if not block_issues:
            verified_blocks += 1
        issues.extend(block_issues)

    ratio = verified_blocks / len(required_entries) if required_entries else 1.0
    report = {
        "version": "1.0",
        "status": "pass" if not issues and ratio == 1.0 else "fail",
        "required_blocks": len(required_entries),
        "verified_blocks": verified_blocks,
        "coverage_ratio": round(ratio, 6),
        "issues": issues,
    }
    if require_complete and report["status"] != "pass":
        sample = ", ".join(
            f"{issue['source_block_id']}:{issue['code']}"
            for issue in issues[:20]
        )
        raise ValueError(
            "Final source coverage is incomplete after composition: " + sample
        )
    return report


def write_source_contracts(
    source_path: Path,
    chapter_document_path: Path,
    coverage_contract_path: Path,
    *,
    source_pdf: str | None = None,
    source_input: str | None = None,
    extraction_artifact_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_markdown_document(
        source_path,
        source_pdf=source_pdf,
        source_input=source_input,
        extraction_artifact_path=extraction_artifact_path,
    )
    coverage = build_coverage_contract(document)
    chapter_document_path.parent.mkdir(parents=True, exist_ok=True)
    coverage_contract_path.parent.mkdir(parents=True, exist_ok=True)
    chapter_document_path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    coverage_contract_path.write_text(
        json.dumps(coverage, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return document, coverage
