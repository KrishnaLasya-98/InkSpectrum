"""Fresh Chapter 3 exact 3D explanatory motion, driven by measured narration.

Render only in the existing isolated Manim environment. Scientific labels are
authored; geographic maps remain the original PDF figures. No imported media.
"""
import json
import math
from pathlib import Path
import numpy as np
from manim import *

P=Path(__file__).resolve().parent
BG='#DCEEF1';INK='#123247';SEA='#328FAF';LAND='#B7CB87';SUN='#F4BF45';CREAM='#FFF9ED';ACCENT='#A83C2D'

def data(sid):
    manifest=json.loads((P/'assets/audio/narration-elevenlabs-timed-v1/narration_manifest.json').read_text())
    audio=next(s for s in manifest['segments'] if s['section_id']==sid)
    words=json.loads((P/'artifacts/alignment-timed-v1/narration_aligned.json').read_text(encoding='utf-8'))
    aligned=next(s for s in words['segments'] if s['section_id']==sid)
    return audio,aligned

def cue(sid,phrase):
    audio,aligned=data(sid);norm=lambda w:''.join(c for c in w.casefold() if c.isalnum())
    wanted=[norm(w) for w in phrase.split()];spoken=[norm(w['word']) for w in aligned['words']]
    for i in range(len(spoken)-len(wanted)+1):
        if spoken[i:i+len(wanted)]==wanted:return aligned['words'][i]['start_ms']/1000-audio['start_seconds']
    raise ValueError(f'Missing exact cue: {sid}: {phrase}')

class ClimateBase(ThreeDScene):
    SID=''
    def setup(self):
        super().setup();self.camera.background_color=BG
        self.set_camera_orientation(phi=65*DEGREES,theta=-90*DEGREES,zoom=.95)
        self.camera.light_source.move_to([-5,-6,8]);self.elapsed=0
    def until(self,t):
        if t>self.elapsed:self.wait(t-self.elapsed);self.elapsed=t
    def finish(self):self.until(data(self.SID)[0]['duration_seconds']+.15)
    def label(self,text,x,y,size=25,color=INK):
        obj=Text(text,font='Segoe UI',font_size=size,color=color).move_to([x,y,0]);self.add_fixed_in_frame_mobjects(obj);return obj
    def blue_globe(self,center=np.array([-2.5,0,0]),radius=1.65):
        globe=Sphere(radius=radius,resolution=(12,24)).set_fill(SEA,1).set_stroke(SEA,0).set_shade_in_3d(True)
        rings=VGroup()
        for latitude in [-66.5,-23.5,0,23.5,66.5]:
            lat=latitude*DEGREES;r=radius*math.cos(lat)
            ring=Circle(radius=r,color=SUN if abs(latitude)<=23.5 else CREAM,stroke_width=2).shift(OUT*radius*math.sin(lat));ring.set_shade_in_3d(True);rings.add(ring)
        lines=VGroup(*[Circle(radius=radius*1.008,color=CREAM,stroke_width=.8).rotate(PI/2,axis=RIGHT).rotate(a,axis=OUT).set_shade_in_3d(True) for a in np.linspace(0,PI,5,endpoint=False)])
        world=VGroup(globe,rings,lines).shift(center)
        lines.add_updater(lambda m,dt:m.rotate(dt*.18,axis=OUT,about_point=center))
        self.add(world);return world
    def moving_cloud(self,point,color=CREAM):
        cloud=VGroup(*[Sphere(radius=r,resolution=(6,12)).set_fill(color,1).set_stroke(color,0).set_shade_in_3d(True).shift([x,0,z]) for x,z,r in [(-.6,0,.35),(0,.15,.5),(.55,0,.35)]]).move_to(point)
        clock=[0.0];origin=np.asarray(point,dtype=float)
        def drift(m,dt):clock[0]+=dt;m.move_to(origin+RIGHT*.23*math.sin(clock[0]/4))
        cloud.add_updater(drift);self.add(cloud);return cloud
    def coast(self):
        ground=Cube(side_length=1).stretch(4,0).stretch(3,1).stretch(.18,2).set_fill(LAND,1).set_stroke(LAND,0).move_to([-3.7,0,-1.2])
        water=Cube(side_length=1).stretch(3.6,0).stretch(3,1).stretch(.17,2).set_fill(SEA,1).set_stroke(SEA,0).move_to([-.05,0,-1.2])
        waves=VGroup(*[ParametricFunction(lambda t,y=y:np.array([t,y,-1.10+.045*math.sin(t*4)]),t_range=[-1.7,1.7],color=CREAM,stroke_width=1.2) for y in [-1,-.5,0,.5,1]]).shift(RIGHT*.05)
        clock=[0.0]
        def ripple(m,dt):clock[0]+=dt;m.shift(OUT*(math.sin(clock[0]*1.5)*.02*dt))
        waves.add_updater(ripple);self.add(ground,water,waves)
        return ground,water
    def airflow(self,start,end,color):
        line=Arrow(start,end,buff=0,color=INK,stroke_width=5,max_tip_length_to_length_ratio=.07)
        point=Dot3D(start,radius=.07,color=color);clock=[0.0]
        def move(m,dt):clock[0]+=dt;u=(clock[0]/3)%1;m.move_to(np.array(start)*(1-u)+np.array(end)*u)
        point.add_updater(move);flow=VGroup(line,point);self.add(flow);return flow

class LatitudeClimate(ClimateBase):
    SID='s08-latitude'
    def construct(self):
        self.blue_globe();self.label('Equator',-2.6,-2.1);self.label('Poles',-5.1,2.4)
        self.label('Sunlight',-.9,2.4)
        for z in [-1.4,-.7,0,.7,1.4]:self.airflow([-.1,-.2,z],[-1.45,-.2,z],SUN)
        self.finish()

class AltitudeClimate(ClimateBase):
    SID='s09-altitude'
    def construct(self):
        sea=Cube(side_length=1).stretch(7,0).stretch(3,1).stretch(.13,2).set_fill(SEA,1).set_stroke(SEA,0).move_to([-2,0,-1.6]);self.add(sea)
        mountain=Cone(base_radius=1.65,height=3.1,resolution=(12,24)).set_fill(LAND,1).set_stroke(LAND,0).move_to([-2,0,-.2]);self.add(mountain)
        summit=Cone(base_radius=.4,height=.8,resolution=(8,16)).set_fill(CREAM,1).set_stroke(CREAM,0).move_to([-2,0,1.1]);self.add(summit)
        self.label('Sea level',-4.6,-2.3);self.label('Higher altitude',-3,2.5);self.label('Cooler',-1.2,1.8)
        self.moving_cloud([-4,.7,1.2]);self.moving_cloud([-.2,.6,1.8]);self.finish()

class BreezeClimate(ClimateBase):
    SID='s10-sea-land-breeze'
    def construct(self):
        self.coast();self.label('Land',-4.7,-1.9);self.label('Sea',-.9,-1.9)
        self.moving_cloud([-2,1,1.8]);day=self.label('Day: sea breeze',-3.4,2.7)
        sun=Sphere(radius=.32,resolution=(8,16)).set_fill(SUN,1).set_stroke(SUN,0).move_to([-5,1,2]);self.add(sun)
        flow=self.airflow([.8,-.5,-.4],[-4.8,-.5,-.4],SEA)
        night=cue(self.SID,'At night, the land');self.until(night)
        self.remove(flow,day,sun);self.label('Night: land breeze',-3.4,2.7)
        self.airflow([-4.8,-.5,-.4],[.8,-.5,-.4],SEA)
        moon=Sphere(radius=.32,resolution=(8,16)).set_fill(CREAM,1).set_stroke(CREAM,0).move_to([-5,1,2]);self.add(moon);self.finish()

class WindClimate(ClimateBase):
    SID='s11-wind'
    def construct(self):
        self.coast();mountain=Cone(base_radius=1.1,height=2.8,resolution=(10,20)).set_fill(LAND,1).set_stroke(LAND,0).move_to([-2.6,0,0]);self.add(mountain)
        self.moving_cloud([-3.8,.2,1.6]);self.airflow([-5,-.2,.1],[-3.1,-.2,1],SEA)
        self.label('Windward',-4.5,2.5);self.label('Leeward',-.7,2.5)
        for i in range(12):
            point=Dot3D([-4.5+(i%4)*.25,-.5+(i//4)*.22,1.3],radius=.025,color=SEA);phase=i*.22;clock=[phase]
            point.add_updater(lambda m,dt,clock=clock,x=-4.5+(i%4)*.25,y=-.5+(i//4)*.22:(clock.__setitem__(0,clock[0]+dt),m.move_to([x,y,1.4-(clock[0]%1.5)])));self.add(point)
        self.finish()

class CurrentsClimate(ClimateBase):
    SID='s13-currents'
    def construct(self):
        self.coast();self.label('Warm current',-4.2,2.5,color=ACCENT);self.label('Cold current',-.8,2.5,color=SEA)
        self.airflow([-4.6,-.6,-.8],[-1.6,-.6,-.8],ACCENT)
        self.airflow([.5,.7,-.8],[-2.2,.7,-.8],SEA)
        self.moving_cloud([-2,1.5,1]);self.finish()

class ZoneBase(ClimateBase):
    LABELS=('Polar regions','Tropics')
    BANDS=((-90,-66.5,SEA),(-66.5,-23.5,LAND),(-23.5,23.5,SUN),(23.5,66.5,LAND),(66.5,90,SEA))
    def construct(self):
        radius=1.7;center=np.array([-2.6,0,0]);parts=VGroup()
        for low,high,color in self.BANDS:
            if high==90:high=89.9
            if low==-90:low=-89.9
            band=Surface(lambda u,v:radius*np.array([math.cos(u)*math.cos(v),math.cos(u)*math.sin(v),math.sin(u)]),u_range=[low*DEGREES,high*DEGREES],v_range=[0,TAU],resolution=(6,24),fill_opacity=1,checkerboard_colors=[color,color],stroke_width=0).shift(center).set_shade_in_3d(True);parts.add(band)
        self.add(parts);parts.add_updater(lambda m,dt:m.rotate(dt*.12,axis=OUT,about_point=center))
        self.label(self.LABELS[0],-3,2.6);self.label(self.LABELS[1],-3,-2.2)
        marker=Dot3D([-4.1,-.6,.1],radius=.07,color=CREAM);clock=[0.0]
        marker.add_updater(lambda m,dt:(clock.__setitem__(0,clock[0]+dt),m.move_to(center+np.array([1.72*math.cos(clock[0]*.12),1.72*math.sin(clock[0]*.12),0]))));self.add(marker)
        self.finish()

class ZonesOverview(ZoneBase):SID='s21-zones'
class TorridClimate(ZoneBase):
    SID='s22-torrid'
    LABELS=('Tropic of Cancer','Tropic of Capricorn')
    BANDS=((-90,-23.5,SEA),(-23.5,23.5,SUN),(23.5,90,SEA))
class TemperateClimate(ZoneBase):
    SID='s23-temperate'
    LABELS=('Temperate zones','Between tropics and polar circles')
    BANDS=((-90,-66.5,SEA),(-66.5,-23.5,SUN),(-23.5,23.5,SEA),(23.5,66.5,SUN),(66.5,90,SEA))
class FrigidClimate(ZoneBase):
    SID='s25-frigid'
    LABELS=('Frigid zones','Near the poles')
    BANDS=((-90,-66.5,CREAM),(-66.5,66.5,SEA),(66.5,90,CREAM))

class LandscapeBase(ClimateBase):
    """True object animation for a whole paragraph, not an extended still."""
    GROUND=LAND
    SKY=BG
    def terrain(self,*,trees=True,snow=False):
        self.camera.background_color=self.SKY
        earth=Cube(side_length=1).stretch(7.4,0).stretch(4,1).stretch(.18,2).set_fill(self.GROUND,1).set_stroke(self.GROUND,0).move_to([-2,0,-1.45]);self.add(earth)
        for x,y,h in [(-5,1.4,1.4),(-3,1.8,1.8),(-.4,1.5,1.35)]:
            peak=Cone(base_radius=1.3,height=h,resolution=(8,16)).set_fill('#A3B9B2' if not snow else CREAM,1).set_stroke(width=0).move_to([x,y,-1.25+h/2]);self.add(peak)
        if trees:
            for x,y in [(-4.8,-.6),(-3.3,.2),(-.9,-.7)]:
                trunk=Cylinder(radius=.065,height=.65,resolution=(6,12)).set_fill('#816447',1).set_stroke(width=0)
                crown=VGroup(*[Sphere(radius=.32,resolution=(6,12)).set_fill('#57967B',1).set_stroke(width=0).shift([dx,0,.5+dz]) for dx,dz in [(-.2,0),(0,.25),(.2,0)]])
                tree=VGroup(trunk,crown).move_to([x,y,-.85]);clock=[0.0];origin=tree.get_center().copy()
                def sway(m,dt,clock=clock,origin=origin):clock[0]+=dt;m.move_to(origin+RIGHT*.06*math.sin(clock[0]*1.2))
                tree.add_updater(sway);self.add(tree)
        self.moving_cloud([-4,1,2]);self.moving_cloud([-1.6,1.5,2.3]);self.moving_cloud([.7,1,1.8]);return earth
    def precipitation(self,*,snow=False):
        group=VGroup()
        for i in range(32):
            x=-5.1+(i%8)*.77;y=-.9+(i//8)*.6;clock=[i*.11]
            drop=Dot3D([x,y,1.6],radius=.038 if snow else .022,color=CREAM if snow else SEA)
            def fall(m,dt,clock=clock,x=x,y=y):clock[0]+=dt;m.move_to([x+.05*math.sin(clock[0]*2),y,1.8-(clock[0]*1.6%3)])
            drop.add_updater(fall);group.add(drop)
        self.add(group);return group
    def sunshine(self):
        sun=Sphere(radius=.32,resolution=(8,16)).set_fill(SUN,1).set_stroke(width=0).move_to([-5,.5,2]);self.add(sun);return sun

class OpeningWeather(LandscapeBase):
    SID='s01-title'
    def construct(self):self.terrain();self.sunshine();self.finish()

class StartupWeather(LandscapeBase):
    SID='s03-startup'
    def construct(self):
        self.terrain();sun=self.sunshine();self.until(cue(self.SID,'rainy?'));rain=self.precipitation()
        self.until(cue(self.SID,'Some places'));self.remove(rain);self.finish()

class WeatherChanges(LandscapeBase):
    SID='s04-weather'
    def construct(self):
        self.terrain();self.sunshine()
        self.until(cue(self.SID,'rainfall,'));rain=self.precipitation();self.until(cue(self.SID,'Weather can change'));self.remove(rain)
        self.until(cue(self.SID,'by afternoon'));self.precipitation();self.finish()

class HotDesert(LandscapeBase):
    SID='s05-hot-desert-fact';GROUND='#D6B272';SKY='#EDF1D6'
    def construct(self):
        self.terrain(trees=False);self.sunshine()
        self.airflow([-5,-1,-.4],[-.4,-1,-.4],SUN);self.finish()

class ClimateContrast(LandscapeBase):
    SID='s06-climate'
    def construct(self):
        self.terrain(trees=False);self.sunshine()
        self.until(cue(self.SID,'the climate of the Amazon'));self.precipitation();self.finish()

class FactorsPreview(ClimateBase):
    SID='s07-factors'
    def construct(self):self.blue_globe();self.moving_cloud([-4,1,1.8]);self.finish()

class HumidityClimate(LandscapeBase):
    SID='s12-humidity'
    def construct(self):
        self.terrain();self.precipitation()
        # Water vapour is invisible; no visible steam is claimed as vapour.
        self.label('Water vapour in air',-3,2.6);self.finish()

class RainforestClimate(LandscapeBase):
    SID='s14-rainforest-fact'
    def construct(self):self.terrain();self.precipitation();self.finish()

class ClimateTypesPreview(ClimateBase):
    SID='s15-climate-types'
    def construct(self):self.blue_globe();self.moving_cloud([-4,1,1.8]);self.finish()

class MonsoonClimate(LandscapeBase):
    SID='s16-monsoon'
    def construct(self):self.terrain();self.precipitation();self.airflow([-5,-.5,1],[-1,-.5,1],SEA);self.finish()

class EquatorialClimate(LandscapeBase):
    SID='s17-equatorial'
    def construct(self):self.terrain();self.precipitation();self.finish()

class DesertClimate(LandscapeBase):
    SID='s18-desert';GROUND='#D6B272'
    def construct(self):
        self.terrain(trees=False);sun=self.sunshine();self.airflow([-5,-1,-.4],[-.4,-1,-.4],SUN)
        self.until(cue(self.SID,'cold nights'));self.remove(sun);self.camera.background_color='#7C9CB1'
        self.moving_cloud([-5,.5,2],color=CREAM);self.finish()

class TundraClimate(LandscapeBase):
    SID='s19-tundra';GROUND='#DBE9E6'
    def construct(self):self.terrain(trees=False,snow=True);self.precipitation(snow=True);self.finish()

class AntarcticaClimate(LandscapeBase):
    SID='s20-antarctica-fact';GROUND='#E8F3EE'
    def construct(self):
        self.terrain(trees=False,snow=True)
        # Blowing existing snow, not precipitation or an invented rain event.
        for y in [-1,-.5,0]:self.airflow([-5,y,-.8],[.5,y,-.8],CREAM)
        self.finish()

class CloudClimate(LandscapeBase):
    SID='s24-cloud-fact'
    def construct(self):
        self.terrain();self.sunshine();fair=self.label('Cumulus',-3,2.7)
        self.until(cue(self.SID,'while nimbostratus'));self.remove(fair);self.label('Nimbostratus',-3,2.7);self.precipitation();self.finish()
