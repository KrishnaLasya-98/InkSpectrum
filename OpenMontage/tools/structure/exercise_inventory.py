"""Conservative, subject-neutral exercise discovery; not an answer generator.

Keep uncertain fragments visible for review. Do not guess diagram answers or
merge neighbouring lines merely because they are on the same PDF page.
"""
from __future__ import annotations

import re
import math


_INSTRUCTION = re.compile(
    r"(?:\d+[.)]\s*)?(?:"
    r"fill in the blanks(?: with the correct (?:option|word))?|"
    r"answer the following(?: questions)?|match the following|"
    r"choose the correct (?:answer|option)|true or false"
    r")[\s.:]*", re.I,
)
_ITEM = re.compile(r"^(?:\(?[a-z]\)|\d+[.)])\s+", re.I)
_BLANK = re.compile(r"_{2,}|\.{3,}|…{2,}")


def exercise_role(block: dict) -> str:
    kind = block.get("block_type", "")
    text = str(block.get("source_text") or "").strip()
    assessment = block.get("semantic_role") == "assessment" or kind in {
        "assessment", "question", "qa_item", "fill_blank", "worked_example"}
    if not assessment:
        return "not_exercise"
    if kind in {"section_heading", "chapter_title"} or _INSTRUCTION.fullmatch(text):
        return "instruction"
    if kind in {"figure", "table", "equation"}:
        return "visual_exercise_review"
    if kind in {"question", "qa_item", "fill_blank", "worked_example"} or _ITEM.match(text) or _BLANK.search(text) or text.endswith("?"):
        return "question_candidate"
    return "fragment_review"


def build_exercise_inventory(document: dict) -> dict:
    items = []
    for block in document.get("blocks", []):
        if not block.get("required_for_coverage", True):
            continue
        role = exercise_role(block)
        if role == "not_exercise":
            continue
        items.append({"source_block_id": block.get("block_id"),
                      "page_number": block.get("page_number"),
                      "source_text": block.get("source_text", ""),
                      "role": role,
                      "requires_boundary_review": role != "instruction"})
    return {"version": "1.0", "items": items,
            "boundary": "Candidates only. Review PDF reading order and grouped source IDs before authoring answers; no automatic answer or coverage approval."}


def propose_question_groups(document: dict) -> dict:
    """Suggest geometrically supported line wraps; never auto-approve them.

    Input order is the extraction reading order. New item labels, page changes,
    headings, figures and tables terminate a group. Missing geometry leaves
    fragments separate rather than inventing a reading order.
    """
    groups, current = [], None
    def close():
        nonlocal current
        if current:
            groups.append({"source_block_ids": [b["block_id"] for b in current],
                           "question": " ".join(" ".join(str(b.get("source_text", "")).split()) for b in current),
                           "page_numbers": list(dict.fromkeys(b.get("page_number") for b in current)),
                           "status": "needs_review",
                           "reason": "geometry_supported_line_wrap" if len(current) > 1 else "unresolved_or_standalone"})
        current = None

    def adjacent(left, right):
        if left.get("page_number") is None or left.get("page_number") != right.get("page_number"):
            return False
        a, b = left.get("bbox"), right.get("bbox")
        if not all(isinstance(box, list) and len(box) == 4 and
                   all(type(x) in (int, float) and math.isfinite(x) for x in box) for box in (a, b)):
            return False
        height = a[3] - a[1]
        return (height > 0 and b[3] > b[1] and a[2] > a[0] and b[2] > b[0]
                and -.2 * height <= b[1] - a[3] <= 1.5 * height
                and abs(b[0] - a[0]) <= 2 * height)

    for block in document.get("blocks", []):
        role = exercise_role(block)
        if not block.get("required_for_coverage", True) or role in {"not_exercise", "instruction", "visual_exercise_review"}:
            close()
            continue
        text = str(block.get("source_text") or "").strip()
        if current:
            preceding = " ".join(str(b.get("source_text", "")) for b in current).strip()
            open_bracket = preceding.count("(") > preceding.count(")")
            unfinished = not re.search(r'[.!?:]["\u2019\u201d)\]]*$', preceding)
            continuation = bool(text and text[0].islower())
            if (not _ITEM.match(text) and adjacent(current[-1], block)
                    and (open_bracket or (unfinished and continuation))):
                current.append(block)
                continue
            close()
        current = [block]
    close()
    return {"version": "1.0", "groups": groups,
            "boundary": "Proposals only: review against PDF before copying groups into teaching_contract.questions. Cross-page and geometry-free fragments are not automatically joined."}
