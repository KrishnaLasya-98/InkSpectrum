"""Validate dynamic Lesson 8 assessment card handoff intervals."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[2] / "projects" / "evs-lesson-8"
HTML = PROJECT / "full-hyperframes" / "index.html"


def _timeline() -> dict:
    raw = (PROJECT / "full-hyperframes" / "timeline-data.js").read_text(encoding="utf-8")
    return json.loads(raw.split("=", 1)[1].strip().rstrip(";"))


def test_assessment_intervals_are_non_overlapping_and_use_explicit_handoffs():
    data = _timeline()
    intervals = data["assessment_intervals"]["intervals"]
    assert len(intervals) == 13
    for item in intervals:
        assert item["prompt_start"] < item["handoff_end"]
        assert item["prediction_end"] - item["prediction_start"] == pytest.approx(5.0)
        assert item["reveal_end"] - item["reveal_start"] == pytest.approx(4.0)
    for previous, current in zip(intervals, intervals[1:]):
        assert previous["handoff_end"] <= current["prompt_start"]


def test_assessment_has_all_source_headers_options_and_safe_fallback():
    data = _timeline()
    headers = data["modules"]["assessment"]["headers"]
    assert headers == [
        "I. Answer the following question.",
        "II. Fill in the blanks.",
        "III. Choose the correct answer.",
    ]
    assert all(item["answer"] == "Guess and move to the next question." for item in data["exercises"])
    assert all(item["options"] for item in data["exercises"][-5:])


def test_shared_card_has_hard_clear_and_single_runtime_exercise():
    html = HTML.read_text(encoding="utf-8")
    assert "const optionRows = [...options.querySelectorAll" in html
    assert "tl.set(exercise, { opacity: 0, display: 'none' }" in html
    assert "exerciseStates" not in html
    assert "state.querySelector" not in html
    assert "tl.to(exercise, { opacity: 0" not in html
