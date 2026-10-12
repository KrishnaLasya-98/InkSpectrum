from __future__ import annotations

import json
from pathlib import Path

from tools.base_tool import ToolResult
from tools.analysis.educational_clip_qa import (
    expected_visual_text,
    technical_motion_audit,
)
from tools.video.render_mode_router import RenderModeRouter, _render_video_gen
from tools.video.character_consistency import (
    CharacterBible,
    discover_recurring_characters,
)


def test_expected_visual_text_uses_source_grounded_cues():
    text = expected_visual_text({
        "title": "Water animals",
        "description": "A fish swims underwater",
        "visual_cues": [{"description": "fish moving its fins"}],
        "source_media": [{"alt_text": "pond with fish"}],
    })

    assert "A fish swims underwater" in text
    assert "fish moving its fins" in text
    assert "pond with fish" in text


def test_technical_motion_audit_rejects_missing_file(tmp_path: Path):
    report = technical_motion_audit(tmp_path / "missing.mp4")

    assert report["status"] == "fail"
    assert "missing or empty" in report["issues"][0]


def test_character_discovery_is_dynamic_and_requires_recurrence():
    sections = [
        {
            "section_id": "story-1",
            "render_mode": "video_gen",
            "source_text": "Maya walks to the beach with a red bucket.",
        },
        {
            "section_id": "story-2",
            "render_mode": "video_gen",
            "source_text": "Maya finds a shell and shows it to Ravi.",
        },
        {
            "section_id": "story-3",
            "render_mode": "video_gen",
            "source_text": "Ravi waves goodbye.",
        },
    ]

    characters = discover_recurring_characters(
        sections,
        chapter_title="At the Beach",
        visual_style="polished child-friendly 3D animated story",
    )

    assert [character["id"] for character in characters] == ["maya", "ravi"]
    assert characters[0]["sections"] == ["story-1", "story-2"]
    assert "Source context" in characters[0]["description"]


def test_character_bible_dry_run_is_isolated_to_chapter_workspace(tmp_path: Path):
    project = tmp_path / "english-class1-chapter2"
    bible = CharacterBible().generate(
        subject="english",
        dry_run=True,
        characters=[{
            "id": "maya",
            "name": "Maya",
            "description": "Maya from the supplied chapter",
            "sections": ["story-1", "story-2"],
            "seed": 99,
        }],
        project_dir=project,
    )

    assert (project / "artifacts" / "character_bible.json").is_file()
    reference = Path(bible["characters"]["maya"]["path"])
    assert reference.parent == project / "assets" / "characters"
    assert reference.is_file()

    changed = CharacterBible().generate(
        subject="english",
        dry_run=True,
        characters=[{
            "id": "maya",
            "name": "Maya",
            "description": "Maya now wears the source chapter's blue uniform",
            "sections": ["story-1", "story-2"],
            "seed": 99,
        }],
        project_dir=project,
    )
    assert changed["source_fingerprint"] != bible["source_fingerprint"]


def test_models_lab_clip_retries_after_semantic_qa_failure(monkeypatch, tmp_path: Path):
    calls: list[dict] = []
    qa_results = iter([
        {"status": "fail", "issues": ["wrong animal"]},
        {"status": "pass", "issues": []},
    ])

    def fake_generate(_self, request):
        calls.append(dict(request))
        Path(request["output_path"]).write_bytes(b"video")
        return ToolResult(success=True, data={"output_path": request["output_path"]})

    monkeypatch.setattr(
        "tools.video.modelslab_video.ModelsLabVideo.execute", fake_generate
    )
    monkeypatch.setattr(
        "tools.analysis.educational_clip_qa.audit_generated_clip",
        lambda *_args, **_kwargs: next(qa_results),
    )
    monkeypatch.setattr(
        "tools.video.render_mode_router._probe_duration", lambda _path: 5.0
    )

    result = _render_video_gen(
        {
            "section_id": "animals-s1",
            "title": "Water animals",
            "description": "A fish swims underwater",
            "duration_seconds": 5,
            "seed": 21,
        },
        "evs",
        tmp_path,
        False,
        {
            "provider": "modelslab",
            "model_id": "wan2.2",
            "max_generation_attempts": 3,
            "semantic_qa": {"required": True},
        },
    )

    assert result.success is True
    assert result.generation_attempts == 2
    assert result.qa_report["status"] == "pass"
    assert Path(result.video_path).is_file()
    assert calls[0]["seed"] == 21
    assert calls[1]["seed"] == 22
    assert "Previous QA: wrong animal" in calls[1]["prompt"]


def test_models_lab_router_uses_reference_to_video_for_recurring_characters(
    monkeypatch, tmp_path: Path
):
    calls: list[dict] = []
    maya = tmp_path / "maya.png"
    ravi = tmp_path / "ravi.png"
    maya.write_bytes(b"image")
    ravi.write_bytes(b"image")

    def fake_generate(_self, request):
        calls.append(dict(request))
        Path(request["output_path"]).write_bytes(b"video")
        return ToolResult(success=True, data={"output_path": request["output_path"]})

    monkeypatch.setattr(
        "tools.video.modelslab_video.ModelsLabVideo.execute", fake_generate
    )
    monkeypatch.setattr(
        "tools.analysis.educational_clip_qa.audit_generated_clip",
        lambda *_args, **_kwargs: {"status": "pass", "issues": []},
    )
    monkeypatch.setattr(
        "tools.video.render_mode_router._probe_duration", lambda _path: 5.0
    )

    result = _render_video_gen(
        {
            "section_id": "story-2",
            "description": "Maya shows a shell to Ravi",
            "duration_seconds": 5,
            "reference_image_paths": [str(maya), str(ravi)],
            "reference_characters": [
                {"id": "maya", "name": "Maya"},
                {"id": "ravi", "name": "Ravi"},
            ],
        },
        "english",
        tmp_path,
        False,
        {
            "provider": "modelslab",
            "reference_model_id": "h3-minimax-r2v",
        },
    )

    assert result.success is True
    assert calls[0]["operation"] == "reference_to_video"
    assert calls[0]["model_id"] == "h3-minimax-r2v"
    assert calls[0]["reference_image_paths"] == [str(maya), str(ravi)]
    assert "Image 1 is Maya" in calls[0]["prompt"]


def test_resume_rejects_stale_or_unverified_generated_clip(
    monkeypatch, tmp_path: Path
):
    section = {
        "section_id": "plants-s1",
        "render_mode": "video_gen",
        "title": "Plants need water",
        "description": "A child waters a growing plant",
        "duration_seconds": 5,
    }
    clip = tmp_path / "plants-s1.mp4"
    clip.write_bytes(b"old")
    (tmp_path / "clip_manifest.json").write_text(
        json.dumps({
            "subject": "science",
            "clips": [{
                "section_id": "plants-s1",
                "success": True,
                "video_path": str(clip),
                "content_fingerprint": "stale",
                "qa_report": {"status": "pass"},
            }],
        }),
        encoding="utf-8",
    )
    generated = {"count": 0}

    def fake_generate(_self, request):
        generated["count"] += 1
        Path(request["output_path"]).write_bytes(b"new")
        return ToolResult(success=True, data={"output_path": request["output_path"]})

    monkeypatch.setattr(
        "tools.video.modelslab_video.ModelsLabVideo.execute", fake_generate
    )
    monkeypatch.setattr(
        "tools.analysis.educational_clip_qa.audit_generated_clip",
        lambda *_args, **_kwargs: {"status": "pass", "issues": []},
    )
    monkeypatch.setattr(
        "tools.video.render_mode_router._probe_duration", lambda _path: 5.0
    )

    result = RenderModeRouter().execute({
        "educational_plan": {"sections": [section]},
        "subject": "science",
        "output_dir": str(tmp_path),
        "video_provider": {
            "provider": "modelslab",
            "model_id": "wan2.2",
            "max_generation_attempts": 1,
        },
    })

    assert result.success is True
    assert generated["count"] == 1
    assert result.data["skipped_clips"] == 0
    assert result.data["clip_manifest"][0]["qa_report"]["status"] == "pass"
