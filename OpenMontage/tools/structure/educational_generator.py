"""Educational content generator — agent-driven, no LLM API calls.

The AI agent (Claude / Kiro / Cursor / Kilo) IS the content generator.
This tool's job is:
  1. Accept either a pre-built educational_plan dict (agent wrote it) OR
     a source_content string (agent will write the plan after reading the
     EduGen 6-step prompt from the skill file)
  2. Validate the plan against the schema
  3. Enforce render_mode on every section
  4. Persist the plan to artifacts/educational_plan.json

There are NO LLM API calls here. The agent reads
  skills/edustream/content-director.md
and follows the 6-step + Step 7 (render_mode) prompt to produce the
educational_plan JSON, then passes it back as an input to this tool.

render_mode values
------------------
  manim        — concept diagrams, equations, number lines, classification trees
  remotion     — Q&A cards, fill-blank, MCQ, glossary, recall
  hyperframes  — chapter title cards and transition bumpers only
  video_gen    — narrative / story scenes requiring animation
"""
from __future__ import annotations

import json
import re
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
# render_mode inference — used when the agent omits the field
# ---------------------------------------------------------------------------

_MANIM_KW = re.compile(
    r"equation|formula|number\s*line|place\s*value|skip\s*count|diagram"
    r"|classif|concept\s*(wheel|tree|map)|worked\s*example|tens|ones",
    re.I,
)
_REMOTION_KW = re.compile(
    r"q&a|question|fill.in|blank|multiple.choice|glossary|recall|assess"
    r"|vocabulary|define|summary",
    re.I,
)
_HF_KW   = re.compile(r"chapter\s*title|title\s*card|bumper|transition|intro\s*card", re.I)
_VID_KW  = re.compile(r"story|narrative|scene|video|illustrat|animation", re.I)

_SUBJECT_RENDER: dict[str, dict[str, str]] = {
    "maths":   {"concept": "manim", "worked_example": "manim"},
    "evs":     {"concept": "manim"},
    "english": {"story_section": "video_gen", "concept": "remotion"},
}


def _infer_render_mode(section: dict[str, Any], subject: str) -> str:
    title = (section.get("title") or "") + " " + (section.get("description") or "")
    btype = section.get("source_block_type", "")
    if _HF_KW.search(title):      return "hyperframes"
    if _REMOTION_KW.search(title): return "remotion"
    if _MANIM_KW.search(title):   return "manim"
    if _VID_KW.search(title):     return "video_gen"
    sub_map = _SUBJECT_RENDER.get(subject, {})
    if btype in sub_map:          return sub_map[btype]
    if subject == "maths":        return "manim"
    if subject == "english":      return "video_gen"
    return "remotion"


# ---------------------------------------------------------------------------
# Plan defaults and enforcement
# ---------------------------------------------------------------------------

def _enforce_plan(plan: dict[str, Any], subject: str) -> dict[str, Any]:
    """Fill defaults and enforce render_mode on every section."""
    valid_rm = {"manim", "remotion", "hyperframes", "video_gen"}
    plan.setdefault("version", "1.0")
    plan.setdefault("subject_classification", "theory")
    plan.setdefault("complexity_level", "elementary")
    plan.setdefault("target_audience", "Class 1, ages 5-7")
    plan.setdefault("total_duration_seconds", 480)
    plan.setdefault("learning_objectives", [])
    plan.setdefault("sections", [])
    plan.setdefault("assessment", {})
    plan.setdefault("metadata", {})
    plan["metadata"]["children_design_system"] = "sunshine-classroom"
    plan["metadata"]["narration_wpm_target"]   = 120
    plan["metadata"]["max_concept_hold_seconds"] = 5
    plan["metadata"]["orchestrator"]           = "agent"

    for section in plan.get("sections", []):
        rm = section.get("render_mode", "")
        if rm not in valid_rm:
            section["render_mode"] = _infer_render_mode(section, subject)

    return plan


# ---------------------------------------------------------------------------
# Dry-run fixture — three subjects
# ---------------------------------------------------------------------------

_DRY_RUN_FIXTURE: dict[str, Any] = {
    "version": "1.0",
    "title": "Animal Life — Chapter 8",
    "subject_classification": "theory",
    "complexity_level": "elementary",
    "target_audience": "Class 1, ages 5-7",
    "total_duration_seconds": 480,
    "learning_objectives": [
        "Identify water and land animals",
        "Name three types of birds",
        "Distinguish domestic from wild animals",
        "Match animals to their homes",
    ],
    "sections": [
        {
            "section_id":        "s00",
            "title":             "Chapter Title Card",
            "description":       "Animated chapter title intro",
            "narration_script":  "Today we learn about Animal Life!",
            "duration_seconds":  3,
            "equations":         [],
            "key_concepts":      [],
            "source_block_type": "intro",
            "visual_elements":   {"diagrams": [], "animations": ["bounce-in title"],
                                  "color_scheme": ["#FF8C42", "#FFD93D"]},
            "render_mode":       "hyperframes",
            "transition_to_next": "fade",
        },
        {
            "section_id":        "s01",
            "title":             "Animals Around Us",
            "description":       "Animals need food, shelter, air, water",
            "narration_script":  (
                "Animals live all around us. Like us, they need food. "
                "They need water. They need air. And they need a safe home. "
                "Can you name an animal you have seen today?"
            ),
            "duration_seconds":  30,
            "equations":         [],
            "key_concepts":      ["animals", "food", "shelter", "air", "water"],
            "source_block_type": "concept",
            "visual_elements":   {"diagrams": ["needs wheel"], "animations": [],
                                  "color_scheme": ["#FF8C42", "#6BCB77"]},
            "render_mode":       "manim",
            "transition_to_next": "slide",
        },
        {
            "section_id":        "s14",
            "title":             "Assessment — Questions",
            "description":       "Short-answer and fill-in-blank questions",
            "narration_script":  "Now let us test what we learned! Are you ready?",
            "duration_seconds":  40,
            "equations":         [],
            "key_concepts":      [],
            "source_block_type": "qa_item",
            "visual_elements":   {"diagrams": [], "animations": ["card flip"],
                                  "color_scheme": ["#FF6B9D", "#FFFDF0"]},
            "render_mode":       "remotion",
            "transition_to_next": "fade",
        },
    ],
    "assessment": {
        "quiz_questions": [
            {"question": "Name any two pet animals.",
             "type": "short_answer",
             "correct_answer": "dog, parrot, rabbit (any two)",
             "explanation": "Pet animals are kept at home."},
            {"question": "Fish live in ___.",
             "type": "fill_blank",
             "correct_answer": "water",
             "explanation": "Fish are aquatic animals."},
            {"question": "Butterfly is a ___.",
             "type": "mcq",
             "choices": ["a) bird", "b) insect", "c) animal"],
             "correct_answer": "b) insect",
             "explanation": "Insects have six legs."},
        ],
        "thought_experiments": ["What would happen if animals had no homes?"],
        "interactive_elements": ["Draw your favourite animal"],
    },
    "metadata": {
        "orchestrator":            "agent",
        "children_design_system":  "sunshine-classroom",
        "narration_wpm_target":    120,
        "max_concept_hold_seconds": 5,
    },
}


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

class EducationalContentGenerator(BaseTool):
    """Validate, enforce, and persist an agent-authored educational_plan.

    The agent produces the JSON plan content by following the EduGen 6-step
    prompt in skills/edustream/content-director.md. This tool validates and
    saves the result — it does not call any LLM API.
    """

    name = "educational_content_generator"
    version = "2.0.0"
    tier = ToolTier.CORE
    capability = "content_generation"
    provider = "openmontage"
    stability = ToolStability.PRODUCTION
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL     # local only — no API calls

    dependencies: list[str] = []   # no external dependencies
    install_instructions = "No setup required."
    agent_skills = ["edu-gen", "pedagogy"]
    capabilities = ["plan_validation", "render_mode_enforcement", "plan_persistence"]

    input_schema = {
        "type": "object",
        "properties": {
            # Option A: agent passes a pre-built plan dict
            "educational_plan": {
                "type": "object",
                "description": "Complete educational_plan JSON authored by the agent.",
            },
            # Option B: minimal fields — tool builds a shell, agent fills sections
            "source_content": {
                "type": "string",
                "description": "Raw source text (used to infer title/subject if plan omitted).",
            },
            "subject_type": {
                "type": "string",
                "enum": ["theory", "mathematics", "mixed"],
                "default": "mixed",
            },
            "complexity_level": {
                "type": "string",
                "enum": ["elementary", "middle_school", "high_school"],
                "default": "elementary",
            },
            "target_audience":        {"type": "string", "default": "Class 1, ages 5-7"},
            "total_duration_seconds": {"type": "number", "default": 480},
            "subject":                {"type": "string", "default": "evs"},
            "output_dir":             {"type": "string"},
            "seed":                   {"type": "integer"},
            "dry_run":                {"type": "boolean", "default": False},
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "educational_plan": {"type": "object"},
            "output_path":      {"type": "string"},
        },
    }

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0   # no API calls

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 1.0   # local validation only

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        dry_run  = inputs.get("dry_run", False)
        subject  = inputs.get("subject", "evs")
        seed     = inputs.get("seed")
        out_dir  = Path(inputs.get("output_dir", "."))
        start    = time.monotonic()

        if dry_run:
            plan = _enforce_plan(dict(_DRY_RUN_FIXTURE), subject)
            return ToolResult(
                success=True,
                data={"educational_plan": plan, "output_path": ""},
                artifacts=["educational_plan", "decision_log"],
                cost_usd=0.0,
                duration_seconds=time.monotonic() - start,
                seed=seed,
            )

        # Use agent-provided plan if present
        plan = inputs.get("educational_plan")

        if not plan:
            # Build a minimal shell — agent must have provided sections via
            # educational_plan input; if they didn't, return a clear error
            return ToolResult(
                success=False,
                error=(
                    "educational_plan not provided. "
                    "The agent must author the plan by following "
                    "skills/edustream/content-director.md and pass it as "
                    "the 'educational_plan' input field."
                ),
            )

        # Enforce defaults and render_mode
        plan = _enforce_plan(plan, subject)
        plan.setdefault("title", inputs.get("source_content", "")[:60] or "Educational Video")
        plan.setdefault("subject_classification", inputs.get("subject_type", "theory"))
        plan.setdefault("total_duration_seconds", inputs.get("total_duration_seconds", 480))
        plan.setdefault("target_audience", inputs.get("target_audience", "Class 1, ages 5-7"))

        # Validate section count
        if len(plan.get("sections", [])) < 2:
            return ToolResult(
                success=False,
                error=f"educational_plan needs at least 2 sections, got {len(plan.get('sections', []))}",
            )

        # Persist
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "educational_plan.json"
        out_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")

        return ToolResult(
            success=True,
            data={"educational_plan": plan, "output_path": str(out_path)},
            artifacts=["educational_plan", "decision_log"],
            cost_usd=0.0,
            duration_seconds=time.monotonic() - start,
            seed=seed,
        )

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {
            "tool":                      self.name,
            "estimated_cost_usd":        0.0,
            "estimated_runtime_seconds": 1.0,
            "status":                    self.get_status().value,
            "would_execute":             True,
        }
