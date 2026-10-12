import pytest
from tools.structure.exercise_resolution import arithmetic_value, resolve_exercises, verify_answer


def fixture():
    doc = {"blocks": [
        {"block_id": "q1", "source_text": "What is", "block_type": "question", "page_number": 1},
        {"block_id": "q2", "source_text": "2 + 3?", "block_type": "question", "page_number": 2}]}
    question = {"source_block_ids": ["q1", "q2"], "question": "What is 2 + 3?",
                "answer": "5", "answer_kind": "derived",
                "answer_evidence": {"method": "arithmetic", "expression": "2 + 3"}}
    plan = {"sections": [{"section_id": "s1", "source_block_ids": ["q1", "q2"],
                          "teaching_contract": {"questions": [question]}}]}
    return doc, plan, question


def test_wrapped_cross_page_question_with_arithmetic_proof():
    doc, plan, _ = fixture()
    assert resolve_exercises(doc, plan)["status"] == "pass"


def test_incorrect_answer_and_uncovered_fragments_block():
    doc, plan, question = fixture()
    question["answer"] = "6"
    assert "incorrect_arithmetic_answer" in [i["code"] for i in resolve_exercises(doc, plan)["issues"]]
    plan["sections"][0]["teaching_contract"]["questions"] = []
    assert len(resolve_exercises(doc, plan)["issues"]) == 2


def test_free_text_review_is_not_answer_verification():
    _, _, question = fixture()
    question.pop("answer_evidence")
    question["verification_evidence"] = "teacher review"
    assert verify_answer(question, {}) == "answer_requires_independent_review"


def test_printed_answer_requires_exact_source_evidence():
    question = {"answer": "Roots", "answer_kind": "textbook",
                "answer_evidence": {"source_block_ids": ["a1"]}}
    assert verify_answer(question, {"a1": {"source_text": "Roots"}}) is None
    assert verify_answer(question, {"a1": {"source_text": "Leaves"}}) == "printed_answer_mismatch"


@pytest.mark.parametrize("expression", ["__import__('os')", "2 ** 100", "x + 2", "1/0", "True"])
def test_arithmetic_is_not_generated_code_execution(expression):
    with pytest.raises((ValueError, ZeroDivisionError)):
        arithmetic_value(expression)


def test_decimal_arithmetic_is_exact():
    assert arithmetic_value("0.1 + 0.2") == arithmetic_value("0.3")


def test_reversed_or_overlapping_question_fragments_block():
    doc, plan, question = fixture()
    question["source_block_ids"].reverse()
    assert resolve_exercises(doc, plan)["status"] == "blocked"
    question["source_block_ids"].reverse()
    plan["sections"][0]["teaching_contract"]["questions"].append(dict(question))
    assert "source_fragment_used_by_multiple_questions" in [i["code"] for i in resolve_exercises(doc, plan)["issues"]]
