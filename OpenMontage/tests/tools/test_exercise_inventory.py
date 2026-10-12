from tools.structure.exercise_inventory import exercise_role, build_exercise_inventory
from tools.analysis.chapter_coverage_audit import audit_chapter


def block(text, kind="assessment"):
    return {"block_id": "b1", "source_text": text, "block_type": kind, "semantic_role": "assessment"}


def test_instructions_are_not_individual_questions():
    for text in ("2. Fill in the blanks with the correct option", "Answer the following questions:", "Match the following"):
        assert exercise_role(block(text)) == "instruction"
    assert exercise_role(block("Fill in the blanks: A triangle has ___ sides.")) == "question_candidate"


def test_subject_neutral_candidates_and_uncertain_fragments():
    for text in ("a) A triangle has ___ sides.", "b) She ___ to school.", "What do plants need?"):
        assert exercise_role(block(text)) == "question_candidate"
    assert exercise_role(block("triangle)")) == "fragment_review"
    assert exercise_role(block("Label the diagram", "figure")) == "visual_exercise_review"


def test_inventory_does_not_merge_or_drop_fragments():
    doc = {"blocks": [block("a) Choose the correct (square/"), {**block("triangle)"), "block_id": "b2"}]}
    inventory = build_exercise_inventory(doc)
    assert [i["source_block_id"] for i in inventory["items"]] == ["b1", "b2"]
    assert all(i["requires_boundary_review"] for i in inventory["items"])


def test_instruction_still_needs_display_and_narration_coverage():
    text = "Fill in the blanks"
    doc = {"blocks": [block(text)]}
    plan = {"sections": [{"section_id": "s1", "source_block_ids": ["b1"]}]}
    narration = {"segments": [{"section_id": "s1", "text": text}]}
    timeline = {"sections": [{"section_id": "s1", "source_block_ids": ["b1"],
                              "start_seconds": 0, "end_seconds": 3, "panel": {"body": text}}]}
    assert audit_chapter(doc, plan, narration, timeline)["status"] == "pass"
    timeline["sections"][0]["panel"] = {}
    report = audit_chapter(doc, plan, narration, timeline)
    assert report["status"] == "blocked"
    assert "answer_evidence_required" not in report["blocks"][0]["issues"]
