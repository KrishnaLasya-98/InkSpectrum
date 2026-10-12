"""Silent, source-safe 3D Earth motion for Lesson 2.

The moving spheres are explanatory geometry, not a geographical map. Exact
textbook figures and labels are supplied separately by the HyperFrames lesson.
No model-generated lettering or invented land outlines appear in these clips.
"""

from manim import (
    DEGREES,
    DOWN,
    LEFT,
    ORIGIN,
    OUT,
    RIGHT,
    TAU,
    UP,
    Circle,
    Create,
    Dot,
    Dot3D,
    FadeIn,
    Line,
    Line3D,
    MoveAlongPath,
    Rotate,
    Sphere,
    ThreeDScene,
    VGroup,
    linear,
)


SKY = "#DCEEF1"
OCEAN = "#328FAF"
SUN = "#F7C863"
LINE = "#EAF7F4"
NIGHT = "#123247"


def teaching_earth(radius=1.65, resolution=(24, 48),
                   axis_extent=1.25, axis_thickness=0.018,
                   show_axis=True, shade=True):
    """A generic globe whose grid conveys spin without fabricated geography."""
    earth = Sphere(radius=radius, resolution=resolution)
    earth.set_fill(OCEAN, opacity=1).set_stroke(OCEAN, width=0.25)
    earth.set_shade_in_3d(shade)
    meridians = VGroup()
    for angle in (-55, -25, 5, 35, 65):
        curve = Circle(radius=radius * 1.003, color=LINE, stroke_width=2)
        curve.rotate(90 * DEGREES, axis=RIGHT)
        curve.rotate(angle * DEGREES, axis=UP)
        meridians.add(curve)
    equator = Circle(radius=radius * 1.006, color=LINE, stroke_width=3)
    equator.rotate(90 * DEGREES, axis=RIGHT)
    axis = Line3D(
        start=DOWN * radius * axis_extent,
        end=UP * radius * axis_extent,
        color=SUN,
        thickness=axis_thickness,
    )
    globe = VGroup(earth, meridians, equator)
    if show_axis:
        globe.add(axis)
    globe.rotate(23.5 * DEGREES, axis=OUT)
    return globe


class EarthMotionBase(ThreeDScene):
    def setup(self):
        super().setup()
        self.camera.background_color = SKY
        self.set_camera_orientation(phi=72 * DEGREES, theta=-75 * DEGREES)
        self.camera.light_source.move_to([-5, -6, 7])


class OpeningEarth(EarthMotionBase):
    """Clean opening movement for the approved title overlay; no embedded text."""

    def construct(self):
        self.camera.background_color = NIGHT
        stars = VGroup(*[
            Dot(point=[x, y, 0], radius=radius, color=LINE).set_opacity(0.55)
            for x, y, radius in [
                (-6.1, 2.8, .025), (-5.5, .8, .018), (-4.6, -2.6, .025),
                (-3.7, 2.0, .022), (-2.6, -1.2, .018), (-1.5, 3.0, .018),
                (-5.8, -1.6, .015), (-3.0, -2.9, .02), (-.8, -3.1, .014),
            ]
        ])
        self.add_fixed_in_frame_mobjects(stars)
        globe = teaching_earth(radius=2.5).shift(RIGHT * 2.15)
        sun = Sphere(radius=0.55, resolution=(16, 24))
        sun.set_fill(SUN, opacity=1).set_stroke(SUN, width=0.1)
        sun.set_shade_in_3d(True).shift(RIGHT * 5.3 + UP * 2.3)
        self.add(globe)
        self.play(FadeIn(sun), run_time=0.55)
        self.play(Rotate(globe, angle=TAU * 0.62, axis=UP, about_point=globe.get_center()),
                  run_time=7.5, rate_func=linear)


class RotationDayNight(EarthMotionBase):
    """A single spinning Earth, illuminated by one Sun at frame right."""

    def construct(self):
        globe = teaching_earth(radius=1.8).shift(LEFT * 1.1)
        sun = Sphere(radius=0.68, resolution=(16, 24))
        sun.set_fill(SUN, opacity=1).set_stroke(SUN, width=0.1)
        sun.set_shade_in_3d(True).shift(RIGHT * 4.2 + UP * 1.1)
        self.camera.light_source.move_to([5, -4, 5])
        self.add(globe, sun)
        self.play(Rotate(globe, angle=TAU, axis=UP, about_point=globe.get_center()),
                  run_time=10.0, rate_func=linear)


class TwoMovementsContrast(EarthMotionBase):
    """Separate, simultaneous spin and orbit examples for the two terms.

    The Earth at left only rotates around its own axis. The smaller Earth at
    right only travels around one Sun, retaining its axial orientation. Exact
    words and arrows are authored in HyperFrames rather than in this clip.
    """

    def construct(self):
        spin_earth = teaching_earth(radius=1.12, resolution=(12, 24)).shift(LEFT * 3.15)
        orbit = Circle(radius=1.42, color="#A83C2D", stroke_width=4)
        orbit.move_to(RIGHT * 2.8)
        sun = Sphere(radius=0.43, resolution=(18, 28))
        sun.set_fill(SUN, opacity=1).set_stroke(SUN, width=0.1)
        sun.set_shade_in_3d(True).move_to(orbit.get_center())
        travel_earth = teaching_earth(radius=0.47, resolution=(12, 24))
        travel_earth.move_to(orbit.point_from_proportion(0))
        self.add(spin_earth, sun, orbit, travel_earth)
        self.play(
            Rotate(spin_earth, angle=TAU, axis=UP,
                   about_point=spin_earth.get_center()),
            MoveAlongPath(travel_earth, orbit),
            run_time=12.0,
            rate_func=linear,
        )


class SolsticeGeometry(EarthMotionBase):
    """December/June positions with one Sun and fixed parallel axial tilt.

    The left Earth has its north pole angled away from the Sun (December);
    the right Earth has its north pole angled toward the Sun (June). All exact
    textbook dates and Tropic labels belong in the authored lesson overlay.
    """

    def construct(self):
        left = teaching_earth(radius=1.05, resolution=(12, 24),
                              show_axis=False, shade=False).shift(LEFT * 3.1)
        right = teaching_earth(radius=1.05, resolution=(12, 24),
                               show_axis=False, shade=False).shift(RIGHT * 3.1)
        sun = Sphere(radius=0.68, resolution=(16, 24))
        sun.set_fill(SUN, opacity=1).set_stroke(SUN, width=0.1)
        sun.set_shade_in_3d(True)
        rays = VGroup()
        for y in (-0.32, 0.32):
            rays.add(Line3D(start=[-0.72, y, 0], end=[-1.93, y, 0],
                            color=SUN, thickness=0.025))
            rays.add(Line3D(start=[0.72, y, 0], end=[1.93, y, 0],
                            color=SUN, thickness=0.025))
        self.add(left, sun, right, rays)
        axes = VGroup(
            Line(start=[-2.7, -1.24, 0], end=[-3.5, 1.24, 0],
                 color=SUN, stroke_width=8),
            Line(start=[3.5, -1.24, 0], end=[2.7, 1.24, 0],
                 color=SUN, stroke_width=8),
        )
        self.add_fixed_in_frame_mobjects(axes)
        tilted_axis = UP * 0.917 + LEFT * 0.399
        self.play(
            Rotate(left, angle=TAU * 0.8, axis=tilted_axis,
                   about_point=left.get_center()),
            Rotate(right, angle=TAU * 0.8, axis=tilted_axis,
                   about_point=right.get_center()),
            run_time=12.0,
            rate_func=linear,
        )


class RevolutionOrbit(EarthMotionBase):
    """One Earth travels once around one Sun with a fixed axial tilt."""

    def construct(self):
        sun = Sphere(radius=0.8, resolution=(20, 32))
        sun.set_fill(SUN, opacity=1).set_stroke(SUN, width=0.1)
        sun.set_shade_in_3d(True)
        orbit = Circle(radius=3.5, color="#A83C2D", stroke_width=4)
        earth = teaching_earth(radius=0.58).shift(RIGHT * 3.5)
        self.add(sun, orbit, earth)
        self.play(Create(orbit), run_time=0.8)
        # Translating along the orbit leaves the Earth's axial tilt fixed in
        # space, matching the textbook. Rotating the whole Earth group about
        # the Sun would incorrectly rotate its axis with the orbital angle.
        self.play(MoveAlongPath(earth, orbit),
                  run_time=11.2, rate_func=linear)


class AroundTheWorld(EarthMotionBase):
    """A generic round-world route, not a claim about Magellan's exact path."""

    def construct(self):
        globe = teaching_earth(radius=1.8)
        route = Circle(radius=2.13, color="#A83C2D", stroke_width=5)
        route.rotate(90 * DEGREES, axis=RIGHT)
        traveler = Dot3D(point=RIGHT * 2.13, radius=0.11, color=SUN)
        self.add(globe, route, traveler)
        self.play(Create(route), run_time=0.7)
        self.play(MoveAlongPath(traveler, route), run_time=8.3, rate_func=linear)
