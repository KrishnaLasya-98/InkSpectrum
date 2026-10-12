from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.structure.educational_pre_render_receipt import (
    create_pre_render_receipt,
    verify_pre_render_receipt,
)
from tools.video.educational_hyperframes_composer import EducationalHyperFramesComposer
from tools.structure.subject_pipeline_runner import (
    _create_strict_production_pre_render_receipt,
)


def _write(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _fixture(tmp_path: Path) -> tuple[dict[str, Path], Path]:
    media = tmp_path / "motion.mp4"
    media.write_bytes(b"reviewed-motion")
    shared = {
        "section_id": "s01",
        "kind": "provider_motion",
        "start_offset_seconds": 0,
        "overlay_label": "Lesson",
        "overlay_label_source": "reviewed_textbook_section_title",
        "overlay_label_style": "lesson2_small_cream_section_label",
        "embedded_generated_text_allowed": False,
    }
    paths = {
        "intervals": _write(tmp_path / "intervals.json", {"intervals": [shared]}),
        "assignments": _write(tmp_path / "assignments.json", {"assignments": [{
            "route_id": "s01:0.000:provider_motion", "section_id": "s01",
            "kind": "provider_motion", "phrase_text": "Lesson begins",
            "phrase_verified": True, "media_path": str(media),
            "encoded_review_status": "accepted",
        }]}),
        "pages": _write(tmp_path / "pages.json", {"teaching_pages": []}),
        "narration": _write(tmp_path / "narration.json", {
            "voice_name": "voice", "metadata": {"model_id": "model", "speed": 0.85},
            "pronunciation_qa_status": "passed", "segments": [{
                "section_id": "s01", "spoken_heading": "Lesson.",
                "measured_title_pause_seconds": 2.0,
                "heading_pause_presentation": "inline", "title_card_hold_seconds": 0,
            }],
        }),
    }
    return paths, media


def test_receipt_is_invalidated_when_approved_media_changes(tmp_path: Path) -> None:
    paths, media = _fixture(tmp_path)
    receipt = tmp_path / "receipt.json"
    create_pre_render_receipt(
        project_path=tmp_path, intervals_path=paths["intervals"],
        assignments_path=paths["assignments"], teaching_pages_path=paths["pages"],
        narration_manifest_path=paths["narration"], output_path=receipt,
        voice_id="voice", model_id="model", speed=0.85,
    )
    assert verify_pre_render_receipt(receipt)["media_verified"] == 1
    media.write_bytes(b"changed-after-review")
    with pytest.raises(ValueError, match="media changed after approval"):
        verify_pre_render_receipt(receipt)


def test_receipt_is_invalidated_when_assignment_manifest_changes(tmp_path: Path) -> None:
    paths, _ = _fixture(tmp_path)
    receipt = tmp_path / "receipt.json"
    create_pre_render_receipt(
        project_path=tmp_path, intervals_path=paths["intervals"],
        assignments_path=paths["assignments"], teaching_pages_path=paths["pages"],
        narration_manifest_path=paths["narration"], output_path=receipt,
        voice_id="voice", model_id="model", speed=0.85,
    )
    assignments = json.loads(paths["assignments"].read_text())
    assignments["assignments"][0]["phrase_text"] = "Changed after approval"
    paths["assignments"].write_text(json.dumps(assignments), encoding="utf-8")
    with pytest.raises(ValueError, match="assignments: input changed after approval"):
        verify_pre_render_receipt(receipt)


def test_strict_stable_visual_receipt_rejects_unreviewed_card(tmp_path: Path) -> None:
    paths, _ = _fixture(tmp_path)
    intervals = json.loads(paths["intervals"].read_text())
    assignments = json.loads(paths["assignments"].read_text())
    intervals["intervals"][0].update({"route_id": "s01:0.000:stable_source_card",
                                      "kind": "stable_source_card"})
    assignments["assignments"][0].update({"route_id": "s01:0.000:stable_source_card",
                                          "kind": "stable_source_card"})
    _write(paths["intervals"], intervals)
    _write(paths["assignments"], assignments)
    kwargs = dict(project_path=tmp_path, intervals_path=paths["intervals"],
                  assignments_path=paths["assignments"], teaching_pages_path=paths["pages"],
                  narration_manifest_path=paths["narration"], output_path=tmp_path / "receipt.json",
                  voice_id="voice", model_id="model", speed=0.85,
                  require_stable_visual_exceptions=True)
    with pytest.raises(ValueError, match="unreviewed stable visual exception"):
        create_pre_render_receipt(**kwargs)
    for row in (intervals["intervals"][0], assignments["assignments"][0]):
        row.update({"stable_exception_type": "objectives", "stable_exception_reviewed": True})
    _write(paths["intervals"], intervals)
    _write(paths["assignments"], assignments)
    result = create_pre_render_receipt(**kwargs)
    assert result["gates"]["stable_visual_exceptions"]["stable_exceptions_checked"] == 1
    assert verify_pre_render_receipt(tmp_path / "receipt.json")["status"] == "pass"


def test_strict_composer_fails_closed_without_receipt() -> None:
    result = EducationalHyperFramesComposer().execute({
        "strict_educational_regression": True,
        "asset_base_dir": ".",
    })
    assert not result.success
    assert "requires a hash-bound pre-render regression receipt" in (result.error or "")


def test_real_runner_entrypoint_creates_and_hashes_strict_receipt(tmp_path: Path) -> None:
    paths, _ = _fixture(tmp_path)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    paths["intervals"].replace(artifacts / "visual-interval-plan-v1.json")
    paths["assignments"].replace(artifacts / "visual-assignments-v1.json")
    paths["pages"].replace(artifacts / "teaching-pages-v1.json")
    paths["narration"].replace(artifacts / "narration_manifest.json")

    receipt = _create_strict_production_pre_render_receipt(
        project_dir=tmp_path,
        artifacts_dir=artifacts,
        voice_id="voice",
        model_id="model",
        speed=0.85,
    )

    receipt_path = artifacts / "pre-render-regression-receipt.json"
    assert receipt_path.is_file()
    assert receipt["status"] == "pass"
    assert set(receipt["input_sha256"]) == {
        "intervals", "assignments", "teaching_pages", "narration_manifest"
    }
    assert verify_pre_render_receipt(receipt_path)["media_verified"] == 1
