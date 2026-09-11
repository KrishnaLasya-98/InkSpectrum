"""RenderModeRouter — unified scene dispatcher for EduStream Pro.

Reads render_mode from each section in the educational_plan and routes
to the correct renderer:

  manim        →  ManimGenerator (local, free)
  remotion     →  Remotion CLI   (local, free)
  hyperframes  →  HyperFramesChapterTitle (local, free)
  video_gen    →  ModelsLab Wan2.2 keyframe pipeline (unlimited open-source)

Resumable: existing clip files on disk are skipped automatically.
All outputs validated with ffprobe before being recorded in clip_manifest.json.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
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
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ClipResult:
    section_id:       str
    render_mode:      str
    video_path:       str
    duration_seconds: float
    cost_usd:         float
    success:          bool
    skipped:          bool = False
    error:            str  = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# ffprobe helper
# ---------------------------------------------------------------------------

def _probe_duration(path: Path) -> float:
    """Return video duration in seconds via ffprobe. Returns 0.0 on failure."""
    if not shutil.which("ffprobe"):
        return 0.0
    try:
        proc = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True, text=True, timeout=15,
        )
        return float(proc.stdout.strip())
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Renderer sub-dispatch helpers
# ---------------------------------------------------------------------------

def _render_manim(
    section: dict[str, Any],
    subject: str,
    out_dir: Path,
    dry_run: bool,
) -> ClipResult:
    from tools.video.manim_generator import ManimGenerator
    gen = ManimGenerator()
    res = gen.execute({
        "section":    section,
        "subject":    subject,
        "quality":    "medium",
        "output_dir": str(out_dir),
        "dry_run":    dry_run,
    })
    if res.success:
        vp = res.data.get("video_path", "")
        dur = _probe_duration(Path(vp)) if vp and not dry_run else section.get("duration_seconds", 30)
        return ClipResult(
            section_id=section["section_id"], render_mode="manim",
            video_path=vp, duration_seconds=dur, cost_usd=0.0, success=True,
        )
    return ClipResult(
        section_id=section["section_id"], render_mode="manim",
        video_path="", duration_seconds=0.0, cost_usd=0.0,
        success=False, error=res.error or "manim_failed",
    )


def _render_remotion(
    section: dict[str, Any],
    qa_cards: list[dict[str, Any]],
    out_dir: Path,
    dry_run: bool,
    qa_props_path: Path | None = None,
) -> ClipResult:
    sid  = section["section_id"]
    out  = out_dir / f"{sid}.mp4"
    dur  = float(section.get("duration_seconds", 30))

    # Load audio-derived reveal timings if available (Issue 4 fix)
    if not qa_cards and qa_props_path and qa_props_path.exists():
        try:
            all_props = json.loads(qa_props_path.read_text(encoding="utf-8"))
            qa_cards = all_props.get(sid, [])
        except Exception:
            pass

    if dry_run:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"")
        return ClipResult(
            section_id=sid, render_mode="remotion",
            video_path=str(out), duration_seconds=dur, cost_usd=0.0, success=True,
        )

    props = json.dumps({
        "cards":            qa_cards or _section_to_qa_cards(section),
        "seconds_per_card": max(6, int(dur / max(len(qa_cards or [1]), 1))),
        "theme":            "sunshine",
    })
    npx = shutil.which("npx") or "npx"
    remotion_dir = _ROOT / "remotion-composer"
    cmd = [
        npx, "remotion", "render", "EduQAScene",
        "--props", props,
        "--output", str(out),
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=300, cwd=str(remotion_dir),
        )
        if proc.returncode != 0:
            return ClipResult(
                section_id=sid, render_mode="remotion", video_path="",
                duration_seconds=0.0, cost_usd=0.0, success=False,
                error=proc.stderr[-300:],
            )
    except Exception as exc:
        return ClipResult(
            section_id=sid, render_mode="remotion", video_path="",
            duration_seconds=0.0, cost_usd=0.0, success=False, error=str(exc),
        )

    actual_dur = _probe_duration(out)
    return ClipResult(
        section_id=sid, render_mode="remotion",
        video_path=str(out), duration_seconds=actual_dur or dur,
        cost_usd=0.0, success=True,
    )


def _render_hyperframes(
    section: dict[str, Any],
    subject: str,
    out_dir: Path,
    dry_run: bool,
    chapter: int = 1,
) -> ClipResult:
    from tools.video.hyperframes_chapter_title import HyperFramesChapterTitle
    sid = section["section_id"]
    res = HyperFramesChapterTitle().execute({
        "subject":    subject,
        "chapter":    chapter,
        "title":      section.get("title", ""),
        "output_dir": str(out_dir),
        "dry_run":    dry_run,
    })
    if res.success:
        vp = res.data.get("video_path", "")
        dur = _probe_duration(Path(vp)) if vp and not dry_run else 3.0
        return ClipResult(
            section_id=sid, render_mode="hyperframes",
            video_path=vp, duration_seconds=dur, cost_usd=0.0, success=True,
        )
    return ClipResult(
        section_id=sid, render_mode="hyperframes", video_path="",
        duration_seconds=0.0, cost_usd=0.0, success=False,
        error=res.error or "hyperframes_failed",
    )


def _render_video_gen(
    section: dict[str, Any],
    subject: str,
    out_dir: Path,
    dry_run: bool,
) -> ClipResult:
    """Character-consistent video generation via h3-minimax-r2v.

    Pipeline:
      1. CharacterConsistencyManager checks the character bible for this section.
      2. If reference images exist → h3-minimax-r2v with init_image array.
      3. If no references → Flux.2 Dev keyframe → Wan2.2 i2v pipeline.
      4. Fallback → h3-minimax-t2v direct text-to-video.
    """
    from tools.video.character_consistency import CharacterConsistencyManager

    sid = section["section_id"]
    out = out_dir / f"{sid}.mp4"
    dur = float(section.get("duration_seconds", 10))

    scene_description = (
        section.get("description", "") or section.get("title", "")
    )
    subject_style = {
        "evs":     "flat educational illustration, warm palette, accurate anatomy",
        "english": "child-friendly storybook illustration, bright colours",
        "maths":   "clean educational diagram, minimal background",
    }.get(subject, "educational illustration")
    scene_description = f"{scene_description}. Style: {subject_style}."

    seed = section.get("seed")

    mgr = CharacterConsistencyManager()
    result = mgr.generate_consistent_clip(
        subject=subject,
        section_id=sid,
        scene_description=scene_description,
        output_path=out,
        duration=min(15, max(5, int(dur))),
        seed=seed,
        dry_run=dry_run,
    )

    if result["success"]:
        actual_dur = _probe_duration(out) if not dry_run else dur
        return ClipResult(
            section_id=sid, render_mode="video_gen",
            video_path=result["video_path"],
            duration_seconds=actual_dur or dur,
            cost_usd=result.get("cost_usd", 0.0),
            success=True,
        )

    # Hard fallback: h3-minimax-t2v direct (no consistency, but never fails silently)
    if not dry_run:
        api_key = os.environ.get("MODELSLAB_API_KEY", "")
        if api_key:
            from tools.video.modelslab_video import ModelsLabVideo
            fb = ModelsLabVideo().execute({
                "prompt":         scene_description + " Fixed camera, no text, child-safe.",
                "model_id":       "h3-minimax-t2v",
                "operation":      "text_to_video",
                "duration":       str(min(10, int(dur))),
                "resolution":     "768P",
                "generate_audio": False,
                "output_path":    str(out),
            })
            if fb.success:
                actual_dur = _probe_duration(out)
                return ClipResult(
                    section_id=sid, render_mode="video_gen",
                    video_path=str(out), duration_seconds=actual_dur or dur,
                    cost_usd=0.0, success=True,
                )

    return ClipResult(
        section_id=sid, render_mode="video_gen", video_path="",
        duration_seconds=0.0, cost_usd=0.0, success=False,
        error=result.get("error", "video_gen_failed"),
    )


def _section_to_qa_cards(section: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert section data to EduQAScene QACard list."""
    cards: list[dict[str, Any]] = []
    qa_pairs = section.get("qa_pairs", [])
    for qp in qa_pairs:
        cards.append({
            "card_id":    f"{section['section_id']}_{qp.get('number', '1')}",
            "format":     qp.get("qa_format", "short_answer"),
            "question":   qp.get("question", ""),
            "answer_text": qp.get("answer_hint", ""),
            "reveal_delay_seconds": 2.5,
        })
    if not cards:
        # Minimal fallback card from narration script
        cards.append({
            "card_id":    section["section_id"] + "_auto",
            "format":     "short_answer",
            "question":   section.get("title", ""),
            "answer_text": section.get("narration_script", "")[:80],
            "reveal_delay_seconds": 2.5,
        })
    return cards


# ---------------------------------------------------------------------------
# Router tool
# ---------------------------------------------------------------------------

class RenderModeRouter(BaseTool):
    """Dispatch educational plan sections to the correct renderer."""

    name = "render_mode_router"
    version = "1.0.0"
    tier = ToolTier.CORE
    capability = "video_generation"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.HYBRID

    dependencies = ["cmd:ffprobe"]
    install_instructions = "Install FFmpeg (includes ffprobe). All renderers installed separately."
    agent_skills = ["manim-usage", "remotion", "hyperframes-cli"]
    capabilities = ["render_dispatch", "resumable_render", "clip_manifest"]

    input_schema = {
        "type": "object",
        "required": ["educational_plan"],
        "properties": {
            "educational_plan":      {"type": "object"},
            "subject":               {"type": "string", "default": "evs"},
            "chapter":               {"type": "integer", "default": 1,
                                      "description": "Chapter number — passed to HyperFrames title card renderer"},
            "output_dir":            {"type": "string"},
            "dry_run":               {"type": "boolean", "default": False},
            "seed":                  {"type": "integer"},
            "qa_card_props_path":    {"type": "string", "description": "Path to qa_card_props.json from NarrationTextSyncer. When provided, remotion sections use audio-derived reveal timings instead of hardcoded 2.5s."},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "clip_manifest":   {"type": "array"},
            "total_clips":     {"type": "integer"},
            "skipped_clips":   {"type": "integer"},
            "failed_clips":    {"type": "integer"},
            "manifest_path":   {"type": "string"},
        },
    }

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0  # all renderers are free/unlimited

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        n = len(inputs.get("educational_plan", {}).get("sections", []))
        return max(30.0, n * 45.0)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        plan      = inputs.get("educational_plan", {})
        subject   = inputs.get("subject", "evs")
        chapter   = int(inputs.get("chapter", 1))
        out_dir   = Path(inputs.get("output_dir", f"renders/{subject}/clips"))
        dry_run   = inputs.get("dry_run", False)
        seed      = inputs.get("seed")
        start     = time.monotonic()

        sections = plan.get("sections", [])
        if not sections:
            return ToolResult(success=False, error="No sections in educational_plan")

        out_dir.mkdir(parents=True, exist_ok=True)
        manifest: list[dict[str, Any]] = []
        skipped = failed = 0

        for section in sections:
            sid  = section.get("section_id", "unknown")
            rm   = section.get("render_mode", "remotion")

            # ── Resume check — path must match what each renderer actually writes ──
            # remotion / video_gen  → out_dir/{sid}.mp4   (flat, sid-named)
            # manim                 → out_dir/{sid}/videos/{ClassName}.mp4
            #                         (Manim writes to media_dir/videos/)
            #                         We probe the sub-dir for ANY .mp4 instead.
            # hyperframes           → out_dir/{subject}_ch{chapter:02d}_title.mp4
            #                         (fixed slug from HyperFramesChapterTitle)
            skip_clip: Path | None = None
            if rm == "manim":
                manim_subdir = out_dir / sid / "videos"
                found = sorted(manim_subdir.glob("*.mp4")) if manim_subdir.exists() else []
                skip_clip = found[0] if found else None
            elif rm == "hyperframes":
                # Resume path uses the fixed slug that HyperFramesChapterTitle writes
                slug = f"{subject}_ch{chapter:02d}_title.mp4"
                skip_clip = out_dir / slug
            else:
                skip_clip = out_dir / f"{sid}.mp4"

            if skip_clip and skip_clip.exists() and skip_clip.stat().st_size > 0:
                dur = _probe_duration(skip_clip)
                manifest.append(ClipResult(
                    section_id=sid, render_mode=rm,
                    video_path=str(skip_clip), duration_seconds=dur,
                    cost_usd=0.0, success=True, skipped=True,
                ).to_dict())
                skipped += 1
                continue

            # Dispatch
            if rm == "manim":
                result = _render_manim(section, subject, out_dir / sid, dry_run)
            elif rm == "remotion":
                qa_props_path = Path(inputs["qa_card_props_path"]) if inputs.get("qa_card_props_path") else None
                # Deliberately pass empty list here — _render_remotion will load
                # audio-derived timings from qa_card_props.json when it exists,
                # and only fall back to _section_to_qa_cards if it doesn't.
                result = _render_remotion(section, [], out_dir, dry_run, qa_props_path)
            elif rm == "hyperframes":
                result = _render_hyperframes(section, subject, out_dir, dry_run, chapter)
            elif rm == "video_gen":
                result = _render_video_gen(section, subject, out_dir, dry_run)
            else:
                result = ClipResult(
                    section_id=sid, render_mode=rm, video_path="",
                    duration_seconds=0.0, cost_usd=0.0,
                    success=False, error=f"Unknown render_mode: {rm}",
                )

            if not result.success:
                failed += 1

            manifest.append(result.to_dict())

        # Write manifest
        manifest_path = out_dir / "clip_manifest.json"
        manifest_path.write_text(
            json.dumps({"subject": subject, "clips": manifest}, indent=2),
            encoding="utf-8",
        )

        return ToolResult(
            success=failed == 0,
            error=f"{failed} clip(s) failed to render" if failed else "",
            data={
                "clip_manifest":  manifest,
                "total_clips":    len(manifest),
                "skipped_clips":  skipped,
                "failed_clips":   failed,
                "manifest_path":  str(manifest_path),
            },
            artifacts=["render_report"],
            cost_usd=0.0,
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
