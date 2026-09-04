"""Mathematics subject plugin."""

from __future__ import annotations

from typing import List

from textbook_pipeline.core.subjects.base import SubjectPlugin
from textbook_pipeline.models.chapter import SectionNode
from textbook_pipeline.models.script import ScriptScene, SceneStep, SceneStepType


class MathPlugin(SubjectPlugin):
    """Mathematics plugin with LaTeX, geometry, and graph support."""

    @property
    def subject_id(self) -> str:
        return "math"

    @property
    def display_name(self) -> str:
        return "Mathematics"

    def allowed_scene_types(self) -> List[str]:
        return [
            SceneStepType.TITLE,
            SceneStepType.SUBTITLE,
            SceneStepType.TEXT,
            SceneStepType.LATEX_INLINE,
            SceneStepType.LATEX_BLOCK,
            SceneStepType.POLYGON,
            SceneStepType.CIRCLE,
            SceneStepType.RECTANGLE,
            SceneStepType.TRIANGLE,
            SceneStepType.ANGLE_ARC,
            SceneStepType.AXES_2D,
            SceneStepType.AXES_3D,
            SceneStepType.PLOT_CURVE,
            SceneStepType.NUMBER_LINE,
            SceneStepType.FRACTION_BAR,
            SceneStepType.GRID,
            SceneStepType.CLEAR,
        ]

    def system_prompt_suffix(self) -> str:
        return """MATH-SPECIFIC RULES:
- Use LATEX_INLINE for inline equations like $x^2$
- Use LATEX_BLOCK for displayed equations
- Use POLYGON, CIRCLE, RECTANGLE, TRIANGLE for geometric shapes
- Use ANGLE_ARC for angle markings
- Use AXES_2D/AXES_3D for coordinate systems
- Use PLOT_CURVE for function graphs
- Use NUMBER_LINE for number line visualizations
- Use FRACTION_BAR for fraction models
- Use GRID for coordinate grids"""

    def post_process_scene(self, scene: ScriptScene, section: SectionNode) -> ScriptScene:
        """Enforce math-specific constraints."""
        # Ensure LaTeX steps have latex field populated
        for step in scene.scene_steps:
            if step.type in (SceneStepType.LATEX_INLINE, SceneStepType.LATEX_BLOCK):
                if not step.latex:
                    step.latex = step.content or "x = 1"
        return scene

    def extract_key_terms(self, text: str) -> List[str]:
        """Extract math key terms."""
        math_terms = [
            "add", "subtract", "multiply", "divide", "fraction", "decimal",
            "equation", "variable", "solve", "calculate", "area", "perimeter",
        ]
        text_lower = text.lower()
        return [term for term in math_terms if term in text_lower]
