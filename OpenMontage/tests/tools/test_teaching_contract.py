from tools.structure.teaching_contract import validate_teaching_contract, spoken_heading


def fixture_plan():
    source = [{"block_id": "q1", "source_text": "What is 2 + 3?", "required_for_coverage": True}]
    plan = {"sections": [{
        "section_id": "s1", "source_block_type": "worked_example",
        "narration_script": "What is 2 + 3? Count two, then three more. The answer is five.",
        "teaching_contract": {
            "source_excerpts": [{"block_id": "q1", "verbatim_text": "What is 2 + 3?", "display_text": "What is 2 + 3?"}],
            "explanations": ["Count two, then three more."],
            "animation_beats": [{"cue_text": "Count two", "visual": "two counters", "action": "reveal two counters"}],
            "questions": [{"source_block_id": "q1", "question": "What is 2 + 3?",
                           "answer": "The answer is five.", "answer_kind": "derived",
                           "verification_evidence": "integer arithmetic: 2+3=5",
                           "solution_steps": ["Count two, then three more."], "thinking_pause_seconds": 4}],
        },
    }]}
    return plan, source


def test_complete_teaching_evidence():
    plan, source = fixture_plan()
    assert validate_teaching_contract(plan, source)["status"] == "pass"


def test_changed_value_cannot_pass_provenance_only():
    plan, source = fixture_plan()
    plan["sections"][0]["teaching_contract"]["source_excerpts"][0]["display_text"] = "What is 2 + 4?"
    review = validate_teaching_contract(plan, source)
    assert review["verified_text_blocks"] == 0
    assert "display_text_mismatch" in {x["code"] for x in review["issues"]}


def test_missing_answer_and_animation_cue_block_readiness():
    plan, source = fixture_plan()
    contract = plan["sections"][0]["teaching_contract"]
    contract["questions"][0].pop("answer")
    contract["animation_beats"][0]["cue_text"] = "never spoken"
    codes = {x["code"] for x in validate_teaching_contract(plan, source)["issues"]}
    assert {"missing_question_field", "animation_cue_not_spoken"} <= codes


def test_absent_contract_does_not_claim_coverage():
    plan, source = fixture_plan()
    plan["sections"][0].pop("teaching_contract")
    review = validate_teaching_contract(plan, source)
    assert review["status"] == "revise"
    assert review["verified_text_blocks"] == 0


def test_heading_deduplicates_label():
    assert spoken_heading({"section_label": "Highlights", "title": "Highlights of the Lesson"}) == "Highlights of the Lesson."
    assert spoken_heading({"section_label": "Maths", "title": "Basic Shapes"}) == "Maths. Basic Shapes."


def test_empty_inputs_cannot_pass():
    assert validate_teaching_contract({"sections": []}, [])["status"] == "revise"


def test_only_maths_questions_require_detailed_explanations():
    plan, source = fixture_plan()
    contract = plan["sections"][0]["teaching_contract"]
    contract.pop("explanations")
    contract["questions"][0].pop("solution_steps")
    assert validate_teaching_contract(plan, source, subject="english")["status"] == "pass"
    codes = {item["code"] for item in validate_teaching_contract(plan, source, subject="maths")["issues"]}
    assert {"missing_explanation", "missing_solution_steps"} <= codes


def test_solution_steps_must_be_narrated():
    plan, source = fixture_plan()
    plan["sections"][0]["teaching_contract"]["questions"][0]["solution_steps"] = ["An omitted step."]
    assert "solution_step_not_narrated" in {i["code"] for i in validate_teaching_contract(plan, source)["issues"]}


def test_wrapped_question_preserves_all_source_fragments():
    plan, source = fixture_plan()
    source[0]["source_text"] = "What is"
    source.append({"block_id": "q2", "source_text": "2 + 3?"})
    contract = plan["sections"][0]["teaching_contract"]
    contract["source_excerpts"] = [
        {"block_id": b["block_id"], "verbatim_text": b["source_text"], "display_text": b["source_text"]}
        for b in source]
    question = contract["questions"][0]
    question.pop("source_block_id")
    question["source_block_ids"] = ["q1", "q2"]
    assert validate_teaching_contract(plan, source, subject="maths")["status"] == "pass"
    question["source_block_ids"] = ["q1", "missing"]
    assert "question_source_mismatch" in {i["code"] for i in validate_teaching_contract(plan, source)["issues"]}


def test_question_cannot_use_only_a_substring_or_conflicting_ids():
    from tools.structure.teaching_contract import question_matches_source
    source = {"q1": {"source_text": "What is 2 + 3?"}}
    assert not question_matches_source({"source_block_id": "q1", "question": "2 + 3?"}, source)
    for ids in (["q1", "q1"], ["q1", "missing"], "q1", []):
        assert not question_matches_source({"source_block_ids": ids, "question": "What is 2 + 3?"}, source)
