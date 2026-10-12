from tools.analysis.final_stage_director import FinalStageDirector, _layer_content


def test_final_stage_dry_run_is_not_a_quality_pass(tmp_path):
    result = FinalStageDirector().execute(
        {
            "video_path": str(tmp_path / "not-rendered.mp4"),
            "subject": "science",
            "output_dir": str(tmp_path),
            "dry_run": True,
        }
    )

    assert result.success
    assert result.data["status"] == "not_evaluated"
    assert result.data["all_passed"] is False
    assert result.data["export_path"] == ""


def test_content_layer_rejects_unverified_generated_clips():
    report = _layer_content(
        {"segments": []},
        {"sections": [{"section_id": "s1", "render_mode": "video_gen"}]},
        [{
            "section_id": "s1",
            "render_mode": "video_gen",
            "success": True,
            "qa_report": {"status": "dry_run"},
        }],
    )

    assert report["unverified_generated_clip_count"] == 1
    assert any("lacks passing" in issue for issue in report["issues"])
