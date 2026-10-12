"""Review grouped PDF questions and verify narrowly supported answer evidence.

This does not infer diagram answers or execute generated Python. Unsupported
reasoning remains blocked for explicit review instead of being called correct.
"""
from __future__ import annotations

import ast
from fractions import Fraction

from tools.structure.exercise_inventory import exercise_role
from tools.structure.teaching_contract import question_source_ids, question_matches_source, normalized_text
from tools.structure.exercise_review import validate_review, review_fingerprint, visual_source_ids


def arithmetic_value(expression):
    if not isinstance(expression, str) or len(expression) > 200:
        raise ValueError("Invalid arithmetic expression")
    tree = ast.parse(expression, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 60:
        raise ValueError("Arithmetic expression is too complex")
    def value(node):
        if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
            return Fraction(ast.get_source_segment(expression, node))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            number = value(node.operand)
            return number if isinstance(node.op, ast.UAdd) else -number
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left, right = value(node.left), value(node.right)
            if isinstance(node.op, ast.Add): return left + right
            if isinstance(node.op, ast.Sub): return left - right
            if isinstance(node.op, ast.Mult): return left * right
            return left / right
        raise ValueError("Only numeric +, -, *, / and parentheses are supported")
    return value(tree.body)


def verify_answer(question, source, reviews=()):
    answer = normalized_text(question.get("answer"))
    evidence = question.get("answer_evidence") or {}
    if not answer or not isinstance(evidence, dict):
        return "missing_answer_evidence"
    if evidence.get("method") == "reviewed" and question.get("answer_kind") in {"derived", "sample_response"}:
        return validate_review(question, source, reviews)
    if question.get("answer_kind") == "textbook":
        ids = evidence.get("source_block_ids")
        if not isinstance(ids, list) or not ids or any(not isinstance(bid, str) or bid not in source for bid in ids):
            return "missing_printed_answer_source"
        quote = " ".join(normalized_text(source[bid].get("source_text")) for bid in ids)
        return None if answer == quote else "printed_answer_mismatch"
    if question.get("answer_kind") == "derived" and evidence.get("method") == "arithmetic":
        # Numeric-only answers: units and word-problem interpretation need an
        # independent review. Never extract numbers out of arbitrary prose.
        try:
            if arithmetic_value(evidence.get("expression")) != arithmetic_value(answer):
                return "incorrect_arithmetic_answer"
        except (ValueError, SyntaxError, ZeroDivisionError, TypeError, OverflowError):
            return "unsupported_arithmetic_evidence"
        if normalized_text(evidence.get("expression")) not in normalized_text(question.get("question")):
            return "arithmetic_expression_not_in_question"
        return None
    return "answer_requires_independent_review"


def resolve_exercises(document, plan, reviews=()):
    blocks = document.get("blocks", [])
    source = {b.get("block_id"): b for b in blocks}
    required = {b.get("block_id") for b in blocks if b.get("required_for_coverage", True)
                and exercise_role(b) not in {"not_exercise", "instruction"}}
    owners, records, issues = {}, [], []
    if not blocks:
        issues.append({"code": "missing_source_authority"})
    for section in plan.get("sections", []):
        for index, question in enumerate((section.get("teaching_contract") or {}).get("questions", [])):
            key = f"{section.get('section_id')}:{index+1}"
            ids = question_source_ids(question)
            errors = []
            if not question_matches_source(question, source):
                errors.append("question_source_mismatch")
            if any(bid not in section.get("source_block_ids", []) for bid in ids):
                errors.append("question_outside_section_sources")
            positions = [list(source).index(bid) for bid in ids if bid in source]
            if positions != sorted(positions):
                errors.append("question_fragments_out_of_order")
            for bid in ids:
                if bid in owners:
                    errors.append("source_fragment_used_by_multiple_questions")
                    for prior in records:
                        if prior["question_id"] == owners[bid]:
                            prior["status"] = "needs_review"
                            if "source_fragment_used_by_multiple_questions" not in prior["issues"]:
                                prior["issues"].append("source_fragment_used_by_multiple_questions")
                owners[bid] = key
            answer_issue = verify_answer(question, source, reviews)
            if answer_issue:
                errors.append(answer_issue)
            try:
                visuals = visual_source_ids(question)
                if visuals and (question.get("answer_evidence") or {}).get("method") != "reviewed":
                    errors.append("diagram_answer_requires_review")
                for bid in visuals:
                    if bid not in section.get("source_block_ids", []) or bid not in source:
                        errors.append("visual_outside_section_sources")
                    elif not errors:
                        owners[bid] = key
                fingerprint = review_fingerprint(question, source)
            except ValueError:
                errors.append("invalid_visual_source_references")
                fingerprint = None
            record = {"question_id": key, "source_block_ids": ids,
                      "question": question.get("question"), "answer": question.get("answer"),
                      "review_content_sha256": fingerprint,
                      "verification_basis": (question.get("answer_evidence") or {}).get("method", question.get("answer_kind")),
                      "issues": errors, "status": "verified" if not errors else "needs_review"}
            records.append(record)
            issues.extend({"question_id": key, "code": code} for code in errors)
    for bid in sorted(required - owners.keys()):
        issues.append({"source_block_id": bid, "code": "unresolved_exercise_fragment"})
    return {"version": "1.0", "status": "blocked" if issues else "pass",
            "questions": records, "issues": issues,
            "boundary": "Source grouping and narrow answer checks only; not PDF-layout, pedagogical, units, diagram, or universal semantic verification."}
