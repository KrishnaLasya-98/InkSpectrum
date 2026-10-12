"""Compose Chapter 2 from forced word alignment and continuous scientific motion."""
from __future__ import annotations
import json
import hashlib
import subprocess
from copy import deepcopy
from pathlib import Path
import numpy as np
from difflib import SequenceMatcher

from tools.video.educational_hyperframes_composer import EducationalHyperFramesComposer
from build_qwen_composition import cue_start_seconds, _tokens
from build_teaching_pages import build as build_pages

P=Path(__file__).resolve().parent
R=P.parents[1]
A=P/'artifacts'
VERSION='elevenlabs-sync-repair-v5'
ALIGN=A/'alignment-ctc-v5'
SCI=P/'assets/video/science-v5/videos/precision_earth_v5/720p24'


def read(p): return json.loads(p.read_text(encoding='utf-8'))
def save(p,data): p.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def probe(p):
    return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(p)],text=True,timeout=30))


def subtitle_safe_science(name, y):
    """Reserve the subtitle lane; duplicate bottom text is in source cards.

    The explanatory globe/orbit, axis and day/night labels remain intact.
    This is a solid background mask, not a frozen image or looped footage.
    """
    source=SCI/f'{name}.mp4'
    target=SCI/f'{name}-subtitle-safe-{y}.mp4'
    if not target.exists():
        subprocess.run(['ffmpeg','-v','error','-i',str(source),'-an','-vf',
            f'drawbox=x=0:y={y}:w=iw:h=ih-{y}:color=0xDCEEF1:t=fill',
            '-c:v','libx264','-preset','fast','-crf','18',str(target)],check=True,timeout=180)
    return str(target.relative_to(P))


def seek_safe(path):
    source=P/path
    fingerprint=hashlib.sha256(source.read_bytes()).hexdigest()[:12]
    target=P/'assets/video/render-safe-v5'/f'{source.stem}-{fingerprint}.mp4'
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():
        subprocess.run(['ffmpeg','-v','error','-i',str(source),'-an','-vf','fps=30',
            '-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',
            '-g','30','-keyint_min','30','-sc_threshold','0','-movflags','+faststart',
            str(target)],check=True,timeout=180)
    return str(target.relative_to(P))


def main():
    clips=deepcopy(read(A/'clip-manifest-elevenlabs-title-pause-v4.json'))
    audio=read(P/'assets/audio/narration-elevenlabs-title-pause-v4/narration_manifest.json')
    aligned={s['section_id']:s for s in read(ALIGN/'narration_aligned.json')['segments']}
    old={s['section_id']:s for s in read(A/'alignment-elevenlabs-title-pause-v4/narration_aligned.json')['segments']}
    narr={s['section_id']:s for s in audio['segments']}
    sync=deepcopy(read(A/'multimedia-sync-elevenlabs-title-pause-v4.json'))
    def anchor(sid,phrase):
        return cue_start_seconds(phrase,aligned[sid],section_id=sid)[0]+.15
    def motion(path,start,dur,cue):
        absolute=P/path
        if not absolute.is_file(): raise FileNotFoundError(absolute)
        available=probe(absolute)
        if available+.045<dur: raise ValueError(f'Insufficient motion: {path}: {available} < {dur}')
        return {'path':path,'offset_seconds':round(start,3),'duration_seconds':round(dur,3),'cue':cue,'timing_basis':'ctc_forced_alignment'}
    def matched_time(sid,value):
        before,after=old[sid],aligned[sid]
        l=[_tokens(w['word'])[0] if _tokens(w['word']) else '' for w in before['words']]
        r=[_tokens(w['word'])[0] if _tokens(w['word']) else '' for w in after['words']]
        pairs=[(0.,0.)]
        for block in SequenceMatcher(None,l,r,autojunk=False).get_matching_blocks():
            for k in range(block.size):
                x=(before['words'][block.a+k]['start_ms']-before['start_ms'])/1000
                y=(after['words'][block.b+k]['start_ms']-after['start_ms'])/1000
                if x>pairs[-1][0]: pairs.append((x,y))
        pairs.append((narr[sid]['duration_seconds'],narr[sid]['duration_seconds']))
        return float(np.interp(value,[p[0] for p in pairs],[p[1] for p in pairs]))
    for clip in clips['clips']:
        sid=clip['section_id']; total=narr[sid]['duration_seconds']
        for f in clip.get('source_figure_overlays',[]):
            a=f['offset_seconds']; b=a+f['duration_seconds']
            f['offset_seconds']=round(matched_time(sid,a),3)
            f['duration_seconds']=round(matched_time(sid,b)-f['offset_seconds'],3)
        for i,v in enumerate(clip.get('visual_segments',[])):
            start=0. if sid in ('s01-title','s02-objectives','s03-startup') and i==0 else max(0.,anchor(sid,v['cue'])-.08) if sid!='s05-two-movements' else 0.
            available=probe(P/v['path'])
            v['offset_seconds']=round(start,3)
            v['duration_seconds']=round(min(available-.035,total-start),3)
        if sid=='s04-spherical-earth':
            base=motion(str((SCI/'SphericalContextV5.mp4').relative_to(P)),0,total,'spherical Earth')
            old_motion=clip['visual_segments']
            ship_start=max(0,anchor(sid,'ships disappear')-.08)
            eclipse_start=max(0,anchor(sid,"the Earth's shadow on the Moon")-.08)
            voyage_start=max(0,anchor(sid,"Ferdinand Magellan's voyage")-.08)
            sphere_path='assets/video/motion-batch-12-sync-repair/spherical-earth-context-12.mp4'
            voyage_path='assets/video/motion-batch-12-sync-repair/voyage-ship-12.mp4'
            for path in (sphere_path,voyage_path):
                if not (P/path).is_file(): raise FileNotFoundError(P/path)
            # Modest 1.12x duration extension keeps the new ship in view for the
            # complete spoken voyage sentence; never loop or freeze its end.
            voyage_target=P/'assets/video/science-v5/voyage-for-spoken-line.mp4'
            needed=total-voyage_start; available=probe(P/voyage_path)
            if needed/available>1.25: raise ValueError('Voyage needs additional unique media')
            if not voyage_target.exists():
                subprocess.run(['ffmpeg','-v','error','-i',str(P/voyage_path),'-an','-vf',f'setpts={needed/available:.8f}*PTS,fps=30,scale=1920:1080','-c:v','libx264','-preset','fast','-crf','18',str(voyage_target)],check=True,timeout=120)
            clip['visual_segments']=[base,
                motion(sphere_path,anchor(sid,'However'),min(probe(P/sphere_path)-.04,ship_start-anchor(sid,'However')),'the Earth is spherical'),
                motion(old_motion[0]['path'],ship_start,eclipse_start-ship_start+.12,'ships disappear over the horizon'),
                motion(old_motion[1]['path'],eclipse_start,min(probe(P/old_motion[1]['path'])-.04,voyage_start-eclipse_start+.12),"the Earth's shadow on the Moon"),
                motion(str(voyage_target.relative_to(P)),voyage_start,needed,"Ferdinand Magellan's voyage")]
            clip['source_figure_overlays']=[{'path':'imageFile3.png','offset_seconds':narr[sid]['body_start_seconds'],'duration_seconds':4.3}]
        elif sid=='s05-two-movements':
            clip['visual_segments']=[motion(str((SCI/'ContrastV5.mp4').relative_to(P)),0,total,'Rotation and Revolution')]
            clip['source_figure_overlays']=[{'path':'source-hires/rotation-revolution.png','offset_seconds':max(0,total-3.5),'duration_seconds':3.5}]
        elif sid=='s06-rotation':
            extras=[v for v in clip['visual_segments'][1:] if 'experiences day' in v['cue'] or 'experiences night' in v['cue']]
            clip['visual_segments']=[motion(subtitle_safe_science('RotationV5',628),0,total,'rotation on the fixed tilted axis')]+extras
            tilt_start=anchor(sid,'The axis is tilted')
            clip['source_figure_overlays']=[{'path':'source-hires/axis-tilt.png','offset_seconds':tilt_start,'duration_seconds':5.0}]
        elif sid=='s08-revolution':
            summer=anchor(sid,'Summer')
            clip['visual_segments']=[motion(subtitle_safe_science('RevolutionV5',610),0,summer,'revolution with fixed axial direction')]+clip['visual_segments'][1:]
            clip['source_figure_overlays']=[{'path':'source-hires/rotation-revolution.png','offset_seconds':anchor(sid,'It takes three hundred'),'duration_seconds':5.2}]
        clip['source_card_intervals']=[[0,total]]
        for v in clip.get('visual_segments',[]):
            v['transition']='cut'
            if 'science-v5' in v['path'] or 'motion-batch-12' in v['path']:
                v['source_asset']=v['path']
                v['path']=seek_safe(v['path'])
    clips['policy']='Exact scientific geometry; CTC-measured word cues; unique Wan contextual clips; no looped or frozen video'
    clips['timing_authority']='alignment-ctc-v5/narration_aligned.json; unchanged title-pause-v4 waveform'
    clips['status']='composition_review_pending'
    sync_path=A/f'multimedia-sync-{VERSION}.json'; save(sync_path,sync)
    pages=build_pages(sync_path,ALIGN/'word_captions.json',A/f'teaching-pages-{VERSION}.json')
    if pages['unmatched_anchors']: raise ValueError('Unmatched teaching-page anchors')
    for clip in clips['clips']:
        if clip['section_id'] in pages['sections']: clip['teaching_pages']=pages['sections'][clip['section_id']]
    save(A/f'clip-manifest-{VERSION}.json',clips)
    result=EducationalHyperFramesComposer().execute({
        'workspace_path':str(P/f'hyperframes-{VERSION}'),'asset_base_dir':str(P),
        'template_contract':str(R/'styles/hyperframes-educational-v1.yaml'),
        'educational_plan':str(A/'educational_plan.json'),'clip_manifest':clips,
        'narration_manifest':audio,'multimedia_sync_plan':sync,'word_captions':str(ALIGN/'word_captions.json'),
        'presentation_variant':read(P/'chapter_config.json')['presentation_variant']})
    if not result.success: raise RuntimeError(result.error)
    print(json.dumps(result.data,indent=2))


if __name__=='__main__': main()
