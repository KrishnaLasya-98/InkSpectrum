"""Build one authoritative audio/visual/caption timeline.

The planner uses measured narration durations as the timing authority and
records how each visual clip must adapt.  It prevents duplicated title offsets
and exposes drift before composition rather than after rendering.
"""
from __future__ import annotations

import time
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


def build_sync_plan(
    narration_manifest: dict[str, Any],
    clip_manifest: list[dict[str, Any]],
    *,
    title_offset_seconds: float = 0.0,
    sync_tolerance_seconds: float = 0.1,
) -> dict[str, Any]:
    clips = {str(item.get("section_id")): item for item in clip_manifest}
    cursor = max(0.0, float(title_offset_seconds))
    timeline: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []

    for segment in narration_manifest.get("segments", []):
        section_id = str(segment.get("section_id") or "")
        audio_duration = max(0.0, float(segment.get("duration_seconds") or 0.0))
        clip = clips.get(section_id)
        clip_duration = max(0.0, float((clip or {}).get("duration_seconds") or 0.0))
        start = cursor
        end = start + audio_duration
        drift = clip_duration - audio_duration if clip else None

        if not clip:
            visual_policy = "missing"
            issues.append({"section_id": section_id, "severity": "critical", "code": "missing_clip"})
        elif abs(drift or 0.0) <= sync_tolerance_seconds:
            visual_policy = "as_is"
        elif clip_duration < audio_duration:
            visual_policy = "loop_or_hold_last_frame"
        else:
            visual_policy = "trim_to_audio"

        timeline.append({
            "section_id": section_id,
            "start_seconds": round(start, 3),
            "end_seconds": round(end, 3),
            "audio_duration_seconds": round(audio_duration, 3),
            "clip_duration_seconds": round(clip_duration, 3) if clip else None,
            "drift_seconds": round(drift, 3) if drift is not None else None,
            "visual_duration_policy": visual_policy,
            "subtitle_offset_seconds": round(start, 3),
            "timeline_source": "measured_narration_duration",
        })
        cursor = end

    return {
        "version": "1.0",
        "title_offset_seconds": round(max(0.0, float(title_offset_seconds)), 3),
        "sync_tolerance_seconds": float(sync_tolerance_seconds),
        "total_duration_seconds": round(cursor, 3),
        "timeline": timeline,
        "issues": issues,
        "status": "pass" if not issues else "blocked",
    }


class MultimediaSyncPlanner(BaseTool):
    name = "multimedia_sync_planner"
    version = "1.0.0"
    tier = ToolTier.ANALYZE
    capability = "multimedia_sync"
    provider = "openmontage"
    stability = ToolStability.PRODUCTION
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL
    dependencies: list[str] = []
    install_instructions = "No setup required."
    agent_skills = ["speech-to-text", "ffmpeg"]
    capabilities = ["authoritative_timeline", "drift_detection", "caption_offsets"]

    input_schema = {
        "type": "object",
        "required": ["narration_manifest", "clip_manifest"],
        "properties": {
            "narration_manifest": {"type": "object"},
            "clip_manifest": {"type": "array", "items": {"type": "object"}},
            "title_offset_seconds": {"type": "number", "minimum": 0, "default": 0},
            "sync_tolerance_seconds": {"type": "number", "minimum": 0, "default": 0.1},
        },
    }
    output_schema = {"type": "object", "properties": {"sync_plan": {"type": "object"}}}

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 0.01 * len(inputs.get("clip_manifest", []))

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.monotonic()
        plan = build_sync_plan(
            inputs["narration_manifest"],
            inputs["clip_manifest"],
            title_offset_seconds=float(inputs.get("title_offset_seconds", 0.0)),
            sync_tolerance_seconds=float(inputs.get("sync_tolerance_seconds", 0.1)),
        )
        return ToolResult(
            success=plan["status"] == "pass",
            error="; ".join(i["code"] + ":" + i["section_id"] for i in plan["issues"]),
            data={"sync_plan": plan},
            artifacts=[],
            cost_usd=0.0,
            duration_seconds=time.monotonic() - started,
        )

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {"tool": self.name, "would_execute": True, "estimated_cost_usd": 0.0}
