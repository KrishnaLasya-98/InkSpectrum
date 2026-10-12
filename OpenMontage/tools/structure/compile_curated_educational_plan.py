"""Compile a reviewed chapter-plan specification against a source contract.

The specification contains human-readable teaching sections and source block
selectors.  This compiler expands those selectors to stable PDF block IDs,
copies the associated source metadata, and fails closed if any required source
block is omitted.  It keeps chapter-specific editorial writing out of the
pipeline implementation while making the approval artifact reproducible.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
from typing import Any


_TERMINAL_PUNCTUATION = re.compile(r"[.!?:][\"'”’)]*$")


def _has_terminal_punctuation(value: str) -> bool:
    """Treat punctuation before a closing quote/bracket as terminal."""
    return bool(_TERMINAL_PUNCTUATION.search(value.rstrip()))


def _source_delivery(section: dict, selected: list[dict], policy: dict) -> None:
    """Compile reviewed source selections without asking a model to retype them.

    This is opt-in. Answers and animation descriptions remain authored inputs;
    the compiler only copies source text and creates testable delivery evidence.
    """
    source = {str(block["block_id"]): block for block in selected}
    questions = section.get("questions", [])
    question_map = {}
    for authored in questions:
        bid = authored["source_block_id"]
        if bid not in source:
            raise ValueError(f"Question source is outside section: {bid}")
        question = dict(authored)
        question["question"] = source[bid]["source_text"]
        question_map[bid] = question
    prefix = section.pop("narration_prefix", "")
    table_reading = section.pop("table_reading", "rows")
    if table_reading not in {"rows", "columns"}:
        raise ValueError("table_reading must be rows or columns")
    spoken, excerpts = ([prefix] if prefix else []), []
    for index, block in enumerate(selected):
        bid = block["block_id"]
        value = " ".join(str(block.get("source_text") or "").split())
        table = block.get("table")
        is_table = bool(table and block.get("block_type") == "table")
        is_figure = block.get("block_type") == "figure"
        excerpts.append({"block_id": bid, "verbatim_text": value,
                         "display_text": value, "narrate_verbatim": not (is_table or is_figure)})
        if is_figure:
            continue  # Labels remain visible on the source diagram, not read as a word salad.
        if is_table:
            rows = {}
            for cell in table.get("cells", []):
                rows.setdefault(cell["column" if table_reading == "columns" else "row"], []).append(cell)
            for row in sorted(rows):
                spoken.append(". ".join(str(cell["text"]).strip().rstrip(".")
                              for cell in sorted(rows[row], key=lambda c: c["row" if table_reading == "columns" else "column"])) + ".")
        elif value:
            next_is_bullet = (
                index + 1 < len(selected)
                and selected[index + 1].get("block_type") == "bullet"
            )
            if next_is_bullet and block.get("block_type") == "paragraph" and not _has_terminal_punctuation(value):
                spoken.append(value + ":")
            else:
                spoken.append(value if _has_terminal_punctuation(value) else value + ".")
        if bid in question_map:
            spoken.append("Answer. " + question_map[bid]["answer"])
            spoken.extend(question_map[bid].get("solution_steps") or [])
    explanations = section.pop("delivery_explanations", [])
    spoken.extend(explanations)
    narration = " ".join(spoken)
    section["narration_script"] = narration
    section["teaching_contract"] = {
        "source_excerpts": excerpts, "explanations": explanations,
        "questions": list(question_map.values()),
        "animation_beats": [{
            "cue_text": " ".join(narration.split()[:6]),
            "visual": section["description"],
            "action": section.pop("animation_action"),
        }],
    }
    section.pop("questions", None)
    section.setdefault("equations", [])
    section.setdefault("duration_seconds", max(3, math.ceil(
        len(narration.split()) * 60 / float(policy.get("estimated_wpm", 120))
        + sum(float(q.get("thinking_pause_seconds", 0)) for q in question_map.values())
        + float(policy.get("heading_pause_seconds", 2))
        + float(policy.get("topic_pause_seconds", 1.5)))))


def _block_number(block_id: str) -> int:
    return int(block_id.rsplit("b", 1)[1])


def _selected_blocks(
    blocks: list[dict[str, Any]], selectors: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for selector in selectors:
        page = int(selector["page"])
        start = int(selector.get("start", 1))
        end = int(selector.get("end", 9999))
        for block in blocks:
            block_id = str(block.get("block_id") or "")
            if int(block.get("page_number") or 0) != page:
                continue
            number = _block_number(block_id)
            if start <= number <= end and block_id not in seen:
                selected.append(block)
                seen.add(block_id)
    return selected


def compile_plan(
    chapter_document: dict[str, Any], specification: dict[str, Any]
) -> dict[str, Any]:
    blocks = list(chapter_document.get("blocks") or [])
    required_ids = {
        str(block["block_id"])
        for block in blocks
        if block.get("required_for_coverage")
    }
    mapped_ids: set[str] = set()
    sections: list[dict[str, Any]] = []

    for raw in specification.get("sections") or []:
        section = {**specification.get("section_defaults", {}), **raw}
        source_delivery = section.pop("source_delivery", False)
        selectors = list(section.pop("source_selectors", []) or [])
        selected = _selected_blocks(blocks, selectors)
        source_ids = [str(block["block_id"]) for block in selected]
        if not source_ids:
            raise ValueError(
                f"Section {section.get('section_id')} selected no source blocks"
            )
        mapped_ids.update(source_ids)
        if source_delivery:
            _source_delivery(section, selected, specification.get("metadata", {}).get("delivery_policy", {}))
        first = selected[0]
        source_texts = [
            " ".join(str(block.get("source_text") or "").split())
            for block in selected
            if str(block.get("source_text") or "").strip()
        ]
        section.update(
            {
                "source_block_ids": source_ids,
                "source_text": "\n".join(source_texts),
                "source_document_block_type": str(
                    first.get("block_type") or "paragraph"
                ),
                "source_semantic_role": str(
                    first.get("semantic_role") or "lesson_content"
                ),
                "source_page_number": int(first.get("page_number") or 0),
                "source_bbox": list(first.get("bbox") or []),
                "source_fragments": [
                    {
                        "block_id": block["block_id"],
                        "page_number": block.get("page_number"),
                        "block_type": block.get("block_type"),
                        "semantic_role": block.get("semantic_role"),
                        "source_text": block.get("source_text", ""),
                        "bbox": block.get("bbox", []),
                    }
                    for block in selected
                ],
                "transition_to_next": section.get(
                    "transition_to_next", "crossfade"
                ),
            }
        )
        sections.append(section)

    missing = sorted(required_ids - mapped_ids)
    unknown = sorted(mapped_ids - {str(block["block_id"]) for block in blocks})
    if missing or unknown:
        raise ValueError(
            "Curated plan source coverage failed: "
            f"missing={missing[:20]} unknown={unknown[:20]}"
        )

    plan = {
        key: value
        for key, value in specification.items()
        if key not in {"sections", "section_defaults"}
    }
    plan["sections"] = sections
    plan["total_duration_seconds"] = round(
        sum(float(section.get("duration_seconds") or 0.0) for section in sections),
        2,
    )
    metadata = dict(plan.get("metadata") or {})
    metadata.update(
        {
            "plan_origin": "reviewed-curated-source-contract",
            "source_block_count": len(blocks),
            "required_source_block_count": len(required_ids),
            "mapped_required_source_block_count": len(required_ids & mapped_ids),
        }
    )
    plan["metadata"] = metadata
    return plan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("chapter_document")
    parser.add_argument("specification")
    parser.add_argument("output")
    args = parser.parse_args()
    chapter_document = json.loads(
        Path(args.chapter_document).read_text(encoding="utf-8")
    )
    specification = json.loads(
        Path(args.specification).read_text(encoding="utf-8")
    )
    plan = compile_plan(chapter_document, specification)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(output.resolve()),
                "sections": len(plan["sections"]),
                "duration_seconds": plan["total_duration_seconds"],
                "mapped_required_source_blocks": plan["metadata"][
                    "mapped_required_source_block_count"
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
