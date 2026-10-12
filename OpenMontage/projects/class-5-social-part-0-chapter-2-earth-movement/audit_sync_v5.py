"""Validate Chapter 2 timing/coverage without claiming perceptual approval."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

P=Path(__file__).resolve().parent
A=P/'artifacts'
def read(path): return json.loads(path.read_text(encoding='utf-8'))

def main():
    narration=read(P/'assets/audio/narration-elevenlabs-title-pause-v4/narration_manifest.json')
    aligned=read(A/'alignment-ctc-v5/narration_aligned.json')['segments']
    lookup={s['section_id']:s for s in narration['segments']}
    rows=[]
    for s in aligned:
        sid=s['section_id']; n=lookup[sid]; w=s['words']
        assert ' '.join(x['word'] for x in w)==n['text'], f'Transcript changed: {sid}'
        assert all(x['end_ms']>x['start_ms'] for x in w), sid
        assert all(x['end_ms']<=y['start_ms'] for x,y in zip(w,w[1:])), sid
        assert w[0]['start_ms']>=n['start_seconds']*1000-2, sid
        assert w[-1]['end_ms']<=(n['start_seconds']+n['duration_seconds'])*1000+2, sid
        assert all(x['timing_basis']=='ctc_forced_alignment' for x in w), sid
        assert n['measured_title_pause_seconds']==2.0, sid
        rows.append({'section_id':sid,'word_count':len(w),'audio_sha256':hashlib.sha256(Path(n['audio_path']).read_bytes()).hexdigest(),'title_pause_seconds':n['measured_title_pause_seconds']})
    result={'status':'timing_structure_pass','sections':rows,'perceptual_qa':'pending','encoded_video_qa':'pending'}
    clips_path=A/'clip-manifest-elevenlabs-sync-repair-v5.json'
    if clips_path.exists():
        coverage=[]
        for c in read(clips_path)['clips']:
            total=lookup[c['section_id']]['duration_seconds']; intervals=[]
            for v in c.get('visual_segments',[]):
                assert (P/v['path']).is_file(), v['path']
                start=v['offset_seconds']; end=start+v['duration_seconds']
                assert start>=0 and end<=total+.05, (c['section_id'],start,end,total)
                intervals.append((start,end))
            edge=0.; gaps=[]
            for start,end in sorted(intervals):
                if start>edge+.05: gaps.append([round(edge,3),round(start,3)])
                edge=max(edge,end)
            if edge<total-.05: gaps.append([round(edge,3),total])
            if c['section_id'] in ('s04-spherical-earth','s05-two-movements','s06-rotation'):
                assert not gaps, (c['section_id'],gaps)
            coverage.append({'section_id':c['section_id'],'video_gaps_seconds':gaps,'note':'Gaps in other sections require deliberate source-diagram/card review, not automatic acceptance.'})
        result['media_coverage']=coverage
    target=A/'sync-v5-structural-audit.json'
    target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'sections':len(rows),'words':sum(r['word_count'] for r in rows),'path':str(target)},indent=2))

if __name__=='__main__': main()
