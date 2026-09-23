"""Deterministic stock-vs-generation planning for educational scenes.

This tool does not download or generate media.  It produces an auditable
strategy that an agent can review, record in the decision log, and then hand
to the normal stock or video selectors.  Keeping this policy separate avoids
silently changing providers or fabricating factual footage.
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


FACTUAL_TYPES = {"factual", "real_world", "historical", "person", "product"}
ABSTRACT_TYPES = {"abstract", "mathematics", "process", "diagram"}


def choose_asset_strategy(scene: dict[str, Any], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return one explainable media strategy for a scene."""
    policy = policy or {}
    scene_id = str(scene.get("scene_id") or "unknown")
    content_type = str(scene.get("content_type") or "factual").lower()
    motion = str(scene.get("motion_requirement") or "generic").lower()
    source_available = bool(scene.get("source_asset_available"))
    stock_matches = list(scene.get("stock_matches") or [])
    generation_available = bool(scene.get("generation_available", True))
    continuity_required = bool(scene.get("identity_continuity_required"))
    allow_generation = bool(policy.get("allow_generation", True))
    prefer_stock = bool(policy.get("prefer_stock_for_factual", True))
    max_generation_cost = float(policy.get("max_generation_cost_usd", 1.0))
    estimated_generation_cost = float(scene.get("estimated_generation_cost_usd", 0.0))

    considered = ["existing_asset", "stock_video", "generated_video", "diagram_animation"]
    approval_required = False
    confidence = 0.9

    if source_available:
        selected = "existing_asset"
        reason = "A reviewed project asset already matches the scene; reuse preserves fidelity and provenance."
    elif content_type in ABSTRACT_TYPES:
        selected = "diagram_animation"
        reason = "The scene explains an abstract process; authored graphics communicate it more accurately than literal footage."
    elif content_type in FACTUAL_TYPES and stock_matches and prefer_stock:
        selected = "stock_video"
        reason = "A licensed stock match exists for factual content, avoiding synthetic representation of a real subject."
    elif continuity_required and generation_available and allow_generation:
        selected = "generated_video"
        reason = "The scene requires identity/style continuity that generic stock footage cannot reliably provide."
        approval_required = estimated_generation_cost > 0
    elif stock_matches:
        selected = "stock_video"
        reason = "A usable licensed stock match is available and is cheaper and more deterministic than generation."
    elif generation_available and allow_generation and estimated_generation_cost <= max_generation_cost:
        selected = "generated_video"
        reason = "No reviewed source or stock match exists, and generation is allowed within the per-scene budget."
        approval_required = estimated_generation_cost > 0
        confidence = 0.75
    elif motion in {"none", "minimal"}:
        selected = "diagram_animation"
        reason = "Motion is not essential and no suitable footage source is available; use deterministic authored graphics."
        confidence = 0.8
    else:
        selected = "blocked"
        reason = "The scene needs motion, but no approved source, stock match, or permitted generation route is available."
        confidence = 1.0

    return {
        "scene_id": scene_id,
        "selected_strategy": selected,
        "options_considered": considered,
        "reason": reason,
        "confidence": confidence,
        "approval_required": approval_required,
        "stock_match_count": len(stock_matches),
        "requires_provenance": selected in {"existing_asset", "stock_video", "generated_video"},
        "execution_tool": {
            "existing_asset": "asset_manifest",
            "stock_video": "pexels_video_or_pixabay_video",
            "generated_video": "video_selector",
            "diagram_animation": "diagram_gen_or_composition_runtime",
            "blocked": None,
        }[selected],
    }


class HybridAssetRouter(BaseTool):
    """Plan the media source for each scene without performing generation."""

    name = "hybrid_asset_router"
    version = "1.0.0"
    tier = ToolTier.CORE
    capability = "asset_strategy"
    provider = "openmontage"
    stability = ToolStability.PRODUCTION
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL
    dependencies: list[str] = []
    install_instructions = "No setup required."
    agent_skills = ["media-use", "ai-video-gen"]
    capabilities = ["stock_generation_routing", "provenance_planning", "budget_gate"]

    input_schema = {
        "type": "object",
        "required": ["scenes"],
        "properties": {
            "scenes": {"type": "array", "items": {"type": "object"}},
            "policy": {"type": "object"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "decisions": {"type": "array"},
            "blocked_scene_ids": {"type": "array"},
            "approval_scene_ids": {"type": "array"},
        },
    }

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 0.01 * len(inputs.get("scenes", []))

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.monotonic()
        decisions = [
            choose_asset_strategy(scene, inputs.get("policy"))
            for scene in inputs.get("scenes", [])
        ]
        blocked = [d["scene_id"] for d in decisions if d["selected_strategy"] == "blocked"]
        approvals = [d["scene_id"] for d in decisions if d["approval_required"]]
        return ToolResult(
            success=not blocked,
            error=f"No viable media strategy for scenes: {blocked}" if blocked else "",
            data={
                "decisions": decisions,
                "blocked_scene_ids": blocked,
                "approval_scene_ids": approvals,
            },
            artifacts=[],
            cost_usd=0.0,
            duration_seconds=time.monotonic() - started,
        )

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {"tool": self.name, "would_execute": True, "estimated_cost_usd": 0.0}
