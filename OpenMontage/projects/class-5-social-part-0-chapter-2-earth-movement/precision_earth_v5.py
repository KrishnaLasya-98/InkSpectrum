"""Source-grounded 3D Earth motion, with a fixed tilted spin axis.

Render in the existing isolated Manim environment. Generic blue globes avoid
invented geography. Positive spin around the north axis is west to east.
Scientific references: NASA Earth Facts and NASA Space Place Seasons.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import numpy as np
from manim import *

ROOT = Path(__file__).resolve().parent
SKY = '#DCEEF1'
INK = '#123247'
BLUE = '#328FAF'
NIGHT = '#16394F'
LINE = '#DFF3F5'
GOLD = '#F4BF45'
RED = '#A83C2D'
TILT = 23.5 * DEGREES
NORTH = np.array([math.sin(TILT), 0., math.cos(TILT)])


def segment(sid):
    return json.loads((ROOT / f'artifacts/alignment-ctc-v5/{sid}.aligned.json').read_text(encoding='utf-8'))


def cue(sid, phrase):
    s = segment(sid)
    norm = lambda v: ''.join(c for c in v.casefold() if c.isalnum())
    target = [norm(w) for w in phrase.split()]
    heard = [norm(w['word']) for w in s['words']]
    for i in range(len(heard)-len(target)+1):
        if heard[i:i+len(target)] == target:
            return (s['words'][i]['start_ms']-s['start_ms'])/1000
    raise ValueError(f'No exact spoken cue: {sid}: {phrase}')


def duration(sid):
    manifest = json.loads((ROOT/'assets/audio/narration-elevenlabs-title-pause-v4/narration_manifest.json').read_text(encoding='utf-8'))
    return next(s['duration_seconds'] for s in manifest['segments'] if s['section_id']==sid)


def globe(radius=1.7, center=ORIGIN, daylight=False):
    sphere = Sphere(radius=radius, resolution=(24,48))
    sphere.set_fill(BLUE,1).set_stroke(BLUE,0)
    sphere.set_shade_in_3d(True)
    grid = VGroup()
    for longitude in np.linspace(0, PI, 6, endpoint=False):
        c=Circle(radius=radius*1.012)
        c.rotate(PI/2,axis=RIGHT).rotate(longitude,axis=OUT)
        for a in np.linspace(0,1,49)[:-1]:
            line=Line(c.point_from_proportion(a),c.point_from_proportion(a+1/48),color=LINE,stroke_width=1.2)
            line.set_shade_in_3d(True); grid.add(line)
    equator=Circle(radius=radius*1.016)
    for a in np.linspace(0,1,65)[:-1]:
        line=Line(equator.point_from_proportion(a),equator.point_from_proportion(a+1/64),color=GOLD,stroke_width=2.4)
        line.set_shade_in_3d(True); grid.add(line)
    marker=Dot3D(point=[radius*1.03,0,0],radius=.07,color=GOLD)
    grid.add(marker)
    sphere.rotate(TILT,axis=UP); grid.rotate(TILT,axis=UP)
    axis=Line3D(-NORTH*radius*1.36,NORTH*radius*1.36,color=GOLD,thickness=.017)
    world=VGroup(sphere,grid,axis).shift(center)
    if daylight:
        # Illuminate the fixed hemisphere facing the Sun (+x). Sphere geometry
        # stays stationary; grid and marker carry the surface rotation.
        for face in sphere:
            n=face.get_center()-center
            light=max(0.,float(n[0]/max(np.linalg.norm(n),1e-6)))
            face.set_fill(interpolate_color(ManimColor(NIGHT),ManimColor('#50BBD2'),light),1)
        # Keep 3D depth sorting enabled, otherwise Cairo paints the sphere
        # over every front-facing grid segment and motion becomes invisible.
        sphere.set_shade_in_3d(True)
    return world,grid,axis


class Base(ThreeDScene):
    def setup(self):
        super().setup()
        self.camera.background_color=SKY
        self.set_camera_orientation(phi=70*DEGREES,theta=-90*DEGREES,zoom=.95)
        self.camera.light_source.move_to([-5,-6,8])
        self.elapsed=0

    def label(self,text,xy,size=28,color=INK):
        obj=Text(text,font='Segoe UI',font_size=size,color=color).move_to([xy[0],xy[1],0])
        self.add_fixed_in_frame_mobjects(obj)
        return obj

    def until(self,t):
        if t>self.elapsed:
            self.wait(t-self.elapsed)
            self.elapsed=t

    def spin(self,grid,center,period=24):
        grid.add_updater(lambda m,dt: m.rotate(TAU*dt/period,axis=NORTH,about_point=center))


class RotationV5(Base):
    def construct(self):
        sid='s06-rotation'; total=duration(sid)
        self.camera.light_source.move_to([20,0,0])
        center=np.array([-2.1,0.,0.])
        earth,grid,axis=globe(1.85,center,daylight=True)
        self.add(*earth); self.spin(grid,center,period=24)
        self.label('N',(-.95,2.2),30)
        self.label('S',(-3.1,-2.2),30)
        self.label('Axis',(-3.8,1.75),28)
        self.until(cue(sid,'west to east'))
        direction=self.label('West → East',(-2.1,-2.8),32,RED)
        self.until(cue(sid,'24 hours'))
        hours=self.label('One rotation = 24 hours',(-2.1,-3.2),28)
        self.until(cue(sid,'equator'))
        eq=self.label('Equator',(-4.6,-.15),28)
        self.until(cue(sid,'The axis is tilted'))
        self.remove(eq,direction,hours)
        tilt=self.label('Axis tilt: 23.5°',(-2.1,-2.8),32,RED)
        self.until(cue(sid,'only one half'))
        self.remove(tilt)
        sun=Sphere(radius=.55,resolution=(24,48)).set_fill(GOLD,1).set_stroke(GOLD,0)
        sun.move_to([2.5,0.,0.]); self.add(sun)
        self.label('Sun',(2.5,-1.),28)
        rays=VGroup(*[Line3D([1.75,y,z],[.1,y,z],color=GOLD,thickness=.012) for y,z in [(0,0),(.15,.45),(-.15,-.45)]])
        self.add(rays)
        self.label('Night',(-3.0,-2.8),30)
        self.label('Day',(-1.1,-2.8),30)
        self.until(total)


class RevolutionV5(Base):
    def construct(self):
        sid='s08-revolution'
        # Stop when the separate seasonal landscape clips start.
        total=cue(sid,'Summer')
        self.set_camera_orientation(phi=65*DEGREES,theta=-90*DEGREES,zoom=.88)
        center=np.array([-1.5,0.,0.])
        minor=3.5*math.sqrt(1-.0167**2)
        orbit=Ellipse(width=7,height=minor*2,color=RED,stroke_width=3).move_to(center)
        sun=Sphere(radius=.62,resolution=(24,48)).set_fill(GOLD,1).set_stroke(GOLD,0).move_to(center+RIGHT*(3.5*.0167))
        earth,grid,axis=globe(.62,center+RIGHT*3.5)
        self.add(orbit,sun,earth)
        # Translation retains the axis direction in space. Do not rotate the
        # complete system around the Sun, which would make the axis precess.
        def travel(m,dt):
            self.orbit_time+=dt
            angle=TAU*self.orbit_time/total
            m.move_to(center+np.array([3.5*math.cos(angle),minor*math.sin(angle),0]))
        self.orbit_time=0
        earth.add_updater(travel)
        self.label('Sun',(-1.4,-.8),28)
        self.label('Orbit',(-4.7,-2.5),28,RED)
        self.label('Revolution: around the Sun',(-2.,-3.0),30,RED)
        self.until(cue(sid,'three hundred'))
        self.label('One revolution = 365¼ days',(-2.,-3.45),28)
        self.until(cue(sid,"The tilt of the Earth's axis"))
        self.label('Axis keeps the same direction',(-2.,2.5),28)
        self.until(total)


class ContrastV5(Base):
    def construct(self):
        sid='s05-two-movements'; total=duration(sid)
        center=np.array([-2.1,0.,0.])
        earth,grid,axis=globe(1.65,center)
        self.add(earth); self.spin(grid,center,period=9)
        rotation=cue(sid,'Rotation')
        revolution=cue(sid,'Revolution')
        self.until(rotation)
        caption=self.label('Rotation: spins on its axis',(-2.1,-2.7),32,RED)
        self.until(revolution)
        self.remove(earth,caption)
        self.set_camera_orientation(phi=45*DEGREES,theta=-90*DEGREES,zoom=.93)
        center=np.array([-1.8,0,0])
        orbit=Ellipse(width=6.2,height=6.0,color=RED,stroke_width=3).move_to(center)
        sun=Sphere(radius=.58,resolution=(10,20)).set_fill(GOLD,1).set_stroke(GOLD,.1).move_to(center)
        travel,_,_=globe(.55,center+RIGHT*3.1)
        self.add(orbit,sun,travel)
        self.label('Revolution: moves around the Sun',(-2.,-2.9),29,RED)
        self.play(MoveAlongPath(travel,orbit),run_time=total-self.elapsed,rate_func=linear)


class SphericalContextV5(Base):
    def construct(self):
        sid='s04-spherical-earth'
        total=duration(sid)
        center=np.array([-2.1,0,0])
        earth,grid,_=globe(2.,center)
        self.add(earth); self.spin(grid,center,period=35)
        self.until(total)
