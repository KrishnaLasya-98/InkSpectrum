"""Durable Chapter 3 narration and first bounded motion batch."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
import requests
from dotenv import load_dotenv
from lib.production_runtime import atomic_json
from tools.structure.educational_run_tracker import EducationalRunTracker

P=Path(__file__).resolve().parent
R=P.parents[1]
VOICE='zJrRUu1KEcKH8qdpNaPJ'
MODEL='eleven_v4'
SETTINGS={'stability':0.5,'similarity_boost':0.8,'speed':0.85}
ROOT=P/'assets/audio/narration-elevenlabs-v1'

SHOTS=[
 ('weather-opening','s01-title','A wide magical but realistic-scale meadow with fluffy clouds moving across blue sky, a leafy tree swaying gently, distant snowy mountains and a warm sun, child-friendly polished 3D animated film, camera glides slowly over grass, large clear space on the left for a later HTML overlay.'),
 ('window-sun','s03-startup','An Indian schoolchild with short dark hair and a blue school uniform looks through a classroom window, outside is a bright sunny garden with leaves moving in a light breeze. Warm friendly polished 3D animated film, child points gently toward the sunshine, stable facial anatomy.'),
 ('window-cloud','s03-startup','From inside an empty bright classroom, look through a wide window at a garden as dense soft clouds drift across the sky and the garden becomes softly shaded, moving tree leaves and a natural change in illumination, child-friendly polished 3D animation, no people.'),
 ('window-rain','s03-startup','From inside an empty bright classroom, look through a wide window at a rainy garden, visible raindrops strike the glass and small puddles ripple outside, tree foliage moves gently, child-friendly polished 3D animated film, calm safe weather.'),
 ('weather-wind','s04-weather','A friendly 3D countryside meadow with grasses and leafy trees bending visibly in a moderate wind, soft clouds moving across the sky, stable wide camera view, bright natural colors, clearly animated foliage throughout, calm child-friendly weather explanation.'),
 ('weather-rain','s04-weather','A child-friendly 3D garden during afternoon rain, visible raindrops falling continuously and making ripples in shallow puddles, gently swaying leaves, soft overcast light and a steady camera, clean landscape with space in upper right for an overlay.'),
 ('lut-rocky-heat','s05-hot-desert-fact','An uninhabited rocky desert with reddish sandstone ridges, shimmering hot air above the ground, an intense bright sun and sparse dust drifting gently, polished child-friendly 3D animated film, slow sideways camera glide, no thermometers or generated measurements.'),
 ('sahara-dunes','s06-climate','An uninhabited hot dry desert with golden sand dunes, gentle wind pushing fine grains along dune crests and a slow low camera glide, bright clear sky, polished child-friendly 3D animated film, no animals or people.'),
 ('amazon-rain','s06-climate','A lush tropical rainforest with layered broad green leaves, tall trees and falling rain, tiny droplets drip from leaves, mist moves between trunks and foliage sways gently, polished child-friendly 3D animated film, slow coherent forward camera movement.'),
 ('mountain-ascending','s09-altitude','A child-friendly 3D mountain landscape with green lowland foothills and a snowy summit, camera rises gradually from the warm valley toward the high snow line, soft moving clouds and trees, clean geography with no labels, sunny readable lighting.'),
 ('coast-day','s10-sea-land-breeze','A sunny coastal landscape with sandy shore on the left and blue sea on the right, gentle ocean waves roll toward shore and dune grass moves in a mild breeze, polished child-friendly 3D animated film, fixed wide camera and natural day lighting, no arrows or labels.'),
 ('coast-night','s10-sea-land-breeze','A calm moonlit coastal landscape with land on the left and sea on the right, waves move gently and a few small clouds drift under a visible crescent moon, polished child-friendly 3D animated film, readable soft night lighting, stable wide view, no text or arrows.'),
]

def prepare_batch():
    path=P/'assets/video/motion-batch-01.json'
    data={'version':'1.0','provider':'modelslab','model_id':'wan2.2','operation':'text_to_video',
        'shots':[{'shot_id':sid,'section_id':section,'prompt':prompt+' No text, no captions, no logos, no watermark, genuine continuous object motion, no frozen image.'} for sid,section,prompt in SHOTS]}
    if path.exists() and json.loads(path.read_text())!=data: raise ValueError('Existing shot batch changed')
    atomic_json(path,data)
    print(json.dumps({'batch':str(path),'shots':len(SHOTS)}))

def speech():
    load_dotenv(R/'.env',override=False)
    key=os.getenv('ELEVENLABS_API_KEY','').strip()
    if not key: raise RuntimeError('Set ELEVENLABS_API_KEY in local ignored environment')
    plan=json.loads((P/'artifacts/educational_plan.json').read_text(encoding='utf-8'))
    ROOT.mkdir(parents=True,exist_ok=True)
    tracker=EducationalRunTracker(P,title=plan['title'],approval_policy='full-run-preauthorized')
    tracker.begin('voice_synthesis',metadata={'provider':'elevenlabs','model':MODEL,'voice_id':VOICE})
    rows=[]; cursor=0.0
    for i,section in enumerate(plan['sections']):
        sid=section['section_id']; text=section['narration_script']
        mp3=ROOT/f'{sid}.mp3'; state=ROOT/f'{sid}.request.json'; wav=ROOT/f'{sid}.wav'
        previous=plan['sections'][i-1]['narration_script'] if i else ''
        following=plan['sections'][i+1]['narration_script'] if i+1<len(plan['sections']) else ''
        payload={'text':text,'model_id':MODEL,'voice_settings':SETTINGS,'apply_text_normalization':'on',
            **({'previous_text':previous[-500:]} if previous else {}),**({'next_text':following[:500]} if following else {})}
        fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
        if state.exists():
            prior=json.loads(state.read_text())
            if prior['fingerprint']!=fingerprint:raise RuntimeError(f'Audio input changed: {sid}')
            if prior['status']!='audio_received' or not mp3.exists():raise RuntimeError(f'Unknown or failed speech outcome for {sid}; do not resubmit automatically')
        else:
            atomic_json(state,{'status':'request_started','fingerprint':fingerprint,'voice_id':VOICE,'model':MODEL,'characters':len(text)})
            try:
                response=requests.post(f'https://api.elevenlabs.io/v1/text-to-speech/{VOICE}',
                    params={'output_format':'mp3_44100_128'},headers={'xi-api-key':key,'Content-Type':'application/json','Accept':'audio/mpeg'},json=payload,timeout=(15,180))
            except requests.RequestException as exc:
                atomic_json(state,{'status':'transport_outcome_unknown','fingerprint':fingerprint,'error_type':type(exc).__name__})
                raise RuntimeError(f'Speech transport outcome unknown: {sid}; no automatic retry') from None
            if not response.ok:
                atomic_json(state,{'status':'http_error','fingerprint':fingerprint,'http_status':response.status_code})
                raise RuntimeError(f'ElevenLabs HTTP {response.status_code} at {sid}; no provider substitution')
            if len(response.content)<1000 or not response.content.startswith((b'ID3',b'\xff\xfb',b'\xff\xf3',b'\xff\xf2')):raise RuntimeError('Invalid speech response')
            temp=mp3.with_suffix('.mp3.part');temp.write_bytes(response.content);temp.replace(mp3)
            atomic_json(state,{'status':'audio_received','fingerprint':fingerprint,'voice_id':VOICE,'model':MODEL,'characters':len(text),'sha256':hashlib.sha256(mp3.read_bytes()).hexdigest()})
        if not wav.exists():
            subprocess.run(['ffmpeg','-v','error','-i',str(mp3),'-af','loudnorm=I=-16:TP=-1.5:LRA=11','-ar','24000','-ac','1','-c:a','pcm_s16le',str(wav)],check=True,timeout=120)
        duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(wav)],text=True,timeout=30))
        heading='Social Studies, Class 5. '+section['title']+'.' if i==0 else section['title'].rstrip('.!?')+('.' if section['title'][-1] not in '!?' else section['title'][-1])
        rows.append({'section_id':sid,'text':text,'spoken_heading':heading,'audio_path':str(wav),'voice_used':VOICE,'duration_seconds':duration,'start_seconds':cursor,'title_card_hold_seconds':0,'topic_end_pause_seconds':0,'heading_holds':[]})
        cursor+=duration
        manifest={'version':'1.0','engine_used':'elevenlabs','voice_name':VOICE,'model_id':MODEL,'speed':0.85,'generation_complete':len(rows)==len(plan['sections']),'segments':rows}
        atomic_json(ROOT/'narration_manifest.json',manifest)
        tracker.progress('voice_synthesis',partial_progress={'generated':len(rows),'total':len(plan['sections']),'duration_seconds':cursor,'status':'raw_speech_received_timing_pending'})
        print(f'Chapter 3 speech {len(rows)}/{len(plan["sections"])} ready: {sid}',flush=True)
    print(json.dumps({'status':'raw_speech_complete_heading_pause_and_alignment_pending','segments':len(rows),'seconds':cursor}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['batch','speech']);a=p.parse_args()
    prepare_batch() if a.mode=='batch' else speech()
