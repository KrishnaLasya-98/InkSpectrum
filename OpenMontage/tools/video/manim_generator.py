"""ManimCE educational video generator with ChildrensTheme base class.

ChildrensTheme provides the Sunshine Classroom design system:
  - Background  #FFFDF0 (warm cream)
  - Primary     #FF8C42 (energetic orange)
  - Secondary   #4ECDC4 (sky teal)
  - Accent      #FFD93D (sunflower yellow)
  - Font        Nunito (rounded, friendly)
  - Spring      damping=14, stiffness=60 (bouncy for ages 5-7)

Tri-agent pipeline (Code2Video / EduGen pattern):
  Planner  → scene blueprint from section data
  Coder    → executable Manim Python class (inherits ChildrensTheme)
  Critic   → AST parse + compile check + design-system compliance

Subject-specific scene blueprints (few-shot seeds):
  Maths   NumberLineScene, PlaceValueScene, SkipCountingScene
  EVS     ClassificationTreeScene, AnimalHomesMapScene, ConceptWheelScene
  English WordFormationScene, VowelConsonantScene
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

# ---------------------------------------------------------------------------
# Sunshine Classroom palette (Manim-ready hex strings)
# ---------------------------------------------------------------------------
SC_BG       = "#FFFDF0"
SC_PRIMARY  = "#FF8C42"
SC_SECONDARY = "#4ECDC4"
SC_ACCENT   = "#FFD93D"
SC_EVS      = "#6BCB77"
SC_ENGLISH  = "#845EC2"
SC_QA_REVEAL = "#FF6B9D"
SC_TEXT     = "#2D2D2D"

# ---------------------------------------------------------------------------
# ChildrensTheme — the base class injected into every generated scene
# ---------------------------------------------------------------------------
CHILDREN_THEME_SRC = f'''\
from manim import *

# Font selection — Nunito preferred; DejaVu Sans is the Manim default fallback.
# Install Nunito: https://fonts.google.com/specimen/Nunito (copy .ttf to
# C:/Windows/Fonts on Windows, or ~/.local/share/fonts on Linux/macOS).
try:
    import matplotlib.font_manager as _fm
    _FONT = "Nunito" if "Nunito" in {{f.name for f in _fm.fontManager.ttflist}} else "DejaVu Sans"
except Exception:
    _FONT = "DejaVu Sans"


class ChildrensTheme(Scene):
    """Sunshine Classroom base class for all EduStream Pro Manim scenes.

    Design system
    -------------
    Background  {SC_BG}
    Primary     {SC_PRIMARY}   (orange  — headings, accents)
    Secondary   {SC_SECONDARY}  (teal    — concept boxes)
    Accent      {SC_ACCENT}  (yellow  — highlights, numbers)
    Font        Nunito
    """

    BG        = "{SC_BG}"
    PRIMARY   = "{SC_PRIMARY}"
    SECONDARY = "{SC_SECONDARY}"
    ACCENT    = "{SC_ACCENT}"
    TEXT      = "{SC_TEXT}"

    def setup(self) -> None:                                # type: ignore[override]
        self.camera.background_color = ManimColor(self.BG)

    def bounce_in(self, mob: Mobject, delay: float = 0.0) -> None:
        """Scale 0 → 1.15 → 1.0 with optional stagger delay (children love the bounce)."""
        mob.scale(0)
        if delay:
            self.wait(delay)
        self.play(mob.animate.scale(1.15), run_time=0.25, rate_func=rush_into)
        self.play(mob.animate.scale(1 / 1.15), run_time=0.15, rate_func=rush_from)

    def word_by_word(self, text: str, delay: float = 0.08,
                     color: str | None = None) -> None:
        """Write each word with stagger — keeps young viewers tracking."""
        col = ManimColor(color or self.TEXT)
        words = [
            Text(w, font=_FONT, font_size=44, color=col)
            for w in text.split()
        ]
        grp = VGroup(*words).arrange(RIGHT, buff=0.2)
        grp.move_to(ORIGIN)
        for w in words:
            w.save_state()
            w.set_opacity(0)
        self.add(grp)
        for w in words:
            self.play(w.animate.set_opacity(1), run_time=delay)

    def section_title(self, text: str) -> Text:
        t = Text(text, font=_FONT, font_size=64,
                 color=ManimColor(self.PRIMARY), weight=BOLD)
        t.to_edge(UP, buff=0.4)
        self.bounce_in(t)
        return t
'''

# ---------------------------------------------------------------------------
# Scene blueprints (few-shot examples given to the Coder agent)
# ---------------------------------------------------------------------------
_BLUEPRINTS: dict[str, str] = {
    "NumberLineScene": f'''\
class NumberLineScene(ChildrensTheme):
    def construct(self) -> None:
        nl = NumberLine(x_range=[0, 100, 10], length=10,
                        color=ManimColor("{SC_PRIMARY}"),
                        include_numbers=True,
                        label_direction=DOWN)
        self.bounce_in(nl)
        dot = Dot(nl.n2p(53), color=ManimColor("{SC_ACCENT}"), radius=0.18)
        label = Text("53", font="Nunito", font_size=48,
                     color=ManimColor("{SC_ACCENT}"))
        label.next_to(dot, UP)
        self.play(FadeIn(dot), Write(label))
        self.wait(2)
''',
    "PlaceValueScene": f'''\
class PlaceValueScene(ChildrensTheme):
    def construct(self) -> None:
        tens_box = RoundedRectangle(corner_radius=0.2, width=2.5, height=1.8,
                                    color=ManimColor("{SC_PRIMARY}"), fill_opacity=0.15)
        ones_box = RoundedRectangle(corner_radius=0.2, width=2.5, height=1.8,
                                    color=ManimColor("{SC_SECONDARY}"), fill_opacity=0.15)
        VGroup(tens_box, ones_box).arrange(RIGHT, buff=0.5)
        tens_lbl = Text("5 Tens", font="Nunito", font_size=44,
                        color=ManimColor("{SC_PRIMARY}"))
        ones_lbl = Text("3 Ones", font="Nunito", font_size=44,
                        color=ManimColor("{SC_SECONDARY}"))
        tens_lbl.move_to(tens_box)
        ones_lbl.move_to(ones_box)
        self.bounce_in(tens_box)
        self.play(Write(tens_lbl))
        self.bounce_in(ones_box)
        self.play(Write(ones_lbl))
        plus = Text("+ = 53", font="Nunito", font_size=56,
                    color=ManimColor("{SC_ACCENT}"))
        plus.to_edge(DOWN, buff=0.5)
        self.play(Write(plus))
        self.wait(2)
''',
    "ConceptWheelScene": f'''\
class ConceptWheelScene(ChildrensTheme):
    def construct(self) -> None:
        centre = Text("Animals\\nNeed", font="Nunito", font_size=44,
                      color=ManimColor("{SC_PRIMARY}"), weight=BOLD)
        needs = ["Food", "Water", "Air", "Shelter"]
        colours = ["{SC_PRIMARY}", "{SC_SECONDARY}", "{SC_ACCENT}", "{SC_EVS}"]
        spokes = VGroup()
        for i, (need, col) in enumerate(zip(needs, colours)):
            angle = i * TAU / len(needs)
            pos = 3 * np.array([np.cos(angle), np.sin(angle), 0])
            box = RoundedRectangle(corner_radius=0.3, width=2.2, height=0.9,
                                   color=ManimColor(col), fill_opacity=0.2)
            lbl = Text(need, font="Nunito", font_size=38, color=ManimColor(col))
            lbl.move_to(box)
            node = VGroup(box, lbl).move_to(pos)
            line = Line(ORIGIN, pos * 0.7, color=ManimColor(col), stroke_width=3)
            spokes.add(VGroup(line, node))
        self.bounce_in(centre)
        for spoke in spokes:
            self.play(Create(spoke), run_time=0.5)
        self.wait(2)
''',
    "ClassificationTreeScene": f'''\
class ClassificationTreeScene(ChildrensTheme):
    def construct(self) -> None:
        root = RoundedRectangle(corner_radius=0.3, width=3, height=1,
                                color=ManimColor("{SC_PRIMARY}"), fill_opacity=0.2)
        root_lbl = Text("Animals", font="Nunito", font_size=44,
                        color=ManimColor("{SC_PRIMARY}")).move_to(root)
        root_g = VGroup(root, root_lbl).to_edge(UP, buff=0.8)
        self.bounce_in(root_g)
        categories = [("Water", "{SC_SECONDARY}"), ("Land", "{SC_EVS}"),
                      ("Birds", "{SC_ACCENT}")]
        nodes = []
        for i, (cat, col) in enumerate(categories):
            box = RoundedRectangle(corner_radius=0.3, width=2.5, height=0.9,
                                   color=ManimColor(col), fill_opacity=0.2)
            lbl = Text(cat, font="Nunito", font_size=38,
                       color=ManimColor(col)).move_to(box)
            node = VGroup(box, lbl).move_to([(i - 1) * 3.5, -1.2, 0])
            line = Line(root_g.get_bottom(), node.get_top(),
                        color=ManimColor(col), stroke_width=3)
            nodes.append(VGroup(line, node))
        for n in nodes:
            self.play(Create(n), run_time=0.6)
        self.wait(2)
''',
}

_BLOCKED_IMPORTS = frozenset({
    "os", "sys", "subprocess", "socket", "shutil", "requests", "urllib",
    "http", "ftplib", "smtplib", "ctypes", "pickle", "importlib",
    "multiprocessing", "threading", "pty", "resource", "signal",
    "tempfile", "webbrowser", "pathlib",
})
_BLOCKED_NAMES = frozenset({
    "eval", "exec", "compile", "__import__", "open", "input", "breakpoint",
    "__builtins__", "globals", "locals", "vars",
})


def _check_nunito_available() -> bool:
    """Return True if Nunito is available to matplotlib's font manager."""
    try:
        import matplotlib.font_manager as fm  # type: ignore[import-untyped]
        fonts = {f.name for f in fm.fontManager.ttflist}
        return "Nunito" in fonts
    except Exception:
        return False


# Cached at module load — avoids repeated font-manager scans
_NUNITO_OK: bool = _check_nunito_available()


def _scan_code(code: str) -> list[str]:
    """Static safety scan — returns list of violation messages."""
    issues: list[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"SyntaxError: {exc}"]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in _BLOCKED_IMPORTS:
                    issues.append(f"Blocked import: {alias.name}")
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in _BLOCKED_IMPORTS:
                issues.append(f"Blocked from-import: {node.module}")
        if isinstance(node, ast.Name) and node.id in _BLOCKED_NAMES:
            issues.append(f"Blocked name: {node.id}")
    return issues


def _design_compliance(code: str) -> list[str]:
    """Check that generated code follows Sunshine Classroom design rules."""
    issues: list[str] = []
    if "ChildrensTheme" not in code:
        issues.append("Scene must inherit ChildrensTheme")
    if "Nunito" not in code:
        issues.append("Font must be 'Nunito'")
    # Ensure at least one of the palette colours is referenced
    palette_colours = [SC_PRIMARY, SC_SECONDARY, SC_ACCENT, SC_EVS, SC_ENGLISH]
    if not any(c in code for c in palette_colours):
        issues.append("No Sunshine Classroom palette colour found in scene code")
    return issues


# ---------------------------------------------------------------------------
# ManimGenerator
# ---------------------------------------------------------------------------

class ManimGenerator(BaseTool):
    """Tri-agent Manim generator with ChildrensTheme and Sunshine Classroom design system."""

    name = "manim_generator"
    version = "2.0.0"
    tier = ToolTier.CORE
    capability = "video_generation"
    provider = "openmontage"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL_GPU

    dependencies = ["cmd:python", "python:manim"]
    install_instructions = "pip install manim\npip install sympy"
    agent_skills = ["manim-usage", "manimce-best-practices"]
    capabilities = [
        "manim_code_generation",
        "children_theme",
        "self_healing_compilation",
        "design_compliance",
    ]

    QUALITY_PRESETS = {
        "low":     {"flag": "-ql", "resolution": "854x480",   "fps": 15},
        "medium":  {"flag": "-qm", "resolution": "1280x720",  "fps": 30},
        "high":    {"flag": "-qh", "resolution": "1920x1080", "fps": 60},
        "preview": {"flag": "-ql", "resolution": "854x480",   "fps": 15},
    }

    input_schema = {
        "type": "object",
        "required": ["section"],
        "properties": {
            "section":        {"type": "object"},
            "subject":        {"type": "string", "default": "evs"},
            "quality":        {"type": "string", "default": "medium"},
            "output_dir":     {"type": "string"},
            "dry_run":        {"type": "boolean", "default": False},
            "max_attempts":   {"type": "integer", "default": 3},
            "seed":           {"type": "integer"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "video_path":   {"type": "string"},
            "manim_code":   {"type": "string"},
            "compile_log":  {"type": "array"},
        },
    }

    # --- planner agent --------------------------------------------------------

    def _planner_agent(self, section: dict[str, Any], subject: str) -> dict[str, Any]:
        """Select the best blueprint seed and build scene metadata."""
        btype = section.get("source_block_type", "concept")
        title = section.get("title", "")

        # Choose blueprint
        if subject == "maths":
            if "place" in title.lower() or "tens" in title.lower():
                blueprint = "PlaceValueScene"
            else:
                blueprint = "NumberLineScene"
        elif subject == "evs":
            if "class" in title.lower() or "type" in title.lower():
                blueprint = "ClassificationTreeScene"
            else:
                blueprint = "ConceptWheelScene"
        else:
            blueprint = "ConceptWheelScene"

        return {
            "blueprint":    blueprint,
            "scene_class":  f"Scene_{re.sub(chr(92) + 'W+', '_', title).strip('_')}",
            "section":      section,
            "subject":      subject,
            "blueprint_src": _BLUEPRINTS.get(blueprint, ""),
        }

    # --- coder agent ----------------------------------------------------------

    def _coder_agent(self, plan: dict[str, Any]) -> str:
        """Generate Manim Python code from the planner's blueprint selection."""
        sec     = plan["section"]
        title   = sec.get("title", "Scene")
        concepts = sec.get("key_concepts", [])
        equations = sec.get("equations", [])
        dur     = sec.get("duration_seconds", 30)
        cls     = plan["scene_class"]

        concepts_str = ", ".join(f'"{c}"' for c in concepts[:5])
        eq_lines = ""
        if equations:
            eq_lines = "\n".join(
                f'        self.play(Write(MathTex(r"{eq}", font_size=48, '
                f'color=ManimColor("{SC_ACCENT}"))))'
                for eq in equations[:3]
            )

        code = f'''\
from manim import *
from tools.video.manim_generator import ChildrensTheme, _FONT


class {cls}(ChildrensTheme):
    """EduStream Pro scene: {title}"""

    def construct(self) -> None:
        # ── Title ──────────────────────────────────────────────────────────
        title = Text(
            "{title}",
            font=_FONT,
            font_size=64,
            color=ManimColor("{SC_PRIMARY}"),
            weight=BOLD,
        )
        title.to_edge(UP, buff=0.5)
        self.bounce_in(title)
        self.wait(0.3)

        # ── Concepts ───────────────────────────────────────────────────────
        concepts = [{concepts_str}]
        colours  = ["{SC_PRIMARY}", "{SC_SECONDARY}", "{SC_ACCENT}",
                    "{SC_EVS}", "{SC_ENGLISH}"]
        items = VGroup()
        for i, (c, col) in enumerate(zip(concepts, colours)):
            box = RoundedRectangle(
                corner_radius=0.25, width=3.5, height=0.85,
                color=ManimColor(col), fill_opacity=0.18,
            )
            lbl = Text(c, font=_FONT, font_size=38,
                       color=ManimColor(col)).move_to(box)
            items.add(VGroup(box, lbl))
        items.arrange(DOWN, buff=0.35).shift(DOWN * 0.5)
        for i, item in enumerate(items):
            self.bounce_in(item, delay=i * 0.3)

        # ── Equations ─────────────────────────────────────────────────────
{eq_lines if eq_lines else "        pass  # no equations for this section"}

        self.wait({max(1, dur - 5)})
'''
        return code

    # --- critic agent ---------------------------------------------------------

    def _critic_agent(self, code: str) -> tuple[bool, list[str]]:
        """Check safety, design compliance, and AST validity."""
        issues: list[str] = []
        issues.extend(_scan_code(code))
        if not issues:
            issues.extend(_design_compliance(code))
        return (len(issues) == 0), issues

    # --- renderer -------------------------------------------------------------

    def _render(
        self,
        code: str,
        scene_class: str,
        quality: str,
        output_dir: Path,
    ) -> tuple[bool, str, str]:
        """Write code to tmp file and invoke Manim CLI. Returns (ok, video_path, stderr)."""
        preset = self.QUALITY_PRESETS.get(quality, self.QUALITY_PRESETS["medium"])
        with tempfile.NamedTemporaryFile(
            suffix=".py", delete=False, mode="w", encoding="utf-8"
        ) as f:
            # Prepend ChildrensTheme source so the file is self-contained
            f.write(CHILDREN_THEME_SRC + "\n\n")
            f.write(code)
            tmp = f.name

        output_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable, "-m", "manim",
            preset["flag"],
            "--media_dir", str(output_dir),
            "--output_file", scene_class,
            tmp, scene_class,
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            ok = proc.returncode == 0
            # Manim outputs to media_dir/videos/<scene_class>.mp4
            mp4 = output_dir / "videos" / f"{scene_class}.mp4"
            if not mp4.exists():
                # search recursively
                found = list(output_dir.rglob(f"{scene_class}*.mp4"))
                mp4 = found[0] if found else output_dir / f"{scene_class}.mp4"
            return ok, str(mp4), proc.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Manim render timed out"
        except Exception as exc:
            return False, "", str(exc)
        finally:
            try:
                Path(tmp).unlink(missing_ok=True)
            except Exception:
                pass

    # --- BaseTool interface ---------------------------------------------------

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 45.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        section      = inputs.get("section", {})
        subject      = inputs.get("subject", "evs")
        quality      = inputs.get("quality", "medium")
        max_attempts = inputs.get("max_attempts", 3)
        dry_run      = inputs.get("dry_run", False)
        seed         = inputs.get("seed")
        output_dir   = Path(inputs.get("output_dir", "renders/manim"))
        start        = time.monotonic()

        plan  = self._planner_agent(section, subject)
        code  = self._coder_agent(plan)
        log: list[dict[str, Any]] = []

        for attempt in range(1, max_attempts + 1):
            ok, issues = self._critic_agent(code)
            log.append({"attempt": attempt, "critic_pass": ok, "issues": issues})
            if ok:
                break
            # Attempt auto-fix: swap bad colour references
            for bad in issues:
                if "palette colour" in bad:
                    code = code.replace('color=WHITE', f'color=ManimColor("{SC_PRIMARY}")')
                if "Nunito" in bad:
                    code = re.sub(r'font\s*=\s*"[^"]*"', 'font="Nunito"', code)
                if "ChildrensTheme" in bad:
                    code = code.replace(
                        "class " + plan["scene_class"] + "(Scene)",
                        "class " + plan["scene_class"] + "(ChildrensTheme)",
                    )

        if dry_run:
            return ToolResult(
                success=True,
                data={
                    "video_path": str(output_dir / f"{plan['scene_class']}_dryrun.mp4"),
                    "manim_code": code,
                    "compile_log": log,
                },
                artifacts=["render_report"],
                cost_usd=0.0,
                duration_seconds=time.monotonic() - start,
                seed=seed,
            )

        ok_render, video_path, stderr = self._render(
            code, plan["scene_class"], quality, output_dir
        )
        if not ok_render:
            return ToolResult(
                success=False,
                error=f"Manim render failed: {stderr[-300:]}",
                data={"manim_code": code, "compile_log": log},
            )

        return ToolResult(
            success=True,
            data={"video_path": video_path, "manim_code": code, "compile_log": log},
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

    def get_status(self) -> ToolStatus:
        import shutil
        return ToolStatus.AVAILABLE if shutil.which("manim") else ToolStatus.UNAVAILABLE
