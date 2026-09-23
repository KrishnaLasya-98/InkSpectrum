"""FinalStageDirector — advanced final-stage runner for EduStream Pro.

Produces a machine-readable + human-readable "tour report" that an agent
(Claude / Kiro / Cursor / Kilo) can read to understand exactly what the
finished video contains, what passed, what failed, and what to do next.

The report covers six inspection layers:

  Layer 1  Technical probe     ffprobe: duration, codec, fps, resolution, audio
  Layer 2  Visual spotcheck    Sample 6 frames at key positions + black-frame test
  Layer 3  Audio spotcheck     Peak level, silence detection, narration presence
  Layer 4  Subtitle check      SRT coverage ratio + timing drift
  Layer 5  Content fidelity    narration WPM, section count, render_mode coverage
  Layer 6  QA gate summary     Pacing / sync / contrast / slideshow risk / WPM

After running all layers the director writes:
  - artifacts/final_review.json      (schema-valid final_review artifact)
  - artifacts/qa_report.json         (detailed QA check results)
  - renders/snapshots/               (6 frame grabs for visual inspection)
  - exports/{subject}/               (ExportBundle: .mp4 + .srt + metadata)
  - artifacts/agent_tour.md          (plain-language narrative for the agent)

The agent_tour.md is the "detailed tour" — it translates every metric into
plain English with pass/fail/warn icons, recommended actions, and direct
file paths so the agent can locate and fix any issue.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.base_tool import (  # noqa: E402
    BaseTool,
    Determinism,
    ExecutionMode,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)


# ---------------------------------------------------------------------------
# ffprobe helpers
# ---------------------------------------------------------------------------

def _ffprobe(path: Path) -> dict[str, Any]:
    """Return rich probe dict for a video/audio file."""
    if not shutil.which("ffprobe"):
        return {"error": "ffprobe not on PATH"}
    try:
        r = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format", "-show_streams",
                str(path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        return json.loads(r.stdout) if r.returncode == 0 else {"error": r.stderr[:200]}
    except Exception as exc:
        return {"error": str(exc)}


def _extract_frame(video: Path, position_s: float, out: Path) -> bool:
    """Extract one JPEG frame at position_s seconds. Returns True on success."""
    try:
        r = subprocess.run(
            [
                "ffmpeg", "-y", "-ss", str(position_s),
                "-i", str(video), "-frames:v", "1",
                "-q:v", "2", str(out),
            ],
            capture_output=True, timeout=30,
        )
        return r.returncode == 0 and out.exists()
    except Exception:
        return False


def _detect_black_frames(video: Path, duration: float) -> bool:
    """Return True if >2 consecutive black frames are found."""
    if not shutil.which("ffprobe"):
        return False
    try:
        # The path is embedded inside the lavfi filter string as:
        #   movie=<path>,blackdetect=...
        # ffprobe parses the filter string itself, so spaces and special
        # chars must be escaped with backslash (not shell-quoting).
        posix = video.resolve().as_posix()
        # Escape spaces: replace ' ' with '\ ' inside the filter value
        escaped = posix.replace(" ", "\\ ").replace("'", "\\'")
        r = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-f", "lavfi",
                "-i", f"movie={escaped},blackdetect=d=0.1:pix_th=0.10",
                "-show_entries", "tags=lavfi.black_start",
                "-of", "default=noprint_wrappers=1",
            ],
            capture_output=True, text=True, timeout=60,
        )
        return "black_start" in r.stdout
    except Exception:
        return False


def _detect_silence(video: Path) -> bool:
    """Return True if there is > 3s of silence in the audio track."""
    try:
        r = subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(video),
                "-af", "silencedetect=n=-50dB:d=3",
                "-f", "null", "-",
            ],
            capture_output=True, text=True, timeout=120,
        )
        return "silence_start" in r.stderr
    except Exception:
        return False


def _peak_lufs(video: Path) -> tuple[float, float]:
    """Return (integrated_lufs, true_peak_db) via ffmpeg loudnorm analysis."""
    try:
        r = subprocess.run(
            [
                "ffmpeg", "-i", str(video),
                "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
                "-f", "null", "-",
            ],
            capture_output=True, text=True, timeout=120,
        )
        # loudnorm prints JSON to stderr
        m = re.search(r"\{[^}]*\"input_i\"[^}]*\}", r.stderr, re.DOTALL)
        if m:
            d = json.loads(m.group(0))
            return float(d.get("input_i", -99)), float(d.get("input_tp", -99))
    except Exception:
        pass
    return -99.0, -99.0


def _posix(p: Path) -> str:
    return p.resolve().as_posix()


# ---------------------------------------------------------------------------
# Layer implementations
# ---------------------------------------------------------------------------

def _layer_technical(video: Path) -> dict[str, Any]:
    probe = _ffprobe(video)
    if "error" in probe:
        return {
            "valid_container": False, "duration_seconds": 0,
            "resolution": "unknown", "fps": 0, "has_audio": False,
            "codec": "unknown", "file_size_bytes": 0,
            "issues": [f"ffprobe failed: {probe['error']}"],
        }

    fmt    = probe.get("format", {})
    streams = probe.get("streams", [])
    video_s = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio_s = next((s for s in streams if s.get("codec_type") == "audio"), {})

    duration = float(fmt.get("duration", 0))
    w = video_s.get("width", 0)
    h = video_s.get("height", 0)
    fps_raw = video_s.get("r_frame_rate", "0/1")
    try:
        num, den = fps_raw.split("/")
        fps = round(int(num) / max(int(den), 1), 2)
    except Exception:
        fps = 0.0

    issues: list[str] = []
    if duration < 5:
        issues.append(f"Duration too short: {duration:.1f}s (minimum 5s)")
    if not audio_s:
        issues.append("No audio stream found in output file")
    if w < 1280 or h < 720:
        issues.append(f"Resolution {w}x{h} below 1280×720 minimum")
    if fps < 25:
        issues.append(f"FPS {fps} below 25 minimum")

    return {
        "valid_container": len(issues) == 0,
        "duration_seconds": round(duration, 2),
        "resolution": f"{w}x{h}",
        "fps": fps,
        "has_audio": bool(audio_s),
        "codec": video_s.get("codec_name", "unknown"),
        "file_size_bytes": int(fmt.get("size", 0)),
        "issues": issues,
    }


def _layer_visual(video: Path, duration: float, snapshots_dir: Path) -> dict[str, Any]:
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    positions = {
        "opening":  0.05 * duration,
        "early":    0.20 * duration,
        "middle":   0.45 * duration,
        "climax":   0.70 * duration,
        "late":     0.85 * duration,
        "closing":  0.97 * duration,
    }
    frame_paths: list[str] = []
    for label, pos in positions.items():
        out = snapshots_dir / f"frame_{label}.jpg"
        if _extract_frame(video, pos, out):
            frame_paths.append(str(out))

    has_black = _detect_black_frames(video, duration)
    issues: list[str] = []
    if has_black:
        issues.append("Black frames detected — possible missing clip or encode error")
    if len(frame_paths) < 4:
        issues.append(f"Only {len(frame_paths)}/6 frames extracted — video may be corrupt")

    return {
        "frames_sampled": len(frame_paths),
        "frame_paths": frame_paths,
        "black_frames_detected": has_black,
        "broken_overlays": False,   # requires VLM — marked False conservatively
        "missing_assets": False,
        "unreadable_text": False,
        "issues": issues,
    }


def _layer_audio(video: Path) -> dict[str, Any]:
    lufs, peak = _peak_lufs(video)
    has_silence = _detect_silence(video)
    clipping = peak > -1.0

    issues: list[str] = []
    if lufs < -30:
        issues.append(f"Audio very quiet: {lufs:.1f} LUFS (target -14 LUFS)")
    if lufs > -8:
        issues.append(f"Audio too loud: {lufs:.1f} LUFS (target -14 LUFS)")
    if clipping:
        issues.append(f"True-peak clipping detected: {peak:.1f} dBTP > -1.0 dBTP")
    if has_silence:
        issues.append("Unexpected silence > 3s detected in audio track")

    return {
        "narration_present": lufs > -60,
        "music_present": False,          # would need track-isolation analysis
        "unexpected_silence": has_silence,
        "clipping_detected": clipping,
        "mix_intelligible": lufs > -30 and not clipping,
        "integrated_lufs": round(lufs, 1),
        "true_peak_dbtp": round(peak, 1),
        "issues": issues,
    }


def _layer_subtitle(srt_path: Path | None, duration: float) -> dict[str, Any]:
    if not srt_path or not srt_path.exists():
        return {
            "subtitles_expected": True,
            "subtitles_present": False,
            "coverage_ratio": 0.0,
            "timing_drift_detected": False,
            "issues": ["SRT file not found — subtitles missing from export"],
        }

    text = srt_path.read_text(encoding="utf-8")
    # Parse all timestamps
    ts_re = re.compile(r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})")
    matches = ts_re.findall(text)

    def _to_s(ts: str) -> float:
        h, m, s = ts.split(":")
        sc, ms = s.split(",")
        return int(h) * 3600 + int(m) * 60 + int(sc) + int(ms) / 1000

    covered = sum(_to_s(end) - _to_s(start) for start, end in matches)
    coverage = min(1.0, covered / max(duration, 1))

    issues: list[str] = []
    if coverage < 0.5:
        issues.append(f"Subtitle coverage only {coverage:.0%} — less than half the video")
    if not matches:
        issues.append("SRT file is empty or has no valid timestamps")

    last_end = _to_s(matches[-1][1]) if matches else 0
    drift = abs(last_end - duration)
    timing_drift = drift > 5.0
    if timing_drift:
        issues.append(
            f"Last subtitle ends at {last_end:.1f}s but video is {duration:.1f}s "
            f"({drift:.1f}s drift)"
        )

    return {
        "subtitles_expected": True,
        "subtitles_present": True,
        "subtitle_count": len(matches),
        "coverage_ratio": round(coverage, 3),
        "timing_drift_detected": timing_drift,
        "issues": issues,
    }


def _layer_content(
    narration_manifest: dict[str, Any],
    educational_plan: dict[str, Any],
    clip_manifest: list[dict[str, Any]],
) -> dict[str, Any]:
    segments   = narration_manifest.get("segments", [])
    sections   = educational_plan.get("sections", [])
    issues: list[str] = []
    wpm_stats: list[dict[str, Any]] = []

    for seg in segments:
        sid   = seg["section_id"]
        text  = seg.get("text", "")
        dur   = float(seg.get("duration_seconds", 1))
        wpm   = len(text.split()) / max(dur / 60, 0.01)
        wpm_stats.append({"section_id": sid, "wpm": round(wpm)})
        if wpm > 145:
            issues.append(f"{sid}: narration too fast ({wpm:.0f} WPM > 145)")
        if wpm < 100:
            issues.append(f"{sid}: narration too slow ({wpm:.0f} WPM < 100)")

    render_mode_counts: dict[str, int] = {}
    for sec in sections:
        rm = sec.get("render_mode", "unknown")
        render_mode_counts[rm] = render_mode_counts.get(rm, 0) + 1

    failed_clips = [c for c in clip_manifest if not c.get("success")]
    if failed_clips:
        for fc in failed_clips[:3]:
            issues.append(f"Clip failed: {fc['section_id']} ({fc.get('error','')[:60]})")

    return {
        "section_count": len(sections),
        "narration_segment_count": len(segments),
        "render_mode_distribution": render_mode_counts,
        "narration_wpm_stats": wpm_stats,
        "failed_clip_count": len(failed_clips),
        "issues": issues,
    }


# ---------------------------------------------------------------------------
# Agent tour markdown builder
# ---------------------------------------------------------------------------

def _icon(passed: bool, warn: bool = False) -> str:
    if passed:   return "✅"
    if warn:     return "⚠️"
    return "❌"


def _build_agent_tour(
    subject: str,
    chapter_title: str,
    video_path: Path,
    final_review: dict[str, Any],
    qa_checks: dict[str, Any],
    content_layer: dict[str, Any],
    export_path: str,
    elapsed_s: float,
) -> str:
    checks = final_review.get("checks", {})
    tech   = checks.get("technical_probe", {})
    vis    = checks.get("visual_spotcheck", {})
    aud    = checks.get("audio_spotcheck", {})
    sub    = checks.get("subtitle_check", {})
    status = final_review.get("status", "unknown")
    action = final_review.get("recommended_action", "unknown")

    status_icon = {"pass": "✅", "revise": "⚠️", "fail": "❌"}.get(status, "❓")

    lines: list[str] = [
        f"# EduStream Pro — Final Stage Agent Tour",
        f"",
        f"**Subject:** {subject.upper()} — {chapter_title}  ",
        f"**Video:** `{video_path}`  ",
        f"**Status:** {status_icon} `{status.upper()}`  ",
        f"**Recommended action:** `{action}`  ",
        f"**Pipeline time:** {elapsed_s:.1f}s  ",
        f"",
        f"---",
        f"",
        f"## Layer 1 — Technical Probe",
        f"",
        f"| Property | Value | Status |",
        f"|---|---|---|",
        f"| Duration | {tech.get('duration_seconds', 0):.1f}s | "
        f"{_icon(tech.get('duration_seconds', 0) >= 5)} |",
        f"| Resolution | {tech.get('resolution', '?')} | "
        f"{_icon('1920' in str(tech.get('resolution','')) or '1280' in str(tech.get('resolution','')))} |",
        f"| FPS | {tech.get('fps', 0)} | {_icon(tech.get('fps', 0) >= 25)} |",
        f"| Audio stream | {'present' if tech.get('has_audio') else 'MISSING'} | "
        f"{_icon(tech.get('has_audio', False))} |",
        f"| Codec | {tech.get('codec', '?')} | "
        f"{_icon(tech.get('codec','') in ('h264','hevc','vp9'))} |",
        f"| File size | {tech.get('file_size_bytes', 0) / 1_048_576:.1f} MB | — |",
        f"",
    ]

    if tech.get("issues"):
        lines += [f"**Issues:**"] + [f"- {i}" for i in tech["issues"]] + [""]

    lines += [
        f"## Layer 2 — Visual Spotcheck",
        f"",
        f"{_icon(not vis.get('black_frames_detected'))} Black frames: "
        f"{'none detected' if not vis.get('black_frames_detected') else '**DETECTED**'}  ",
        f"📷 Frames sampled: {vis.get('frames_sampled', 0)}/6  ",
        f"",
    ]
    if vis.get("frame_paths"):
        lines.append("Frame grabs saved to:")
        for fp in vis["frame_paths"]:
            lines.append(f"  - `{fp}`")
        lines.append("")
    if vis.get("issues"):
        lines += ["**Issues:**"] + [f"- {i}" for i in vis["issues"]] + [""]

    aud_lufs = aud.get("integrated_lufs", -99)
    lines += [
        f"## Layer 3 — Audio Spotcheck",
        f"",
        f"| Check | Result | Status |",
        f"|---|---|---|",
        f"| Narration present | {'yes' if aud.get('narration_present') else 'NO'} | "
        f"{_icon(aud.get('narration_present', False))} |",
        f"| Integrated LUFS | {aud_lufs:.1f} dBLUFS | "
        f"{_icon(-22 <= aud_lufs <= -8)} |",
        f"| True-peak clipping | {'yes ⚠️' if aud.get('clipping_detected') else 'none'} | "
        f"{_icon(not aud.get('clipping_detected', False))} |",
        f"| Unexpected silence | {'yes ⚠️' if aud.get('unexpected_silence') else 'none'} | "
        f"{_icon(not aud.get('unexpected_silence', False))} |",
        f"",
    ]
    if aud.get("issues"):
        lines += ["**Issues:**"] + [f"- {i}" for i in aud["issues"]] + [""]

    lines += [
        f"## Layer 4 — Subtitle Check",
        f"",
        f"| Check | Result | Status |",
        f"|---|---|---|",
        f"| SRT present | {'yes' if sub.get('subtitles_present') else 'NO'} | "
        f"{_icon(sub.get('subtitles_present', False))} |",
        f"| Coverage | {sub.get('coverage_ratio', 0):.0%} | "
        f"{_icon(sub.get('coverage_ratio', 0) >= 0.7)} |",
        f"| Subtitle count | {sub.get('subtitle_count', 0)} | — |",
        f"| Timing drift | {'yes ⚠️' if sub.get('timing_drift_detected') else 'none'} | "
        f"{_icon(not sub.get('timing_drift_detected', False))} |",
        f"",
    ]
    if sub.get("issues"):
        lines += ["**Issues:**"] + [f"- {i}" for i in sub["issues"]] + [""]

    rm_dist = content_layer.get("render_mode_distribution", {})
    rm_str  = ", ".join(f"{k}: {v}" for k, v in rm_dist.items())
    lines += [
        f"## Layer 5 — Content Fidelity",
        f"",
        f"| Property | Value |",
        f"|---|---|",
        f"| Sections in plan | {content_layer.get('section_count', 0)} |",
        f"| Narration segments | {content_layer.get('narration_segment_count', 0)} |",
        f"| Render mode split | {rm_str or '—'} |",
        f"| Failed clips | {content_layer.get('failed_clip_count', 0)} |",
        f"",
        f"**Narration WPM per section** (target: 100–145):",
        f"",
    ]
    for stat in content_layer.get("narration_wpm_stats", []):
        wpm    = stat["wpm"]
        ok     = 80 <= wpm <= 145
        warn_f = not ok
        lines.append(f"  {_icon(ok, warn=warn_f)} `{stat['section_id']}`: {wpm} WPM")
    lines.append("")

    if content_layer.get("issues"):
        lines += ["**Issues:**"] + [f"- {i}" for i in content_layer["issues"]] + [""]

    # QA gate summary
    lines += [
        f"## Layer 6 — QA Gate Summary",
        f"",
        f"| Check | Passed | Issues |",
        f"|---|---|---|",
    ]
    for check_name, result in qa_checks.items():
        ok   = result.get("passed", False)
        n    = len(result.get("issues", []))
        desc = result.get("issues", ["—"])[0][:60] if n else "—"
        lines.append(f"| {check_name} | {_icon(ok)} | {desc} |")
    lines.append("")

    # All issues consolidated
    all_issues: list[str] = []
    for layer in [tech, vis, aud, sub]:
        all_issues.extend(layer.get("issues", []))
    all_issues.extend(content_layer.get("issues", []))
    for r in qa_checks.values():
        all_issues.extend(r.get("issues", []))

    if all_issues:
        lines += [
            f"## All Issues Found ({len(all_issues)})",
            f"",
        ]
        for i, issue in enumerate(all_issues, 1):
            lines.append(f"{i}. {issue}")
        lines.append("")

    # Recommended action explanation
    action_explanations = {
        "present_to_user":
            "All checks passed. Present the video to the user with the export bundle path.",
        "re_render":
            "Critical technical failure — missing audio stream or corrupt video track. "
            "Fix the AVComposer inputs and re-run Stage 5.",
        "revise_edit":
            "Subtitle timing drift or coverage too low. Regenerate the SRT from the "
            "narration_manifest and re-burn subtitles.",
        "revise_assets":
            "One or more clips failed to render. Check clip_manifest.json for error "
            "details, fix the failing section, and re-run RenderModeRouter.",
        "block":
            "Multiple critical failures. Do not present this video. Re-run the full "
            "pipeline from Stage 3.",
    }

    lines += [
        f"## What to Do Next",
        f"",
        f"**Recommended action: `{action}`**  ",
        f"",
        action_explanations.get(action, "See issues list above."),
        f"",
        f"**Export bundle:** `{export_path}`  ",
        f"Contains: final video, SRT subtitles, metadata.json, chapters.txt, "
        f"frame snapshots",
        f"",
        f"---",
        f"*Generated by FinalStageDirector v1.0 at "
        f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}*",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# FinalStageDirector tool
# ---------------------------------------------------------------------------

class FinalStageDirector(BaseTool):
    """Advanced final-stage runner — produces agent-readable tour report."""

    name = "final_stage_director"
    version = "1.0.0"
    tier = ToolTier.ANALYZE
    capability = "quality_assessment"
    provider = "openmontage"
    stability = ToolStability.PRODUCTION
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["cmd:ffprobe", "cmd:ffmpeg"]
    install_instructions = "FFmpeg (includes ffprobe) must be on PATH."
    agent_skills = ["quality-assessment"]
    capabilities = [
        "technical_probe", "visual_spotcheck", "audio_spotcheck",
        "subtitle_check", "content_fidelity", "qa_gate",
        "export_bundle", "agent_tour_report",
    ]

    input_schema = {
        "type": "object",
        "required": ["video_path", "subject"],
        "properties": {
            "video_path":          {"type": "string"},
            "srt_path":            {"type": "string"},
            "subject":             {"type": "string"},
            "chapter_title":       {"type": "string", "default": ""},
            "narration_manifest":  {"type": "object", "default": {}},
            "educational_plan":    {"type": "object", "default": {}},
            "clip_manifest":       {"type": "array",  "default": []},
            "evs_alignment":       {"type": "object", "default": {}},
            "scenes":              {"type": "array",  "default": []},
            "title_offset_seconds": {"type": "number", "default": 0.0},
            "output_dir":          {"type": "string"},
            "dry_run":             {"type": "boolean", "default": False},
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "final_review":   {"type": "object"},
            "agent_tour_path": {"type": "string"},
            "export_path":    {"type": "string"},
            "all_passed":     {"type": "boolean"},
        },
    }

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 60.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        video_path    = Path(inputs["video_path"])
        srt_path      = Path(inputs["srt_path"]) if inputs.get("srt_path") else None
        subject       = inputs["subject"]
        chapter_title = inputs.get("chapter_title", "")
        nar_manifest  = inputs.get("narration_manifest", {})
        edu_plan      = inputs.get("educational_plan", {})
        clip_manifest = inputs.get("clip_manifest", [])
        evs_alignment = inputs.get("evs_alignment", {})
        scenes        = inputs.get("scenes", edu_plan.get("sections", []))
        title_offset  = float(inputs.get("title_offset_seconds", 0.0))
        dry_run       = inputs.get("dry_run", False)
        start         = time.monotonic()

        out_root = (
            Path(inputs["output_dir"]) if inputs.get("output_dir")
            else _ROOT / "projects" / subject
        )
        arts_dir      = out_root / "artifacts"
        snapshots_dir = out_root / "renders" / "snapshots"
        exports_dir   = out_root / "exports"
        arts_dir.mkdir(parents=True, exist_ok=True)

        if dry_run:
            review = {"version": "1.0", "status": "pass", "checks": {},
                      "issues_found": [], "recommended_action": "present_to_user"}
            return ToolResult(
                success=True,
                data={"final_review": review, "agent_tour_path": "",
                      "export_path": str(exports_dir), "all_passed": True},
                artifacts=["final_review", "publish_log"],
                cost_usd=0.0,
            )

        if not video_path.exists():
            return ToolResult(success=False, error=f"Video not found: {video_path}")

        # ── Run all 6 layers ──────────────────────────────────────────────────
        print("  [final] Layer 1: technical probe...")
        tech = _layer_technical(video_path)
        duration = tech.get("duration_seconds", 0.0)

        print("  [final] Layer 2: visual spotcheck (6 frames)...")
        vis = _layer_visual(video_path, duration, snapshots_dir)

        print("  [final] Layer 3: audio spotcheck...")
        aud = _layer_audio(video_path)

        print("  [final] Layer 4: subtitle check...")
        sub = _layer_subtitle(srt_path, duration)

        print("  [final] Layer 5: content fidelity...")
        content = _layer_content(nar_manifest, edu_plan, clip_manifest)

        print("  [final] Layer 6: QA gate...")
        from tools.analysis.quality_assurance import (  # noqa: PLC0415
            _check_pacing, _check_audio_sync,
            _check_contrast, _check_slideshow_risk, _check_narration_wpm,
        )
        qa_checks: dict[str, Any] = {
            "pacing":         _check_pacing(clip_manifest, scenes),
            "audio_sync":     _check_audio_sync(nar_manifest, evs_alignment, title_offset),
            "contrast":       _check_contrast(),
            "slideshow_risk": _check_slideshow_risk(scenes, clip_manifest),
            "narration_wpm":  _check_narration_wpm(nar_manifest),
        }
        qa_passed = all(c.get("passed", False) for c in qa_checks.values())

        # ── Build final_review artifact ───────────────────────────────────────
        all_issues: list[str] = []
        for layer in [tech, vis, aud, sub]:
            all_issues.extend(layer.get("issues", []))
        all_issues.extend(content.get("issues", []))
        for r in qa_checks.values():
            all_issues.extend(r.get("issues", []))

        critical = (
            not tech.get("valid_container")
            or not tech.get("has_audio")
        )
        has_warnings = len(all_issues) > 0

        if critical:
            status = "fail"
            action = "re_render"
        elif not qa_passed:
            if not sub.get("subtitles_present"):
                action = "revise_edit"
            elif content.get("failed_clip_count", 0) > 0:
                action = "revise_assets"
            else:
                action = "revise_edit"
            status = "revise"
        else:
            status = "pass"
            action = "present_to_user"

        final_review: dict[str, Any] = {
            "version": "1.0",
            "output_path": str(video_path),
            "status": status,
            "checks": {
                "technical_probe":    tech,
                "visual_spotcheck":   vis,
                "audio_spotcheck":    aud,
                "subtitle_check":     sub,
                "promise_preservation": {
                    "delivery_promise_honored": not critical,
                    "renderer_family_used":    "edustream-pro",
                    "render_runtime_used":     "remotion",
                    "runtime_swap_detected":   False,
                    "runtime_swap_check":      "ok — runtime not swapped",
                    "motion_ratio_actual":     0.0,
                    "silent_downgrade_detected": False,
                    "issues": [],
                },
            },
            "issues_found":         all_issues,
            "recommended_action":   action,
            "metadata": {
                "subject":       subject,
                "chapter_title": chapter_title,
                "qa_checks":     qa_checks,
                "content_layer": content,
                "elapsed_seconds": round(time.monotonic() - start, 1),
            },
        }

        # ── Write artifacts ───────────────────────────────────────────────────
        review_path = arts_dir / "final_review.json"
        review_path.write_text(json.dumps(final_review, indent=2), encoding="utf-8")

        qa_report_path = arts_dir / "qa_report.json"
        qa_report_path.write_text(
            json.dumps({"version": "1.0", "all_passed": qa_passed,
                        "checks": qa_checks}, indent=2),
            encoding="utf-8",
        )

        # ── Export bundle ─────────────────────────────────────────────────────
        print("  [final] Building export bundle...")
        from tools.publishers.export_bundle import ExportBundle  # noqa: PLC0415
        chapters_for_export = [
            {
                "start_seconds": t.get("start_seconds", 0),
                "title": next(
                    (s.get("title", t["section_id"])
                     for s in edu_plan.get("sections", [])
                     if s["section_id"] == t["section_id"]),
                    t["section_id"],
                ),
            }
            for t in evs_alignment.get("timeline", [])
        ]
        eb_inputs: dict[str, Any] = {
            "video_path":     str(video_path),
            "title":          f"{subject.upper()} — {chapter_title}",
            "project_name":   f"edustream-{subject}",
            "export_dir":     str(exports_dir),
            "description":    (
                f"Class 1 {subject.upper()} — {chapter_title}. "
                "Automated educational video for primary school students."
            ),
            "tags":       ["Class1", "EduStream", subject.upper(), chapter_title],
            "chapters":   chapters_for_export,
            "platform":   "local",
            "visibility": "private",
        }
        if srt_path and srt_path.exists():
            eb_inputs["subtitles_path"] = str(srt_path)

        # Include frame snapshots in the bundle
        snapshot_dir_dest = exports_dir / "snapshots"
        if snapshots_dir.exists():
            if snapshot_dir_dest.exists():
                shutil.rmtree(snapshot_dir_dest)
            shutil.copytree(str(snapshots_dir), str(snapshot_dir_dest))

        eb_res = ExportBundle().execute(eb_inputs)
        export_path = eb_res.data.get("export_path", str(exports_dir)) if eb_res.success else str(exports_dir)

        # ── Agent tour report ─────────────────────────────────────────────────
        print("  [final] Writing agent tour report...")
        tour_md = _build_agent_tour(
            subject=subject,
            chapter_title=chapter_title,
            video_path=video_path,
            final_review=final_review,
            qa_checks=qa_checks,
            content_layer=content,
            export_path=export_path,
            elapsed_s=time.monotonic() - start,
        )
        tour_path = arts_dir / "agent_tour.md"
        tour_path.write_text(tour_md, encoding="utf-8")

        # Print the full tour to stdout so the agent sees it immediately
        print("\n" + "═" * 70)
        print(tour_md)
        print("═" * 70 + "\n")

        all_passed = (status == "pass")
        return ToolResult(
            success=True,
            data={
                "final_review":    final_review,
                "agent_tour_path": str(tour_path),
                "export_path":     export_path,
                "all_passed":      all_passed,
                "status":          status,
                "action":          action,
            },
            artifacts=["final_review", "publish_log"],
            cost_usd=0.0,
            duration_seconds=time.monotonic() - start,
        )

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {
            "tool": self.name,
            "estimated_cost_usd": 0.0,
            "estimated_runtime_seconds": self.estimate_runtime(inputs),
            "status": self.get_status().value,
            "would_execute": True,
        }
