from tools.analysis.multimedia_sync_planner import build_sync_plan


def _narration():
    return {
        "segments": [
            {"section_id": "s1", "duration_seconds": 2.5},
            {"section_id": "s2", "duration_seconds": 3.0},
        ]
    }


def test_audio_is_timing_authority_and_title_offset_applied_once():
    plan = build_sync_plan(
        _narration(),
        [
            {"section_id": "s1", "duration_seconds": 2.5},
            {"section_id": "s2", "duration_seconds": 3.0},
        ],
        title_offset_seconds=3.0,
    )
    assert plan["timeline"][0]["start_seconds"] == 3.0
    assert plan["timeline"][1]["start_seconds"] == 5.5
    assert plan["total_duration_seconds"] == 8.5


def test_short_visual_is_explicitly_looped_or_held():
    plan = build_sync_plan(
        {"segments": [{"section_id": "s1", "duration_seconds": 8.0}]},
        [{"section_id": "s1", "duration_seconds": 5.0}],
    )
    assert plan["timeline"][0]["visual_duration_policy"] == "loop_or_hold_last_frame"
    assert plan["status"] == "pass"


def test_missing_clip_blocks_composition_plan():
    plan = build_sync_plan(_narration(), [{"section_id": "s1", "duration_seconds": 2.5}])
    assert plan["status"] == "blocked"
    assert plan["issues"] == [{"section_id": "s2", "severity": "critical", "code": "missing_clip"}]
