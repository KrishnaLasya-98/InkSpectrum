"""Resume fresh explanatory clips sequentially; stop on a failed local render."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from lib.production_runtime import atomic_json
from tools.structure.educational_run_tracker import EducationalRunTracker
P=Path(__file__).resolve().parent
R=P.parents[1]
PYTHON=Path('C:/Users/user/Miniconda3/envs/openmontage-maths-manim/python.exe')
CLASSES=['OpeningWeather','StartupWeather','WeatherChanges','HotDesert','ClimateContrast','FactorsPreview','LatitudeClimate','AltitudeClimate','BreezeClimate','WindClimate','HumidityClimate','CurrentsClimate','RainforestClimate','ClimateTypesPreview','MonsoonClimate','EquatorialClimate','DesertClimate','TundraClimate','AntarcticaClimate','ZonesOverview','TorridClimate','TemperateClimate','CloudClimate','FrigidClimate']
ROOT=P/'assets/video/precision-v2';OUT=ROOT/'videos/precision_climate/720p24';LOGS=P/'artifacts/precision-render-v2'
def main():
 LOGS.mkdir(parents=True,exist_ok=True)
 source_hash=hashlib.sha256((P/'precision_climate.py').read_bytes()).hexdigest()
 state_path=LOGS/'progress.json'
 state=json.loads(state_path.read_text()) if state_path.exists() else {'source_sha256':source_hash,'completed':[]}
 if state['source_sha256']!=source_hash:raise RuntimeError('Rendered scientific source changed; choose a new version')
 tracker=EducationalRunTracker(P,title='Worlds Weather and Climate',approval_policy='full-run-preauthorized');tracker.begin('render_clips')
 for name in CLASSES:
  target=OUT/f'{name}.mp4'
  if name not in state['completed']:
   if target.exists():raise RuntimeError(f'Unjournalled rendered output: {name}')
   atomic_json(state_path,{**state,'active':name,'status':'rendering','total':len(CLASSES)})
   with (LOGS/f'{name}.log').open('w',encoding='utf-8') as log:
    result=subprocess.run([str(PYTHON),'-m','manim','-qm','--fps','24','--disable_caching',str(P/'precision_climate.py'),name,'--media_dir',str(ROOT)],cwd=R,stdout=log,stderr=subprocess.STDOUT,timeout=2400)
   if result.returncode or not target.is_file():
    atomic_json(state_path,{**state,'active':name,'status':'failed','exit_code':result.returncode});raise RuntimeError(f'{name} failed; inspect local log')
   seconds=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(target)],text=True,timeout=30))
   state['completed'].append(name);state.setdefault('durations',{})[name]=seconds
   atomic_json(state_path,{**state,'active':None,'status':'rendering','total':len(CLASSES)})
  wan_downloads=sum(1 for path in (P/'assets/video').glob('motion-batch-*/*.mp4') if path.stat().st_size>1000)
  tracker.progress('render_clips',partial_progress={'precision_clips_ready':len(state['completed']),'precision_clips_total':len(CLASSES),'wan_downloads':wan_downloads,'status':'media_generation_not_encoded_final'})
  print(f"Precision clip ready {len(state['completed'])}/{len(CLASSES)}: {name}",flush=True)
 atomic_json(state_path,{**state,'active':None,'status':'precision_complete_media_qa_pending','total':len(CLASSES)})
 print('All precise clips rendered; motion QA and composition still required',flush=True)
if __name__=='__main__':main()
