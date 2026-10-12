"""Six additional, unique paragraph-specific Wan shots; submission is separate."""
from pathlib import Path
from lib.production_runtime import atomic_json
P=Path(__file__).resolve().parent
SHOTS=[
 ('humid-coast','s12-humidity','A lush green tropical coast, visibly moving warm sea waves and soft mist drifting between palm trees, droplets on broad leaves, leafy branches sway gently. Wide composed landscape, upper right free for teaching card.'),
 ('rainforest-canopy','s14-rainforest-fact','A rich tropical rainforest canopy with many broad green leaves, rain drops fall and drip from foliage while mist moves slowly through tall trees, sunlight softly filters through moving leaves. No people or text.'),
 ('monsoon-rain','s16-monsoon','An Indian tropical landscape during seasonal heavy rainfall, lush trees sway moderately, strong rain falls visibly into a stream with rippling water, a small safe rural house in the distance. No flooding or people.'),
 ('equatorial-rain','s17-equatorial','A dense equatorial forest with a winding stream, continuous falling rain and droplets on broad leaves, low mist drifts between trunks, warm overcast light. Camera glides slowly beside the stream.'),
 ('tundra-wind','s19-tundra','An open extremely cold tundra landscape with sparse low vegetation and distant snow covered ridges, wind visibly moves small frost covered grass patches and fine snow dust near ground, pale readable sky. No forests or large animals.'),
 ('antarctic-wind','s20-antarctica-fact','An uninhabited Antarctic ice plain with rugged distant ice cliffs, fine drifting snow blows across the surface and soft clouds move through a pale blue sky, continuously moving safe natural wind scene, no rain or animals.'),
]
data={'version':'1.0','provider':'modelslab','model_id':'wan2.2','operation':'text_to_video','shots':[{'shot_id':shot,'section_id':sid,'prompt':prompt+' Polished child-friendly 3D animated film, coherent continuous object motion throughout, no captions, no labels, no logos, no watermark, not a still image.'} for shot,sid,prompt in SHOTS]}
path=P/'assets/video/motion-batch-02.json'
if path.exists():
 import json
 if json.loads(path.read_text())!=data:raise ValueError('Durable batch changed')
else:atomic_json(path,data)
print(path)
