"""Base Manim scene template."""

from __future__ import annotations

from manim import Scene, Circle, Tex, LEFT, RIGHT, UP


class BaseEducationScene(Scene):
    """Base scene for educational content."""

    def construct(self):
        title = Tex("Educational Scene")
        self.add(title)
