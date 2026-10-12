"""Long opening shot, preserving the title card for its entire spoken hold."""
import json
from pathlib import Path
from lib.production_runtime import atomic_json
P=Path(__file__).resolve().parent
data={'version':'1.0','provider':'modelslab','model_id':'wan2.2','operation':'text_to_video','shots':[{'shot_id':'long-weather-title','section_id':'s01-title','num_frames':120,'prompt':'A polished child-friendly 3D animated film opening landscape, wide green meadow with moving foliage, gently drifting large fluffy white clouds, a bright warm sun and distant snow capped mountains, rich softly rounded three-dimensional shapes, natural scale, clear space on the left for a later title card, continuous gentle object motion and a slow coherent camera glide. No people, words, titles, logos, captions, watermark, frozen image or live action.'}]}
path=P/'assets/video/motion-batch-04.json'
if path.exists():
 if json.loads(path.read_text())!=data:raise ValueError('Durable opening contract differs')
else:atomic_json(path,data)
print(path)
