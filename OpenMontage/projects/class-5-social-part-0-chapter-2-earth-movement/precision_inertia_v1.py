"""Silent 3D teaching inset for the exact bicycle-stop inertia cue.

The bicycle translates, stops, then the rider's upper body continues forward.
No generated lettering or unsupported geographic detail is embedded here.
"""

from manim import (
    DEGREES, DOWN, LEFT, OUT, RIGHT, UP,
    Circle, Line, Line3D, Rotate, Sphere, ThreeDScene, Torus, VGroup, linear,
)


NAVY = "#123247"
SKY = "#DCEEF1"
BLUE = "#327EA8"
WHEEL = "#263C4B"
SKIN = "#C98665"
SHIRT = "#BE5346"
SUN = "#F7C863"


def tube(a, b, color, width=0.05):
    return Line3D(start=a, end=b, color=color, thickness=width)


class BicycleStopInertia(ThreeDScene):
    """One continuous stop-and-forward-lean demonstration for section s11."""

    def construct(self):
        self.camera.background_color = SKY
        self.set_camera_orientation(phi=12 * DEGREES, theta=-85 * DEGREES)
        self.camera.light_source.move_to([-3, -4, 7])

        rear = LEFT * 1.65 + DOWN * 1.32
        front = RIGHT * 1.65 + DOWN * 1.32
        crank = DOWN * 1.20
        seat = LEFT * 0.52 + DOWN * 0.05
        steering = RIGHT * 0.91 + DOWN * 0.12

        wheels = VGroup()
        for center in (rear, front):
            tire = Torus(major_radius=0.61, minor_radius=0.055)
            tire.set_fill(WHEEL, opacity=1).set_stroke(WHEEL, width=0.1)
            tire.move_to(center)
            hub = Sphere(radius=0.11, resolution=(10, 16))
            hub.set_fill(SUN, opacity=1).set_stroke(SUN, width=0.1)
            hub.move_to(center)
            wheels.add(tire, hub)

        frame = VGroup(
            tube(rear, seat, BLUE), tube(seat, crank, BLUE),
            tube(crank, rear, BLUE), tube(seat, steering, BLUE),
            tube(steering, crank, BLUE), tube(steering, front, BLUE),
            tube(seat + LEFT * 0.28, seat + RIGHT * 0.26, NAVY, 0.09),
            tube(steering, steering + RIGHT * 0.24 + UP * 0.20, NAVY, 0.06),
        )
        hip = seat + UP * 0.39
        chest = hip + RIGHT * 0.06 + UP * 0.93
        head_center = chest + RIGHT * 0.12 + UP * 0.36
        head = Sphere(radius=0.24, resolution=(14, 22))
        head.set_fill(SKIN, opacity=1).set_stroke(SKIN, width=0.1)
        head.move_to(head_center)
        helmet = Sphere(radius=0.25, resolution=(14, 22))
        helmet.set_fill(BLUE, opacity=1).set_stroke(BLUE, width=0.1)
        helmet.move_to(head_center + UP * 0.12)
        upper = VGroup(
            tube(hip, chest, SHIRT, 0.18),
            tube(chest, steering + RIGHT * 0.20 + UP * 0.18, SKIN, 0.07),
            head, helmet,
        )
        lower = VGroup(
            tube(hip, crank + RIGHT * 0.18, NAVY, 0.09),
            tube(hip, crank + LEFT * 0.19, NAVY, 0.09),
        )
        bicycle = VGroup(wheels, frame, lower, upper)
        bicycle.shift(LEFT * 1.05)
        ground = Line(LEFT * 7 + DOWN * 2.02, RIGHT * 7 + DOWN * 2.02,
                      color=NAVY, stroke_width=5)
        self.add(ground, bicycle)
        self.play(bicycle.animate.shift(RIGHT * 2.1), run_time=2.2,
                  rate_func=linear)
        # The bike is now stationary; only the rider's upper body advances.
        stopped_hip = hip + RIGHT * 1.05
        self.play(Rotate(upper, angle=-24 * DEGREES, axis=OUT,
                         about_point=stopped_hip), run_time=0.85,
                  rate_func=linear)
        self.wait(1.2)
