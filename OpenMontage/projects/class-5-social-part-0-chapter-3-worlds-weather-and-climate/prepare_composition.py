"""Prepare source-faithful cards and cue-driven motion; refuse incomplete media.

--audit-only never invokes a paid provider or render. Full mode composes HTML
only after the sequential local clip worker has completed all 24 sections.
"""
from __future__ import annotations
import argparse,json,re,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from lib.production_runtime import atomic_json
from tools.video.educational_hyperframes_composer import EducationalHyperFramesComposer,_panel_content,_section_type
from tools.structure.teaching_contract import validate_teaching_contract
from schemas.artifacts import validate_artifact
P=Path(__file__).resolve().parent;R=P.parents[1];A=P/'artifacts'
SCI=P/'assets/video/precision-v2/videos/precision_climate/720p24'
CLASSES=['OpeningWeather','StartupWeather','WeatherChanges','HotDesert','ClimateContrast','FactorsPreview','LatitudeClimate','AltitudeClimate','BreezeClimate','WindClimate','HumidityClimate','CurrentsClimate','RainforestClimate','ClimateTypesPreview','MonsoonClimate','EquatorialClimate','DesertClimate','TundraClimate','AntarcticaClimate','ZonesOverview','TorridClimate','TemperateClimate','CloudClimate','FrigidClimate']
SIDS=['s01-title','s03-startup','s04-weather','s05-hot-desert-fact','s06-climate','s07-factors','s08-latitude','s09-altitude','s10-sea-land-breeze','s11-wind','s12-humidity','s13-currents','s14-rainforest-fact','s15-climate-types','s16-monsoon','s17-equatorial','s18-desert','s19-tundra','s20-antarctica-fact','s21-zones','s22-torrid','s23-temperate','s24-cloud-fact','s25-frigid']
MOTION={
 's01-title':[('motion-batch-01','weather-opening',None)],
 's03-startup':[('motion-batch-01','window-sun','Look outside'),('motion-batch-01','window-cloud','Have you ever noticed'),('motion-batch-01','window-rain','the weather changes'),('motion-batch-06','startup-cold-place','while others are cold')],
 's04-weather':[('motion-batch-01','weather-wind','It includes'),('motion-batch-06','weather-cloud-cover','and cloud cover'),('motion-batch-06','weather-change-rain-to-sun','Weather can change'),('motion-batch-03','weather-sunny-garden','For example'),('motion-batch-01','weather-rain','by afternoon')],
 's05-hot-desert-fact':[('motion-batch-01','lut-rocky-heat','The hottest'),('motion-batch-05','lut-heat-shimmer','where temperatures'),('motion-batch-05','lut-scorched-ridges','Imagine how hot')],
 's06-climate':[('motion-batch-06','climate-long-term-seasons','Climate is the average'),('motion-batch-06','climate-wet-dry-contrast','It tells us'),('motion-batch-01','sahara-dunes','the climate of the Sahara'),('motion-batch-01','amazon-rain','the climate of the Amazon')],
 's07-factors':[('motion-batch-05','climate-factors-landscape','Several factors')],
 's08-latitude':[('motion-batch-05','equator-strong-sunlight','Places near the equator'),('motion-batch-05','polar-low-sunlight','As we move towards the poles')],
 's09-altitude':[('motion-batch-06','altitude-foothill-to-peak','Higher altitudes'),('motion-batch-01','mountain-ascending','For example')],
 's10-sea-land-breeze':[('motion-batch-01','coast-day','Oceans and seas'),('motion-batch-06','coast-day-thermal-lag','During the day'),('motion-batch-01','coast-night','At night'),('motion-batch-06','coast-night-thermal-lag','the land cools down quickly')],
 's12-humidity':[('motion-batch-06','humidity-lush-coast','Places with high humidity'),('motion-batch-03','dry-desert-air','while dry areas'),('motion-batch-02','humid-coast','For example')],
 's13-currents':[('motion-batch-03','sea-current-waves','Ocean currents are'),('motion-batch-06','warm-current-coast','Warm ocean currents'),('motion-batch-06','cold-current-coast','while cold currents')],
 's14-rainforest-fact':[('motion-batch-02','rainforest-canopy','Rainforests receive'),('motion-batch-03','rainforest-food','because they provide')],
 's16-monsoon':[('motion-batch-02','monsoon-rain','It has hot summers'),('motion-batch-06','monsoon-rice-fields','receives heavy rainfall')],
 's17-equatorial':[('motion-batch-06','equatorial-rainforest-river','Found near the equator'),('motion-batch-02','equatorial-rain','It is hot')],
 's18-desert':[('motion-batch-03','desert-hot-day','Found in places'),('motion-batch-03','desert-cool-night','cold nights')],
 's19-tundra':[('motion-batch-02','tundra-wind','It is extremely')],
 's20-antarctica-fact':[('motion-batch-02','antarctic-wind','Antarctica is')],
 's21-zones':[('motion-batch-05','earth-equator-to-poles','The Earth is divided')],
 's23-temperate':[('motion-batch-06','temperate-four-seasons-tree','Found between the tropics'),('motion-batch-03','temperate-seasons','It has moderate')],
 's24-cloud-fact':[('motion-batch-03','cumulus-fair','cumulus clouds'),('motion-batch-03','nimbostratus-rain','while nimbostratus')],
 's25-frigid':[('motion-batch-03','frigid-ice','It is the coldest')],
}
FIGURES={'s08-latitude':'world-map.png','s09-altitude':'altitude-photo.png','s10-sea-land-breeze':'sea-land-breeze.png','s11-wind':'rain-shadow.png','s12-humidity':'humidity-photo.png','s13-currents':'ocean-wave.png','s17-equatorial':'rainforest-photo.png','s18-desert':'desert-photo.png','s19-tundra':'tundra-photo.png','s25-frigid':'climatic-zones.png'}
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def norm(t):return re.sub(r'[^a-z0-9]','',t.casefold())
def cue(words,phrase,previous=-1):
 wanted=[norm(x) for x in phrase.split() if norm(x)];observed=[(i,norm(w['word'])) for i,w in enumerate(words) if norm(w['word'])]
 for i in range(len(observed)-len(wanted)+1):
  if observed[i][0]>previous and [v for _,v in observed[i:i+len(wanted)]]==wanted:return observed[i][0],words[observed[i][0]]['start_ms']/1000
 raise ValueError(f'Unmatched exact speech cue: {phrase}')
def pages(text,limit=185):
 chunks=[]
 for sentence in re.split(r'(?<=[.!?])\s+(?=[A-Z])',' '.join(text.split())):
  piece=''
  for w in sentence.split():
   if piece and len(piece)+len(w)+1>limit:chunks.append(piece);piece=''
   piece=(piece+' '+w).strip()
  if piece:
   if chunks and len(chunks[-1])+len(piece)+1<=limit:chunks[-1]+=' '+piece
   else:chunks.append(piece)
 if ' '.join(chunks)!=' '.join(text.split()):raise ValueError('Paging changed source words')
 return chunks
def probe(path):return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(path)],text=True,timeout=30))
def seek_safe(path):
 import hashlib
 target=P/'assets/video/seek-safe-v1'/f'{path.stem}-{hashlib.sha256(path.read_bytes()).hexdigest()[:12]}.mp4'
 target.parent.mkdir(parents=True,exist_ok=True)
 if not target.exists():subprocess.run(['ffmpeg','-v','error','-i',str(path),'-an','-vf','fps=30','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-g','30','-keyint_min','30','-sc_threshold','0','-movflags','+faststart',str(target)],check=True,timeout=240)
 return target
def main(audit_only=False):
 plan=read(A/'educational_plan.json');doc=read(A/'chapter_document.json');audio=read(P/'assets/audio/narration-elevenlabs-timed-v1/narration_manifest.json');aligned={s['section_id']:s for s in read(A/'alignment-timed-v1/narration_aligned.json')['segments']};narr={s['section_id']:s for s in audio['segments']}
 for s in plan['sections']:
  if s['section_id']=='s01-title':s['source_block_type']='intro'
  if s['section_id'] in {'s26-recall','s27-remember'}:s['source_block_type']='recall'
  if s['section_id']=='s28-wordbank':
   s['section_type']='table';s['section_label']='Word Bank';s['source_table']=next(b['table'] for b in doc['blocks'] if b['block_id'] in s['source_block_ids'] and b.get('table'))
 validate_artifact('educational_plan',plan)
 review=validate_teaching_contract(plan,doc['blocks'],subject='social-studies')
 if review['status']!='pass':raise ValueError(review)
 atomic_json(A/'educational_plan.json',plan)
 sync={'version':'1.0','status':'pass','review_state':'encoded_qa_pending','issues':[],'total_duration_seconds':round(audio['total_duration_seconds'],3),'timeline':[{'section_id':s['section_id'],'start_seconds':round(s['start_seconds'],3),'end_seconds':round(s['start_seconds']+s['duration_seconds'],3),'visual_duration_policy':'as_is'} for s in audio['segments']]}
 card_pages={};coverage=[]
 for s in plan['sections']:
  sid=s['section_id'];n=narr[sid];_,body,items=_panel_content(s,plan);text=' '.join([body,*items]).strip()
  if sid not in {'s01-title','s02-objectives','s27-remember','s28-wordbank'} and len(text)>220:
   copy=pages(text);starts=[0.];previous=len(n['spoken_heading'].split())-1
   for page in copy[1:]:
    previous,t=cue(aligned[sid]['words'],' '.join(page.split()[:3]),previous);starts.append(round(t-n['start_seconds'],3))
   starts.append(round(n['duration_seconds'],3))
   if any(b<=a for a,b in zip(starts,starts[1:])):raise ValueError('Non-monotonic card timing')
   card_pages[sid]=[{'text':p,'start_offset_seconds':starts[i],'end_offset_seconds':starts[i+1]} for i,p in enumerate(copy)]
  spoken=' '.join(w['word'] for w in aligned[sid]['words'])
  if spoken!=' '.join(n['text'].split()):raise ValueError(f'Caption text differs: {sid}')
  coverage.append({'section_id':sid,'source_block_ids':s['source_block_ids'],'required_motion':sid in SIDS,'precision_class':dict(zip(SIDS,CLASSES)).get(sid),'text_and_caption_exact':True})
 atomic_json(A/'teaching-pages-v1.json',card_pages);atomic_json(A/'multimedia-sync-v1.json',sync);atomic_json(A/'source-and-timing-preflight-v1.json',{'status':'source_and_timing_pass_media_and_encoded_review_pending','sections':coverage,'required_source_blocks':80,'figures_expected':len(FIGURES),'duration_seconds':audio['total_duration_seconds'],'textbook_table_cells':len(plan['sections'][-1]['source_table']['cells'])})
 if audit_only:
  collection_path=R/'textbook-collections/class-5-social/artifacts/video_production_plan.json';collection=read(collection_path);entry=next(c for c in collection['chapters'] if c['chapter']==3)
  entry.update(status='media_generation_in_progress',project_id=P.name,project_dir=str(P),reviewed_text=str(R/'textbook-collections/class-5-social/reviewed/chapter-03/chapter-03-reviewed.md'),progress_evidence=str(A/'precision-render-v2/progress.json'),audio_evidence=str(A/'audio-pause-audit-v1.json'))
  atomic_json(collection_path,collection)
  print(json.dumps({'status':'source_and_timing_preflight_pass','sections':len(coverage),'seconds':audio['total_duration_seconds'],'final_video':'not_rendered'}));return
 worker=read(A/'precision-render-v2/progress.json')
 if worker['status']!='precision_complete_media_qa_pending':raise RuntimeError('The sequential local media worker has not completed; do not compose placeholders')
 clips=[]
 for s in plan['sections']:
  sid=s['section_id'];n=narr[sid];total=round(n['duration_seconds'],3);clip={'section_id':sid,'success':True,'render_mode':'hyperframes','visual_segments':[],'source_figure_overlays':[],'source_card_intervals':[[0,total]]}
  if sid in SIDS and sid!='s01-title':
   path=SCI/f'{dict(zip(SIDS,CLASSES))[sid]}.mp4'
   if probe(path)<total:raise ValueError(f'Short precise media: {sid}')
   clip['visual_segments'].append({'path':str(path),'offset_seconds':0,'duration_seconds':total,'transition':'cut','cue':'full section explanatory motion'})
  shots=[] if sid=='s01-title' else MOTION.get(sid,[])
  if sid=='s01-title':
   first=P/'assets/video/motion-batch-01/weather-opening.mp4';second=P/'assets/video/motion-batch-04/long-weather-title.mp4'
   # The live provider returned 81 frames even for a 120-frame request.
   # Use measured durations and two UNIQUE related shots. The title card
   # itself stays unchanged for the entire heading and its measured pause.
   first_end=min(probe(first)-.04,total);handoff=max(0,first_end-.55)
   if probe(second)<total-handoff:raise ValueError('Opening lacks actual motion coverage')
   clip['visual_segments']=[{'path':str(first),'offset_seconds':0,'duration_seconds':round(first_end,3),'transition':'cut','cue':'opening landscape'},
      {'path':str(second),'offset_seconds':round(handoff,3),'duration_seconds':round(total-handoff,3),'transition':'crossfade','cue':'related unique meadow shot; constant title UI; no repeated video'}]
  for batch,shot,phrase in shots:
   path=P/'assets/video'/batch/f'{shot}.mp4';start=0 if phrase is None else max(0,cue(aligned[sid]['words'],phrase)[1]-n['start_seconds']-.05)
   duration=min(probe(path)-.04,total-start)
   later=[max(0,cue(aligned[sid]['words'],ph)[1]-n['start_seconds']-.05) for b,sh,ph in shots if ph is not None and sh!=shot]
   next_cue=min((t for t in later if t>start+.02),default=total)
   duration=min(duration,next_cue-start)
   if duration<=0:raise ValueError('Motion cue lies beyond section')
   clip['visual_segments'].append({'path':str(path),'offset_seconds':round(start,3),'duration_seconds':round(duration,3),'transition':'crossfade','cue':phrase or 'opening context'})
  if sid in FIGURES:
   start=n['body_start_seconds'];duration=min(5,total-start)
   clip['source_figure_overlays'].append({'path':str(A/'images'/FIGURES[sid]),'offset_seconds':round(start,3),'duration_seconds':round(duration,3)})
  if sid in card_pages:clip['teaching_pages']=card_pages[sid]
  for v in clip['visual_segments']:v['path']=str(seek_safe(Path(v['path'])))
  clips.append(clip)
 atomic_json(A/'clip-manifest-v1.json',{'clips':clips,'status':'visual_qa_pending','policy':'full-length fresh precise motion under unique Wan cutaways; no media loops or frozen extension'})
 result=EducationalHyperFramesComposer().execute({'workspace_path':str(P/'hyperframes-final'),'asset_base_dir':str(P),'template_contract':str(R/'styles/hyperframes-educational-v1.yaml'),'educational_plan':plan,'clip_manifest':{'clips':clips},'narration_manifest':audio,'multimedia_sync_plan':sync,'word_captions':str(A/'alignment-timed-v1/word_captions.json'),'presentation_variant':'class5-social-chapter1-v4'})
 if not result.success:raise RuntimeError(result.error)
 atomic_json(A/'composition-build-v1.json',result.data);print(json.dumps(result.data,indent=2))
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--audit-only',action='store_true');args=parser.parse_args();main(args.audit_only)
