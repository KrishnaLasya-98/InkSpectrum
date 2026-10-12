"""Sample the actual downloaded footage and probe frame counts for visual QA."""
import json
import subprocess
from pathlib import Path
from PIL import Image,ImageDraw
from lib.production_runtime import atomic_json
P=Path(__file__).resolve().parent
OUT=P/'artifacts/motion-review-v1'
def main():
 OUT.mkdir(parents=True,exist_ok=True);records=[]
 for batch in sorted((P/'assets/video').glob('motion-batch-0[1-5].json')):
  spec=json.loads(batch.read_text())
  for shot in spec['shots']:
   source=P/'assets/video'/batch.stem/f"{shot['shot_id']}.mp4"
   if not source.exists():raise FileNotFoundError(source)
   probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(source)],text=True,timeout=30))
   frames=[];duration=float(probe['format']['duration'])
   for index,t in enumerate([.25,duration/2,duration-.25]):
    frame=OUT/f"{shot['shot_id']}-{index}.png"
    if not frame.exists():subprocess.run(['ffmpeg','-v','error','-ss',str(t),'-i',str(source),'-vf','scale=320:180','-frames:v','1',str(frame)],check=True,timeout=30)
    frames.append(frame)
   records.append({'shot_id':shot['shot_id'],'section_id':shot['section_id'],'path':str(source),'duration':duration,'streams':[{k:s.get(k) for k in ['codec_type','width','height','avg_frame_rate','nb_frames']} for s in probe['streams']],'frames':[str(p) for p in frames],'semantic_review':'pending'})
 for offset in range(0,len(records),6):
  group=records[offset:offset+6];canvas=Image.new('RGB',(960,len(group)*210),'#FFF9ED');draw=ImageDraw.Draw(canvas)
  for row,record in enumerate(group):
   draw.text((8,row*210+5),record['shot_id'],fill='#123247')
   for i,path in enumerate(record['frames']):
    with Image.open(path) as im:canvas.paste(im,(i*320,row*210+25))
  canvas.save(OUT/f'contact-{offset//6+1}.jpg',quality=90)
 atomic_json(OUT/'probe-and-frame-review.json',{'status':'visual_review_pending','shots':records})
 print(json.dumps({'sampled_shots':len(records),'contacts':(len(records)+5)//6}))
if __name__=='__main__':main()
