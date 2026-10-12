from __future__ import annotations

import json

from tools.video.audit_chapter_modelslab_jobs import collect_decisions


def test_semantic_decisions_are_loaded_for_partial_recovered_batch(tmp_path) -> None:
    payload = {
        "decisions": [
            {"shot_id": "clean", "status": "accept"},
            {"shot_id": "bad", "status": "reject"},
        ]
    }
    (tmp_path / "motion-batch-14-semantic-decisions.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    assert collect_decisions(tmp_path) == {
        (14, "clean"): "accepted",
        (14, "bad"): "rejected",
    }


def test_semantic_decisions_override_earlier_frame_review(tmp_path) -> None:
    review = {"clips": [{"shot_id": "clip", "visual_status": "rejected"}]}
    decision = {"decisions": [{"shot_id": "clip", "status": "accept"}]}
    (tmp_path / "motion-batch-01-review.json").write_text(json.dumps(review), encoding="utf-8")
    (tmp_path / "motion-batch-01-semantic-decisions.json").write_text(
        json.dumps(decision), encoding="utf-8"
    )
    assert collect_decisions(tmp_path)[(1, "clip")] == "accepted"
