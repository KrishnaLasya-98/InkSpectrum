"""Additional unique 120-frame Wan shots, never repeated short footage."""
import json
from pathlib import Path
from lib.production_runtime import atomic_json
P=Path(__file__).resolve().parent
SHOTS=[
 ('weather-sunny-garden','s04-weather','A sunny garden in the morning with visible moving leaves, a warm sun and soft clouds drifting overhead, wide readable composition, no rain.'),
 ('dry-desert-air','s12-humidity','An uninhabited dry desert of sand and rocky ridges, fine dust blows gently across the ground under a bright blue sky, sparse plants, no water, no fog or visible steam.'),
 ('sea-current-waves','s13-currents','Blue open ocean water viewed at a low oblique angle with broad water movement and rolling waves, no generated arrows or land map, sunlight reflections move naturally.'),
 ('rainforest-food','s14-rainforest-fact','A tropical rainforest with ripe fruits hanging naturally among leaves, rainwater drips gently from the canopy and green leaves sway, no people or letters, wide close landscape.'),
 ('desert-hot-day','s18-desert','Wide desert dunes in bright hot daylight, sparse desert shrubs and gentle wind moving fine grains over dune crests, clear sky and golden sunlight, no rain.'),
 ('desert-cool-night','s18-desert','The same kind of wide desert dune terrain under a visible crescent moon and a deep blue readable night sky, a gentle wind moves grains and a few small clouds drift, no fog, rain or snow.'),
 ('temperate-seasons','s23-temperate','A temperate woodland in mild autumn weather with orange and green broad leaves visibly swaying, a shallow stream flowing continuously and several leaves drifting to the ground, calm readable composition.'),
 ('cumulus-fair','s24-cloud-fact','A bright blue sky above a green meadow with large fluffy white cumulus clouds visibly drifting, sunlight and gently swaying grass, pleasant fair weather, no rain or snow.'),
 ('nimbostratus-rain','s24-cloud-fact','A green meadow under a broad low uniform gray layer of nimbostratus clouds, continuous moderate rain falls into small rippling puddles while foliage moves gently, no thunder or lightning.'),
 ('frigid-ice','s25-frigid','A cold polar sea with ice covered land on the left and floating ice on softly moving blue water, small soft clouds drift through a clear readable sky, no animals, labels or invented geographic shapes.'),
]
data={'version':'1.0','provider':'modelslab','model_id':'wan2.2','operation':'text_to_video','shots':[{'shot_id':shot,'section_id':sid,'num_frames':120,'prompt':prompt+' Polished child-friendly 3D animated film, genuine continuous object motion, steady gentle cinematic camera, no captions, text, logos, watermarks or frozen frames.'} for shot,sid,prompt in SHOTS]}
path=P/'assets/video/motion-batch-03.json'
if path.exists():
 if json.loads(path.read_text())!=data:raise ValueError('Existing shot contract changed')
else:atomic_json(path,data)
print(path)
