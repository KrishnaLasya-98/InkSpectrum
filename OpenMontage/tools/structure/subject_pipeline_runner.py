"""SubjectPipelineRunner — end-to-end chapter video builder.

Chains all EduStream Pro stages for one subject:

  Stage 0  SectionParser           markdown → ContentBlock[]
  Stage 1  EducationalContentGenerator  blocks → educational_plan
  Stage 2  EduStreamOrchestrator    plan → enriched EVS script
  Stage 3  VoiceSynthesisPipeline  script → narration audio + STT QA
  Stage 4  NarrationTextSyncer     audio → word captions + Q&A timing
  Stage 5  RenderModeRouter        timed script → clip per section
  Stage 6  MultimediaSyncPlanner   measured audio + clips → authoritative timeline
  Stage 7  EducationalHyperFramesComposer + HyperFrames → chapter_final.mp4
  Stage 8  QualityAssurance        pacing / sync / contrast / WPM / slideshow checks

This compatibility runner executes in one process while persisting the same
manifest-ordered checkpoints and Backlot events used by agent-driven runs.
Completed media can be reused by the underlying renderers on a resumed run.
Running with dry_run=True exercises every stage without API calls or renders.

Usage
-----
    python -m tools.structure.subject_pipeline_runner --subject evs --dry-run
    python -m tools.structure.subject_pipeline_runner --subject maths
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
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
from tools.extract.section_parser import SectionParser  # noqa: E402
from tools.structure.source_fidelity import write_source_manifest  # noqa: E402
from tools.structure.source_contract import (  # noqa: E402
    validate_coverage_contract,
    validate_final_source_coverage,
)
from tools.structure.educational_generator import EducationalContentGenerator  # noqa: E402
from tools.structure.edustream_orchestrator import EduStreamOrchestrator  # noqa: E402
from tools.structure.subject_profiles import resolve_subject_profile  # noqa: E402
from tools.structure.subject_registry import get_subject, md_path as _md_path  # noqa: E402
from tools.structure.chapter_config import load_chapter_config, registry_view  # noqa: E402
from tools.structure.educational_pre_render_receipt import (  # noqa: E402
    create_pre_render_receipt,
)
from tools.video.render_mode_router import RenderModeRouter  # noqa: E402
from tools.voice.voice_synthesis_pipeline import VoiceSynthesisPipeline  # noqa: E402
from tools.video.educational_hyperframes_composer import (  # noqa: E402
    EducationalHyperFramesComposer,
)
from tools.video.hyperframes_compose import HyperFramesCompose  # noqa: E402

_ODL_DIR = Path(
    os.environ.get(
        "OPENDATALOADER_OUTPUT_DIR",
        r"C:\Users\user\Downloads\opendataloader_output",
    )
)


def _create_strict_production_pre_render_receipt(
    *,
    project_dir: Path,
    artifacts_dir: Path,
    voice_id: str,
    model_id: str,
    speed: float,
) -> dict[str, Any]:
    """Run the full timeline gates and persist their hash-bound receipt.

    Production composition uses these canonical, reviewed chapter artifacts.
    The helper deliberately fails closed when any one is absent so the real
    runner cannot bypass interval labels, phrase-to-media assignments, stable
    teaching pages, or the locked narration identity.
    """

    return create_pre_render_receipt(
        project_path=project_dir,
        intervals_path=artifacts_dir / "visual-interval-plan-v1.json",
        assignments_path=artifacts_dir / "visual-assignments-v1.json",
        teaching_pages_path=artifacts_dir / "teaching-pages-v1.json",
        narration_manifest_path=artifacts_dir / "narration_manifest.json",
        output_path=artifacts_dir / "pre-render-regression-receipt.json",
        voice_id=voice_id,
        model_id=model_id,
        speed=speed,
    )


def _source_content_for_planning(blocks: list[dict[str, Any]]) -> str:
    """Return the complete ordered textbook content supplied to planning.

    This intentionally performs no length truncation.  Source reduction is a
    later, auditable pedagogical decision; ingestion must remain lossless.
    """

    return "\n\n".join(
        f"## {block.get('heading', '')}\n{block.get('body_text', '')}"
        for block in blocks
    )


def _map_plan_to_coverage(
    coverage: dict[str, Any],
    plan: dict[str, Any],
    *,
    require_complete: bool = True,
) -> dict[str, Any]:
    """Apply explicit section source IDs to the source coverage ledger."""

    sections_by_source: dict[str, list[dict[str, Any]]] = {}
    for section in plan.get("sections", []):
        for source_block_id in section.get("source_block_ids", []):
            sections_by_source.setdefault(str(source_block_id), []).append(section)

    for entry in coverage.get("entries", []):
        mapped_sections = sections_by_source.get(entry["source_block_id"], [])
        if not mapped_sections:
            continue
        entry["status"] = "mapped"
        entry["omission_reason"] = None
        entry["mappings"] = {
            "narration_segment_ids": [
                section["section_id"]
                for section in mapped_sections
                if section.get("narration_script")
            ],
            "screen_ids": [section["section_id"] for section in mapped_sections],
            "visual_cue_ids": [
                f"{section['section_id']}:visual" for section in mapped_sections
            ],
        }
    coverage["summary"] = validate_coverage_contract(
        coverage, require_complete=require_complete
    )
    return coverage["summary"]


class SubjectPipelineRunner(BaseTool):
    """End-to-end chapter video runner for one subject."""

    name = "subject_pipeline_runner"
    version = "1.0.0"
    tier = ToolTier.CORE
    capability = "pipeline"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.HYBRID

    dependencies: list[str] = []
    install_instructions = "All dependencies installed via sub-tools."
    agent_skills = ["edu-gen", "pipeline-runner"]
    capabilities = ["full_pipeline", "checkpoint_tracked", "cost_tracking"]

    input_schema = {
        "type": "object",
        "required": ["subject"],
        "properties": {
            "subject": {
                "type": "string",
                # Dynamically pulled from registry — any registered subject is valid
                "description": "Subject ID. Must be registered in subject_registry.py.",
            },
            "dry_run":    {"type": "boolean", "default": False},
            "quality":    {"type": "string", "default": "medium"},
            "seed":       {"type": "integer"},
            "output_dir": {"type": "string"},
            "educational_plan": {"type": "object"},
            "educational_plan_path": {"type": "string"},
            "chapter_config_path": {"type": "string"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "final_video":    {"type": "string"},
            "cost_usd":       {"type": "number"},
            "stages_summary": {"type": "object"},
        },
    }

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # ModelsLab pricing is model- and account-dependent. The concrete cost
        # is accumulated from provider results during execution.
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 300.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:  # noqa: C901
        subject   = inputs["subject"]
        dry_run   = inputs.get("dry_run", False)
        seed      = inputs.get("seed")
        start     = time.monotonic()

        # Load subject metadata from registry (raises KeyError for unknown subjects)
        chapter_config_path = inputs.get("chapter_config_path")
        if chapter_config_path:
            try:
                chapter_config = load_chapter_config(chapter_config_path)
                reg = registry_view(chapter_config)
                subject = chapter_config["subject"]
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                return ToolResult(success=False, error=f"Invalid chapter config: {exc}")
            subject_md_path = Path(reg["source_markdown"])
        else:
            try:
                reg = get_subject(subject)
            except KeyError as exc:
                return ToolResult(success=False, error=str(exc))
            subject_md_path = _md_path(subject)

        default_project_id = (
            chapter_config.get("project_id", subject)
            if chapter_config_path
            else subject
        )
        out_root = Path(inputs.get("output_dir", str(_ROOT / "projects" / default_project_id)))
        subject_type      = reg["subject_type"]
        chapter_num       = reg["chapter"]
        chapter_title     = reg["title"]
        target_duration   = reg["duration_s"]
        target_audience   = reg.get("audience", "Class 1, ages 5-7")

        proj_id   = f"edustream-{subject}"
        arts_dir  = out_root / "artifacts"
        clips_dir = out_root / "renders" / "clips"
        audio_dir = out_root / "renders" / "audio"
        final_dir = out_root / "renders"
        arts_dir.mkdir(parents=True, exist_ok=True)
        clips_dir.mkdir(parents=True, exist_ok=True)
        audio_dir.mkdir(parents=True, exist_ok=True)
        final_dir.mkdir(parents=True, exist_ok=True)

        summary: dict[str, Any] = {}
        total_cost = 0.0
        from tools.structure.educational_run_tracker import EducationalRunTracker

        approval_policy = (
            "full-run-preauthorized"
            if dry_run
            else str(chapter_config.get("approval_policy", "guided"))
            if chapter_config_path
            else str(inputs.get("approval_policy", "guided"))
        )
        tracker = EducationalRunTracker(
            out_root,
            title=chapter_title,
            approval_policy=approval_policy,
        )

        # ── Preflight: fail before paid generation ───────────────────────────
        from tools.structure.educational_preflight import run_educational_preflight
        preflight = run_educational_preflight(
            reg,
            workspace=out_root,
            dry_run=bool(dry_run),
        )
        (arts_dir / "preflight_report.json").write_text(
            json.dumps(preflight, indent=2), encoding="utf-8"
        )
        summary["preflight"] = preflight
        if preflight["status"] != "pass":
            details = "; ".join(
                f"{item['name']}: {item['detail']}"
                for item in preflight["failures"]
            )
            return ToolResult(success=False, error=f"Preflight failed: {details}")

        # ── Stage 0: Section Parsing ─────────────────────────────────────────
        tracker.begin(
            "input_ingestion",
            metadata={"source": str(subject_md_path), "dry_run": bool(dry_run)},
        )
        print(f"[Stage 0] Parsing markdown for {subject}...")
        parser_res = SectionParser().execute({
            "subject":    subject,
            "md_path":    str(subject_md_path),
            "output_dir": str(arts_dir),
        })
        if not parser_res.success:
            return ToolResult(success=False, error=f"Stage 0 failed: {parser_res.error}")
        blocks     = parser_res.data["blocks"]
        planning_blocks = blocks
        chapter_document_path = reg.get("source_document")
        if chapter_document_path and Path(chapter_document_path).is_file():
            try:
                chapter_document = json.loads(
                    Path(chapter_document_path).read_text(encoding="utf-8")
                )
                planning_blocks = list(chapter_document.get("blocks") or [])
            except (OSError, json.JSONDecodeError) as exc:
                return ToolResult(
                    success=False,
                    error=f"Invalid canonical source document: {exc}",
                )
            if not planning_blocks:
                return ToolResult(
                    success=False,
                    error="Canonical source document contains no content blocks",
                )
        source_manifest_path = arts_dir / "source_text_manifest.json"
        source_manifest = write_source_manifest(subject_md_path, source_manifest_path)
        # The educational planner must receive the complete extracted source.
        # Truncating each block silently drops questions, glossary entries,
        # table rows, and the ends of long textbook explanations.  Downstream
        # agents may simplify delivery, but they may not plan from a partial
        # copy of the source of truth.
        block_text = _source_content_for_planning(blocks)
        summary["stage_0"] = {
            "blocks": parser_res.data["block_count"],
            "source_text_manifest": str(source_manifest_path),
            "source_cards": source_manifest["validation"]["card_count"],
            "max_content_lines": source_manifest["validation"]["max_content_lines"],
        }
        tracker.finish(
            "input_ingestion",
            {
                "extracted_content_path": str(subject_md_path),
                "chapter_document_path": str(reg.get("source_document") or ""),
                "coverage_contract_path": str(reg.get("coverage_contract") or ""),
                "section_blocks_path": str(arts_dir / "section_blocks.json"),
            },
            metadata=summary["stage_0"],
            total_spent_usd=total_cost,
        )
        print(f"  ✓ {parser_res.data['block_count']} blocks")

        # ── Stage 1: Educational Plan ────────────────────────────────────────
        print(f"[Stage 1] Generating educational plan...")
        provided_plan = inputs.get("educational_plan")
        selected_plan_path = inputs.get("educational_plan_path") or reg.get("educational_plan_path")
        if not provided_plan and selected_plan_path:
            try:
                provided_plan = json.loads(
                    Path(selected_plan_path).read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError) as exc:
                return ToolResult(success=False, error=f"Invalid educational_plan_path: {exc}")

        if reg.get("production_scope_audit"):
            try:
                scope = json.loads(Path(reg["production_scope_audit"]).read_text(encoding="utf-8"))
                expected = scope["included_section_ids"]
                actual = [s["section_id"] for s in (provided_plan or {}).get("sections", [])]
                if not scope["scope"].get("user_approved") or actual != expected:
                    raise ValueError("Plan does not match the user-approved production scope")
            except (OSError, ValueError, KeyError) as exc:
                return ToolResult(success=False, error=f"Production scope validation failed: {exc}")

        plan_res = EducationalContentGenerator().execute({
            "educational_plan":        provided_plan,
            "source_content":          block_text,
            "content_blocks":          planning_blocks,
            "subject_type":            subject_type,
            "complexity_level":        reg.get("complexity", "elementary"),
            "target_audience":         target_audience,
            "delivery_profile":        reg.get("grade_delivery", {}),
            "total_duration_seconds":  target_duration,
            "subject":                 subject,
            "title":                   chapter_title,
            "dry_run":                 dry_run,
            "seed":                    seed,
        })
        if not plan_res.success:
            return ToolResult(success=False, error=f"Stage 1 failed: {plan_res.error}")
        plan = plan_res.data["educational_plan"]
        total_cost += plan_res.cost_usd or 0.0

        # Enrich plan sections with qa_pairs from parser blocks
        block_map = {b["block_id"]: b for b in blocks}
        for sec in plan.get("sections", []):
            # A shared block type is not source identity: two assessments can
            # have different questions. Preserve authored pairs; otherwise use
            # only explicitly referenced source blocks.
            if sec.get("qa_pairs"):
                continue
            source_pairs = []
            for block_id in sec.get("source_block_ids", []):
                source_pairs.extend(block_map.get(block_id, {}).get("qa_pairs") or [])
            if source_pairs:
                sec["qa_pairs"] = source_pairs

        (arts_dir / "educational_plan.json").write_text(
            json.dumps(plan, indent=2), encoding="utf-8"
        )
        coverage_path = reg.get("coverage_contract")
        coverage: dict[str, Any] | None = None
        coverage_summary: dict[str, Any] | None = None
        if coverage_path and Path(coverage_path).is_file():
            try:
                coverage = json.loads(Path(coverage_path).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                return ToolResult(success=False, error=f"Invalid coverage contract: {exc}")

            require_complete = bool(
                reg.get("automation_policy", {}).get(
                    "fail_on_missing_source_coverage", True
                )
            )
            try:
                coverage_summary = _map_plan_to_coverage(
                    coverage,
                    plan,
                    require_complete=require_complete,
                )
            except ValueError as exc:
                return ToolResult(success=False, error=f"Stage 1 coverage failed: {exc}")
            Path(coverage_path).write_text(
                json.dumps(coverage, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        summary["stage_1"] = {
            "sections": len(plan.get("sections", [])),
            "coverage": coverage_summary,
        }
        print(f"  ✓ {len(plan.get('sections', []))} sections")

        # ── Stage 2: Orchestration ───────────────────────────────────────────
        print(f"[Stage 2] Running orchestration + critique loops...")
        orch_res = EduStreamOrchestrator().execute({
            "educational_plan": plan,
            "subject":          subject,
            "target_audience":  target_audience,
            "delivery_profile": reg.get("grade_delivery", {}),
            "dry_run":          dry_run,
            "seed":             seed,
        })
        if not orch_res.success:
            return ToolResult(success=False, error=f"Stage 2 failed: {orch_res.error}")
        evs = orch_res.data["evs_script"]
        enriched_sections = evs["P"]
        total_cost += orch_res.cost_usd or 0.0

        # Update plan with enriched sections
        plan["sections"] = enriched_sections
        (arts_dir / "evs_script.json").write_text(
            json.dumps(evs, indent=2), encoding="utf-8"
        )
        summary["stage_2"] = {
            "sections_ready": orch_res.data["sections_ready"],
            "first_pass_rate": orch_res.data.get("first_pass_rate", 0),
        }
        print(f"  ✓ {orch_res.data['sections_ready']} sections enriched")

        # Content evidence must be checked after orchestration, which can edit
        # narration. Legacy projects receive a report; strict projects stop
        # before spending on media if their teaching plan is incomplete.
        from tools.structure.teaching_contract import validate_teaching_contract
        teaching_review = validate_teaching_contract(plan, planning_blocks, subject=subject)
        from tools.structure.exercise_resolution import resolve_exercises
        from tools.structure.exercise_inventory import propose_question_groups
        (arts_dir / "exercise_grouping_proposals.json").write_text(
            json.dumps(propose_question_groups({"blocks": planning_blocks}), indent=2, ensure_ascii=False),
            encoding="utf-8")
        reviews_path = arts_dir / "exercise_reviews.json"
        try:
            reviews = json.loads(reviews_path.read_text(encoding="utf-8")) if reviews_path.exists() else []
            if not isinstance(reviews, list):
                raise ValueError("Expected a list of review records")
        except (ValueError, OSError) as exc:
            return ToolResult(success=False, error=f"Invalid exercise_reviews.json: {exc}")
        exercise_review = resolve_exercises({"blocks": planning_blocks}, plan, reviews)
        (arts_dir / "exercise_resolution.json").write_text(
            json.dumps(exercise_review, indent=2, ensure_ascii=False), encoding="utf-8")
        summary["exercise_resolution"] = {"status": exercise_review["status"],
                                           "issue_count": len(exercise_review["issues"])}
        (arts_dir / "teaching_contract_review.json").write_text(
            json.dumps(teaching_review, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        summary["teaching_contract"] = {
            "status": teaching_review["status"],
            "issue_count": len(teaching_review["issues"]),
        }
        if reg.get("content_policy", {}).get("require_teaching_contract", False) and teaching_review["status"] != "pass":
            return ToolResult(
                success=False,
                error="Teaching contract needs repair; see artifacts/teaching_contract_review.json",
            )
        if reg.get("content_policy", {}).get("require_teaching_contract", False) and exercise_review["status"] != "pass":
            return ToolResult(success=False,
                error="Exercise resolution needs review; see artifacts/exercise_resolution.json")

        # ── Stage 2a: Proposal, scene plan, and asset strategy ───────────────
        tracker.begin(
            "proposal",
            metadata={"sections": len(plan.get("sections", []))},
        )
        from tools.structure.educational_production_artifacts import (
            build_production_artifacts,
        )
        production_config = {
            "project_id": default_project_id,
            "subject": subject,
            "grade": (
                chapter_config.get("grade") if chapter_config_path else None
            ),
            "chapter": chapter_num,
            "title": chapter_title,
            "source_input": reg.get("source_input") or reg.get("source_pdf"),
            "providers": reg.get("providers", {}),
            "content_policy": reg.get("content_policy", {}),
            "render_policy": reg.get("render_policy", {}),
            "approval_policy": (
                chapter_config.get("approval_policy", "guided")
                if chapter_config_path
                else "guided"
            ),
        }
        production_artifacts = build_production_artifacts(production_config, plan)
        # The checkpoint binds approval to this exact proposal payload. Do not
        # restore approval by stage name or inject a changing timestamp here.
        from schemas.artifacts import validate_artifact
        for artifact_name, artifact in production_artifacts.items():
            try:
                validate_artifact(artifact_name, artifact)
            except Exception as exc:
                return ToolResult(
                    success=False,
                    error=f"Stage 2a invalid {artifact_name}: {exc}",
                )
            (arts_dir / f"{artifact_name}.json").write_text(
                json.dumps(artifact, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        blocked_scenes = production_artifacts["asset_strategy"]["blocked_scene_ids"]
        if blocked_scenes:
            return ToolResult(
                success=False,
                error="Stage 2a has blocked scenes: " + ", ".join(blocked_scenes),
            )
        summary["stage_2a"] = {
            "proposal": str(arts_dir / "proposal_packet.json"),
            "scene_plan": str(arts_dir / "scene_plan.json"),
            "asset_strategy": str(arts_dir / "asset_strategy.json"),
            "asset_manifest": str(arts_dir / "asset_manifest.json"),
            "scenes": production_artifacts["scene_plan"]["metadata"]["total_scenes"],
        }
        proposal_status = tracker.finish(
            "proposal",
            {
                "proposal_packet": production_artifacts["proposal_packet"],
                "decision_log": production_artifacts["decision_log"],
            },
            metadata={
                "proposal_path": str(arts_dir / "proposal_packet.json"),
                "decision_log_path": str(out_root / "decision_log.json"),
            },
            total_spent_usd=total_cost,
        )
        if proposal_status == "awaiting_human":
            return ToolResult(
                success=True,
                data={
                    "status": "awaiting_human",
                    "stage": "proposal",
                    "project_dir": str(out_root),
                    "proposal_path": str(arts_dir / "proposal_packet.json"),
                },
                artifacts=["proposal_packet", "decision_log"],
                cost_usd=round(total_cost, 4),
            )

        tracker.begin("content_structuring")
        (arts_dir / "educational_plan.json").write_text(
            json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        content_status = tracker.finish(
            "content_structuring",
            {
                "educational_plan_path": str(arts_dir / "educational_plan.json"),
                "source_coverage_path": str(reg.get("coverage_contract") or ""),
            },
            metadata={"sections": len(plan.get("sections", []))},
            total_spent_usd=total_cost,
        )
        if content_status == "awaiting_human":
            return ToolResult(
                success=True,
                data={
                    "status": "awaiting_human",
                    "stage": "content_structuring",
                    "project_dir": str(out_root),
                    "educational_plan_path": str(arts_dir / "educational_plan.json"),
                },
                artifacts=["educational_plan", "decision_log"],
                cost_usd=round(total_cost, 4),
            )

        tracker.begin("scene_plan")
        tracker.finish(
            "scene_plan",
            {"scene_plan": production_artifacts["scene_plan"]},
            metadata={"scene_plan_path": str(arts_dir / "scene_plan.json")},
            total_spent_usd=total_cost,
        )

        tracker.begin("media_research")
        from tools.analysis.educational_media_research_planner import (
            EducationalMediaResearchPlanner,
        )
        media_research_res = EducationalMediaResearchPlanner().execute({
            "subject": subject,
            "scenes": production_artifacts["scene_plan"]["scenes"],
        })
        if not media_research_res.success:
            tracker.fail("media_research", media_research_res.error or "media research failed")
            return ToolResult(
                success=False,
                error=f"Stage 2b media research failed: {media_research_res.error}",
            )
        media_research_plan = media_research_res.data["media_research_plan"]
        try:
            validate_artifact("media_research_plan", media_research_plan)
        except Exception as exc:
            tracker.fail("media_research", str(exc))
            return ToolResult(
                success=False,
                error=f"Stage 2b invalid media_research_plan: {exc}",
            )
        media_research_path = arts_dir / "media_research_plan.json"
        media_research_path.write_text(
            json.dumps(media_research_plan, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tracker.finish(
            "media_research",
            {"media_research_plan": media_research_plan},
            metadata={"path": str(media_research_path)},
            total_spent_usd=total_cost,
        )

        tracker.begin("assets")
        assets_status = tracker.finish(
            "assets",
            {
                "asset_manifest": production_artifacts["asset_manifest"],
                "asset_strategy": production_artifacts["asset_strategy"],
            },
            metadata={
                "asset_manifest_path": str(arts_dir / "asset_manifest.json"),
                "asset_strategy_path": str(arts_dir / "asset_strategy.json"),
            },
            total_spent_usd=total_cost,
        )
        if assets_status == "awaiting_human":
            return ToolResult(
                success=True,
                data={
                    "status": "awaiting_human",
                    "stage": "assets",
                    "project_dir": str(out_root),
                    "asset_manifest_path": str(arts_dir / "asset_manifest.json"),
                },
                artifacts=["asset_manifest", "asset_strategy"],
                cost_usd=round(total_cost, 4),
            )

        # ── Opening treatment ─────────────────────────────────────────────────
        # The chapter identity is overlaid on the first narrated animated scene.
        # A detached title clip creates an empty visual lead and a second timing
        # origin, so the locked educational template forbids it.
        print("[Stage 2b] Opening title will be integrated with first motion scene...")
        title_clip = ""
        summary["stage_2b"] = {"mode": "integrated_opening", "offset_seconds": 0.0}

        # ── Stage 2c: Character bible ─────────────────────────────────────────
        # Continuity is derived from this chapter's actual sections and stored
        # inside this project. It must never pull a hard-coded subject cast or
        # another chapter's references.
        print(f"[Stage 2c] Building chapter-scoped visual continuity references...")
        providers = reg.get("providers", {})
        video_provider = providers.get("video", {})
        if isinstance(video_provider, str):
            video_provider = {"provider": video_provider}
        from tools.video.character_consistency import (
            CharacterBible,
            discover_recurring_characters,
        )
        try:
            visual_style = str(
                resolve_subject_profile(subject).get("visual_style")
                or "polished child-friendly 3D educational animation"
            )
            character_specs = discover_recurring_characters(
                enriched_sections,
                chapter_title=str(plan.get("title") or reg.get("title") or "Chapter"),
                visual_style=visual_style,
            )
            bible = CharacterBible().generate(
                subject=subject,
                dry_run=dry_run,
                characters=character_specs,
                project_dir=out_root,
                image_model_id=str(
                    video_provider.get("reference_image_model_id", "flux")
                ),
            )
            n_chars = len(bible.get("characters", {}))
            if n_chars != len(character_specs):
                return ToolResult(
                    success=False,
                    error=(
                        "Stage 2c failed: generated "
                        f"{n_chars}/{len(character_specs)} required character references"
                    ),
                )
            by_section: dict[str, list[tuple[str, dict[str, Any]]]] = {}
            for character_id, character in bible.get("characters", {}).items():
                for section_id in character.get("sections", []):
                    by_section.setdefault(str(section_id), []).append(
                        (str(character_id), character)
                    )
            for section in enriched_sections:
                entries = by_section.get(str(section.get("section_id")), [])
                references = [
                    str(character.get("path"))
                    for _character_id, character in entries
                    if character.get("path")
                ]
                if references:
                    section["reference_image_paths"] = references
                    section["reference_characters"] = [
                        {
                            "id": character_id,
                            "name": character.get("name", character_id),
                            "description": character.get("description", ""),
                        }
                        for character_id, character in entries
                    ]
            print(f"  ✓ {n_chars} character reference(s) ready")
            summary["stage_2c"] = {
                "characters": n_chars,
                "mode": "dynamic-chapter-scoped",
                "manifest": str(out_root / "artifacts" / "character_bible.json"),
            }
        except Exception as exc:
            return ToolResult(success=False, error=f"Stage 2c failed: {exc}")

        # ── Stage 4: Voice synthesis ─────────────────────────────────────────
        tracker.begin("voice_synthesis")
        print(f"[Stage 4] Synthesising narration...")
        title_card_hold_types = {
            "we_learn",
            "lesson_highlights",
            "activity",
            "fill_blank",
            "assessment",
            "glossary",
            "recall",
        }
        nar_segments = []
        from tools.structure.teaching_contract import spoken_heading
        delivery = reg.get("content_policy", {}).get("delivery_timing", {})
        for section in enriched_sections:
            if not section.get("narration_script"):
                continue
            block_type = section.get("source_block_type", "concept")
            chunk_index = int(section.get("source_chunk_index") or 1)
            chunk_count = int(section.get("source_chunk_count") or 1)
            is_first_chunk = chunk_index <= 1
            is_last_chunk = chunk_index >= chunk_count
            default_title_hold = (
                4.0
                if is_first_chunk
                and section.get("render_mode") == "hyperframes"
                and block_type in title_card_hold_types
                else 0.0
            )
            heading = spoken_heading(section) if delivery and is_first_chunk else ""
            headings = (
                list(dict.fromkeys(
                    str(value).strip()
                    for value in [section.get("title"), section.get("subtitle")]
                    if isinstance(value, str) and value.strip()
                ))
                if delivery and is_first_chunk
                else []
            )
            nar_segments.append(
                {
                    "section_id": section["section_id"],
                    "text": section.get("narration_script", ""),
                    "exercise_questions": (section.get("teaching_contract") or {}).get("questions") or section.get("qa_pairs", []),
                    "spoken_heading": heading,
                    "spoken_headings": headings,
                    "topic_end_pause_seconds": (
                        float(delivery.get("topic_end_pause_seconds", 0))
                        if is_last_chunk and section.get("topic_end", True)
                        else 0
                    ),
                    "source_block_type": block_type,
                    "duration_seconds": section.get("duration_seconds", 30),
                    "title_card_hold_seconds": (
                        section.get(
                            "title_card_hold_seconds",
                            delivery.get("spoken_heading_pause_seconds", default_title_hold),
                        )
                        if is_first_chunk and heading
                        else 0
                    ),
                }
            )
        audio_provider = providers.get("audio", {})
        if isinstance(audio_provider, str):
            audio_provider = {"provider": audio_provider}
        audio_provider_name = str(audio_provider.get("provider", "modelslab"))
        if audio_provider_name not in {
            "modelslab", "kokoro", "huggingface-kokoro", "hyperframes-kokoro",
        }:
            tracker.fail("voice_synthesis", "Unsupported narration provider")
            return ToolResult(
                success=False,
                error=(
                    "Unsupported narration provider: " + audio_provider_name
                ),
            )

        voice_res = VoiceSynthesisPipeline().execute({
            "narration_segments": nar_segments,
            "output_dir":         str(audio_dir),
            "dry_run":            dry_run,
            "seed":               seed,
            "provider":           audio_provider_name,
            "voice_profile": {
                "voice_id": audio_provider.get("voice_id", "nova"),
                "model_id": audio_provider.get("model_id", "text-to-speech"),
                "language": audio_provider.get("language", "english"),
                "speed": delivery.get("narration_speed", audio_provider.get("speed", 0.85)),
            },
            "enable_stt_qa":      audio_provider.get("enable_stt_qa", True),
            "allow_voice_fallback": not audio_provider.get("lock_voice", True),
        })
        if not voice_res.success:
            tracker.fail("voice_synthesis", voice_res.error or "voice synthesis failed")
            return ToolResult(success=False, error=f"Stage 4 failed: {voice_res.error}")
        narration_manifest = voice_res.data["narration_manifest"]
        # Measured narration is the timing authority.  Estimated plan durations
        # must not survive voice synthesis: spoken headings, thinking pauses,
        # and topic-end holds all make the real audio longer than the text-only
        # estimate.  Rebuild both the narration and scene timeline before clips
        # are rendered so audio, subtitles, teaching UI, and motion share one
        # duration contract.
        sections_by_id = {
            str(section.get("section_id")): section
            for section in plan.get("sections", [])
        }
        cursor = 0.0
        for seg in narration_manifest["segments"]:
            section_id = str(seg.get("section_id") or "")
            duration = max(0.0, float(seg.get("duration_seconds") or 0.0))
            seg["start_seconds"] = round(cursor, 3)
            seg["end_seconds"] = round(cursor + duration, 3)
            section = sections_by_id.get(section_id)
            if section is not None:
                section["duration_seconds"] = round(duration, 3)
            cursor += duration
        plan["total_duration_seconds"] = round(cursor, 3)

        scene_cursor = 0.0
        for scene in production_artifacts["scene_plan"].get("scenes", []):
            section = sections_by_id.get(str(scene.get("section_id") or ""), {})
            duration = max(0.0, float(section.get("duration_seconds") or 0.0))
            scene["start_seconds"] = round(scene_cursor, 3)
            scene["end_seconds"] = round(scene_cursor + duration, 3)
            scene["duration_seconds"] = round(duration, 3)
            scene_cursor += duration

        (arts_dir / "educational_plan.json").write_text(
            json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (arts_dir / "scene_plan.json").write_text(
            json.dumps(
                production_artifacts["scene_plan"], indent=2, ensure_ascii=False
            ),
            encoding="utf-8",
        )

        (arts_dir / "narration_manifest.json").write_text(
            json.dumps(narration_manifest, indent=2), encoding="utf-8"
        )
        summary["stage_4"] = {
            "segments": len(narration_manifest["segments"]),
            "qa_issues": len(voice_res.data.get("qa_report", {}).get("qa_issues", [])),
        }
        tracker.finish(
            "voice_synthesis",
            {"narration_manifest": narration_manifest},
            metadata={
                **summary["stage_4"],
                "path": str(arts_dir / "narration_manifest.json"),
            },
            total_spent_usd=total_cost,
        )
        print(f"  ✓ {len(narration_manifest['segments'])} narration segments")

        # ── Stage 4b: Text-audio alignment ───────────────────────────────────
        # Run before Stage 3 so the chapter has speech-derived word timing and
        # answer-reveal metadata before any teaching scene is dispatched.
        tracker.begin("text_audio_alignment")
        print(f"[Stage 4b] Aligning text to audio (word-level sync)...")
        from tools.analysis.narration_text_syncer import NarrationTextSyncer
        sync_res = NarrationTextSyncer().execute({
            "narration_manifest":    narration_manifest,
            "educational_plan":      plan,
            "output_dir":            str(arts_dir),
            "title_offset_seconds":  0.0,
            "dry_run":               dry_run,
        })
        # Use formatted SRT from syncer (properly phrased, word-timed)
        formatted_srt_path = None
        qa_card_props_path = None
        if sync_res.success:
            formatted_srt_path = sync_res.data.get("formatted_srt_path")
            qa_card_props_path = arts_dir / "qa_card_props.json"
            alignment_method   = sync_res.data.get("alignment_method", "linear")
            summary["stage_4b"] = {
                "words_aligned":    len(sync_res.data.get("word_captions", [])),
                "alignment_method": alignment_method,
                "qa_sections_timed": len(sync_res.data.get("qa_card_props", {})),
            }
            print(f"  ✓ {len(sync_res.data.get('word_captions', []))} words "
                  f"aligned via {alignment_method}")
            reject_linear = bool(
                reg.get("render_policy", {}).get(
                    "reject_linear_subtitle_alignment", False
                )
            )
            if (
                reject_linear
                and not dry_run
                and "linear" in str(alignment_method).lower()
            ):
                tracker.fail(
                    "text_audio_alignment",
                    "Speech-derived timing required; linear interpolation returned",
                )
                return ToolResult(
                    success=False,
                    error=(
                        "Stage 4b failed: speech-derived word alignment is "
                        "required, but only linear interpolation was available"
                    ),
                )
        else:
            tracker.fail(
                "text_audio_alignment", sync_res.error or "alignment failed"
            )
            return ToolResult(
                success=False,
                error=f"Stage 4b failed: {sync_res.error}",
            )
        tracker.finish(
            "text_audio_alignment",
            {
                "narration_aligned_path": str(arts_dir / "narration_aligned.json"),
                "word_captions_path": str(arts_dir / "word_captions.json"),
                "formatted_srt_path": str(formatted_srt_path or ""),
                "qa_card_props_path": str(qa_card_props_path or ""),
            },
            metadata=summary["stage_4b"],
            total_spent_usd=total_cost,
        )

        # ── Stage 3: Render clips ────────────────────────────────────────────
        # Runs after Stage 4b so timing metadata is available to every renderer.
        tracker.begin("render_clips")
        print(f"[Stage 3] Dispatching {len(enriched_sections)} clips to renderers...")
        video_provider = providers.get("video", {})
        if isinstance(video_provider, str):
            video_provider = {"provider": video_provider}

        router_res = RenderModeRouter().execute({
            "educational_plan": plan,
            "subject":          subject,
            "chapter":          chapter_num,
            "output_dir":       str(clips_dir),
            "dry_run":          dry_run,
            "seed":             seed,
            "qa_card_props_path": str(arts_dir / "qa_card_props.json"),
            "video_provider":   video_provider,
            "quality":          inputs.get("quality", "standard"),
        })
        if not router_res.success or router_res.data.get("failed_clips", 0) > 0:
            tracker.fail(
                "render_clips",
                router_res.error or f"{router_res.data.get('failed_clips', 0)} clips failed",
            )
            return ToolResult(
                success=False,
                error=(
                    "Stage 3 failed: every required section must have a valid "
                    "motion clip or deterministic teaching scene; "
                    f"{router_res.data.get('failed_clips', 0)} clip(s) failed"
                ),
            )
        clip_manifest = router_res.data["clip_manifest"]
        total_cost += sum(
            float(clip.get("cost_usd", 0.0) or 0.0) for clip in clip_manifest
        )
        from tools.structure.educational_production_artifacts import (
            finalize_asset_manifest,
        )
        production_artifacts["asset_manifest"] = finalize_asset_manifest(
            production_artifacts["asset_manifest"], clip_manifest
        )
        try:
            validate_artifact(
                "asset_manifest", production_artifacts["asset_manifest"]
            )
        except Exception as exc:
            tracker.fail("render_clips", str(exc))
            return ToolResult(
                success=False,
                error=f"Stage 3 invalid asset_manifest: {exc}",
            )
        (arts_dir / "asset_manifest.json").write_text(
            json.dumps(
                production_artifacts["asset_manifest"],
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        if not production_artifacts["asset_manifest"].get("ready"):
            tracker.fail("render_clips", "Finalized asset manifest is not ready")
            return ToolResult(
                success=False,
                error="Stage 3 failed: finalized asset manifest is not ready",
            )
        summary["stage_3"] = {
            "total":   router_res.data["total_clips"],
            "skipped": router_res.data["skipped_clips"],
            "failed":  router_res.data["failed_clips"],
        }
        clip_outputs = [
            {
                "path": str(clip.get("video_path") or clips_dir / f"{clip.get('section_id', 'scene')}.mp4"),
                "format": "mp4",
                "resolution": "1920x1080",
                "duration_seconds": float(clip.get("duration_seconds") or 0.0),
            }
            for clip in clip_manifest
        ]
        clip_render_report = {
            "version": "1.0",
            "outputs": clip_outputs,
            "render_time_seconds": float(router_res.duration_seconds or 0.0),
            "warnings": [],
            "verification_notes": [
                "Per-scene render report; final composition is tracked separately."
            ],
            "render_grammar": "animation-first",
            "slideshow_risk_score": {
                "average": 0.0,
                "verdict": "not-evaluated-dry-run" if dry_run else "pending-final-qa",
            },
            "metadata": {
                "kind": "clip-render",
                "clip_manifest_path": str(router_res.data.get("manifest_path") or ""),
            },
        }
        validate_artifact("render_report", clip_render_report)
        (arts_dir / "clip_render_report.json").write_text(
            json.dumps(clip_render_report, indent=2), encoding="utf-8"
        )
        tracker.finish(
            "render_clips",
            {"render_report": clip_render_report},
            metadata={
                **summary["stage_3"],
                "clip_manifest_path": str(router_res.data.get("manifest_path") or ""),
            },
            total_spent_usd=total_cost,
        )
        print(f"  ✓ {router_res.data['total_clips']} clips"
              f" ({router_res.data['skipped_clips']} skipped)")

        # ── Stage 4c: Authoritative multimedia synchronization ───────────────
        # Reconcile measured narration and rendered clip durations before
        # composition.  This is the only place that assigns global start/end
        # positions; title offsets must never be added again downstream.
        tracker.begin("multimedia_synchronization")
        print("[Stage 4c] Building authoritative multimedia timeline...")
        from tools.analysis.multimedia_sync_planner import MultimediaSyncPlanner
        sync_plan_res = MultimediaSyncPlanner().execute({
            "narration_manifest": narration_manifest,
            "clip_manifest": clip_manifest,
            "title_offset_seconds": 0.0,
            "sync_tolerance_seconds": 0.1,
        })
        sync_plan = sync_plan_res.data.get("sync_plan", {})
        (arts_dir / "multimedia_sync_plan.json").write_text(
            json.dumps(sync_plan, indent=2), encoding="utf-8"
        )
        sync_by_section = {
            item["section_id"]: item for item in sync_plan.get("timeline", [])
        }
        for segment in narration_manifest.get("segments", []):
            timing = sync_by_section.get(segment.get("section_id"))
            if timing:
                segment["start_seconds"] = timing["start_seconds"]
                segment["end_seconds"] = timing["end_seconds"]
                segment["timeline_source"] = timing["timeline_source"]
        if not sync_plan_res.success:
            tracker.fail(
                "multimedia_synchronization",
                sync_plan_res.error or "multimedia synchronization failed",
            )
            return ToolResult(success=False, error=f"Stage 4c failed: {sync_plan_res.error}")

        # Text alignment ran on the individual narration files. Rebase every
        # word once onto the measured global cursor now that it is authoritative,
        # then rewrite all derivative caption artifacts from the rebased data.
        from tools.analysis.narration_text_syncer import rebase_alignment_to_timeline
        try:
            rebased = rebase_alignment_to_timeline(
                sync_res.data.get("narration_aligned", []),
                sync_plan.get("timeline", []),
            )
        except ValueError as exc:
            tracker.fail("multimedia_synchronization", str(exc))
            return ToolResult(success=False, error=f"Stage 4c alignment failed: {exc}")
        sync_res.data.update(rebased)
        (arts_dir / "narration_aligned.json").write_text(
            json.dumps(
                {
                    "segments": rebased["narration_aligned"],
                    "method": sync_res.data.get("alignment_method", "unknown"),
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (arts_dir / "word_captions.json").write_text(
            json.dumps(rebased["word_captions"], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        if formatted_srt_path:
            Path(formatted_srt_path).write_text(
                rebased["formatted_srt"], encoding="utf-8"
            )
        summary["stage_4c"] = {
            "status": sync_plan.get("status"),
            "total_duration_seconds": sync_plan.get("total_duration_seconds"),
            "issues": len(sync_plan.get("issues", [])),
        }
        tracker.finish(
            "multimedia_synchronization",
            {"multimedia_sync_plan_path": str(arts_dir / "multimedia_sync_plan.json")},
            metadata=summary["stage_4c"],
            total_spent_usd=total_cost,
        )

        # ── Stage 5: Author and render the locked HyperFrames composition ─────
        tracker.begin("composition")
        print("[Stage 5] Authoring locked educational HyperFrames workspace...")
        workspace = out_root / "hyperframes-final"
        render_policy = reg.get("render_policy", {})
        template_path = _ROOT / render_policy.get(
            "ui_template_contract_path", "styles/hyperframes-educational-v1.yaml"
        )
        receipt_path = arts_dir / "pre-render-regression-receipt.json"
        if not dry_run:
            try:
                receipt = _create_strict_production_pre_render_receipt(
                    project_dir=out_root,
                    artifacts_dir=arts_dir,
                    voice_id=str(audio_provider.get("voice_id", "nova")),
                    model_id=str(audio_provider.get("model_id", "text-to-speech")),
                    speed=float(
                        delivery.get(
                            "narration_speed", audio_provider.get("speed", 0.85)
                        )
                    ),
                )
                summary["pre_render_regression_receipt"] = {
                    "path": str(receipt_path),
                    "status": receipt.get("status"),
                    "input_sha256": receipt.get("input_sha256", {}),
                    "media_count": len(receipt.get("media_sha256", {})),
                }
            except Exception as exc:
                tracker.fail("composition", f"Pre-render regression gate failed: {exc}")
                return ToolResult(
                    success=False,
                    error=f"Stage 5 pre-render regression gate failed: {exc}",
                )
        composition_clip_manifest = clip_manifest
        if dry_run:
            # A dry run verifies planning, source coverage, timing and authored
            # structure without generating media. Remove the future output
            # paths so the composer can materialize the reviewable timeline
            # without pretending that provider clips already exist.
            composition_clip_manifest = []
            for clip in clip_manifest:
                planned_clip = dict(clip)
                for path_key in (
                    "output_path",
                    "video_path",
                    "clip_path",
                    "audio_path",
                    "path",
                    "asset_path",
                ):
                    planned_clip.pop(path_key, None)
                planned_clip.pop("visual_segments", None)
                planned_clip["render_mode"] = "hyperframes"
                composition_clip_manifest.append(planned_clip)

        authored = EducationalHyperFramesComposer().execute({
            "workspace_path": str(workspace),
            "template_contract": str(template_path),
            "template_package_sha256": render_policy.get(
                "ui_template_package_sha256"
            ),
            "educational_plan": plan,
            "clip_manifest": composition_clip_manifest,
            "narration_manifest": narration_manifest,
            "multimedia_sync_plan": sync_plan,
            "word_captions": rebased["word_captions"],
            "asset_base_dir": str(out_root),
            "strict_educational_regression": not dry_run,
            "pre_render_regression_receipt": str(
                receipt_path
            ) if not dry_run else "",
        })
        if not authored.success:
            tracker.fail("composition", authored.error or "HyperFrames authoring failed")
            return ToolResult(success=False, error=f"Stage 5 authoring failed: {authored.error}")

        final_source_coverage: dict[str, Any] | None = None
        if coverage is not None:
            try:
                authored_timeline = json.loads(
                    Path(authored.data["timeline_json"]).read_text(encoding="utf-8")
                )
                final_source_coverage = validate_final_source_coverage(
                    coverage,
                    educational_plan=plan,
                    narration_manifest=narration_manifest,
                    clip_manifest=clip_manifest,
                    composition_timeline=authored_timeline,
                    require_complete=bool(
                        reg.get("automation_policy", {}).get(
                            "fail_on_missing_source_coverage", True
                        )
                    ),
                )
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                tracker.fail("composition", str(exc))
                return ToolResult(
                    success=False,
                    error=f"Stage 5 final source coverage failed: {exc}",
                )
            (arts_dir / "final_source_coverage.json").write_text(
                json.dumps(final_source_coverage, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        if reg.get("source_document"):
            from tools.analysis.chapter_coverage_audit import audit_chapter
            evidence = audit_chapter(
                json.loads(Path(reg["source_document"]).read_text(encoding="utf-8")),
                plan, narration_manifest,
                json.loads(Path(authored.data["timeline_json"]).read_text(encoding="utf-8")),
            )
            (arts_dir / "authored_coverage_audit.json").write_text(
                json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
            if (not dry_run and reg.get("content_policy", {}).get("require_authored_coverage_audit")
                    and evidence["status"] != "pass"):
                tracker.fail("composition", "Unresolved source-to-screen/narration evidence")
                return ToolResult(success=False, error="Authored coverage gate blocked; inspect artifacts/authored_coverage_audit.json")

        composed_path = final_dir / f"{subject}_chapter.mp4"
        if dry_run:
            final_path = composed_path
            compose_steps = {"status": "not_rendered_dry_run"}
        else:
            render_policy = reg.get("render_policy", {})
            rendered = HyperFramesCompose().execute({
                "operation": "render_existing",
                "workspace_path": str(workspace),
                "output_path": str(composed_path),
                "quality": inputs.get("quality", "standard"),
                "fps": 30,
                "strict": True,
                "strict_check": True,
                "snapshots": True,
                "skip_contrast": False,
                "workers": int(render_policy.get("workers", 1)),
                "low_memory_mode": bool(
                    render_policy.get("low_memory_mode", True)
                ),
            })
            if not rendered.success:
                tracker.fail("composition", rendered.error or "HyperFrames render failed")
                return ToolResult(success=False, error=f"Stage 5 render failed: {rendered.error}")
            final_path = Path(rendered.data["output"])
            compose_steps = rendered.data.get("steps", {})

        srt_path = Path(formatted_srt_path) if formatted_srt_path else None

        # Copy SRT alongside the video for external use
        if srt_path and srt_path.is_file():
            dest_srt = final_dir / f"{subject}_chapter.srt"
            import shutil as _shu
            _shu.copy2(str(srt_path), str(dest_srt))

        summary["stage_5"] = {
            "runtime": "hyperframes",
            "workspace": str(workspace),
            "output": str(final_path),
            "template_sha256": authored.data.get("template_sha256"),
            "video_count": authored.data.get("video_count"),
            "audio_count": authored.data.get("audio_count"),
            "caption_group_count": authored.data.get("caption_group_count"),
            "source_coverage": final_source_coverage,
            "steps": compose_steps,
        }

        # ── Stage 6: Final stage director (full agent tour) ──────────────────
        print(f"[Stage 6] Running final stage inspection + agent tour...")
        from tools.analysis.final_stage_director import FinalStageDirector
        fsd_res = FinalStageDirector().execute({
            "video_path":           str(final_path),
            "srt_path":             str(formatted_srt_path) if formatted_srt_path else "",
            "subject":              subject,
            "chapter_title":        chapter_title,
            "narration_manifest":   narration_manifest,
            "educational_plan":     plan,
            "clip_manifest":        clip_manifest,
            "evs_alignment":        evs.get("A", {}),
            "scenes":               enriched_sections,
            "title_offset_seconds": 0.0,
            "render_runtime":        reg.get("render_policy", {}).get(
                "runtime", "hyperframes"
            ),
            "output_dir":           str(out_root),
            "dry_run":              dry_run,
        })
        all_passed  = fsd_res.data.get("all_passed", False) if fsd_res.success else False
        tour_path   = fsd_res.data.get("agent_tour_path", "") if fsd_res.success else ""
        export_path = fsd_res.data.get("export_path", "") if fsd_res.success else ""
        summary["stage_6"] = {
            "all_passed":      all_passed,
            "status":          fsd_res.data.get("status", "unknown") if fsd_res.success else "error",
            "action":          fsd_res.data.get("action", "") if fsd_res.success else "",
            "agent_tour_path": tour_path,
            "export_path":     export_path,
        }

        final_review = (
            fsd_res.data.get("final_review", {}) if fsd_res.success else {}
        )
        if dry_run or not final_review:
            final_review = {
                "version": "1.0",
                "output_path": str(final_path),
                "status": "revise" if dry_run else "fail",
                "checks": {
                    "technical_probe": {
                        "valid_container": False,
                        "duration_seconds": float(
                            sync_plan.get("total_duration_seconds") or 0.0
                        ),
                        "resolution": "1920x1080",
                        "fps": 30.0,
                        "has_audio": False,
                        "codec": "not-rendered" if dry_run else "unknown",
                        "issues": [
                            "Dry run: encoded output was not created."
                            if dry_run
                            else "Final-stage inspection did not return a review."
                        ],
                    },
                    "visual_spotcheck": {
                        "frames_sampled": 4,
                        "frame_paths": [],
                        "black_frames_detected": False,
                        "broken_overlays": False,
                        "missing_assets": False,
                        "unreadable_text": False,
                        "issues": ["Pending encoded-output inspection."],
                    },
                    "audio_spotcheck": {
                        "narration_present": False,
                        "music_present": False,
                        "unexpected_silence": False,
                        "clipping_detected": False,
                        "mix_intelligible": False,
                        "issues": ["Pending encoded-output inspection."],
                    },
                    "promise_preservation": {
                        "delivery_promise_honored": False,
                        "renderer_family_used": "animation-first",
                        "render_runtime_used": "hyperframes",
                        "runtime_swap_detected": False,
                        "runtime_swap_check": "ok - HyperFrames remains selected",
                        "motion_ratio_actual": 0.0,
                        "silent_downgrade_detected": False,
                        "issues": ["Pending encoded-output inspection."],
                    },
                    "subtitle_check": {
                        "subtitles_expected": True,
                        "subtitles_present": bool(formatted_srt_path),
                        "coverage_ratio": 0.0,
                        "timing_drift_detected": False,
                        "issues": ["Pending encoded-output inspection."],
                    },
                },
                "issues_found": ["Encoded-output QA is pending."],
                "recommended_action": "re_render" if not dry_run else "revise_edit",
                "metadata": {"dry_run": bool(dry_run)},
            }

        technical = final_review.get("checks", {}).get("technical_probe", {})
        render_report = {
            "version": "1.0",
            "outputs": [
                {
                    "path": str(final_path),
                    "format": "mp4",
                    "codec": str(technical.get("codec") or "h264"),
                    "audio_codec": "aac" if not dry_run else "not-rendered",
                    "resolution": str(technical.get("resolution") or "1920x1080"),
                    "fps": float(technical.get("fps") or 30.0),
                    "duration_seconds": float(
                        technical.get("duration_seconds")
                        or sync_plan.get("total_duration_seconds")
                        or 0.0
                    ),
                }
            ],
            "render_time_seconds": round(time.monotonic() - start, 3),
            "warnings": list(final_review.get("issues_found") or []),
            "verification_notes": [
                "Encoded output inspected by FinalStageDirector."
                if not dry_run
                else "Dry run completed; encoded-output inspection is pending."
            ],
            "render_grammar": "animation-first",
            "slideshow_risk_score": {
                "average": 0.0,
                "verdict": "pending" if dry_run else str(final_review.get("status")),
            },
            "decision_log_ref": str(out_root / "decision_log.json"),
            "final_review_ref": str(arts_dir / "final_review.json"),
            "metadata": {
                "render_runtime": "hyperframes",
                "dry_run": bool(dry_run),
                "workspace": str(workspace),
            },
        }
        try:
            validate_artifact("final_review", final_review)
            validate_artifact("render_report", render_report)
        except Exception as exc:
            tracker.fail("composition", f"Final artifacts invalid: {exc}")
            return ToolResult(
                success=False,
                error=f"Stage 5 final artifacts invalid: {exc}",
            )
        (arts_dir / "final_review.json").write_text(
            json.dumps(final_review, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (arts_dir / "render_report.json").write_text(
            json.dumps(render_report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        tracker.finish(
            "composition",
            {"render_report": render_report, "final_review": final_review},
            metadata=summary["stage_5"],
            review={
                "status": final_review.get("status"),
                "recommended_action": final_review.get("recommended_action"),
            },
            total_spent_usd=total_cost,
        )

        tracker.begin("quality_assurance")
        if not dry_run and (not fsd_res.success or not all_passed):
            tracker.fail(
                "quality_assurance",
                "Final encoded-output QA did not pass",
                metadata={"review_video": str(final_path)},
            )
            return ToolResult(
                success=False,
                error=(
                    "Stage 6 failed: final encoded-output QA did not pass; "
                    "the render remains a review artifact and was not exported"
                ),
                data={"stages_summary": summary, "review_video": str(final_path)},
            )

        # ── Cost log ──────────────────────────────────────────────────────────
        cost_log = {
            "subject": subject,
            "total_cost_usd": round(total_cost, 4),
            "stages": summary,
        }
        (arts_dir / "cost_log.json").write_text(
            json.dumps(cost_log, indent=2), encoding="utf-8"
        )

        publish_log = {
            "version": "1.0",
            "entries": [
                {
                    "platform": "local",
                    "status": (
                        "draft"
                        if dry_run
                        else "exported"
                        if export_path
                        else "pending_review"
                    ),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "visibility": "private",
                    "export_path": str(export_path or final_path),
                }
            ],
            "metadata": {
                "subject": subject,
                "chapter_title": chapter_title,
                "dry_run": bool(dry_run),
            },
        }
        try:
            validate_artifact("publish_log", publish_log)
        except Exception as exc:
            tracker.fail("quality_assurance", f"publish_log invalid: {exc}")
            return ToolResult(
                success=False, error=f"Stage 6 publish_log invalid: {exc}"
            )
        (arts_dir / "publish_log.json").write_text(
            json.dumps(publish_log, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        qa_status = tracker.finish(
            "quality_assurance",
            {"publish_log": publish_log},
            metadata=summary["stage_6"],
            review={
                "status": final_review.get("status"),
                "recommended_action": final_review.get("recommended_action"),
            },
            total_spent_usd=total_cost,
        )
        from tools.structure.educational_run_tracker import write_status_json
        status_path = write_status_json(out_root)
        if qa_status == "awaiting_human":
            return ToolResult(
                success=True,
                data={
                    "status": "awaiting_human",
                    "stage": "quality_assurance",
                    "project_dir": str(out_root),
                    "review_video": "" if dry_run else str(final_path),
                    "status_path": str(status_path),
                    "cost_usd": round(total_cost, 4),
                    "stages_summary": summary,
                },
                artifacts=["render_report", "final_review", "publish_log"],
                cost_usd=round(total_cost, 4),
            )

        if dry_run:
            print(f"\n✓ Dry run complete → {summary['stage_5']['workspace']}")
        else:
            print(f"\n✓ Done → {final_path}")
        print(f"  Total cost: ${total_cost:.4f} | Time: {time.monotonic()-start:.1f}s")

        return ToolResult(
            success=True,
            data={
                "final_video":    "" if dry_run else str(final_path),
                "workspace_path": summary["stage_5"]["workspace"],
                "status": "completed",
                "status_path": str(status_path),
                "cost_usd":       round(total_cost, 4),
                "stages_summary": summary,
            },
            artifacts=["render_report", "publish_log"],
            cost_usd=round(total_cost, 4),
            duration_seconds=time.monotonic() - start,
            seed=seed,
        )

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {
            "tool": self.name,
            "estimated_cost_usd": 0.0,
            "estimated_runtime_seconds": self.estimate_runtime(inputs),
            "status": self.get_status().value,
            "would_execute": True,
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:
    from tools.structure.subject_registry import all_subject_ids
    ap = argparse.ArgumentParser(description="EduStream Pro — subject pipeline runner.")
    ap.add_argument(
        "--subject",
        choices=all_subject_ids(),
        help=f"Subject to process. Registered: {', '.join(all_subject_ids())}. "
             "Add new subjects to tools/structure/subject_registry.py.",
    )
    ap.add_argument("--chapter-config", dest="chapter_config_path")
    ap.add_argument("--educational-plan", dest="educational_plan_path")
    ap.add_argument("--dry-run", dest="dry_run", action="store_true")
    ap.add_argument("--output-dir", dest="output_dir")
    ap.add_argument("--quality", default="medium")
    args = ap.parse_args()

    if not args.subject and not args.chapter_config_path:
        ap.error("provide either --subject or --chapter-config")

    inp: dict[str, Any] = {
        "subject":  args.subject or "dynamic-chapter",
        "dry_run":  args.dry_run,
        "quality":  args.quality,
    }
    if args.output_dir:
        inp["output_dir"] = args.output_dir
    if args.chapter_config_path:
        inp["chapter_config_path"] = args.chapter_config_path
    if args.educational_plan_path:
        inp["educational_plan_path"] = args.educational_plan_path

    res = SubjectPipelineRunner().execute(inp)
    if res.success:
        print(f"\nFinal video: {res.data['final_video']}")
        print(f"Total cost : ${res.data['cost_usd']:.4f}")
    else:
        print(f"Pipeline failed: {res.error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _cli()
