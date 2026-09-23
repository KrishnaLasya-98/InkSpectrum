"""Focused regression tests for the EVS Lesson 8 FFmpeg compositor."""

import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMPOSER_DIR = PROJECT_ROOT / "projects" / "evs-lesson-8"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, COMPOSER_DIR / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


compose1 = _load("evs_lesson8_compose1_test", "_compose1.py")
compose2 = _load("evs_lesson8_compose2_test", "_compose2.py")


def test_subtitle_filter_uses_absolute_windows_safe_argument():
    path = Path(r"C:\EVS Lesson 8\renders\final.srt")
    value = compose2.subtitle_filter(path)
    assert value.startswith(r"subtitles=C\:/EVS\ Lesson\ 8/renders/final.srt")
    assert "force_style=FontName=Arial" in value
    assert r"FontName=Arial\,FontSize=22" in value
    assert "\"" not in value


def test_drawtext_subtitle_filter_uses_srt_cue_timings(tmp_path):
    subtitle = tmp_path / "final.srt"
    subtitle.write_text(
        "1\n00:00:00,000 --> 00:00:03,500\nAnimal life\n\n",
        encoding="utf-8",
    )
    value, cue_files = compose2.drawtext_subtitle_filter(subtitle)
    assert "drawtext=" in value
    assert r"between(t\,0.000\,3.500)" in value
    assert len(cue_files) == 1
    assert cue_files[0].read_text(encoding="utf-8") == "Animal life"


def test_subtitle_timestamp_carries_milliseconds():
    assert compose2._duration_to_ts(59.9999) == "00:01:00,000"
    assert compose2._duration_to_ts(3599.9999) == "01:00:00,000"


def test_cues_are_section_local_and_fallback_is_nonempty():
    section = {
        "id": "s02",
        "label": "What animals need",
        "start_seconds": 30,
        "end_seconds": 60,
        "enhancement_cues": [
            {"type": "overlay", "description": "Food and water", "timestamp_seconds": 48}
        ],
    }
    cues = compose1._cue_items(section, None)
    assert cues[0]["local_start"] == 18

    fallback = compose1._cue_items({**section, "enhancement_cues": []}, None)
    assert fallback[0]["text"] == "What animals need"
    assert fallback[0]["source"] == "fallback"


def test_probe_ok_allows_full_timeline_when_explicit_maximum_is_given(monkeypatch, tmp_path):
    media = tmp_path / "video_track.mp4"
    media.write_bytes(b"placeholder")
    monkeypatch.setattr(
        compose1,
        "probe_media",
        lambda path: {"duration": 480.0, "has_video": True, "has_audio": False},
    )
    assert compose1.probe_ok(media, min_seconds=478.0, max_seconds=482.0)
    assert not compose1.probe_ok(media, min_seconds=4.0)


def test_overlay_paths_cannot_escape_project_root():
    try:
        compose1._safe_project_path("../outside.png")
    except RuntimeError as exc:
        assert "escapes project root" in str(exc)
    else:
        raise AssertionError("path traversal was accepted")


def test_dry_run_reports_all_existing_sections_without_ffmpeg_work(tmp_path, monkeypatch):
    # This is a command-construction guard: dry-run must not call the encoder.
    calls = []
    monkeypatch.setattr(compose1, "sh", lambda cmd, timeout=900: calls.append(cmd))
    report = compose1.render(dry_run=True)
    assert report["completion_status"] == "dry_run"
    assert len(report["sections"]) == 16
    assert not calls
