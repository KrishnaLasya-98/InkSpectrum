"""Pre-generation evidence checks for source-faithful educational plans.

This validates authored evidence; it cannot certify OCR accuracy, answer truth,
voice pronunciation, or encoded pixels. Those need independent downstream QA.
Historical plans remain usable in report mode. New productions can opt into a
blocking gate with content_policy.require_teaching_contract=true.
"""
from __future__ import annotations

from typing import Any


def normalized_text(value: Any) -> str:
    # Only whitespace is normalized: case, punctuation, units, and values matter.
    return " ".join(str(value or "").split())


def question_source_ids(question: dict) -> list[str]:
    """Ordered PDF fragments, with backward-compatible single-block input.

    Invalid or conflicting references fail closed; never silently discard an ID.
    """
    single = question.get("source_block_id")
    multiple = question.get("source_block_ids")
    if multiple is None:
        return [single] if isinstance(single, str) and single.strip() else []
    if (not isinstance(multiple, list) or not multiple
            or any(not isinstance(x, str) or not x.strip() for x in multiple)
            or len(set(multiple)) != len(multiple)
            or (single is not None and single not in multiple)):
        return []
    return multiple


def question_matches_source(question: dict, source: dict) -> bool:
    ids = question_source_ids(question)
    if not ids or any(bid not in source for bid in ids):
        return False
    fragments = [normalized_text(source[bid].get("source_text") or source[bid].get("body_text"))
                 for bid in ids]
    actual = normalized_text(question.get("question"))
    return bool(actual and all(fragments) and actual == " ".join(fragments))


def spoken_heading(section: dict) -> str:
    title = normalized_text(section.get("title"))
    label = normalized_text(section.get("section_label"))
    parts = [title] if not label or label.casefold() in title.casefold() else [label, title]
    return " ".join(part if part[-1:] in ".!?" else part + "." for part in parts if part)


def validate_teaching_contract(plan: dict, source_blocks: list[dict], *, subject: str = "") -> dict:
    source = {str(b.get("block_id")): b for b in source_blocks if b.get("block_id")}
    required = {key for key, block in source.items()
                if block.get("required_for_coverage", True) and block.get("block_type") != "decorative"}
    covered: set[str] = set()
    issues: list[dict] = []
    def issue(section, code, detail):
        issues.append({"section_id": section, "code": code, "detail": detail})

    if not required:
        issue("", "missing_source_authority", "No required source blocks were supplied")
    if not plan.get("sections"):
        issue("", "empty_plan", "No teaching sections were supplied")

    seen = set()
    for section in plan.get("sections", []):
        sid = str(section.get("section_id") or "")
        if not sid or sid in seen:
            issue(sid, "invalid_section_id", "Section IDs must be nonempty and unique")
        seen.add(sid)
        contract = section.get("teaching_contract")
        if not isinstance(contract, dict):
            issue(sid, "missing_teaching_contract", "Needs source excerpts, explanations, animation beats, and questions")
            continue
        narration = normalized_text(section.get("narration_script"))
        excerpts = contract.get("source_excerpts", [])
        if not isinstance(excerpts, list) or not excerpts:
            issue(sid, "missing_source_excerpts", "No verbatim source evidence")
            excerpts = []
        for excerpt in excerpts:
            if not isinstance(excerpt, dict):
                issue(sid, "invalid_excerpt", "Expected an object")
                continue
            bid = str(excerpt.get("block_id") or "")
            if bid not in source:
                issue(sid, "unknown_source_block", bid)
                continue
            expected = normalized_text(source[bid].get("source_text") or source[bid].get("body_text"))
            actual = normalized_text(excerpt.get("verbatim_text"))
            if not expected or actual != expected:
                issue(sid, "source_text_mismatch", bid)
                continue
            # Require an authored display value, not just a provenance copy.
            if normalized_text(excerpt.get("display_text")) != expected:
                issue(sid, "display_text_mismatch", bid)
                continue
            if excerpt.get("narrate_verbatim", True) and expected not in narration:
                issue(sid, "source_missing_from_narration", bid)
                continue
            covered.add(bid)

        explanations = contract.get("explanations", [])
        detailed_maths = subject.casefold() in {"math", "maths", "mathematics"} and section.get("source_block_type") in {"worked_example", "qa_item", "assessment", "fill_blank"}
        if detailed_maths and (not isinstance(explanations, list) or not any(normalized_text(x) for x in explanations)):
            issue(sid, "missing_explanation", "Add grade-appropriate teaching explanation separately from textbook text")
        elif isinstance(explanations, list):
            for explanation in explanations:
                if normalized_text(explanation) not in narration:
                    issue(sid, "explanation_not_narrated", str(explanation))

        beats = contract.get("animation_beats")
        if not isinstance(beats, list) or not beats:
            issue(sid, "missing_animation_beats", "Describe what appears and changes at each spoken cue")
        else:
            for beat in beats:
                if not isinstance(beat, dict) or not all(normalized_text(beat.get(k)) for k in ("cue_text", "visual", "action")):
                    issue(sid, "invalid_animation_beat", "Requires cue_text, visual, and action")
                elif normalized_text(beat["cue_text"]) not in narration:
                    issue(sid, "animation_cue_not_spoken", beat["cue_text"])

        questions = contract.get("questions", [])
        if not isinstance(questions, list):
            issue(sid, "invalid_questions", "Questions must be a list")
            questions = []
        question_section = section.get("source_block_type") in {"qa_item", "assessment", "fill_blank", "worked_example"}
        if question_section and not questions:
            issue(sid, "missing_question_answer", "Provide the source question, solution, and answer")
        for question in questions:
            if not isinstance(question, dict):
                issue(sid, "invalid_question", "Expected a question object")
                continue
            for field in ("question", "answer", "answer_kind", "verification_evidence"):
                if not normalized_text(question.get(field)):
                    issue(sid, "missing_question_field", field)
            if question.get("answer_kind") not in {"textbook", "derived", "sample_response"}:
                issue(sid, "invalid_answer_kind", "Use textbook, derived, or sample_response")
            if detailed_maths and not question.get("solution_steps"):
                issue(sid, "missing_solution_steps", "Explain how the answer follows")
            elif question.get("solution_steps") and not isinstance(question["solution_steps"], list):
                issue(sid, "invalid_solution_steps", "Solution steps must be an ordered list")
            else:
                for step in question.get("solution_steps", []) or []:
                    if not normalized_text(step) or normalized_text(step) not in narration:
                        issue(sid, "solution_step_not_narrated", str(step))
            for field in ("question", "answer"):
                value = normalized_text(question.get(field))
                if value and value not in narration:
                    issue(sid, "question_answer_not_narrated", field)
            if not question_matches_source(question, source):
                issue(sid, "question_source_mismatch", str(question_source_ids(question)))
            try:
                pause = float(question.get("thinking_pause_seconds", -1))
                if not 0 <= pause <= 60:
                    raise ValueError()
            except (TypeError, ValueError):
                issue(sid, "invalid_thinking_pause", "Specify 0 to 60 seconds")

    for bid in sorted(required - covered):
        issue("", "uncovered_source_text", bid)
    return {
        "version": "1.0", "status": "pass" if not issues else "revise",
        "required_blocks": len(required), "verified_text_blocks": len(required & covered),
        "issues": issues,
        "validation_boundary": "Authored text and evidence only; PDF visual verification, answer verification, cue resolution, and encoded-output QA remain mandatory.",
    }
