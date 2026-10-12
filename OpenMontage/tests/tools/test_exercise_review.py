from copy import deepcopy
import pytest
from tools.structure.exercise_review import review_fingerprint, validate_review
from tools.structure.exercise_resolution import resolve_exercises


def fixture(visual=False):
    source = {"q1": {"block_id": "q1", "block_type": "question", "page_number": 1,
                     "source_text": "Name the part that absorbs water."}}
    question = {"source_block_id": "q1", "question": source["q1"]["source_text"],
                "answer": "Roots.", "answer_kind": "derived", "author_id": "writer",
                "answer_evidence": {"method": "reviewed", "review_id": "r1"}}
    if visual:
        source["f1"] = {"block_id": "f1", "block_type": "figure", "page_number": 1,
                        "bbox": [0, 0, 100, 100], "source_text": "Plant diagram",
                        "semantic_role": "assessment"}
        question["visual_source_block_ids"] = ["f1"]
    record = {"review_id": "r1", "content_sha256": review_fingerprint(question, source),
              "decision": "approved", "reviewer": {"type": "human", "id": "teacher"},
              "reviewed_at": "2026-09-29T12:00:00+05:30", "rationale": "Checked the textbook explanation and labels.",
              "checks": {"textbook_fidelity": True, "answer_correctness": True,
                         "grade_appropriate": True, "diagram_accuracy": True},
              "visual_observations": [{"source_block_id": "f1", "observation": "The pointer marks roots below the stem."}]}
    return source, question, record


def test_valid_structured_review():
    source, question, record = fixture()
    assert validate_review(question, source, [record]) is None


def test_changed_visual_mapping_invalidates_review():
    source, question, record = fixture(True)
    question["exercise_visual"] = {"kind": "diagram_label", "labels": [{"text": "Roots", "x": .5}]}
    record["content_sha256"] = review_fingerprint(question, source)
    question["exercise_visual"]["labels"][0]["x"] = .7
    assert validate_review(question, source, [record]) == "stale_answer_review"


@pytest.mark.parametrize("change", ["answer", "question", "solution_steps", "source"])
def test_content_changes_invalidate_review(change):
    source, question, record = fixture()
    if change == "source": source["q1"]["source_text"] += " Revised."
    elif change == "solution_steps": question[change] = ["New reasoning."]
    else: question[change] += " Revised."
    assert validate_review(question, source, [record]) == "stale_answer_review"


@pytest.mark.parametrize("decision", ["pending", "rejected", None])
def test_nonapproved_review_stays_blocked(decision):
    source, question, record = fixture()
    record["decision"] = decision
    assert validate_review(question, source, [record]) == "answer_review_not_approved"


def test_duplicate_and_self_reviews_rejected():
    source, question, record = fixture()
    assert validate_review(question, source, [record, deepcopy(record)]) == "missing_or_duplicate_answer_review"
    record["reviewer"]["id"] = "writer"
    assert validate_review(question, source, [record]) == "answer_review_not_independent"


def test_diagram_needs_visual_observation_and_check():
    source, question, record = fixture(True)
    assert validate_review(question, source, [record]) is None
    record["visual_observations"] = []
    assert validate_review(question, source, [record]) == "missing_visual_observations"
    record["checks"]["diagram_accuracy"] = False
    assert validate_review(question, source, [record]) == "incomplete_answer_review_checks"


def test_visual_is_resolved_only_after_review():
    source, question, record = fixture(True)
    plan = {"sections": [{"section_id": "s1", "source_block_ids": ["q1", "f1"],
                          "teaching_contract": {"questions": [question]}}]}
    doc = {"blocks": list(source.values())}
    assert resolve_exercises(doc, plan)["status"] == "blocked"
    assert resolve_exercises(doc, plan, [record])["status"] == "pass"
    source["f1"]["bbox"] = [0, 0, 200, 100]
    assert resolve_exercises(doc, plan, [record])["status"] == "blocked"


def test_sample_response_can_be_reviewed_without_claiming_printed_answer():
    source, question, record = fixture()
    question["answer_kind"] = "sample_response"
    record["content_sha256"] = review_fingerprint(question, source)
    assert validate_review(question, source, [record]) is None
