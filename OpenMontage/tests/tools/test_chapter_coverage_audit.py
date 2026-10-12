from tools.analysis.chapter_coverage_audit import audit_chapter


def fixture():
    return ({"blocks": [{"block_id": "b1", "source_text": "A circle is round.", "page_number": 1}]},
            {"sections": [{"section_id": "s1", "source_block_ids": ["b1"]}]},
            {"segments": [{"section_id": "s1", "text": "A circle is round."}]},
            {"sections": [{"section_id": "s1", "source_block_ids": ["b1"],
               "start_seconds": 0, "end_seconds": 5, "panel": {"body": "A circle is round."}}]})


def test_exact_authored_evidence_passes():
    assert audit_chapter(*fixture())["status"] == "pass"


def test_exercise_cards_replace_legacy_panel_body_evidence():
    doc, plan, narration, timeline = fixture()
    screen = timeline["sections"][0]
    screen["exercise_cards"] = [{"question": "Different text", "answer_text": "Unknown"}]
    assert "display_requires_review" in audit_chapter(doc, plan, narration, timeline)["blocks"][0]["issues"]
    screen["exercise_cards"][0]["question"] = "A circle is round."
    assert audit_chapter(doc, plan, narration, timeline)["status"] == "pass"


def test_provenance_alone_does_not_pass():
    doc, plan, narration, timeline = fixture()
    timeline["sections"][0]["panel"] = {"body": "Shapes"}
    result = audit_chapter(doc, plan, narration, timeline)
    assert result["status"] == "blocked"
    assert "display_requires_review" in result["blocks"][0]["issues"]


def test_question_needs_classified_verified_answer():
    doc, plan, narration, timeline = fixture()
    doc["blocks"][0]["block_type"] = "question"
    assert audit_chapter(doc, plan, narration, timeline)["status"] == "blocked"
    plan["sections"][0]["teaching_contract"] = {"questions": [{"source_block_id": "b1",
        "question": "A circle is round.",
        "answer": "A circle is round.", "answer_kind": "derived", "verification_evidence": "teacher review"}]}
    assert audit_chapter(doc, plan, narration, timeline)["status"] == "pass"


def test_empty_source_and_invalid_time_block():
    assert audit_chapter({}, {}, {}, {})["status"] == "blocked"
    doc, plan, narration, timeline = fixture()
    timeline["sections"][0]["end_seconds"] = -1
    assert audit_chapter(doc, plan, narration, timeline)["status"] == "blocked"


def test_wrapped_question_answer_is_checked_for_each_source_fragment():
    doc, plan, narration, timeline = fixture()
    doc["blocks"] = [
        {"block_id": "b1", "source_text": "A circle", "block_type": "question"},
        {"block_id": "b2", "source_text": "is round.", "block_type": "question"},
    ]
    plan["sections"][0]["source_block_ids"] = ["b1", "b2"]
    timeline["sections"][0]["source_block_ids"] = ["b1", "b2"]
    question = {"source_block_ids": ["b1", "b2"], "question": "A circle is round.",
                "answer": "round", "answer_kind": "derived", "verification_evidence": "review"}
    plan["sections"][0]["teaching_contract"] = {"questions": [question]}
    assert audit_chapter(doc, plan, narration, timeline)["status"] == "pass"
    question["question"] = "An unrelated question?"
    report = audit_chapter(doc, plan, narration, timeline)
    assert all("question_source_mismatch" in row["issues"] for row in report["blocks"])
