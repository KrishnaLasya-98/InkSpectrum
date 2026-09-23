"""Build subject-aware stock-media research plans for educational scenes.

This tool plans searches; it does not call external providers. The agent passes
the resulting queries to ``direct_clip_search`` or the Pexels/Pixabay tools,
reviews thumbnails, and records selected candidates in the asset manifest.
"""
from __future__ import annotations

import re
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


SUBJECT_ALIASES = {
    "mathematics": {"math", "maths", "mathematics", "arithmetic", "algebra", "geometry"},
    "english": {"english", "language arts", "literature", "reading", "grammar", "phonics"},
    "science": {"science", "evs", "environmental studies", "biology", "physics", "chemistry"},
    "social_studies": {"social", "social studies", "history", "geography", "civics", "economics"},
    "computing": {"computer", "computing", "coding", "programming", "ict"},
}


def classify_subject(subject: str) -> str:
    normalized = re.sub(r"[^a-z0-9 ]+", " ", subject.lower()).strip()
    for family, aliases in SUBJECT_ALIASES.items():
        if normalized in aliases or any(alias in normalized for alias in aliases):
            return family
    return "general"


def _clean_query(value: str) -> str:
    words = re.findall(r"[A-Za-z0-9'-]+", value)
    return " ".join(words[:12]).strip()


def _scene_query(scene: dict[str, Any]) -> str:
    for key in ("search_query", "visual_description", "title", "heading", "narration"):
        value = _clean_query(str(scene.get(key) or ""))
        if value:
            return value
    return _clean_query(str(scene.get("scene_id") or "educational concept"))


def plan_scene_research(subject_family: str, scene: dict[str, Any]) -> dict[str, Any]:
    scene_id = str(scene.get("scene_id") or "unknown")
    content_type = str(scene.get("content_type") or "").lower()
    intent = str(scene.get("learning_intent") or scene.get("scene_type") or "").lower()
    base_query = _scene_query(scene)
    factual = content_type in {"factual", "real_world", "historical", "person", "place", "nature"}
    narrative = content_type in {"story", "narrative", "character"} or "story" in intent

    if subject_family == "mathematics":
        if factual or "real world" in intent:
            treatment = "stock_reference_plus_authored_overlay"
            search_required = True
            sources = ["pexels", "pixabay_video", "unsplash"]
            fallback = "diagram_animation"
            rationale = "Use real objects only as a concrete hook; mathematical meaning stays in authored diagrams and labels."
        else:
            treatment = "diagram_animation"
            search_required = False
            sources = []
            fallback = "composition_graphics"
            rationale = "Exact quantities, symbols, and transformations require deterministic authored graphics."
    elif subject_family == "english":
        if narrative:
            treatment = "illustrated_or_generated_story"
            search_required = bool(scene.get("stock_setting_useful", False))
            sources = ["pexels", "unsplash", "pixabay_video"] if search_required else []
            fallback = "generated_image_or_video_with_character_reference"
            rationale = "Story scenes need character/style continuity; stock is limited to establishing shots or real-world vocabulary."
        else:
            treatment = "typography_and_realia"
            search_required = factual or content_type in {"vocabulary", "object"}
            sources = ["pexels", "pixabay_image", "unsplash"] if search_required else []
            fallback = "composition_graphics"
            rationale = "Grammar and phonics need timed typography; concrete vocabulary may use licensed real-world images."
    elif subject_family == "science":
        treatment = "documentary_stock_with_diagram_overlay"
        search_required = True
        sources = ["nasa", "wikimedia", "pexels", "pixabay_video", "archive_org"]
        fallback = "diagram_animation"
        rationale = "Observable phenomena should use authentic media, with authored diagrams for invisible or abstract processes."
    elif subject_family == "social_studies":
        treatment = "historical_or_geographic_evidence"
        search_required = True
        sources = ["wikimedia", "archive_org", "nara", "pexels", "pixabay_video"]
        fallback = "map_timeline_or_diagram"
        rationale = "Places, people, maps, and historical claims need attributable evidence rather than synthetic documentary footage."
    elif subject_family == "computing":
        treatment = "screen_demo_and_diagram"
        search_required = False
        sources = []
        fallback = "synthetic_screen_recording"
        rationale = "Interface behavior and code are clearest as deterministic screen demonstrations and diagrams."
    else:
        treatment = "stock_if_factual_otherwise_authored"
        search_required = factual
        sources = ["pexels", "pixabay_video", "wikimedia", "unsplash"] if factual else []
        fallback = "diagram_or_generated_media"
        rationale = "Unknown subjects use factuality and motion needs rather than a hardcoded subject name."

    queries = []
    if search_required:
        queries = [base_query]
        context = _clean_query(str(scene.get("context") or scene.get("keywords") or ""))
        if context and context.lower() != base_query.lower():
            queries.append(context)

    return {
        "scene_id": scene_id,
        "subject_family": subject_family,
        "recommended_treatment": treatment,
        "search_required": search_required,
        "queries": queries,
        "preferred_sources": sources,
        "fallback_strategy": fallback,
        "rationale": rationale,
        "selection_status": "pending_review" if search_required else "not_required",
    }


def build_media_research_plan(subject: str, scenes: list[dict[str, Any]]) -> dict[str, Any]:
    family = classify_subject(subject)
    scene_plans = [plan_scene_research(family, scene) for scene in scenes]
    return {
        "version": "1.0",
        "subject": subject,
        "subject_family": family,
        "scenes": scene_plans,
        "search_scene_count": sum(1 for scene in scene_plans if scene["search_required"]),
        "selection_policy": {
            "stock_results_are_candidates_only": True,
            "require_visual_review": True,
            "require_source_and_license_provenance": True,
            "reject_watermarks_and_inaccurate_representations": True,
        },
    }


class EducationalMediaResearchPlanner(BaseTool):
    name = "educational_media_research_planner"
    version = "1.0.0"
    tier = ToolTier.CORE
    capability = "media_research"
    provider = "openmontage"
    stability = ToolStability.PRODUCTION
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL
    dependencies: list[str] = []
    install_instructions = "No setup required; provider credentials are checked by acquisition tools."
    agent_skills = ["media-use"]
    capabilities = ["subject_classification", "stock_query_planning", "source_routing"]

    input_schema = {
        "type": "object",
        "required": ["subject", "scenes"],
        "properties": {
            "subject": {"type": "string", "minLength": 1},
            "scenes": {"type": "array", "items": {"type": "object"}},
        },
    }
    output_schema = {"type": "object", "properties": {"media_research_plan": {"type": "object"}}}

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 0.01 * len(inputs.get("scenes", []))

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.monotonic()
        plan = build_media_research_plan(str(inputs["subject"]), list(inputs.get("scenes", [])))
        return ToolResult(
            success=True,
            data={"media_research_plan": plan},
            artifacts=["media_research_plan"],
            cost_usd=0.0,
            duration_seconds=time.monotonic() - started,
        )

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {"tool": self.name, "would_execute": True, "estimated_cost_usd": 0.0}
