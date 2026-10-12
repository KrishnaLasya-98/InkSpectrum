import json
from lib.checkpoint import read_checkpoint

from tools.structure.educational_production_artifacts import build_production_artifacts
from tools.structure.educational_run_tracker import (
    EducationalRunTracker,
    approve_educational_stage,
    checkpoint_summary,
    migrate_legacy_educational_project,
)
from tools.structure.educational_agent_cli import portability_doctor


def _artifacts():
    config = {
        "project_id": "portable-chapter",
        "subject": "science",
        "grade": 1,
        "chapter": 1,
        "title": "Plants",
        "source_input": "chapter.pdf",
        "approval_policy": "guided",
        "content_policy": {"allow_invented_labels": False},
        "render_policy": {
            "runtime": "hyperframes",
            "ui_template_id": "hyperframes-educational-v1",
            "ui_template_version": "1.0.1",
            "ui_template_package_sha256": "test-hash",
            "composition_mode": "atelier",
            "visual_media": "animated-video-only",
        },
        "providers": {
            "audio": {"provider": "modelslab", "voice_id": "nova"},
            "video": {
                "provider": "modelslab",
                "model_id": "wan2.2",
                "image_model_id": "wan-2.2-i2v",
                "reference_model_id": "h3-minimax-r2v",
                "fallback_model_id": "h3-minimax-t2v",
                "fresh_assets_only": True,
                "allow_clip_reuse": False,
            },
        },
    }
    plan = {
        "title": "Plants",
        "sections": [
            {
                "section_id": "s1",
                "title": "Plants need water",
                "render_mode": "video_gen",
                "source_block_ids": ["p0001-b0001"],
                "description": "A plant is watered",
                "duration_seconds": 6,
            }
        ],
    }
    return build_production_artifacts(config, plan)


def test_guided_checkpoint_gate_can_be_approved_and_resumed(tmp_path):
    project = tmp_path / "portable-chapter"
    tracker = EducationalRunTracker(project, title="Plants", approval_policy="guided")
    tracker.begin("input_ingestion")
    assert tracker.finish("input_ingestion", {"source_path": "chapter.pdf"}) == "completed"

    artifacts = _artifacts()
    tracker.begin("proposal")
    status = tracker.finish(
        "proposal",
        {
            "proposal_packet": artifacts["proposal_packet"],
            "decision_log": artifacts["decision_log"],
        },
    )
    assert status == "awaiting_human"

    approve_educational_stage(project, "proposal")
    resumed = EducationalRunTracker(project, title="Plants", approval_policy="guided")
    resumed.begin("proposal")
    assert resumed.finish(
        "proposal",
        {
            "proposal_packet": artifacts["proposal_packet"],
            "decision_log": artifacts["decision_log"],
        },
    ) == "completed"
    assert checkpoint_summary(project)["stages"][1]["human_approved"] is True


def test_legacy_migration_adds_backlot_marker_without_fake_checkpoints(tmp_path):
    project = tmp_path / "old-chapter"
    (project / "renders").mkdir(parents=True)
    marker = migrate_legacy_educational_project(project, title="Old Chapter")

    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert payload["pipeline_type"] == "educational-video"
    assert payload["title"] == "Old Chapter"
    assert checkpoint_summary(project)["stages"][0]["status"] == "pending"


def _approve_predecessors(tracker):
    tracker.finish("input_ingestion", {"source_path": "chapter.pdf"})
    artifacts = _artifacts()
    status = tracker.finish("proposal", {
        "proposal_packet": artifacts["proposal_packet"],
        "decision_log": artifacts["decision_log"],
    })
    if status == "awaiting_human":
        approve_educational_stage(tracker.project_dir, "proposal")


def test_changed_content_requires_fresh_approval(tmp_path):
    project = tmp_path / "changed"
    tracker = EducationalRunTracker(project, title="Test")
    _approve_predecessors(tracker)
    original = {"content": {"question": "One plus one?", "answer": "Two"}}
    assert tracker.finish("content_structuring", original) == "awaiting_human"
    approve_educational_stage(project, "content_structuring")
    resumed = EducationalRunTracker(project, title="Test")
    resumed.begin("content_structuring")
    changed = {"content": {"question": "One plus two?", "answer": "Three"}}
    assert resumed.finish("content_structuring", changed) == "awaiting_human"
    assert not read_checkpoint(project.parent, project.name, "content_structuring")["human_approved"]
    # Returning to an old payload does not resurrect a revoked approval.
    assert resumed.finish("content_structuring", original) == "awaiting_human"


def test_approval_hash_is_order_independent_and_failure_revokes_cache(tmp_path):
    tracker = EducationalRunTracker(tmp_path / "ordered", title="Test")
    _approve_predecessors(tracker)
    tracker.finish("content_structuring", {"one": 1, "two": 2})
    approve_educational_stage(tracker.project_dir, "content_structuring")
    tracker.begin("content_structuring")
    assert tracker.was_approved("content_structuring", {"two": 2, "one": 1})
    tracker.fail("content_structuring", "Content failed QA")
    assert not tracker.was_approved("content_structuring", {"one": 1, "two": 2})


def test_checkpoint_tampering_is_visible_to_resume(tmp_path):
    tracker = EducationalRunTracker(tmp_path / "tampered", title="Test")
    _approve_predecessors(tracker)
    tracker.finish("content_structuring", {"content": "Original"})
    path = approve_educational_stage(tracker.project_dir, "content_structuring")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["artifacts"]["content"] = "Changed after approval"
    path.write_text(json.dumps(payload), encoding="utf-8")
    status = next(s for s in checkpoint_summary(tracker.project_dir)["stages"]
                  if s["name"] == "content_structuring")
    assert status["status"] == "invalid"
    assert not status["human_approved"]


def test_explicit_preauthorization_binds_each_payload(tmp_path):
    tracker = EducationalRunTracker(tmp_path / "preauthorized", title="Test",
                                    approval_policy="full-run-preauthorized")
    _approve_predecessors(tracker)
    assert tracker.finish("content_structuring", {"content": "One"}) == "completed"
    assert tracker.finish("content_structuring", {"content": "Two"}) == "completed"
    assert tracker.was_approved("content_structuring", {"content": "Two"})


def test_cross_agent_package_and_manifest_skills_are_present():
    result = portability_doctor()
    assert result["status"] == "pass"
    assert result["stage_count"] == 12
    assert result["failures"] == []


def test_upstream_restart_invalidates_outputs_without_deleting_them(tmp_path):
    tracker = EducationalRunTracker(tmp_path / "dependencies", title="Test")
    _approve_predecessors(tracker)
    tracker.finish("content_structuring", {"content": "Reviewed lesson"})
    approve_educational_stage(tracker.project_dir, "content_structuring")
    tracker.begin("input_ingestion")
    state = checkpoint_summary(tracker.project_dir)
    assert state["stages"][1]["status"] == "blocked"
    tracker.finish("input_ingestion", {"source_path": "changed.pdf"})
    for stage in ("proposal", "content_structuring"):
        checkpoint = read_checkpoint(tracker.pipeline_dir, tracker.project_id, stage)
        assert checkpoint["status"] == "failed"
        assert not checkpoint["human_approved"]
        assert checkpoint["artifacts"]
        assert checkpoint["metadata"]["invalidated_by"] == "input_ingestion"
    assert list((tracker.project_dir / "history").rglob("*.json"))


def test_process_restart_preserves_approval_and_partial_progress(tmp_path):
    from tools.structure.educational_startup import resume_project
    project = tmp_path / "restart"
    tracker = EducationalRunTracker(project, title="Test")
    _approve_predecessors(tracker)
    payload = {"content": "Reviewed lesson"}
    tracker.finish("content_structuring", payload)
    approve_educational_stage(project, "content_structuring")
    tracker.begin("content_structuring")
    tracker.progress("content_structuring", partial_progress={"completed_scene_ids": ["s1"],
                                                             "pending_job_ids": ["fake-job"]})
    # New instance models a process restart; no in-memory approval cache survives.
    fresh = EducationalRunTracker(project, title="Test")
    state = resume_project(project)
    assert state["next_stage"]["name"] == "content_structuring"
    assert state["recovery"]["partial_progress"]["pending_job_ids"] == ["fake-job"]
    fresh.begin("content_structuring")
    assert fresh.finish("content_structuring", payload) == "completed"


def test_failure_preserves_partial_work_but_not_approval(tmp_path):
    from tools.structure.educational_startup import resume_project
    tracker = EducationalRunTracker(tmp_path / "partial", title="Test")
    _approve_predecessors(tracker)
    tracker.begin("content_structuring")
    tracker.progress("content_structuring", partial_progress={"completed_scene_ids": ["s1"]})
    tracker.fail("content_structuring", "Interrupted")
    state = resume_project(tracker.project_dir)
    assert state["recovery"]["partial_progress"]["completed_scene_ids"] == ["s1"]
    assert state["next_stage"]["status"] == "failed"


def test_direct_changed_finish_invalidates_downstream(tmp_path):
    tracker = EducationalRunTracker(tmp_path / "direct", title="Test")
    _approve_predecessors(tracker)
    tracker.finish("input_ingestion", {"source_path": "different.pdf"})
    assert read_checkpoint(tracker.pipeline_dir, tracker.project_id, "proposal")["status"] == "failed"


def test_unchanged_upstream_rerun_unblocks_approved_dependents(tmp_path):
    tracker = EducationalRunTracker(tmp_path / "unchanged", title="Test")
    _approve_predecessors(tracker)
    tracker.begin("input_ingestion")
    assert checkpoint_summary(tracker.project_dir)["stages"][1]["status"] == "blocked"
    fresh = EducationalRunTracker(tracker.project_dir, title="Test")
    fresh.finish("input_ingestion", {"source_path": "chapter.pdf"})
    proposal = checkpoint_summary(tracker.project_dir)["stages"][1]
    assert proposal["status"] == "completed"
    assert proposal["human_approved"]


def test_tracker_records_measured_duration_estimate_accuracy_and_real_budget(tmp_path, monkeypatch):
    tracker = EducationalRunTracker(tmp_path / "timed", title="Test")
    clock = iter([100.0, 130.0])
    monkeypatch.setattr("tools.structure.educational_run_tracker.time.time", lambda: next(clock))
    tracker.begin("input_ingestion", metadata={"estimated_duration_seconds": 60})
    tracker.finish("input_ingestion", {"source_path": "chapter.pdf"}, total_spent_usd=1.25)
    checkpoint = read_checkpoint(tracker.pipeline_dir, tracker.project_id, "input_ingestion")
    assert checkpoint["metadata"]["stage_duration_seconds"] == 30
    assert checkpoint["metadata"]["eta_accuracy_ratio"] == 0.5
    assert checkpoint["cost_snapshot"]["budget_remaining_usd"] == 3.75
