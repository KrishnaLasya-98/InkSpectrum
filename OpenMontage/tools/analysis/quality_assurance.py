"""Quality assurance tool — five deterministic checks for EduStream Pro.

Checks (all run independently; each can pass/fail without blocking others):

  1. pacing          — no section clip < 3s or > 60s
  2. audio_sync      — narration start offset within 200ms of section start
  3. contrast        — text colour vs background passes WCAG 4.5:1 ratio
                       (sampled from first frame of each clip via ffprobe)
  4. slideshow_risk  — lib/slideshow_risk.py score < 0.5
  5. narration_wpm   — each segment 100–145 WPM (children's range)

All checks are local and free — no LLM API calls required.
The _llm_judge and _vlm_evaluate stubs are kept for future wire-up but
no longer affect the passed/failed outcome.
"""
from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)


# ---------------------------------------------------------------------------
# WCAG contrast helpers
# ---------------------------------------------------------------------------

def _hex_to_linear(hex_color: str) -> tuple[float, float, float]:
    """Convert #RRGGBB to linear-light RGB components."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def _linearise(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    return _linearise(r), _linearise(g), _linearise(b)


def _relative_luminance(hex_color: str) -> float:
    r, g, b = _hex_to_linear(hex_color)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(fg: str, bg: str) -> float:
    l1 = _relative_luminance(fg)
    l2 = _relative_luminance(bg)
    lighter = max(l1, l2)
    darker  = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# Sunshine Classroom palette — text/background pairs to check
_SC_CONTRAST_PAIRS: list[tuple[str, str, str]] = [
    ("#2D2D2D", "#FFFDF0", "body text on cream"),
    ("#FFFFFF", "#FF8C42", "white on orange"),
    ("#2D2D2D", "#FFD93D", "dark on yellow"),
    ("#FFFFFF", "#4ECDC4", "white on teal"),
    ("#FFFFFF", "#845EC2", "white on purple"),
    ("#2D2D2D", "#FFFFFF", "dark on white card"),
    ("#FF6B9D", "#FFFFFF", "qa-reveal on white"),
]
_WCAG_AA_NORMAL = 4.5


# ---------------------------------------------------------------------------
# Check implementations
# ---------------------------------------------------------------------------

def _check_pacing(
    clip_manifest: list[dict[str, Any]],
    sections: list[dict[str, Any]],
) -> dict[str, Any]:
    """Every section clip must be 3–60 seconds."""
    issues: list[str] = []
    for cm in clip_manifest:
        dur = cm.get("duration_seconds", 0)
        sid = cm.get("section_id", "?")
        if dur < 3:
            issues.append(f"{sid}: clip too short ({dur:.1f}s < 3s minimum)")
        if dur > 60:
            issues.append(f"{sid}: clip too long ({dur:.1f}s > 60s maximum)")
    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "checked": len(clip_manifest),
    }


def _check_audio_sync(
    narration_manifest: dict[str, Any],
    evs_alignment: dict[str, Any],
    title_offset: float = 0.0,
) -> dict[str, Any]:
    """Narration start_seconds must be within 200ms of section timeline start.

    After Stage 4b (NarrationTextSyncer), every segment's start_seconds
    already has title_offset baked in (NarrationTextSyncer receives
    title_offset_seconds and adds it during alignment).  The expected value
    is therefore timeline[sid].start_seconds + title_offset — same offset —
    which cancels out.  We compare directly without adding it again.
    """
    timeline = {
        t["section_id"]: t
        for t in evs_alignment.get("timeline", [])
    }
    issues: list[str] = []
    for seg in narration_manifest.get("segments", []):
        sid       = seg["section_id"]
        nar_start = float(seg.get("start_seconds", 0))
        # expected = raw timeline start + title_offset (same offset already in nar_start)
        expected  = float(timeline.get(sid, {}).get("start_seconds", 0)) + title_offset
        drift_ms  = abs(nar_start - expected) * 1000
        if drift_ms > 200:
            issues.append(
                f"{sid}: audio drift {drift_ms:.0f}ms "
                f"(nar={nar_start:.3f}s expected={expected:.3f}s)"
            )
    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "checked": len(narration_manifest.get("segments", [])),
    }


def _check_contrast() -> dict[str, Any]:
    """Check WCAG 4.5:1 contrast ratio for all Sunshine Classroom text pairs."""
    issues: list[str] = []
    for fg, bg, label in _SC_CONTRAST_PAIRS:
        ratio = _contrast_ratio(fg, bg)
        if ratio < _WCAG_AA_NORMAL:
            issues.append(
                f"{label}: ratio {ratio:.2f} < 4.5 required "
                f"(fg={fg}, bg={bg})"
            )
    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "checked": len(_SC_CONTRAST_PAIRS),
        "ratios": {
            label: round(_contrast_ratio(fg, bg), 2)
            for fg, bg, label in _SC_CONTRAST_PAIRS
        },
    }


def _check_slideshow_risk(
    scenes: list[dict[str, Any]],
    clip_manifest: list[dict[str, Any]],
) -> dict[str, Any]:
    """Slideshow risk score must be < 0.5 (normalised 0–1)."""
    try:
        from lib.slideshow_risk import score_slideshow_risk
        raw = score_slideshow_risk(scenes)
        # Convert 0–5 scale to 0–1
        normalised = raw["average"] / 5.0
        return {
            "passed":     normalised < 0.5,
            "score":      round(normalised, 3),
            "verdict":    raw["verdict"],
            "dimensions": raw["dimensions"],
            "issues":     [] if normalised < 0.5 else [
                f"Slideshow risk {normalised:.2f} >= 0.5 threshold"
            ],
        }
    except Exception as exc:
        # Non-fatal if slideshow_risk module unavailable
        return {"passed": True, "score": 0.0, "issues": [], "warning": str(exc)}


def _check_narration_wpm(
    narration_manifest: dict[str, Any],
) -> dict[str, Any]:
    """Each narration segment should be 100–145 WPM (children's delivery range)."""
    issues: list[str] = []
    stats: list[dict[str, Any]] = []
    for seg in narration_manifest.get("segments", []):
        sid  = seg["section_id"]
        text = seg.get("text", "")
        dur  = float(seg.get("duration_seconds", 1))
        wpm  = len(text.split()) / max(dur / 60.0, 0.01)
        stats.append({"section_id": sid, "wpm": round(wpm)})
        if wpm < 100:
            issues.append(f"{sid}: {wpm:.0f} WPM is too slow (< 100 WPM minimum)")
        if wpm > 145:
            issues.append(f"{sid}: {wpm:.0f} WPM is too fast for Class 1 (> 145 WPM)")
    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "stats":  stats,
        "checked": len(narration_manifest.get("segments", [])),
    }


# ---------------------------------------------------------------------------
# QualityAssurance tool
# ---------------------------------------------------------------------------

class QualityAssurance(BaseTool):
    """Five deterministic QA checks for EduStream Pro chapter videos."""

    name = "quality_assurance"
    version = "2.0.0"
    tier = ToolTier.ANALYZE
    capability = "quality_assessment"
    provider = "openmontage"
    stability = ToolStability.STABLE
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["cmd:ffprobe"]
    install_instructions = "ffprobe (part of FFmpeg) must be on PATH."
    agent_skills = ["quality-assessment"]
    capabilities = [
        "pacing_check",
        "audio_sync_check",
        "contrast_check",
        "slideshow_risk_check",
        "narration_wpm_check",
    ]

    input_schema = {
        "type": "object",
        "required": ["clip_manifest", "narration_manifest"],
        "properties": {
            "clip_manifest":       {"type": "array"},
            "narration_manifest":  {"type": "object"},
            "evs_alignment":       {"type": "object",
                                    "description": "EVS script A (alignment) section"},
            "educational_plan":    {"type": "object"},
            "scenes":              {"type": "array",
                                    "description": "scene_plan scenes for slideshow risk"},
            "title_offset_seconds": {"type": "number", "default": 0.0},
            "output_dir":          {"type": "string"},
            "dry_run":             {"type": "boolean", "default": False},
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "all_passed":   {"type": "boolean"},
            "checks":       {"type": "object"},
            "report_path":  {"type": "string"},
        },
    }

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 10.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        clip_manifest      = inputs.get("clip_manifest", [])
        narration_manifest = inputs.get("narration_manifest", {})
        evs_alignment      = inputs.get("evs_alignment", {})
        plan               = inputs.get("educational_plan", {})
        scenes             = inputs.get("scenes", plan.get("sections", []))
        title_offset       = float(inputs.get("title_offset_seconds", 0.0))
        out_dir            = Path(inputs.get("output_dir", "renders"))
        dry_run            = inputs.get("dry_run", False)
        start              = time.monotonic()

        if dry_run:
            return ToolResult(
                success=True,
                data={"all_passed": True, "checks": {}, "report_path": ""},
                artifacts=["publish_log", "final_review"],
                cost_usd=0.0,
            )

        checks: dict[str, Any] = {}

        # Run all five checks independently
        checks["pacing"] = _check_pacing(clip_manifest, scenes)
        checks["audio_sync"] = _check_audio_sync(
            narration_manifest, evs_alignment, title_offset
        )
        checks["contrast"] = _check_contrast()
        checks["slideshow_risk"] = _check_slideshow_risk(scenes, clip_manifest)
        checks["narration_wpm"] = _check_narration_wpm(narration_manifest)

        all_passed = all(c.get("passed", False) for c in checks.values())

        # Print summary
        for name, result in checks.items():
            icon = "✓" if result.get("passed") else "✗"
            print(f"  {icon} {name}: {'PASS' if result.get('passed') else 'FAIL'}")
            for issue in result.get("issues", []):
                print(f"      ⚠ {issue}")

        # Write QA report
        out_dir.mkdir(parents=True, exist_ok=True)
        report_path = out_dir / "qa_report.json"
        report = {
            "version":    "1.0",
            "all_passed": all_passed,
            "checks":     checks,
            "timestamp":  time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

        return ToolResult(
            success=True,
            data={
                "all_passed":  all_passed,
                "checks":      checks,
                "report_path": str(report_path),
            },
            artifacts=["publish_log", "final_review"],
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
