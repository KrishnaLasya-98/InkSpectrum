"""Measure final encoding and audio placement; leave visual approval explicit."""
from __future__ import annotations
import hashlib,json,subprocess,re
from pathlib import Path
import numpy as np

P=Path(__file__).resolve().parent
V=P/'hyperframes-elevenlabs-sync-repair-v5/renders/class5-social-chapter2-earth-movement-sync-repair-v5.mp4'
A=P/'artifacts'

def read(p): return json.loads(p.read_text(encoding='utf-8'))
def decode(path,rate=4000):
    r=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-vn','-ar',str(rate),'-ac','1','-f','f32le','pipe:1'],capture_output=True,check=True,timeout=90)
    return np.frombuffer(r.stdout,dtype=np.float32)

def main():
    if not V.exists(): raise FileNotFoundError(V)
    probe=read_json_command(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(V)])
    audio=read(P/'assets/audio/narration-elevenlabs-title-pause-v4/narration_manifest.json')
    aligned={s['section_id']:s for s in read(A/'alignment-ctc-v5/narration_aligned.json')['segments']}
    track=decode(V); rate=4000; checks=[]
    for s in audio['segments']:
        source=decode(s['audio_path'])
        sid=s['section_id']; words=aligned[sid]['words']
        # Compare two voiced windows per segment, not the synthetic heading gap.
        picks=[max(0,(words[min(2,len(words)-1)]['start_ms']/1000-s['start_seconds'])),
               max(0,(words[max(0,len(words)-5)]['start_ms']/1000-s['start_seconds']))]
        for offset in picks:
            source_i=int(offset*rate); sample=source[source_i:source_i+rate]
            if len(sample)<rate//2 or np.linalg.norm(sample)<.001: continue
            center=round((s['start_seconds']+offset)*rate)
            margin=int(.15*rate); left=max(0,center-margin)
            search=track[left:center+margin+len(sample)]
            x=sample-sample.mean()
            cc=np.correlate(search,x,mode='valid')
            best=int(np.argmax(cc)); y=search[best:best+len(x)]; y=y-y.mean()
            correlation=float(np.dot(x,y)/(np.linalg.norm(x)*np.linalg.norm(y)+1e-12))
            shift=(left+best-center)/rate
            checks.append({'section_id':sid,'source_offset_seconds':round(offset,3),'encoded_shift_seconds':round(shift,5),'correlation':round(correlation,5)})
    analysis=subprocess.run(['ffmpeg','-hide_banner','-i',str(V),'-vf','scale=480:-2,blackdetect=d=0.15:pix_th=0.10,freezedetect=n=-50dB:d=3','-af','silencedetect=noise=-38dB:d=2.5','-f','null','-'],capture_output=True,text=True,timeout=300)
    (A/'encoded-sync-v5-detection.log').write_text(analysis.stderr,encoding='utf-8')
    events=[line for line in analysis.stderr.splitlines() if any(t in line for t in ['black_start:','freeze_start:','freeze_end:','silence_start:','silence_end:'])]
    roi=subprocess.run(['ffmpeg','-hide_banner','-i',str(V),'-an','-vf',
        'crop=1240:735:0:160,scale=496:294,freezedetect=n=-55dB:d=3',
        '-f','null','-'],capture_output=True,text=True,timeout=300)
    (A/'encoded-sync-v5-visual-roi.log').write_text(roi.stderr,encoding='utf-8')
    roi_events=[line for line in roi.stderr.splitlines() if 'freeze_' in line]
    issues=[]
    if analysis.returncode: issues.append('ffmpeg_decode_failure')
    if any(abs(r['encoded_shift_seconds'])>.04 or r['correlation']<.90 for r in checks): issues.append('audio_placement_or_content')
    if any('black_start:' in e for e in events): issues.append('black_interval')
    if roi.returncode: issues.append('visual_roi_decode_failure')
    result={'status':'technical_pass' if not issues else 'review_required','issues':issues,'path':str(V),'sha256':hashlib.sha256(V.read_bytes()).hexdigest(),'probe':probe,'audio_placement_checks':checks,'detection_events':events,'visual_roi_events':roi_events,'visual_review':'pending; source-diagram and recall static intervals require contextual review','coverage':read(A/'source-coverage-elevenlabs-sync-repair-v5.json')}
    (A/'encoded-sync-v5-qa.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'issues':issues,'duration':probe['format']['duration'],'audio_windows':len(checks),'max_abs_audio_shift_seconds':max(abs(r['encoded_shift_seconds']) for r in checks),'minimum_audio_correlation':min(r['correlation'] for r in checks),'events':events,'visual_roi_events':roi_events},indent=2))

def read_json_command(cmd): return json.loads(subprocess.check_output(cmd,text=True,timeout=30))
if __name__=='__main__': main()
