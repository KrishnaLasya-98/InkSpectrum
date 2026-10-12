from __future__ import annotations

import pytest

from tools.structure.educational_regression_gates import (
    validate_complete_visual_routes,
    validate_full_timeline_semantic_review,
    validate_interval_labeling,
    validate_pre_render_timeline,
    validate_stable_card_scope,
    validate_timed_narration,
)


def test_timed_narration_checks_every_heading_and_lock() -> None:
    manifest = {
        "voice_name": "voice", "metadata": {"model_id": "model", "speed": 0.85},
        "pronunciation_qa_status": "passed",
        "segments": [
            {"section_id": "s01", "spoken_heading": "Title.", "measured_title_pause_seconds": 2.0,
             "heading_pause_presentation": "inline", "title_card_hold_seconds": 0},
            {"section_id": "s02", "spoken_heading": "Location.", "measured_title_pause_seconds": 2.03,
             "heading_pause_presentation": "inline", "title_card_hold_seconds": 0},
        ],
    }
    assert validate_timed_narration(manifest, voice_id="voice", model_id="model", speed=0.85)["sections_checked"] == 2


def test_timed_narration_rejects_one_late_heading_in_full_set() -> None:
    manifest = {
        "voice_name": "voice", "metadata": {"model_id": "model", "speed": 0.85},
        "pronunciation_qa_status": "passed",
        "segments": [
            {"section_id": "s01", "spoken_heading": "Title.", "measured_title_pause_seconds": 2.0,
             "heading_pause_presentation": "inline", "title_card_hold_seconds": 0},
            {"section_id": "s40", "spoken_heading": "Word Bank.", "measured_title_pause_seconds": 1.6,
             "heading_pause_presentation": "inline", "title_card_hold_seconds": 0},
        ],
    }
    with pytest.raises(ValueError, match="s40"):
        validate_timed_narration(manifest, voice_id="voice", model_id="model", speed=0.85)


def test_visual_gate_rejects_dropped_accepted_figure_section_motion() -> None:
    routes = [{
        "section_id": "s10", "exact_source_figure": "figure.png", "provider_motion_required": True,
        "provider_submission_status": "accepted",
    }]
    with pytest.raises(ValueError, match="silently dropped"):
        validate_complete_visual_routes(routes, [])


def test_visual_gate_rejects_primitive_fallback() -> None:
    routes = [{"section_id": "s08", "provider_motion_required": False, "fallback_kind": "colored_rectangle"}]
    with pytest.raises(ValueError, match="primitive or irrelevant fallback"):
        validate_complete_visual_routes(routes, [])


def test_encoded_semantic_gate_requires_complete_distinct_review() -> None:
    technical = {"review_id": "technical", "automated_status": "pass"}
    semantic = {
        "review_id": "semantic", "status": "pass", "sections_reviewed": ["s01", "s02"],
        "clipped_text_or_subtitles": 0, "semantic_visual_mismatches": 0, "unreadable_source_figures": 0,
    }
    assert validate_full_timeline_semantic_review(technical, semantic, ["s01", "s02"])["sections_checked"] == 2


def test_encoded_semantic_gate_rejects_opening_only_sample() -> None:
    technical = {"review_id": "technical", "automated_status": "pass"}
    semantic = {
        "review_id": "semantic", "status": "pass", "sections_reviewed": ["s01"],
        "clipped_text_or_subtitles": 0, "semantic_visual_mismatches": 0, "unreadable_source_figures": 0,
    }
    with pytest.raises(ValueError, match="s40"):
        validate_full_timeline_semantic_review(technical, semantic, ["s01", "s40"])


def test_interval_labeling_checks_every_visual_kind() -> None:
    shared = {
        "section_id": "s07-earthquakes",
        "overlay_label": "Earthquakes",
        "overlay_label_source": "reviewed_textbook_section_title",
        "overlay_label_style": "lesson2_small_cream_section_label",
        "embedded_generated_text_allowed": False,
    }
    rows = [
        {**shared, "kind": "provider_motion"},
        {**shared, "kind": "exact_source_figure", "preserve_source_labels": True},
        {**shared, "kind": "precision_diagram", "authored_diagram_labels_reviewed": True},
    ]
    assert validate_interval_labeling(rows) == {"status": "pass", "intervals_checked": 3}


def test_interval_labeling_rejects_unlabeled_motion() -> None:
    with pytest.raises(ValueError, match="overlay label missing"):
        validate_interval_labeling([{
            "section_id": "s03-startup",
            "kind": "provider_motion",
            "overlay_label_source": "reviewed_textbook_section_title",
            "overlay_label_style": "lesson2_small_cream_section_label",
            "embedded_generated_text_allowed": False,
        }])


def test_pre_render_timeline_checks_phrase_page_figure_motion_and_uniqueness() -> None:
    intervals = [
        {"section_id":"s01", "start_offset_seconds":0, "kind":"provider_motion"},
        {"section_id":"s01", "start_offset_seconds":5, "kind":"exact_source_figure"},
    ]
    assignments = [
        {"route_id":"s01:0.000:provider_motion", "section_id":"s01", "kind":"provider_motion",
         "phrase_text":"The lesson begins", "phrase_verified":True, "media_path":"motion-a.mp4",
         "encoded_review_status":"accepted"},
        {"route_id":"s01:5.000:exact_source_figure", "section_id":"s01", "kind":"exact_source_figure",
         "phrase_text":"Study the figure", "phrase_verified":True, "source_sha256":"abc",
         "preserve_source_labels":True},
    ]
    pages = [{"page_id":"s02-p1", "source_text_exact":True, "phrase_verified":True,
              "start_offset_seconds":0, "end_offset_seconds":5}]
    result = validate_pre_render_timeline(intervals, assignments, pages)
    assert result == {"status":"pass", "intervals_checked":2, "assignments_checked":2,
                      "teaching_pages_checked":1, "unique_motion_paths":1}


def test_pre_render_timeline_rejects_missing_route_and_reused_motion() -> None:
    intervals = [
        {"section_id":"s01", "start_offset_seconds":0, "kind":"provider_motion"},
        {"section_id":"s01", "start_offset_seconds":5, "kind":"provider_motion"},
    ]
    assignments = [{"route_id":"s01:0.000:provider_motion", "section_id":"s01",
                    "kind":"provider_motion", "phrase_text":"Opening", "phrase_verified":True,
                    "media_path":"same.mp4", "encoded_review_status":"accepted"}]
    with pytest.raises(ValueError, match="missing assignments"):
        validate_pre_render_timeline(intervals, assignments, [])


def test_stable_card_scope_rejects_narrated_explanation_gaps() -> None:
    rows = [
        {"interval_id": "s01:01", "section_id": "s01-story", "kind": "provider_motion"},
        {"interval_id": "s01:02", "section_id": "s01-story", "kind": "stable_source_card"},
        {"interval_id": "s02:whole", "section_id": "s02-recall", "kind": "stable_source_card"},
    ]
    with pytest.raises(ValueError, match="s01:02"):
        validate_stable_card_scope(rows, allowed_section_ids={"s02-recall"})
    rows[1]["kind"] = "exact_source_figure"
    assert validate_stable_card_scope(
        rows, allowed_section_ids={"s02-recall"}
    )["intervals_checked"] == 3
