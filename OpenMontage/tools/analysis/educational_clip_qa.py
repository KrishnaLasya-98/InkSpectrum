"""Fail-closed QA for generated educational motion clips.

The provider returning an MP4 is not sufficient evidence that the clip is
usable. This module verifies the media contract (playable, moving, silent,
and non-black) and can sample rendered pixels with the local vision-language
evaluator to check that they match the current source-grounded section.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


def expected_visual_text(section: dict[str, Any]) -> str:
    """Return a concise, source-derived visual description for one section."""
    parts: list[str] = []
    for key in ("description", "title"):
        value = str(section.get(key) or "").strip()
        if value:
            parts.append(value)

    for value in section.get("visual_cues") or []:
        if isinstance(value, dict):
            value = value.get("description") or value.get("text") or value.get("label")
        value = str(value or "").strip()
        if value:
            parts.append(value)

    for value in section.get("key_concepts") or []:
        value = str(value or "").strip()
        if value:
            parts.append(value)

    media = section.get("source_media") or []
    if isinstance(media, dict):
        media = [media]
    for item in media:
        if not isinstance(item, dict):
            continue
        value = str(item.get("alt_text") or item.get("caption") or "").strip()
        if value:
            parts.append(value)

    unique: list[str] = []
    seen: set[str] = set()
    for part in parts:
        compact = " ".join(part.split())
        key = compact.casefold()
        if compact and key not in seen:
            unique.append(compact)
            seen.add(key)
    return ". ".join(unique[:4])[:700]


def _probe(path: Path) -> dict[str, Any]:
    if not shutil.which("ffprobe"):
        return {"error": "ffprobe is unavailable"}
    try:
        proc = subprocess.run(
            [
                "ffprobe", "-v", "error", "-print_format", "json",
                "-show_format", "-show_streams", str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            return {"error": proc.stderr.strip() or "ffprobe failed"}
        return json.loads(proc.stdout)
    except Exception as exc:
        return {"error": str(exc)}


def _filter_events(
    path: Path, filter_spec: str, pattern: str, *, media_duration: float | None = None
) -> tuple[list[float], str | None]:
    if not shutil.which("ffmpeg"):
        return [], "ffmpeg is unavailable"
    try:
        proc = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
                "-vf", filter_spec, "-an", "-f", "null", "-",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0:
            return [], (proc.stderr.strip()[-500:] or "ffmpeg filter failed")
        events = [float(value) for value in re.findall(pattern, proc.stderr)]
        if filter_spec.startswith("freezedetect") and media_duration is not None:
            # FFmpeg may not emit freeze_duration for a freeze continuing to
            # EOF. Otherwise a completely still generated clip can pass QA.
            starts = re.findall(r"freeze_start:\s*([0-9.]+)", proc.stderr)
            ends = re.findall(r"freeze_end:\s*([0-9.]+)", proc.stderr)
            if len(starts) > len(ends):
                events.append(max(0.0, media_duration - float(starts[-1])))
        return events, None
    except Exception as exc:
        return [], str(exc)


def technical_motion_audit(
    video_path: str | Path,
    *,
    minimum_duration_seconds: float = 1.0,
    freeze_duration_seconds: float = 1.5,
) -> dict[str, Any]:
    """Check the generated-file contract without trusting its extension."""
    path = Path(video_path)
    if not path.is_file() or path.stat().st_size == 0:
        return {
            "status": "fail", "duration_seconds": 0.0,
            "has_video": False, "has_audio": False,
            "black_events": [], "freeze_durations": [],
            "issues": ["generated file is missing or empty"],
        }

    probe = _probe(path)
    if probe.get("error"):
        return {
            "status": "fail", "duration_seconds": 0.0,
            "has_video": False, "has_audio": False,
            "black_events": [], "freeze_durations": [],
            "issues": [f"media probe failed: {probe['error']}"],
        }

    streams = probe.get("streams") or []
    has_video = any(stream.get("codec_type") == "video" for stream in streams)
    has_audio = any(stream.get("codec_type") == "audio" for stream in streams)
    try:
        duration = float((probe.get("format") or {}).get("duration") or 0.0)
    except (TypeError, ValueError):
        duration = 0.0

    issues: list[str] = []
    if not has_video:
        issues.append("no video stream")
    if duration < minimum_duration_seconds:
        issues.append(
            f"duration {duration:.2f}s is below {minimum_duration_seconds:.2f}s"
        )
    if has_audio:
        issues.append("generated clip contains audio; narration must remain separate")

    black_events, black_error = _filter_events(
        path, "blackdetect=d=0.20:pix_th=0.10", r"black_duration:([0-9.]+)"
    )
    if black_error:
        issues.append(f"black-frame audit failed: {black_error}")
    if black_events:
        issues.append("black frames detected")

    freeze_durations, freeze_error = _filter_events(
        path,
        f"freezedetect=n=0.003:d={freeze_duration_seconds:.3f}",
        r"freeze_duration:\s*([0-9.]+)",
        media_duration=duration,
    )
    if freeze_error:
        issues.append(f"frozen-motion audit failed: {freeze_error}")
    if freeze_durations:
        issues.append(
            "frozen motion detected "
            f"(longest {max(freeze_durations):.2f}s)"
        )

    return {
        "status": "pass" if not issues else "fail",
        "duration_seconds": round(duration, 3),
        "has_video": has_video,
        "has_audio": has_audio,
        "black_events": black_events,
        "freeze_durations": freeze_durations,
        "issues": issues,
    }


def semantic_frame_audit(
    video_path: str | Path,
    section: dict[str, Any],
    *,
    model: str = "clip",
    max_frames: int = 5,
    minimum_match_ratio: float = 0.4,
) -> dict[str, Any]:
    """Check sampled pixels against the section's source-derived visual cue."""
    expected = expected_visual_text(section)
    if not expected:
        return {
            "status": "fail", "expected_visual": "", "match_ratio": 0.0,
            "issues": ["section has no source-grounded visual description"],
        }

    from tools.analysis.video_understand import VideoUnderstand
    from tools.base_tool import ToolStatus

    evaluator = VideoUnderstand()
    if evaluator.get_status() != ToolStatus.AVAILABLE:
        return {
            "status": "pending", "expected_visual": expected, "match_ratio": None,
            "issues": ["semantic visual evaluator is unavailable"],
        }

    query = f"a clear child-friendly animated scene showing {expected}"
    result = evaluator.execute({
        "input_path": str(video_path), "mode": "qa", "model": model,
        "query": query, "max_frames": max_frames,
    })
    if not result.success:
        return {
            "status": "pending", "expected_visual": expected, "match_ratio": None,
            "issues": [f"semantic visual evaluation failed: {result.error}"],
        }

    frames = result.data.get("frames") or []
    if not frames:
        return {
            "status": "pending", "expected_visual": expected, "match_ratio": None,
            "issues": ["semantic evaluator returned no frames"],
        }
    matches = sum(
        1 for frame in frames
        if str(frame.get("answer") or "").strip().casefold().startswith("yes")
    )
    ratio = matches / max(len(frames), 1)
    issues = [] if ratio >= minimum_match_ratio else [
        f"visual match ratio {ratio:.0%} is below {minimum_match_ratio:.0%}"
    ]
    return {
        "status": "pass" if not issues else "fail",
        "expected_visual": expected,
        "query": query,
        "frames_checked": len(frames),
        "matching_frames": matches,
        "match_ratio": round(ratio, 3),
        "model": model,
        "issues": issues,
    }


def audit_generated_clip(
    video_path: str | Path,
    section: dict[str, Any],
    *,
    semantic_required: bool = True,
    semantic_model: str = "clip",
    max_frames: int = 5,
    minimum_match_ratio: float = 0.4,
) -> dict[str, Any]:
    """Run technical and optional semantic QA and return one gate result."""
    technical = technical_motion_audit(video_path)
    if technical["status"] != "pass":
        return {
            "status": "fail", "technical": technical,
            "semantic": {"status": "not_run", "issues": []},
            "issues": list(technical["issues"]),
        }

    semantic = (
        semantic_frame_audit(
            video_path, section, model=semantic_model, max_frames=max_frames,
            minimum_match_ratio=minimum_match_ratio,
        )
        if semantic_required
        else {"status": "not_required", "issues": []}
    )
    issues = [*technical.get("issues", []), *semantic.get("issues", [])]
    passed = technical["status"] == "pass" and (
        not semantic_required or semantic.get("status") == "pass"
    )
    return {
        "status": "pass" if passed else "pending" if semantic.get("status") == "pending" else "fail",
        "technical": technical, "semantic": semantic, "issues": issues,
    }
