"""Measure output pauses; decode unconstrained CTC for pronunciation triage."""
import json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import numpy as np
from transformers import Wav2Vec2Processor
from lib.production_runtime import atomic_json
from finalize_audio import silence
P=Path(__file__).resolve().parent;R=P.parents[1];A=P/'artifacts'
def main():
 audio=json.loads((P/'assets/audio/narration-elevenlabs-timed-v1/narration_manifest.json').read_text());aligned=json.loads((A/'alignment-timed-v1/narration_aligned.json').read_text());pauses=json.loads((A/'audio-pause-audit-v1.json').read_text());checks=[]
 for n,audit,segment in zip(audio['segments'],pauses,aligned['segments'],strict=True):
  if n['section_id']!=audit['section_id'] or n['section_id']!=segment['section_id']:raise ValueError('Section ordering differs')
  if any(w['end_ms']<=w['start_ms'] for w in segment['words']):raise ValueError('Non-positive word interval')
  if any(a['end_ms']>b['start_ms'] for a,b in zip(segment['words'],segment['words'][1:])):raise ValueError('Overlapping word intervals')
  gaps=silence(n['audio_path']);expected=audit['heading_end'];matches=[(a,b) for a,b in gaps if a<=expected+.06 and b>=expected-.06]
  if not matches:raise ValueError(f'No measured heading pause: {n["section_id"]}')
  gap=min(matches,key=lambda pair:abs(pair[0]-expected));seconds=gap[1]-gap[0]
  # The title-only opening ends in silence; the file ends after its pause.
  if abs(seconds-2)>.08:raise ValueError(f'Incorrect encoded waveform heading pause: {n["section_id"]}: {seconds}')
  checks.append({'section_id':n['section_id'],'measured_quiet_heading_gap_seconds':round(seconds,5),'words':len(segment['words']),'word_intervals_valid':True})
 processor=Wav2Vec2Processor.from_pretrained('facebook/wav2vec2-base-960h',cache_dir=R/'.cache/alignment',token=False,local_files_only=True)
 transcriptions=[]
 for cache in sorted((A/'alignment-raw-v1').glob('*.emission.npz')):
  sid=cache.name.split('-',1)[0] # get exact ID from cached align artifacts instead
  sid=next(s['section_id'] for s in audio['segments'] if cache.name.startswith(s['section_id']+'-'))
  with np.load(cache) as emissions:ids=emissions['logp'].argmax(axis=-1)
  heard=processor.decode(ids);transcriptions.append({'section_id':sid,'unconstrained_ctc_transcript':heard,'review_status':'triage_not_human_listening'})
 result={'status':'pause_and_word_interval_pass_pronunciation_review_pending','method':'ffmpeg silence measurement and unconstrained acoustic decoder; not scripted transcript substitution','pause_checks':checks,'unconstrained_transcripts':transcriptions}
 atomic_json(A/'audio-waveform-qa-v1.json',result)
 print(json.dumps({'heading_pause_checks':len(checks),'minimum_pause':min(x['measured_quiet_heading_gap_seconds'] for x in checks),'maximum_pause':max(x['measured_quiet_heading_gap_seconds'] for x in checks),'transcriptions':len(transcriptions)}))
if __name__=='__main__':main()
