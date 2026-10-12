from schemas.artifacts import validate_artifact
from tools.structure.educational_production_artifacts import (
    build_production_artifacts,
    finalize_asset_manifest,
)


def test_production_artifacts_are_source_linked_and_subject_independent():
    config = {
        "project_id": "robotics-lesson-1",
        "subject": "robotics",
        "grade": 4,
        "chapter": 1,
        "content_policy": {"allow_invented_labels": False},
        "render_policy": {
            "ui_template_id": "hyperframes-educational-v1",
            "ui_template_version": "1.0.1",
            "ui_template_package_sha256": "hash",
        },
        "providers": {
            "audio": {"provider": "modelslab"},
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
        "title": "Friendly Robots",
        "sections": [
            {
                "section_id": "s1", "render_mode": "video_gen",
                "source_block_ids": ["p0001-b0001"],
                "description": "A small robot follows a path", "duration_seconds": 6,
            },
            {
                "section_id": "s2", "render_mode": "hyperframes",
                "source_block_ids": ["p0001-b0002"],
                "source_semantic_role": "recall", "duration_seconds": 8,
            },
        ],
    }

    artifacts = build_production_artifacts(config, plan)

    assert artifacts["proposal_packet"]["production_plan"]["render_runtime"] == "hyperframes"
    assert artifacts["scene_plan"]["scenes"][0]["source_block_ids"] == ["p0001-b0001"]
    assert artifacts["asset_strategy"]["decisions"][0]["selected_strategy"] == "generated_3d_video"
    assert artifacts["asset_strategy"]["decisions"][1]["selected_strategy"] == "stable_teaching_ui"
    assert artifacts["asset_strategy"]["blocked_scene_ids"] == []
    validate_artifact("proposal_packet", artifacts["proposal_packet"])
    validate_artifact("scene_plan", artifacts["scene_plan"])
    validate_artifact("asset_strategy", artifacts["asset_strategy"])
    validate_artifact("asset_manifest", artifacts["asset_manifest"])


def test_asset_manifest_is_finalized_from_verified_clips():
    manifest = {
        "version": "1.0",
        "assets": [{
            "id": "s1:visual", "scene_id": "s1", "type": "video",
            "source_tool": "modelslab",
            "strategy": "generated_3d_video", "status": "planned",
            "path": "", "qa_status": "pending",
        }],
    }
    final = finalize_asset_manifest(manifest, [{
        "section_id": "s1", "success": True, "video_path": "clips/s1.mp4",
        "content_fingerprint": "abc", "qa_report": {"status": "pass"},
    }])

    assert final["ready"] is True
    assert final["assets"][0]["path"] == "clips/s1.mp4"
    assert final["assets"][0]["qa_status"] == "pass"
    validate_artifact("asset_manifest", final)
