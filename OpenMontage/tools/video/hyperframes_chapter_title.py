"""HyperFrames chapter title card generator.

Produces a 3-second animated chapter title card using the HyperFrames CLI
and the Sunshine Classroom style playbook.

The HTML workspace is materialised from a template, CSS vars are injected
via hyperframes_style_bridge, and the HyperFrames CLI renders it to MP4.

Usage
-----
    python -m tools.video.hyperframes_chapter_title \\
        --subject evs --chapter 8 --title "Animal Life" --output-dir renders/titles

    # or programmatically
    from tools.video.hyperframes_chapter_title import HyperFramesChapterTitle
    tool = HyperFramesChapterTitle()
    result = tool.execute({"subject": "evs", "chapter": 8, "title": "Animal Life"})
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from lib.hyperframes_style_bridge import style_bridge  # noqa: E402
from tools.base_tool import (  # noqa: E402
    BaseTool,
    Determinism,
    ExecutionMode,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

# Subject colour accents (secondary highlight colour per subject)
_SUBJECT_ACCENT: dict[str, str] = {
    "evs":     "#6BCB77",
    "english": "#845EC2",
    "maths":   "#FFD93D",
}
_SUBJECT_ICON: dict[str, str] = {
    "evs":     "🌿",
    "english": "📖",
    "maths":   "🔢",
}

# ---------------------------------------------------------------------------
# HTML workspace template (self-contained, no external font CDN — uses Nunito
# loaded from local system or bundled by HyperFrames)
# ---------------------------------------------------------------------------
_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>Chapter Title Card</title>
<style>
  :root {{
{css_vars}
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    width: 1920px; height: 1080px; overflow: hidden;
    background: var(--color-bg);
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    font-family: var(--font-heading), 'Segoe UI', Arial, sans-serif;
  }}

  .bg-gradient {{
    position: absolute; inset: 0;
    background: radial-gradient(ellipse at 30% 40%,
      {accent}33 0%, transparent 60%),
      radial-gradient(ellipse at 70% 60%,
      var(--color-primary)22 0%, transparent 55%);
  }}

  .card {{
    position: relative; z-index: 10;
    background: rgba(255,255,255,0.82);
    border-radius: 36px;
    padding: 64px 96px;
    max-width: 1400px;
    text-align: center;
    box-shadow: 0 8px 40px rgba(0,0,0,0.10);
    display: flex; flex-direction: column; align-items: center; gap: 24px;
    transform: scale(0); opacity: 0;
  }}

  .subject-icon {{
    font-size: 96px;
    transform: scale(0); opacity: 0;
  }}

  .subject-label {{
    font-size: 42px;
    font-weight: 700;
    color: {accent};
    letter-spacing: 0.12em;
    text-transform: uppercase;
    opacity: 0; transform: translateY(20px);
  }}

  .chapter-title {{
    font-size: 86px;
    font-weight: 900;
    color: var(--color-primary);
    line-height: 1.15;
    opacity: 0; transform: translateY(30px);
  }}

  .lesson-badge {{
    background: var(--color-accent, #FFD93D);
    color: #2D2D2D;
    font-size: 36px; font-weight: 800;
    padding: 14px 40px;
    border-radius: 100px;
    opacity: 0; transform: scale(0.6);
  }}

  .sparky {{
    position: absolute; bottom: 80px; right: 100px;
    transform: scale(0) translateX(40px); opacity: 0;
  }}
</style>
</head>
<body>
<div class="bg-gradient"></div>

<div class="card"
     data-timing-in="0" data-timing-duration="0.6"
     data-gsap-from='{{"scale":0,"opacity":0}}'
     data-gsap-to='{{"scale":1,"opacity":1,"ease":"back.out(1.8)"}}'>

  <div class="subject-icon"
       data-timing-in="0.3" data-timing-duration="0.5"
       data-gsap-from='{{"scale":0,"opacity":0}}'
       data-gsap-to='{{"scale":1,"opacity":1,"ease":"back.out(2.5)"}}'>{icon}</div>

  <div class="subject-label"
       data-timing-in="0.5" data-timing-duration="0.5"
       data-gsap-from='{{"opacity":0,"y":20}}'
       data-gsap-to='{{"opacity":1,"y":0,"ease":"power2.out"}}'>{subject_label}</div>

  <div class="chapter-title"
       data-timing-in="0.7" data-timing-duration="0.6"
       data-gsap-from='{{"opacity":0,"y":30}}'
       data-gsap-to='{{"opacity":1,"y":0,"ease":"power3.out"}}'>{title}</div>

  <div class="lesson-badge"
       data-timing-in="0.9" data-timing-duration="0.5"
       data-gsap-from='{{"scale":0.6,"opacity":0}}'
       data-gsap-to='{{"scale":1,"opacity":1,"ease":"back.out(2)"}}'>{lesson_label}</div>
</div>

<!-- Sparky mascot (inline SVG — no external assets) -->
<div class="sparky"
     data-timing-in="1.1" data-timing-duration="0.5"
     data-gsap-from='{{"scale":0,"x":40,"opacity":0}}'
     data-gsap-to='{{"scale":1,"x":0,"opacity":1,"ease":"back.out(2.5)"}}'>
  <svg width="120" height="120" viewBox="0 0 80 80">
    <polygon points="40,5 49,30 76,30 54,48 63,74 40,57 17,74 26,48 4,30 31,30"
             fill="#FFD93D" stroke="#FF8C42" stroke-width="3"/>
    <circle cx="34" cy="36" r="4" fill="#2D2D2D"/>
    <circle cx="46" cy="36" r="4" fill="#2D2D2D"/>
    <path d="M33,47 Q40,54 47,47" stroke="#2D2D2D" stroke-width="3"
          fill="none" stroke-linecap="round"/>
  </svg>
</div>
</body>
</html>
"""


class HyperFramesChapterTitle(BaseTool):
    """Generate animated chapter title cards with HyperFrames CLI."""

    name = "hyperframes_chapter_title"
    version = "1.0.0"
    tier = ToolTier.CORE
    capability = "video_generation"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["cmd:hyperframes"]
    install_instructions = (
        "Install HyperFrames CLI: npm install -g hyperframes\n"
        "Verify: hyperframes --version"
    )
    agent_skills = ["hyperframes-core", "hyperframes-cli"]
    capabilities = ["title_card", "chapter_bumper", "gsap_animation"]

    input_schema = {
        "type": "object",
        "required": ["subject", "title"],
        "properties": {
            "subject":     {"type": "string", "enum": ["evs", "english", "maths"]},
            "chapter":     {"type": "integer", "default": 1},
            "title":       {"type": "string"},
            "lesson_label": {"type": "string"},
            "output_dir":  {"type": "string"},
            "duration_seconds": {"type": "number", "default": 3.0},
            "dry_run":     {"type": "boolean", "default": False},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "video_path":     {"type": "string"},
            "workspace_path": {"type": "string"},
        },
    }

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 20.0

    def _build_html(
        self,
        subject: str,
        chapter: int,
        title: str,
        lesson_label: str,
    ) -> str:
        # Load sunshine-classroom playbook for CSS vars
        playbook_path = _ROOT / "styles" / "sunshine-classroom.yaml"
        playbook: dict[str, Any] = {}
        if playbook_path.exists():
            try:
                import yaml  # type: ignore[import-untyped]
                playbook = yaml.safe_load(playbook_path.read_text(encoding="utf-8")) or {}
            except ImportError:
                playbook = {}
                print(
                    "⚠ pyyaml not installed — playbook vars will be empty, "
                    "run: pip install pyyaml",
                    file=sys.stderr,
                )

        css_vars_dict, _ = style_bridge(playbook)
        css_vars_str = "\n".join(
            f"    {k}: {v};" for k, v in css_vars_dict.items()
        )

        accent = _SUBJECT_ACCENT.get(subject, "#FF8C42")
        icon   = _SUBJECT_ICON.get(subject, "⭐")
        sub_label = subject.upper()

        return _HTML_TEMPLATE.format(
            css_vars      = css_vars_str,
            accent        = accent,
            icon          = icon,
            subject_label = sub_label,
            title         = title,
            lesson_label  = lesson_label or f"Chapter {chapter}",
        )

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        subject   = inputs["subject"]
        chapter   = inputs.get("chapter", 1)
        title     = inputs["title"]
        lesson_lb = inputs.get("lesson_label", f"Chapter {chapter}")
        out_dir   = Path(inputs.get("output_dir", f"renders/titles"))
        duration  = inputs.get("duration_seconds", 3.0)
        dry_run   = inputs.get("dry_run", False)
        start     = time.monotonic()

        out_dir.mkdir(parents=True, exist_ok=True)
        slug      = f"{subject}_ch{chapter:02d}"
        out_mp4   = out_dir / f"{slug}_title.mp4"

        html = self._build_html(subject, chapter, title, lesson_lb)

        if dry_run:
            ws_path = out_dir / f"{slug}_workspace"
            ws_path.mkdir(parents=True, exist_ok=True)
            (ws_path / "index.html").write_text(html, encoding="utf-8")
            return ToolResult(
                success=True,
                data={"video_path": str(out_mp4), "workspace_path": str(ws_path)},
                artifacts=["render_report"],
                cost_usd=0.0,
                duration_seconds=time.monotonic() - start,
            )

        # Write workspace
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Path(tmpdir) / slug
            ws.mkdir()
            (ws / "index.html").write_text(html, encoding="utf-8")

            hf_bin = shutil.which("hyperframes") or "hyperframes"
            cmd = [
                hf_bin, "render",
                "--input",    str(ws / "index.html"),
                "--output",   str(out_mp4),
                "--duration", str(duration),
                "--fps",      "30",
                "--width",    "1920",
                "--height",   "1080",
            ]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if proc.returncode != 0:
                    return ToolResult(
                        success=False,
                        error=f"HyperFrames render failed: {proc.stderr[-300:]}",
                    )
            except FileNotFoundError:
                return ToolResult(
                    success=False,
                    error="HyperFrames CLI not found. Install: npm install -g hyperframes",
                )
            except subprocess.TimeoutExpired:
                return ToolResult(success=False, error="HyperFrames render timed out")

        # Copy workspace HTML for inspection
        ws_final = out_dir / f"{slug}_workspace"
        ws_final.mkdir(parents=True, exist_ok=True)
        (ws_final / "index.html").write_text(html, encoding="utf-8")

        return ToolResult(
            success=True,
            data={"video_path": str(out_mp4), "workspace_path": str(ws_final)},
            artifacts=["render_report"],
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

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if shutil.which("hyperframes") else ToolStatus.UNAVAILABLE


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _cli() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Generate chapter title card.")
    ap.add_argument("--subject",  required=True, choices=["evs", "english", "maths"])
    ap.add_argument("--chapter",  type=int, default=1)
    ap.add_argument("--title",    required=True)
    ap.add_argument("--lesson-label", dest="lesson_label")
    ap.add_argument("--output-dir",   dest="output_dir")
    ap.add_argument("--dry-run",  dest="dry_run", action="store_true")
    args = ap.parse_args()

    inp: dict[str, Any] = {
        "subject":  args.subject,
        "chapter":  args.chapter,
        "title":    args.title,
        "dry_run":  args.dry_run,
    }
    if args.lesson_label: inp["lesson_label"] = args.lesson_label
    if args.output_dir:   inp["output_dir"]   = args.output_dir

    res = HyperFramesChapterTitle().execute(inp)
    if res.success:
        print(f"✓ {res.data['video_path']}")
    else:
        print(f"✗ {res.error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _cli()
