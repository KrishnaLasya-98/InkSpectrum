"""Collection progress must reflect encoded QA, not stale plan labels."""

from __future__ import annotations

import json
from pathlib import Path

from backlot.collections import list_collections, load_collection_state


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_collection_requires_delivered_mp4_and_qa(tmp_path: Path, monkeypatch) -> None:
    from backlot import state

    collection = tmp_path / "collections" / "class-5-social"
    projects = tmp_path / "projects"
    active = projects / "class-5-social-part-0-chapter-2-earth-movement"
    active.mkdir(parents=True)
    video = tmp_path / "final" / "chapter-1.mp4"
    video.parent.mkdir()
    video.write_bytes(b"encoded")
    qa = tmp_path / "qa.json"
    qa.write_text("{}", encoding="utf-8")
    _write(collection / "artifacts" / "video_production_plan.json", {
        "execution_policy": {"max_concurrent_chapters": 1},
        "chapters": [
            {"chapter": 1, "title": "One", "status": "completed", "final_video": str(video), "qa_evidence": str(qa)},
            {"chapter": 2, "title": "Two", "status": "motion_jobs_submitted"},
            {"chapter": 3, "title": "Three", "status": "queued"},
        ],
    })
    monkeypatch.setattr(state, "summarize_project", lambda path: {"active_stage": "composition", "last_activity": 123})
    assert list_collections(collection.parent) == [{"id": "class-5-social", "chapter_count": 3}]
    board = load_collection_state(collection, projects)
    assert [row["status"] for row in board["chapters"]] == ["completed", "in_progress", "queued"]
    assert board["chapters"][1]["project_id"] == active.name
    assert board["completed_count"] == 1
    assert board["next_chapter"] == 2
    qa.unlink()
    board = load_collection_state(collection, projects)
    assert board["chapters"][0]["status"] == "in_progress"
    assert board["chapters"][1]["status"] == "waiting_for_previous_chapter"
    assert board["next_chapter"] == 1


def test_collection_api_rejects_unsafe_id(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient
    from backlot import server

    async def no_watch():
        return None

    monkeypatch.setattr(server, "_watch_projects", no_watch)
    monkeypatch.setattr(server, "COLLECTIONS_DIR", tmp_path)
    monkeypatch.setattr(server, "PROJECTS_DIR", tmp_path / "projects")
    _write(tmp_path / "class-5-social" / "artifacts" / "video_production_plan.json", {
        "chapters": [{"chapter": 1, "title": "Earth", "status": "queued"}],
    })
    with TestClient(server.create_app()) as client:
        response = client.get("/api/collections/class-5-social")
        assert response.status_code == 200
        assert response.json()["chapters"][0]["status"] == "ready"
        assert client.get("/c/class-5-social").status_code == 200
        assert client.get("/api/collections/no-such-collection").status_code == 404
        assert client.get("/api/collections/bad.id").status_code == 400


def test_collection_shows_review_video_without_marking_chapter_complete(tmp_path: Path, monkeypatch) -> None:
    from backlot import state

    collection = tmp_path / "collections" / "class-5-social"
    projects = tmp_path / "projects"
    project = projects / "class-5-social-part-0-chapter-2-earth-movement"
    review = project / "hyperframes-draft-v1" / "renders" / "chapter-2.mp4"
    review.parent.mkdir(parents=True)
    review.write_bytes(b"review")
    _write(project / "artifacts" / "latest-review-render.json", {
        "status": "review_ready",
        "path": "hyperframes-draft-v1/renders/chapter-2.mp4",
    })
    _write(collection / "artifacts" / "video_production_plan.json", {
        "chapters": [
            {"chapter": 2, "title": "Earth Movement", "status": "in_progress"},
        ],
    })
    monkeypatch.setattr(state, "summarize_project", lambda path: {"active_stage": None, "last_activity": 123})
    row = load_collection_state(collection, projects)["chapters"][0]
    assert row["status"] == "in_progress"
    assert row["qa_verified"] is False
    assert row["video"] is None
    assert row["review_render"]["url"].endswith("/hyperframes-draft-v1/renders/chapter-2.mp4")

    _write(project / "artifacts" / "latest-review-render.json", {
        "status": "review_ready", "path": "../../outside.mp4",
    })
    assert load_collection_state(collection, projects)["chapters"][0]["review_render"] is None
