"""SubjectPipelineRunner — end-to-end chapter video builder.

Chains all EduStream Pro stages for one subject:

  Stage 0  SectionParser           markdown → ContentBlock[]
  Stage 1  EducationalContentGenerator  blocks → educational_plan
  Stage 2  EduStreamOrchestrator    plan → enriched EVS script
  Stage 3  VoiceSynthesisPipeline  script → narration audio + STT QA
  Stage 4  NarrationTextSyncer     audio → word captions + Q&A timing
  Stage 5  RenderModeRouter        timed script → clip per section
  Stage 6  MultimediaSyncPlanner   measured audio + clips → authoritative timeline
  Stage 7  AVComposer              clips + audio + subtitles → chapter_final.mp4
  Stage 8  QualityAssurance        pacing / sync / contrast / WPM / slideshow checks

This compatibility runner executes in one process and is not checkpoint-resumable.
For agent-managed resumable production, use the manifest-driven
`educational-video` pipeline and `lib/checkpoint.py`.
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
from tools.structure.educational_generator import EducationalContentGenerator  # noqa: E402
from tools.structure.edustream_orchestrator import EduStreamOrchestrator  # noqa: E402
from tools.structure.subject_registry import get_subject, md_path as _md_path  # noqa: E402
from tools.structure.chapter_config import load_chapter_config, registry_view  # noqa: E402
from tools.video.render_mode_router import RenderModeRouter  # noqa: E402
from tools.voice.voice_synthesis_pipeline import VoiceSynthesisPipeline  # noqa: E402
from tools.video.av_composer import AVComposer  # noqa: E402
from tools.video.hyperframes_chapter_title import HyperFramesChapterTitle  # noqa: E402

_ODL_DIR = Path(
    os.environ.get(
        "OPENDATALOADER_OUTPUT_DIR",
        r"C:\Users\user\Downloads\opendataloader_output",
    )
)


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
    capabilities = ["full_pipeline", "resumable", "cost_tracking"]

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
        return 0.0  # all free/unlimited models

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

        # ── Stage 0: Section Parsing ─────────────────────────────────────────
        print(f"[Stage 0] Parsing markdown for {subject}...")
        parser_res = SectionParser().execute({
            "subject":    subject,
            "md_path":    str(subject_md_path),
            "output_dir": str(arts_dir),
        })
        if not parser_res.success:
            return ToolResult(success=False, error=f"Stage 0 failed: {parser_res.error}")
        blocks     = parser_res.data["blocks"]
        source_manifest_path = arts_dir / "source_text_manifest.json"
        source_manifest = write_source_manifest(subject_md_path, source_manifest_path)
        block_text = "\n\n".join(
            f"## {b['heading']}\n{b['body_text'][:500]}" for b in blocks
        )
        summary["stage_0"] = {
            "blocks": parser_res.data["block_count"],
            "source_text_manifest": str(source_manifest_path),
            "source_cards": source_manifest["validation"]["card_count"],
            "max_content_lines": source_manifest["validation"]["max_content_lines"],
        }
        print(f"  ✓ {parser_res.data['block_count']} blocks")

        # ── Stage 1: Educational Plan ────────────────────────────────────────
        print(f"[Stage 1] Generating educational plan...")
        provided_plan = inputs.get("educational_plan")
        if not provided_plan and inputs.get("educational_plan_path"):
            try:
                provided_plan = json.loads(
                    Path(inputs["educational_plan_path"]).read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError) as exc:
                return ToolResult(success=False, error=f"Invalid educational_plan_path: {exc}")

        plan_res = EducationalContentGenerator().execute({
            "educational_plan":        provided_plan,
            "source_content":          block_text,
            "subject_type":            subject_type,
            "complexity_level":        reg.get("complexity", "elementary"),
            "target_audience":         target_audience,
            "total_duration_seconds":  target_duration,
            "subject":                 subject,
            "dry_run":                 dry_run,
            "seed":                    seed,
        })
        if not plan_res.success:
            return ToolResult(success=False, error=f"Stage 1 failed: {plan_res.error}")
        plan = plan_res.data["educational_plan"]
        total_cost += plan_res.cost_usd or 0.0

        # Enrich plan sections with qa_pairs from parser blocks
        block_map = {b["block_id"]: b for b in blocks}
        for i, sec in enumerate(plan.get("sections", [])):
            # Inject qa_pairs from matching block if available
            btype = sec.get("source_block_type", "")
            for b in blocks:
                if b["block_type"] == btype and b.get("qa_pairs"):
                    sec["qa_pairs"] = b["qa_pairs"]
                    break

        (arts_dir / "educational_plan.json").write_text(
            json.dumps(plan, indent=2), encoding="utf-8"
        )
        summary["stage_1"] = {"sections": len(plan.get("sections", []))}
        print(f"  ✓ {len(plan.get('sections', []))} sections")

        # ── Stage 2: Orchestration ───────────────────────────────────────────
        print(f"[Stage 2] Running orchestration + critique loops...")
        orch_res = EduStreamOrchestrator().execute({
            "educational_plan": plan,
            "subject":          subject,
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

        # ── Chapter title card (HyperFrames) ─────────────────────────────────
        print(f"[Stage 2b] Generating chapter title card...")
        title_res = HyperFramesChapterTitle().execute({
            "subject":    subject,
            "chapter":    chapter_num,
            "title":      chapter_title,
            "output_dir": str(clips_dir),
            "dry_run":    dry_run,
        })
        title_clip = title_res.data.get("video_path", "") if title_res.success else ""

        # ── Stage 2c: Character bible ─────────────────────────────────────────
        print(f"[Stage 2c] Building character reference bible for {subject}...")
        from tools.video.character_consistency import CharacterBible
        try:
            bible = CharacterBible().generate(subject=subject, dry_run=dry_run)
            n_chars = len(bible.get("characters", {}))
            print(f"  ✓ {n_chars} character reference(s) ready")
            summary["stage_2c"] = {"characters": n_chars}
        except Exception as exc:
            # Non-fatal — video_gen will fall back to direct t2v
            print(f"  ⚠ Character bible skipped: {exc}")
            summary["stage_2c"] = {"characters": 0, "warning": str(exc)}

        # ── Stage 4: Voice synthesis ─────────────────────────────────────────
        print(f"[Stage 4] Synthesising narration...")
        nar_segments = [
            {
                "section_id":        s["section_id"],
                "text":              s.get("narration_script", ""),
                "source_block_type": s.get("source_block_type", "concept"),
                "duration_seconds":  s.get("duration_seconds", 30),
            }
            for s in enriched_sections
            if s.get("narration_script")
        ]
        voice_res = VoiceSynthesisPipeline().execute({
            "narration_segments": nar_segments,
            "output_dir":         str(audio_dir),
            "dry_run":            dry_run,
            "seed":               seed,
        })
        if not voice_res.success:
            return ToolResult(success=False, error=f"Stage 4 failed: {voice_res.error}")
        narration_manifest = voice_res.data["narration_manifest"]
        # Inject start_seconds from alignment timeline (single authoritative build)
        alignment_timeline = {
            t["section_id"]: t
            for t in evs.get("A", {}).get("timeline", [])
        }
        for seg in narration_manifest["segments"]:
            t = alignment_timeline.get(seg["section_id"], {})
            seg["start_seconds"] = t.get("start_seconds", 0.0)

        (arts_dir / "narration_manifest.json").write_text(
            json.dumps(narration_manifest, indent=2), encoding="utf-8"
        )
        summary["stage_4"] = {
            "segments": len(narration_manifest["segments"]),
            "qa_issues": len(voice_res.data.get("qa_report", {}).get("qa_issues", [])),
        }
        print(f"  ✓ {len(narration_manifest['segments'])} narration segments")

        # ── Stage 4b: Text-audio alignment ───────────────────────────────────
        # MUST run before Stage 3 so qa_card_props.json exists when
        # RenderModeRouter calls _render_remotion with audio-derived reveal timings.
        print(f"[Stage 4b] Aligning text to audio (word-level sync)...")
        from tools.analysis.narration_text_syncer import NarrationTextSyncer
        sync_res = NarrationTextSyncer().execute({
            "narration_manifest":    narration_manifest,
            "educational_plan":      plan,
            "output_dir":            str(arts_dir),
            "title_offset_seconds":  3.0 if (title_clip and Path(title_clip).exists()) else 0.0,
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
        else:
            print(f"  ⚠ Text sync failed ({sync_res.error}) — using basic SRT")

        # ── Stage 3: Render clips ────────────────────────────────────────────
        # Runs AFTER Stage 4b so qa_card_props.json is on disk and
        # _render_remotion can load audio-derived reveal timings.
        print(f"[Stage 3] Dispatching {len(enriched_sections)} clips to renderers...")
        router_res = RenderModeRouter().execute({
            "educational_plan": plan,
            "subject":          subject,
            "chapter":          chapter_num,
            "output_dir":       str(clips_dir),
            "dry_run":          dry_run,
            "seed":             seed,
            "qa_card_props_path": str(arts_dir / "qa_card_props.json"),
        })
        if not router_res.success and router_res.data.get("failed_clips", 0) > 0:
            print(f"  ⚠ {router_res.data['failed_clips']} clips failed — continuing with available clips")
        clip_manifest = router_res.data["clip_manifest"]
        summary["stage_3"] = {
            "total":   router_res.data["total_clips"],
            "skipped": router_res.data["skipped_clips"],
            "failed":  router_res.data["failed_clips"],
        }
        print(f"  ✓ {router_res.data['total_clips']} clips"
              f" ({router_res.data['skipped_clips']} skipped)")

        # ── Stage 4c: Authoritative multimedia synchronization ───────────────
        # Reconcile measured narration and rendered clip durations before
        # composition.  This is the only place that assigns global start/end
        # positions; title offsets must never be added again downstream.
        print("[Stage 4c] Building authoritative multimedia timeline...")
        from tools.analysis.multimedia_sync_planner import MultimediaSyncPlanner
        sync_plan_res = MultimediaSyncPlanner().execute({
            "narration_manifest": narration_manifest,
            "clip_manifest": clip_manifest,
            "title_offset_seconds": 3.0 if (title_clip and Path(title_clip).exists()) else 0.0,
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
            return ToolResult(success=False, error=f"Stage 4c failed: {sync_plan_res.error}")
        summary["stage_4c"] = {
            "status": sync_plan.get("status"),
            "total_duration_seconds": sync_plan.get("total_duration_seconds"),
            "issues": len(sync_plan.get("issues", [])),
        }

        # ── Stage 5: Compose video ───────────────────────────────────────────
        print(f"[Stage 5] Composing final video...")
        # Collect ordered clip paths (title card first, then content clips)
        ordered_clips = []
        if title_clip and Path(title_clip).exists():
            ordered_clips.append(title_clip)
        for cm in clip_manifest:
            vp = cm.get("video_path", "")
            if vp and Path(vp).exists() and cm.get("success"):
                ordered_clips.append(vp)

        if not ordered_clips:
            return ToolResult(success=False, error="No rendered clips available for composition")

        # The authoritative multimedia planner assigned start/end positions.
        # Do not add the title offset again downstream.

        composed_path = final_dir / f"{subject}_chapter.mp4"

        compose_res = AVComposer().execute({
            "video_segments":     ordered_clips,
            "narration_manifest": narration_manifest,
            "output_path":        str(composed_path),
            "target_lufs":        -14.0,
            "burn_subtitles":     True,
            "subtitle_style":     (
                "FontName=Arial,FontSize=22,"
                "PrimaryColour=&H00FFFFFF,"
                "OutlineColour=&H00000000,"
                "Outline=2,Alignment=2,MarginV=36"
            ),
            "formatted_srt_path": str(formatted_srt_path) if formatted_srt_path else None,
            "dry_run":            dry_run,
        })
        if not compose_res.success:
            return ToolResult(success=False, error=f"Stage 5 failed: {compose_res.error}")

        # AVComposer now handles subtitle burn internally — no second ffmpeg call needed
        final_path = Path(compose_res.data["final_render"])
        srt_path   = Path(compose_res.data.get("subtitle_path", ""))

        # Copy SRT alongside the video for external use
        if srt_path.exists():
            dest_srt = final_dir / f"{subject}_chapter.srt"
            import shutil as _shu
            _shu.copy2(str(srt_path), str(dest_srt))

        summary["stage_5"] = {"output": str(final_path)}

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
            "title_offset_seconds": 3.0 if title_clip else 0.0,
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

        # ── Cost log ──────────────────────────────────────────────────────────
        total_cost += sum(
            cm.get("cost_usd", 0.0) for cm in clip_manifest
        )
        cost_log = {
            "subject": subject,
            "total_cost_usd": round(total_cost, 4),
            "stages": summary,
        }
        (arts_dir / "cost_log.json").write_text(
            json.dumps(cost_log, indent=2), encoding="utf-8"
        )

        print(f"\n✓ Done → {final_path}")
        print(f"  Total cost: ${total_cost:.4f} | Time: {time.monotonic()-start:.1f}s")

        return ToolResult(
            success=True,
            data={
                "final_video":    str(final_path),
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

    res = SubjectPipelineRunner().execute(inp)
    if res.success:
        print(f"\nFinal video: {res.data['final_video']}")
        print(f"Total cost : ${res.data['cost_usd']:.4f}")
    else:
        print(f"Pipeline failed: {res.error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _cli()
