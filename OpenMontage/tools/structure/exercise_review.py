"""Content-bound review records, not an assertion of reviewer authenticity."""
import hashlib
import json
from datetime import datetime

from tools.structure.teaching_contract import question_source_ids


def visual_source_ids(question):
    ids = question.get("visual_source_block_ids", [])
    if not isinstance(ids, list) or any(not isinstance(x, str) or not x for x in ids) or len(ids) != len(set(ids)):
        raise ValueError("Invalid visual source references")
    return ids


def review_fingerprint(question, source):
    ids = question_source_ids(question) + visual_source_ids(question)
    payload = {"question": question.get("question"), "answer": question.get("answer"),
               "answer_kind": question.get("answer_kind"),
               "solution_steps": question.get("solution_steps", []),
               "exercise_visual": question.get("exercise_visual"),
               "source_block_ids": question_source_ids(question),
               "visual_source_block_ids": visual_source_ids(question),
               "source_blocks": [source.get(bid) for bid in ids]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def validate_review(question, source, records):
    evidence = question.get("answer_evidence") or {}
    review_id = evidence.get("review_id")
    matches = [r for r in records if isinstance(r, dict) and r.get("review_id") == review_id] if review_id else []
    if len(matches) != 1:
        return "missing_or_duplicate_answer_review"
    record = matches[0]
    if record.get("decision") != "approved":
        return "answer_review_not_approved"
    reviewer = record.get("reviewer") or {}
    if (not isinstance(reviewer, dict) or reviewer.get("type") not in {"human", "agent"}
            or not str(reviewer.get("id") or "").strip()):
        return "missing_reviewer_identity"
    if question.get("author_id") and reviewer["id"] == question["author_id"]:
        return "answer_review_not_independent"
    try:
        timestamp = datetime.fromisoformat(str(record.get("reviewed_at", "")).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError()
    except ValueError:
        return "invalid_review_timestamp"
    if not str(record.get("rationale") or "").strip():
        return "missing_review_rationale"
    try:
        visuals = visual_source_ids(question)
        if record.get("content_sha256") != review_fingerprint(question, source):
            return "stale_answer_review"
    except ValueError:
        return "invalid_visual_source_references"
    checks = record.get("checks") or {}
    required = ["textbook_fidelity", "answer_correctness", "grade_appropriate"]
    if visuals:
        required.append("diagram_accuracy")
    if not isinstance(checks, dict) or any(checks.get(k) is not True for k in required):
        return "incomplete_answer_review_checks"
    observations = record.get("visual_observations", [])
    if not isinstance(observations, list):
        return "missing_visual_observations"
    for bid in visuals:
        block = source.get(bid, {})
        if block.get("block_type") not in {"figure", "table", "equation"} or not block.get("page_number"):
            return "invalid_visual_source_references"
        if not any(isinstance(o, dict) and o.get("source_block_id") == bid
                   and str(o.get("observation") or "").strip() for o in observations):
            return "missing_visual_observations"
    return None
