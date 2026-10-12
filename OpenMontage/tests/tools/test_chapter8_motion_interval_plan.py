"""Guard the measured Chapter 8 plan before any paid motion admission."""
import importlib.util
from pathlib import Path


SCRIPT = (Path(__file__).resolve().parents[2] / "projects" /
          "class-5-social-part-0-chapter-8-struggle-for-indians-freedom" /
          "plan_motion_intervals.py")
SPEC = importlib.util.spec_from_file_location("chapter8_motion_interval_plan", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_no_word_reuse_or_gap_in_planned_intervals():
    words = [
        {"word": "First.", "start_ms": 0, "end_ms": 4100},
        {"word": "Second.", "start_ms": 4200, "end_ms": 5100},
        {"word": "Third.", "start_ms": 5200, "end_ms": 6200},
    ]
    rows = MODULE.plan_words(words, 9000)
    assert rows[0][0] == 0 and rows[-1][1] == 9000
    assert all(a[1] == b[0] for a, b in zip(rows, rows[1:]))
    assert [word["word"] for _, _, segment in rows for word in segment] == [w["word"] for w in words]


def test_short_tail_needs_a_distinct_clip():
    words = [
        {"word": "Heading.", "start_ms": 0, "end_ms": 4100},
        {"word": "Content.", "start_ms": 4700, "end_ms": 6300},
    ]
    rows = MODULE.plan_words(words, 8300)
    assert len(rows) == 2
    assert rows[0][1] <= 5300
    assert rows[1][1] - rows[1][0] >= 3000
