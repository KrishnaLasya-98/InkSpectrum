"""RenderModeRouter — unified scene dispatcher for EduStream Pro.

Reads render_mode from each section in the educational_plan and routes
to the correct renderer:

  manim        →  ManimGenerator (local, free)
  remotion     →  Remotion CLI   (local, free)
  hyperframes  →  native surface in the final HyperFrames composition
  video_gen    →  configured ModelsLab video model (account plan required)

Resumable: generated clips are reused only when their source fingerprint still
matches and the prior QA result passed. Outputs are technically and semantically
audited before being recorded in clip_manifest.json.
"""
from __future__ import annotations

import hashlib
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
from tools.structure.subject_profiles import resolve_subject_profile  # noqa: E402

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
    content_fingerprint: str = ""
    generation_attempts: int = 0
    qa_report: dict[str, Any] | None = None
    production_state: str = ""

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


def _provider_failure_state(error: str) -> str:
    """Separate account/configuration blocks from retryable provider errors."""
    message = error.casefold()
    if any(token in message for token in (
        "exhausted", "fund your wallet", "insufficient", "unauthorized",
        "invalid api", "invalid key", "subscription", "payment required",
        "access denied", "third party access",
    )):
        return "provider_blocked"
    if any(token in message for token in ("timed out", "timeout", "processing", "pending")):
        return "provider_pending"
    return "provider_failed"


def _content_fingerprint(
    section: dict[str, Any],
    subject: str,
    provider_cfg: dict[str, Any],
) -> str:
    """Identify the exact source/prompt/provider contract for safe resume."""
    payload = {
        "section_id": section.get("section_id"),
        "source_block_ids": section.get("source_block_ids") or [],
        "source_text": section.get("source_text") or "",
        "title": section.get("title") or "",
        "description": section.get("description") or "",
        "visual_cues": section.get("visual_cues") or [],
        "reference_characters": section.get("reference_characters") or [],
        "reference_image_paths": section.get("reference_image_paths") or [],
        "subject": subject,
        "provider": provider_cfg.get("provider", "modelslab"),
        "model_id": section.get("model_id") or provider_cfg.get("model_id"),
        "image_model_id": provider_cfg.get("image_model_id"),
        "reference_model_id": provider_cfg.get("reference_model_id"),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Renderer sub-dispatch helpers
# ---------------------------------------------------------------------------

def _render_manim(
    section: dict[str, Any],
    subject: str,
    out_dir: Path,
    dry_run: bool,
    quality: str = "standard",
) -> ClipResult:
    from tools.video.manim_generator import ManimGenerator
    gen = ManimGenerator()
    res = gen.execute({
        "section":    section,
        "subject":    subject,
        "quality":    quality,
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
    del subject, out_dir, dry_run, chapter
    sid = section["section_id"]
    # The final locked composer owns every HyperFrames teaching surface,
    # including opening overlays. Rendering a separate title-card MP4 creates
    # a second timing origin, blank lead-ins, and a shared filename that can be
    # accidentally reused across sections during resume.
    return ClipResult(
        section_id=sid,
        render_mode="hyperframes",
        video_path="",
        duration_seconds=float(section.get("duration_seconds", 30)),
        cost_usd=0.0,
        success=True,
    )


def _render_video_gen(
    section: dict[str, Any],
    subject: str,
    out_dir: Path,
    dry_run: bool,
    video_provider: dict[str, Any] | None = None,
) -> ClipResult:
    """Generate one narration-aligned educational motion clip.

    Provider/model selection comes from the chapter configuration.  This keeps
    new subjects out of core code while still enforcing the educational rule
    that generated clip audio is never used as narration.
    """
    sid = section["section_id"]
    out = out_dir / f"{sid}.mp4"
    dur = float(section.get("duration_seconds", 10))
    provider_cfg = dict(video_provider or {})
    fingerprint = _content_fingerprint(section, subject, provider_cfg)
    provider_name = provider_cfg.get("provider", "modelslab")
    if provider_name != "modelslab":
        return ClipResult(
            section_id=sid,
            render_mode="video_gen",
            video_path="",
            duration_seconds=0.0,
            cost_usd=0.0,
            success=False,
            error=f"Unsupported educational video provider: {provider_name}",
            content_fingerprint=fingerprint,
        )

    scene_description = (
        section.get("description", "") or section.get("title", "")
    )
    subject_style = str(
        resolve_subject_profile(subject).get("visual_style")
        or "polished child-friendly 3D educational animation"
    )
    scene_description = f"{scene_description}. Style: {subject_style}."

    seed = section.get("seed")
    if dry_run:
        out.parent.mkdir(parents=True, exist_ok=True)
        return ClipResult(
            section_id=sid,
            render_mode="video_gen",
            video_path=str(out),
            duration_seconds=dur,
            cost_usd=0.0,
            success=True,
            content_fingerprint=fingerprint,
            qa_report={"status": "dry_run", "issues": []},
        )

    from tools.video.modelslab_video import ModelsLabVideo

    reference_images = [
        str(path) for path in (section.get("reference_image_paths") or []) if path
    ]
    reference_image = (
        section.get("reference_image_path")
        or section.get("image_path")
        or section.get("keyframe_path")
    )
    operation = (
        "reference_to_video"
        if reference_images
        else "image_to_video"
        if reference_image
        else "text_to_video"
    )
    model_id = section.get("model_id") or (
        provider_cfg.get("reference_model_id", "h3-minimax-r2v")
        if reference_images
        else
        provider_cfg.get("image_model_id", "wan-2.2-i2v")
        if reference_image
        else provider_cfg.get("model_id", "wan2.2")
    )
    reference_characters = section.get("reference_characters") or []
    reference_prompt = " ".join(
        f"Image {index} is {str(character.get('name') or character.get('id') or 'the recurring character')}; preserve the same face, colours, clothing, proportions, and 3D style."
        for index, character in enumerate(reference_characters[:len(reference_images)], 1)
        if isinstance(character, dict)
    )
    request: dict[str, Any] = {
        "prompt": ((reference_prompt + " ") if reference_prompt else "")
        + scene_description
        + " Smooth intentional motion, seamless shot, no text, no logo, no watermark, child-safe.",
        "negative_prompt": (
            "still image, slideshow, ken burns, replay, loop, stutter, camera jump, "
            "text, subtitles, watermark, logo, malformed anatomy, extra limbs"
        ),
        "model_id": model_id,
        "operation": operation,
        "duration": str(min(10, max(5, int(round(dur))))),
        "resolution": provider_cfg.get("resolution", "768P"),
        # Never permit generated native audio in an educational composition.
        "generate_audio": False,
        "educational_mode": True,
        "output_path": str(out),
    }
    if seed is not None:
        request["seed"] = seed
    if reference_image:
        request["image_path"] = str(reference_image)
    if reference_images:
        request["reference_image_paths"] = reference_images[:4]

    qa_cfg = provider_cfg.get("semantic_qa") or {}
    semantic_required = bool(qa_cfg.get("required", False))
    max_attempts = max(1, int(provider_cfg.get("max_generation_attempts", 1)))
    base_seed = int(seed if seed is not None else 1337)
    total_cost = 0.0
    last_error = "video_gen_failed"
    last_qa: dict[str, Any] | None = None

    from tools.analysis.educational_clip_qa import audit_generated_clip

    for attempt in range(1, max_attempts + 1):
        attempt_path = out.with_name(f"{out.stem}.attempt-{attempt}{out.suffix}")
        attempt_request = dict(request)
        attempt_request["output_path"] = str(attempt_path)
        attempt_request["seed"] = base_seed + attempt - 1
        if attempt > 1 and last_qa:
            issue_text = "; ".join(last_qa.get("issues") or [])[:300]
            attempt_request["prompt"] += (
                " Regeneration correction: make the required subject unmistakable "
                f"and maintain continuous visible motion. Previous QA: {issue_text}."
            )

        result = ModelsLabVideo().execute(attempt_request)
        total_cost += result.cost_usd or 0.0

        if not result.success:
            last_error = result.error or "video_gen_failed"
            # Never silently switch models, remove reference conditioning, or
            # submit a new paid job because a previous job is still pending.
            return ClipResult(
                section_id=sid, render_mode="video_gen", video_path="",
                duration_seconds=0.0, cost_usd=total_cost, success=False,
                error=last_error, content_fingerprint=fingerprint,
                generation_attempts=attempt,
                production_state=_provider_failure_state(last_error),
            )

        last_qa = audit_generated_clip(
            attempt_path,
            section,
            semantic_required=semantic_required,
            semantic_model=str(qa_cfg.get("model", "clip")),
            max_frames=int(qa_cfg.get("max_frames", 5)),
            minimum_match_ratio=float(qa_cfg.get("minimum_match_ratio", 0.4)),
        )
        if last_qa.get("status") == "pass":
            out.parent.mkdir(parents=True, exist_ok=True)
            attempt_path.replace(out)
            actual_dur = _probe_duration(out)
            return ClipResult(
                section_id=sid,
                render_mode="video_gen",
                video_path=str(out),
                duration_seconds=actual_dur or dur,
                cost_usd=total_cost,
                success=True,
                content_fingerprint=fingerprint,
                generation_attempts=attempt,
                qa_report=last_qa,
                production_state="accepted",
            )

        last_error = "; ".join(last_qa.get("issues") or []) or "clip QA failed"
        if last_qa.get("status") == "pending":
            return ClipResult(
                section_id=sid, render_mode="video_gen", video_path=str(attempt_path),
                duration_seconds=_probe_duration(attempt_path), cost_usd=total_cost,
                success=False, error=last_error, content_fingerprint=fingerprint,
                generation_attempts=attempt, qa_report=last_qa,
                production_state="semantic_pending",
            )
        # Retain rejected files and provider sidecars for review/recovery.

    return ClipResult(
        section_id=sid,
        render_mode="video_gen",
        video_path="",
        duration_seconds=0.0,
        cost_usd=total_cost,
        success=False,
        error=f"video generation failed QA after {max_attempts} attempt(s): {last_error}",
        content_fingerprint=fingerprint,
        generation_attempts=max_attempts,
        qa_report=last_qa,
        production_state="qa_rejected",
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
            "video_provider":        {"type": "object"},
            "quality":               {"type": "string", "default": "standard"},
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
        return 0.0  # concrete API costs are reported by provider results

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
        manifest_path = out_dir / "clip_manifest.json"
        prior_by_section: dict[str, dict[str, Any]] = {}
        if manifest_path.exists():
            try:
                prior = json.loads(manifest_path.read_text(encoding="utf-8"))
                prior_by_section = {
                    str(item.get("section_id")): item
                    for item in prior.get("clips", [])
                }
            except Exception:
                prior_by_section = {}

        generation_blocker = ""
        for section in sections:
            sid  = section.get("section_id", "unknown")
            rm   = section.get("render_mode", "remotion")
            if rm == "video_gen" and generation_blocker:
                prior = prior_by_section.get(str(sid))
                manifest.append(prior if prior else ClipResult(
                    section_id=sid, render_mode=rm, video_path="",
                    duration_seconds=0.0, cost_usd=0.0, success=False,
                    error=generation_blocker, production_state="deferred",
                ).to_dict())
                failed += 1
                continue
            # ── Resume check — path must match what each renderer actually writes ──
            # remotion / video_gen  → out_dir/{sid}.mp4   (flat, sid-named)
            # manim                 → out_dir/{sid}/videos/{ClassName}.mp4
            #                         (Manim writes to media_dir/videos/)
            #                         We probe the sub-dir for ANY .mp4 instead.
            # hyperframes           → no standalone clip; final composer owns UI
            skip_clip: Path | None = None
            if rm == "manim":
                manim_subdir = out_dir / sid / "videos"
                found = (
                    sorted(
                        path
                        for path in manim_subdir.rglob("*.mp4")
                        if "partial_movie_files" not in path.parts
                        and path.stat().st_size > 0
                    )
                    if manim_subdir.exists()
                    else []
                )
                skip_clip = found[0] if found else None
            elif rm == "hyperframes":
                # Native teaching surfaces are authored once by the final
                # composition and never resume from a standalone MP4.
                skip_clip = None
            else:
                skip_clip = out_dir / f"{sid}.mp4"

            if skip_clip and skip_clip.exists() and skip_clip.stat().st_size > 0:
                prior = prior_by_section.get(str(sid), {})
                if rm == "video_gen":
                    provider_cfg = dict(inputs.get("video_provider") or {})
                    expected_fingerprint = _content_fingerprint(
                        section, subject, provider_cfg
                    )
                    qa_status = (prior.get("qa_report") or {}).get("status")
                    if (
                        prior.get("content_fingerprint") != expected_fingerprint
                        or qa_status != "pass"
                    ):
                        skip_clip = None
                if skip_clip is not None:
                    dur = _probe_duration(skip_clip)
                    manifest.append(ClipResult(
                        section_id=sid, render_mode=rm,
                        video_path=str(skip_clip), duration_seconds=dur,
                        cost_usd=0.0, success=True, skipped=True,
                        content_fingerprint=str(
                            prior.get("content_fingerprint") or ""
                        ),
                        generation_attempts=int(
                            prior.get("generation_attempts") or 0
                        ),
                        qa_report=prior.get("qa_report"),
                    ).to_dict())
                    skipped += 1
                    continue

            # Dispatch
            if rm == "manim":
                result = _render_manim(
                    section,
                    subject,
                    out_dir / sid,
                    dry_run,
                    str(inputs.get("quality") or "standard"),
                )
            elif rm == "remotion":
                qa_props_path = Path(inputs["qa_card_props_path"]) if inputs.get("qa_card_props_path") else None
                # Deliberately pass empty list here — _render_remotion will load
                # audio-derived timings from qa_card_props.json when it exists,
                # and only fall back to _section_to_qa_cards if it doesn't.
                result = _render_remotion(section, [], out_dir, dry_run, qa_props_path)
            elif rm == "hyperframes":
                result = _render_hyperframes(section, subject, out_dir, dry_run, chapter)
            elif rm == "video_gen":
                result = _render_video_gen(
                    section,
                    subject,
                    out_dir,
                    dry_run,
                    inputs.get("video_provider"),
                )
            else:
                result = ClipResult(
                    section_id=sid, render_mode=rm, video_path="",
                    duration_seconds=0.0, cost_usd=0.0,
                    success=False, error=f"Unknown render_mode: {rm}",
                )

            if not result.success:
                failed += 1

            manifest.append(result.to_dict())
            if result.production_state in {"provider_blocked", "semantic_pending", "provider_pending"}:
                generation_blocker = result.error
            # Persist after every unit so interruption cannot lose paid work.
            remaining = [
                item for key, item in prior_by_section.items()
                if key not in {str(clip["section_id"]) for clip in manifest}
            ]
            manifest_path.write_text(
                json.dumps({"subject": subject, "clips": manifest + remaining}, indent=2),
                encoding="utf-8",
            )

        # Write manifest
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
