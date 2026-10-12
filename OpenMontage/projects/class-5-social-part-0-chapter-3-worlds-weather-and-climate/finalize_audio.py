"""Count natural heading silence, insert only the missing two-second pause."""
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import subprocess
import numpy as np
import soundfile as sf
from lib.production_runtime import atomic_json
from tools.analysis.narration_text_syncer import _build_word_captions,_build_formatted_srt
from tools.structure.educational_run_tracker import EducationalRunTracker

P=Path(__file__).resolve().parent
RAW=P/'assets/audio/narration-elevenlabs-v1/narration_manifest.json'
ALIGN=P/'artifacts/alignment-raw-v1/narration_aligned.json'
OUT=P/'assets/audio/narration-elevenlabs-timed-v1'

def silence(path):
    result=subprocess.run(['ffmpeg','-v','info','-i',str(path),'-af','silencedetect=noise=-38dB:d=0.12','-f','null',os.devnull],capture_output=True,text=True,check=True,timeout=60)
    starts=[float(x) for x in re.findall(r'silence_start:\s*([0-9.]+)',result.stderr)]
    ends=[float(x) for x in re.findall(r'silence_end:\s*([0-9.]+)',result.stderr)]
    return list(zip(starts,ends,strict=True))

def main(checkpoints=True):
    manifest=json.loads(RAW.read_text(encoding='utf-8'));aligned=json.loads(ALIGN.read_text(encoding='utf-8'))
    lookup={s['section_id']:s for s in aligned['segments']};result=deepcopy(manifest);rebased=[];audit=[];cursor=0.0
    OUT.mkdir(parents=True,exist_ok=True)
    for i,s in enumerate(result['segments']):
        entry=deepcopy(lookup[s['section_id']]);old_start=entry['start_ms'];n=len(s['spoken_heading'].split())
        if n>len(entry['words']):raise ValueError('Heading word count invalid')
        boundary=(entry['words'][n-1]['end_ms']-old_start)/1000
        samples,sr=sf.read(s['audio_path'],dtype='float32');gaps=silence(s['audio_path']);has_body=n<len(entry['words'])
        if has_body:
            candidates=[(a,b) for a,b in gaps if a<=boundary+.3 and b>=boundary-.15]
            if not candidates:raise ValueError(f"No quiet heading edit point: {s['section_id']}")
            a,b=min(candidates,key=lambda g:abs(g[0]-boundary));natural=b-a;pad=max(0.0,2-natural);cut=(a+b)/2
            idx=round(cut*sr);pre=samples[:idx].copy();post=samples[idx:].copy();fade=min(round(.006*sr),len(pre),len(post))
            if fade:pre[-fade:]*=np.linspace(1,0,fade);post[:fade]*=np.linspace(0,1,fade)
            edited=np.concatenate((pre,np.zeros(round(pad*sr),dtype=samples.dtype),post));body_start=b+pad;heading_end=a
        else:
            trailing_gaps=[(a,b) for a,b in gaps if abs(b-len(samples)/sr)<.02 and a>=boundary-.2]
            if not trailing_gaps:raise ValueError('No measured trailing title silence')
            heading_end=trailing_gaps[-1][0];natural=len(samples)/sr-heading_end;pad=max(0.0,2-natural);cut=len(samples)/sr
            edited=np.concatenate((samples,np.zeros(round(pad*sr),dtype=samples.dtype)));body_start=boundary
        # Count existing trailing silence before adding processing time.
        final_word_end=(entry['words'][-1]['end_ms']-old_start)/1000+(pad if has_body else 0)
        trailing=len(edited)/sr-final_word_end
        topic_pad=0 if i==0 else max(0,1.5-trailing)
        edited=np.concatenate((edited,np.zeros(round(topic_pad*sr),dtype=samples.dtype)))
        target=OUT/f"{s['section_id']}.wav";sf.write(target,edited,sr,subtype='PCM_16');duration=len(edited)/sr
        for w in entry['words']:
            for key in ('start_ms','end_ms'):
                rel=w[key]-old_start;shift=round(pad*1000) if has_body and rel>=round(cut*1000) else 0
                w[key]=round(cursor*1000)+rel+shift
        entry['start_ms']=round(cursor*1000);entry['end_ms']=round((cursor+duration)*1000);entry['audio_path']=str(target)
        entry['words'][n-1]['end_ms']=round((cursor+heading_end)*1000)
        if has_body:entry['words'][n]['start_ms']=round((cursor+body_start)*1000)
        s.update(audio_path=str(target),start_seconds=cursor,duration_seconds=duration,heading_duration_seconds=heading_end,body_start_seconds=body_start,heading_pause_presentation='inline',measured_title_pause_seconds=natural+pad,title_card_hold_seconds=0,topic_end_pause_seconds=topic_pad)
        audit.append({'section_id':s['section_id'],'heading_end':heading_end,'body_start':body_start,'natural_heading_pause':natural,'inserted_heading_pause':pad,'total_heading_pause':natural+pad,'topic_padding':topic_pad})
        rebased.append(entry);cursor+=duration
    result['metadata']={**result.get('metadata',{}),'model_id':result.pop('model_id',None),'speed':result.pop('speed',None),'timing_policy':'two seconds total after headings; in-scene heading; natural pause counted; topic trailing pause 1.5 seconds total'}
    result['total_duration_seconds']=cursor
    result['pronunciation_qa_status']='unverified'
    result['word_alignment_status']='passed'
    atomic_json(OUT/'narration_manifest.json',result)
    dest=P/'artifacts/alignment-timed-v1';atomic_json(dest/'narration_aligned.json',{'segments':rebased,'method':'acoustic CTC with exact sample insertion rebase'})
    atomic_json(dest/'word_captions.json',_build_word_captions(rebased));(dest/'formatted_subtitles.srt').write_text(_build_formatted_srt(rebased),encoding='utf-8')
    atomic_json(P/'artifacts/audio-pause-audit-v1.json',audit)
    if checkpoints:
        tracker=EducationalRunTracker(P,title='Worlds Weather and Climate',approval_policy='full-run-preauthorized')
        tracker.finish('voice_synthesis',{'narration_manifest':result},metadata={'segments':len(rebased),'duration_seconds':cursor,'spoken_heading_pause_seconds':2,'voice_id':result['voice_name']})
        tracker.begin('text_audio_alignment');tracker.finish('text_audio_alignment',{'narration_aligned_path':str(dest/'narration_aligned.json'),'word_captions_path':str(dest/'word_captions.json'),'formatted_srt_path':str(dest/'formatted_subtitles.srt'),'timing_qa_path':str(P/'artifacts/audio-pause-audit-v1.json')},metadata={'method':'measured CTC; no proportional word timings','words':sum(len(s['words']) for s in rebased)})
    print(json.dumps({'status':'timed_audio_ready','sections':len(rebased),'seconds':cursor}))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--skip-checkpoints',action='store_true');args=parser.parse_args();main(checkpoints=not args.skip_checkpoints)
