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
import textwrap
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
    if "Nunito" not in code and "_FONT" not in code:
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
        "standard": {"flag": "-qh", "resolution": "1920x1080", "fps": 30},
        "high":    {"flag": "-qh", "resolution": "1920x1080", "fps": 30},
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

        safe_section_id = re.sub(r"\W+", "_", str(section.get("section_id") or "section"))
        safe_title = re.sub(r"\W+", "_", title).strip("_") or "Lesson"
        return {
            "blueprint":    blueprint,
            "scene_class":  f"Scene_{safe_section_id}_{safe_title}"[:120],
            "section":      section,
            "subject":      subject,
            "blueprint_src": _BLUEPRINTS.get(blueprint, ""),
        }

    # --- coder agent ----------------------------------------------------------

    def _math_geometry_coder(self, plan: dict[str, Any]) -> str:
        """Return a deterministic, source-driven geometry animation.

        The final HyperFrames layer owns headings and subtitles, so these
        clips contain only diagram labels that are needed to teach the maths.
        A gentle continuous motion tail keeps long narration sections alive;
        the compositor trims the surplus against measured narration.
        """
        sec = plan["section"]
        cls = plan["scene_class"]
        visual_template = str(sec.get("visual_template") or "concept_cards")
        concepts = [
            str(value)[:34]
            for value in sec.get("key_concepts", [])
            if str(value).strip()
        ][:6]
        equations = [
            str(value)[:40]
            for value in sec.get("equations", [])
            if str(value).strip()
        ][:3]
        target_duration = max(
            12.0, float(sec.get("duration_seconds") or 24.0) * 1.35 + 4.0
        )
        code = r'''
from manim import *


class __CLASS__(ChildrensTheme):
    """Reviewed deterministic geometry scene."""

    def construct(self) -> None:
        template = __TEMPLATE__
        concepts = __CONCEPTS__
        equations = __EQUATIONS__
        target_duration = __DURATION__
        ink = ManimColor("#17324D")
        orange = ManimColor("#FF8C42")
        teal = ManimColor("#4ECDC4")
        yellow = ManimColor("#FFD93D")
        green = ManimColor("#6BCB77")
        pink = ManimColor("#FF6B9D")
        content = VGroup()

        def label(text, point, colour=ink, size=30):
            item = Text(str(text), font=_FONT, font_size=size, color=colour)
            item.move_to(point)
            content.add(item)
            return item

        def reveal(*items, run_time=0.7):
            for item in items:
                content.add(item)
                self.play(Create(item) if isinstance(item, VMobject) else FadeIn(item),
                          run_time=run_time)

        if template == "shape_world":
            dot = Dot(LEFT * 4 + UP * 1.2, radius=0.16, color=orange)
            segment = Line(LEFT * 2.7 + UP * 1.2, LEFT * 0.5 + UP * 1.2,
                           color=teal, stroke_width=10)
            triangle = Polygon(LEFT * 2.8 + DOWN * 1.4, LEFT * 1.7 + UP * 0.3,
                               LEFT * 0.6 + DOWN * 1.4, color=yellow,
                               fill_color=yellow, fill_opacity=0.24)
            circle = Circle(radius=1.15, color=pink, fill_color=pink,
                            fill_opacity=0.18).shift(RIGHT * 1.4 + DOWN * 0.5)
            square = Square(side_length=1.8, color=green, fill_color=green,
                            fill_opacity=0.16).shift(RIGHT * 4 + UP * 0.6)
            reveal(dot, segment, triangle, circle, square)
            for text, point in [("point", dot.get_center() + DOWN * 0.5),
                                ("line segment", segment.get_center() + DOWN * 0.5),
                                ("polygon", triangle.get_center() + DOWN * 1.3),
                                ("circle", circle.get_center() + DOWN * 1.45),
                                ("solid view", square.get_center() + DOWN * 1.25)]:
                self.play(FadeIn(label(text, point, size=27)), run_time=0.35)

        elif template == "geometry_primitives":
            rows = [1.8, 0.6, -0.6, -1.8]
            point = Dot(LEFT * 3.2 + UP * rows[0], radius=0.14, color=orange)
            seg = Line(LEFT * 4 + UP * rows[1], LEFT * 2 + UP * rows[1],
                       color=teal, stroke_width=8)
            seg.add(Dot(seg.get_start(), color=ink), Dot(seg.get_end(), color=ink))
            line = DoubleArrow(LEFT * 4 + UP * rows[2], LEFT * 2 + UP * rows[2],
                               color=yellow, stroke_width=7, buff=0)
            ray = Arrow(LEFT * 4 + UP * rows[3], LEFT * 2 + UP * rows[3],
                        color=pink, stroke_width=7, buff=0)
            reveal(point, seg, line, ray)
            for text, y in [("Point A", rows[0]), ("Segment AB", rows[1]),
                            ("Line CD", rows[2]), ("Ray EF", rows[3])]:
                self.play(FadeIn(label(text, RIGHT * 0.2 + UP * y, size=34)), run_time=0.35)

        elif template == "line_orientations_and_solid":
            horizontal = Line(LEFT * 4 + UP, LEFT * 1.5 + UP, color=orange, stroke_width=8)
            vertical = Line(LEFT * 3 + DOWN * 1.7, LEFT * 3 + UP * 0.3,
                            color=teal, stroke_width=8)
            slant = Line(LEFT * 1.4 + DOWN * 1.7, RIGHT * 0.2 + UP * 0.2, color=pink, stroke_width=8)
            cube = Cube(side_length=1.8, fill_color=green, fill_opacity=0.18,
                        stroke_color=green).shift(RIGHT * 3 + DOWN * 0.2)
            reveal(horizontal, vertical, slant, cube)
            label("horizontal", horizontal.get_center() + UP * 0.45, size=27)
            label("vertical", vertical.get_center() + RIGHT * 0.7, size=27)
            label("slanting", slant.get_center() + RIGHT * 0.8, size=27)
            for text, point in [("vertex", RIGHT * 4.1 + UP * 1.1),
                                ("edge", RIGHT * 4.3),
                                ("surface", RIGHT * 3 + DOWN * 1.5)]:
                self.play(FadeIn(label(text, point, size=26)), run_time=0.3)

        elif template == "open_closed_curves":
            open_curve = ArcBetweenPoints(LEFT * 4 + DOWN * 0.3,
                                          LEFT * 1.4 + UP * 0.7,
                                          angle=-PI * 0.9, color=orange,
                                          stroke_width=10)
            closed = Circle(radius=1.2, color=teal).shift(RIGHT * 0.7)
            simple = RoundedRectangle(width=2.2, height=2.0, corner_radius=0.65,
                                      color=green).shift(RIGHT * 4)
            reveal(open_curve, closed, simple)
            label("open curve", LEFT * 2.7 + DOWN * 1.8, size=30)
            label("closed curve", RIGHT * 0.7 + DOWN * 1.8, size=30)
            label("simple closed curve", RIGHT * 4 + DOWN * 1.8, size=27)

        elif template == "polygon_family":
            triangle = Polygon(LEFT * 4 + DOWN, LEFT * 2.7 + UP * 1.3,
                               LEFT * 1.4 + DOWN, color=orange,
                               fill_color=orange, fill_opacity=0.15)
            quad = Polygon(LEFT * 0.3 + DOWN, LEFT * 0.1 + UP,
                           RIGHT * 1.7 + UP * 1.3, RIGHT * 2 + DOWN,
                           color=teal, fill_color=teal, fill_opacity=0.15)
            curved = Circle(radius=1.15, color=pink).shift(RIGHT * 4)
            reveal(triangle, quad, curved)
            label("triangle • 3 sides", triangle.get_center() + DOWN * 1.55, size=28)
            label("quadrilateral • 4 sides", quad.get_center() + DOWN * 1.55, size=26)
            label("not a polygon", curved.get_center() + DOWN * 1.55, size=28)

        elif template == "rectangle_square":
            rect = Rectangle(width=4.0, height=2.2, color=orange,
                             fill_color=orange, fill_opacity=0.12).shift(LEFT * 2.4)
            sq = Square(side_length=2.2, color=teal, fill_color=teal,
                        fill_opacity=0.12).shift(RIGHT * 3)
            reveal(rect, sq)
            label("length", rect.get_top() + UP * 0.35, size=28)
            label("width", rect.get_left() + LEFT * 0.55, size=28)
            label("equal opposite sides", rect.get_center() + DOWN * 1.6, size=27)
            label("four equal sides", sq.get_center() + DOWN * 1.6, size=27)

        elif template in {"measurement_tools", "ruler_construction"}:
            ruler = RoundedRectangle(width=7.5, height=1.0, corner_radius=0.15,
                                     color=yellow, fill_color=yellow,
                                     fill_opacity=0.24).shift(DOWN * 0.8 + LEFT)
            ticks = VGroup()
            for i in range(11):
                x = -4.75 + i * 0.65
                tick = Line([x, -0.3, 0], [x, -0.65 if i % 5 else -0.45, 0],
                            color=ink, stroke_width=3)
                ticks.add(tick)
            reveal(ruler, ticks)
            if template == "measurement_tools":
                leg1 = Line(RIGHT * 2.6 + UP * 1.6, RIGHT * 1.7 + DOWN * 1.0,
                            color=teal, stroke_width=7)
                leg2 = Line(RIGHT * 2.6 + UP * 1.6, RIGHT * 3.7 + DOWN * 1.0,
                            color=orange, stroke_width=7)
                joint = Circle(radius=0.18, color=pink, fill_opacity=1).move_to(leg1.get_start())
                reveal(leg1, leg2, joint)
                label("compass", RIGHT * 2.7 + DOWN * 1.45, size=30)
            else:
                a = Dot([-4.75, 0.6, 0], color=pink)
                b = Dot([-1.5, 0.6, 0], color=pink)
                segment = Line(a.get_center(), b.get_center(), color=teal, stroke_width=10)
                reveal(a, b, segment)
                label("A", a.get_center() + UP * 0.4, size=30)
                label("B", b.get_center() + UP * 0.4, size=30)
                label("5 cm", segment.get_center() + UP * 0.45, size=32)

        elif template == "compass_segment":
            base = Line(LEFT * 4.7 + DOWN, RIGHT * 3.8 + DOWN,
                        color=ink, stroke_width=5)
            a = Dot(LEFT * 3 + DOWN, color=pink)
            b = Dot(RIGHT * 0.2 + DOWN, color=pink)
            legs = VGroup(
                Line(LEFT * 1.4 + UP * 1.8, a.get_center(), color=teal, stroke_width=7),
                Line(LEFT * 1.4 + UP * 1.8, b.get_center(), color=orange, stroke_width=7),
                Circle(radius=0.16, color=pink, fill_opacity=1).move_to(LEFT * 1.4 + UP * 1.8),
            )
            reveal(base, a, legs)
            self.play(FadeIn(b), run_time=0.5)
            content.add(b)
            label("A", a.get_center() + DOWN * 0.45, size=30)
            label("B", b.get_center() + DOWN * 0.45, size=30)
            label("5 cm", (a.get_center() + b.get_center()) / 2 + DOWN * 0.5, size=32)

        elif template == "circumference_thread":
            circle = Circle(radius=1.65, color=orange, stroke_width=10).shift(LEFT * 2.3)
            thread = Line(RIGHT * 0.2 + DOWN * 0.4, RIGHT * 5 + DOWN * 0.4,
                          color=teal, stroke_width=10)
            reveal(circle)
            self.play(TransformFromCopy(circle, thread), run_time=1.2)
            content.add(thread)
            label("circumference", circle.get_center() + DOWN * 2.05, size=30)
            label("straightened thread", thread.get_center() + DOWN * 0.6, size=29)

        elif template in {"circle_anatomy", "radius_diameter_relation", "pizza_radius"}:
            circle = Circle(radius=2.0, color=orange, fill_color=yellow,
                            fill_opacity=0.12).shift(LEFT * 1.4)
            centre = Dot(circle.get_center(), color=pink)
            diameter = Line(circle.get_left(), circle.get_right(), color=teal, stroke_width=8)
            radius = Line(circle.get_center(), circle.get_right(), color=green, stroke_width=9)
            reveal(circle, centre, diameter, radius)
            label("O", centre.get_center() + UP * 0.35, size=28)
            label("diameter d", circle.get_center() + DOWN * 0.45, size=28)
            label("radius r", radius.get_center() + UP * 0.45, size=28)
            if template == "pizza_radius":
                label("24 cm", circle.get_center() + DOWN * 2.45, size=34)
                label("radius = 12 cm", RIGHT * 3 + UP * 0.4, colour=orange, size=34)
            elif template == "radius_diameter_relation":
                label("d = 2 × r", RIGHT * 3 + UP * 0.6, colour=orange, size=38)
                label("r = d ÷ 2", RIGHT * 3 + DOWN * 0.3, colour=teal, size=38)
            else:
                label("centre • radius • diameter", RIGHT * 3 + DOWN * 0.1, size=31)

        elif template == "compass_circle":
            circle = Circle(radius=2.0, color=orange, stroke_width=9).shift(LEFT * 1.2)
            centre = Dot(circle.get_center(), color=pink)
            radius = Line(circle.get_center(), circle.get_right(), color=teal, stroke_width=7)
            reveal(centre, radius)
            self.play(Create(circle), Rotate(radius, angle=TAU, about_point=circle.get_center()),
                      run_time=2.2)
            content.add(circle)
            label("centre", circle.get_center() + DOWN * 0.45, size=28)
            label("radius = 4 cm", RIGHT * 3 + UP * 0.4, size=34)
            arc = Arc(radius=1.0, start_angle=0, angle=PI * 0.75, color=pink).shift(RIGHT * 3 + DOWN)
            reveal(arc)
            label("arc", RIGHT * 3 + DOWN * 1.8, size=28)

        elif template == "four_circles":
            circles = VGroup(*[
                Circle(radius=0.95, color=teal, fill_color=yellow, fill_opacity=0.12)
                .shift(LEFT * 3 + RIGHT * i * 1.9)
                for i in range(4)
            ])
            reveal(circles, run_time=1.2)
            for circle in circles:
                radius = Line(circle.get_center(), circle.get_right(), color=pink, stroke_width=5)
                self.play(Create(radius), run_time=0.25)
                content.add(radius)
            label("each r = 3 cm", UP * 1.6, size=34)
            label("each d = 6 cm", DOWN * 1.6, size=34)
            label("4 × 6 = 24 cm", DOWN * 2.35, colour=orange, size=38)

        elif template == "solid_views_tent":
            tent = Polygon(LEFT * 1.8 + DOWN, ORIGIN + UP * 1.8,
                           RIGHT * 1.8 + DOWN, color=orange,
                           fill_color=yellow, fill_opacity=0.2).shift(LEFT * 1.5)
            front = Polygon(LEFT * 0.75 + DOWN * 0.6, UP * 0.75,
                            RIGHT * 0.75 + DOWN * 0.6, color=teal).shift(RIGHT * 3 + UP * 1.3)
            top = Rectangle(width=1.8, height=0.9, color=green).shift(RIGHT * 3)
            side = Polygon(LEFT * 0.7 + DOWN * 0.5, UP * 0.65,
                           RIGHT * 0.7 + DOWN * 0.5, color=pink).shift(RIGHT * 3 + DOWN * 1.5)
            reveal(tent, front, top, side)
            label("tent", tent.get_center() + DOWN * 1.65, size=30)
            label("front • elevation", front.get_center() + RIGHT * 1.65, size=25)
            label("top • plane", top.get_center() + RIGHT * 1.5, size=25)
            label("side view", side.get_center() + RIGHT * 1.25, size=25)

        elif template == "solid_view_projections":
            solid = Cube(side_length=2.2, fill_color=yellow, fill_opacity=0.16,
                         stroke_color=orange).shift(LEFT * 2.8)
            front = Square(side_length=1.5, color=teal).shift(RIGHT * 2.6 + UP * 1.5)
            top = Square(side_length=1.5, color=green).shift(RIGHT * 2.6)
            side = Square(side_length=1.5, color=pink).shift(RIGHT * 2.6 + DOWN * 1.5)
            reveal(solid, front, top, side)
            label("elevation", front.get_center() + RIGHT * 1.45, size=27)
            label("plane", top.get_center() + RIGHT * 1.15, size=27)
            label("side view", side.get_center() + RIGHT * 1.3, size=27)

        else:
            cards = VGroup()
            for i, text in enumerate(concepts[:4]):
                box = RoundedRectangle(width=4.4, height=0.9, corner_radius=0.2,
                                       color=[orange, teal, green, pink][i % 4],
                                       fill_opacity=0.12)
                item = Text(text, font=_FONT, font_size=30, color=ink).move_to(box)
                cards.add(VGroup(box, item))
            cards.arrange(DOWN, buff=0.28).shift(LEFT * 1.4)
            reveal(cards, run_time=1.0)

        if equations and template not in {"radius_diameter_relation", "pizza_radius", "four_circles"}:
            eq_group = VGroup(*[
                Text(eq, font=_FONT, font_size=30, color=orange)
                for eq in equations
            ]).arrange(DOWN, buff=0.25).to_edge(RIGHT, buff=0.45).shift(DOWN * 2.1)
            self.play(FadeIn(eq_group), run_time=0.7)
            content.add(eq_group)

        # Keep meaningful motion under longer narration without looping media.
        remaining = max(1.0, target_duration - self.time)
        while remaining > 1.1:
            step = min(2.0, remaining)
            self.play(content.animate.shift(UP * 0.045),
                      rate_func=there_and_back, run_time=step)
            remaining -= step
        if remaining > 0:
            self.wait(remaining)
'''
        return (
            code.replace("__CLASS__", cls)
            .replace("__TEMPLATE__", json.dumps(visual_template))
            .replace("__CONCEPTS__", json.dumps(concepts, ensure_ascii=False))
            .replace("__EQUATIONS__", json.dumps(equations, ensure_ascii=False))
            .replace("__DURATION__", f"{target_duration:.3f}")
        )

    def _coder_agent(self, plan: dict[str, Any]) -> str:
        """Generate Manim Python code from the planner's blueprint selection."""
        sec     = plan["section"]
        if plan.get("subject") == "maths" and sec.get("visual_template"):
            return self._math_geometry_coder(plan)
        title   = sec.get("title", "Scene")
        concepts = [str(value) for value in sec.get("key_concepts", []) if str(value).strip()]
        source_text = str(
            sec.get("source_text") or sec.get("description") or ""
        ).strip()
        if (
            not concepts
            and source_text
            and sec.get("source_document_block_type") != "equation"
        ):
            concepts = textwrap.wrap(
                source_text,
                width=42,
                break_long_words=False,
                break_on_hyphens=False,
            )
        equations = [str(value) for value in sec.get("equations", []) if str(value).strip()]
        if not equations and sec.get("source_document_block_type") == "equation":
            equations = [source_text]
        dur     = sec.get("duration_seconds", 30)
        cls     = plan["scene_class"]

        title_literal = json.dumps(str(title), ensure_ascii=False)
        concepts_literal = json.dumps(concepts, ensure_ascii=False)
        eq_lines = ""
        if equations:
            eq_lines = "\n".join(
                "        self.play(Write(Text("
                + json.dumps(eq, ensure_ascii=False)
                + f', font=_FONT, font_size=46, color=ManimColor("{SC_ACCENT}"))))'
                for eq in equations
            )

        code = f'''\
from manim import *


class {cls}(ChildrensTheme):
    """Source-grounded EduStream Pro precision scene."""

    def construct(self) -> None:
        # ── Title ──────────────────────────────────────────────────────────
        title = Text(
            {title_literal},
            font=_FONT,
            font_size=64,
            color=ManimColor("{SC_PRIMARY}"),
            weight=BOLD,
        )
        title.to_edge(UP, buff=0.5)
        self.bounce_in(title)
        self.wait(0.3)

        # ── Concepts ───────────────────────────────────────────────────────
        concepts = {concepts_literal}
        colours  = ["{SC_PRIMARY}", "{SC_SECONDARY}", "{SC_ACCENT}",
                    "{SC_EVS}", "{SC_ENGLISH}"]
        items = VGroup()
        for i, c in enumerate(concepts):
            col = colours[i % len(colours)]
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
        manim_python = os.environ.get("OPENMONTAGE_MANIM_PYTHON") or sys.executable
        cmd = [
            manim_python, "-m", "manim",
            preset["flag"],
            "--fps", str(preset["fps"]),
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
            output_dir.mkdir(parents=True, exist_ok=True)
            dry_run_path = output_dir / f"{plan['scene_class']}_dryrun.mp4"
            dry_run_path.write_bytes(b"")
            return ToolResult(
                success=True,
                data={
                    "video_path": str(dry_run_path),
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
