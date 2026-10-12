"""Compile Chapter 3 from the audited source; create manifests, never dummy assets."""
import json
from pathlib import Path
from tools.structure.compile_curated_educational_plan import compile_plan
from tools.structure.prepare_curated_educational_chapter import prepare
from schemas.artifacts import validate_artifact
from tools.structure.teaching_contract import validate_teaching_contract

P = Path(__file__).resolve().parent
R = P.parents[1]
NAMES = ['title','objectives','startup','weather','hot-desert-fact','climate','factors','latitude','altitude','sea-land-breeze','wind','humidity','currents','rainforest-fact','climate-types','monsoon','equatorial','desert','tundra','antarctica-fact','zones','torrid','temperate','cloud-fact','frigid','recall','remember','wordbank']
VISUALS = [
    'A child-friendly 3D sunny meadow with clouds and distant snowy mountains, moving foliage and a gently gliding camera; reserve the left area for the exact chapter title.',
    'Readable exact learning-objective list with aligned subtitles; retain a stable cream reading card.',
    'An Indian schoolchild looks out a classroom window onto sunny, cloudy and rainy weather cues; time weather changes to the spoken words.',
    'A 3D landscape demonstrates cloud movement, blowing foliage, rain and changing sunlight; exact temperature and humidity graphics are authored separately.',
    'A hot rocky desert with heat shimmer; no fake measurement labels or air-temperature display.',
    'Distinct hot dry dunes and warm rainy rainforest shots, timed to Sahara and Amazon descriptions; authored 30-year comparison graphic.',
    'A precise animated overview shows sunlight, mountains, coast, moving air and ocean water; exact source text remains on the cream card.',
    'A new blue 3D globe with authored latitude rings and sunlight paths toward the equator and poles; original textbook world map shown unchanged.',
    'An authored 3D terrain view moves from sea level to a snowy mountain; label altitude with precise editable text; original mountain photograph remains visible when referenced.',
    'Precise coastal 3D model with day sea-to-land airflow and night land-to-sea airflow; preserve the original two-panel breeze diagram.',
    'A 3D mountain and moving cloud/rain illustrate windward moisture and leeward rain shadow, with exact original diagram labels retained.',
    'A humid coastal garden and a dry desert in distinct shots; precise water-vapour cue; show the textbook photograph in a source inset.',
    'Moving ocean water with authored warm and cold current arrows; geographic labels only on reviewed source-derived graphics, never AI-generated maps.',
    'A fresh lush 3D rainforest with falling rain, moving leaves and fruit; cream source fact box.',
    'A concise precise 3D overview of hot wet, dry and cold environments; source transition text remains exact.',
    'Heavy monsoon rain over a child-friendly Indian rural landscape with moving trees and accumulating puddles.',
    'A dense 3D rainforest canopy with falling rain and moving leaves; show the original rainforest photograph as an inset.',
    'Fresh desert dunes in hot daylight and a separate cool moonlit desert shot; original desert photograph preserved.',
    'Cold sparsely vegetated snowy terrain, gentle wind and sparse low plants; original source photo preserved without inventing Antarctic reindeer geography.',
    'Antarctic ice and wind context, no rainfall simulation or unsupported historical claims beyond the printed source card.',
    'A new blue 3D globe with precisely authored tropical, temperate and polar bands.',
    'Authored globe highlights the band between Tropic of Cancer and Tropic of Capricorn with clean editable labels.',
    'Authored globe highlights both temperate bands; a fresh moving woodland shows moderate conditions.',
    'Distinct fluffy fair-weather cumulus and layered rainy nimbostratus cloud scenes matched to narration.',
    'Authored globe highlights polar regions; exact original climatic-zone diagram stays readable.',
    'Exact Recall paragraph on a cream reading panel with punctuated word-highlight subtitles.',
    'Exact five-item Let’s Remember list on a cream reading panel with word-highlight subtitles.',
    'Exact five-row Word Bank table with term and meaning spoken together; finish after the last definition.',
]

def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def main():
    doc=json.loads((P/'artifacts/chapter_document.json').read_text(encoding='utf-8'))
    groups=[]
    for block in doc['blocks']:
        if block['block_type'] in {'chapter_title','section_heading'}: groups.append([])
        groups[-1].append(block)
    if len(groups)!=len(NAMES): raise ValueError('Source section count changed')
    sections=[]
    for i,(name,blocks,visual) in enumerate(zip(NAMES,groups,VISUALS),1):
        ids=[int(b['block_id'].split('-b')[-1]) for b in blocks]
        sections.append({'section_id':f's{i:02d}-{name}','title':blocks[0]['source_text'],
            'source_delivery':True,'source_selectors':[{'page':blocks[0]['page_number'],'start':min(ids),'end':max(ids)}],
            'description':visual,'animation_action':visual,
            **({'narration_prefix':'Social Studies, Class 5.'} if i==1 else {})})
    spec={'version':'1.0','title':'Worlds Weather and Climate','subject_classification':'theory',
        'domain':'social-studies','complexity_level':'elementary','target_audience':'Class 5, ages 9-11',
        'learning_objectives':[b['source_text'] for b in groups[1] if b['block_type']=='bullet'],
        'metadata':{'subject':'social-studies','subject_label':'Social Studies','grade':5,'chapter':3,
            'narration_speed':0.85,'delivery_policy':{'estimated_wpm':140,'heading_pause_seconds':2,'topic_pause_seconds':1.5},
            'production_scope':{'user_approved':True,'start_section_id':'s01-title','end_section_id':'s28-wordbank','exclude_assessments':True,'description':'Opening through Word Bank, original PDF pages 1-7.'},
            'source_audit':str(R/'textbook-collections/class-5-social/reviewed/chapter-03/audits/source-audit.json'),
            'approval':{'status':'approved','evidence':'User requested remaining chapters sequentially and explicitly requested Chapter 3 generation on 2026-10-06.'}},
        'section_defaults':{'render_mode':'video_gen','transition_to_next':'crossfade'},'sections':sections}
    plan=compile_plan(doc,spec)
    for section in plan['sections']:
        sid=section['section_id']
        if sid=='s01-title':section['source_block_type']='intro'
        if sid in {'s26-recall','s27-remember'}:section['source_block_type']='recall'
        if sid=='s28-wordbank':
            section['section_type']='table';section['section_label']='Word Bank'
            section['source_table']=next(b['table'] for b in doc['blocks'] if b['block_id'] in section['source_block_ids'] and b.get('table'))
    validate_artifact('educational_plan',plan)
    review=validate_teaching_contract(plan,doc['blocks'],subject='social-studies')
    if review['status']!='pass': raise ValueError(review)
    save(P/'artifacts/educational_plan_spec.json',spec)
    save(P/'artifacts/educational_plan.json',plan)
    audio={'provider':'elevenlabs','model_id':'eleven_v4','voice_id':'zJrRUu1KEcKH8qdpNaPJ','language':'en','speed':0.85,'lock_voice':True,'enable_stt_qa':True}
    result=prepare(P,audio_provider='elevenlabs',audio_config=audio)
    config=json.loads((P/'chapter_config.json').read_text(encoding='utf-8'))
    config['presentation_variant']='class5-social-chapter1-v4'
    config['content_policy']['delivery_timing']={'narration_speed':0.85,'spoken_heading_pause_seconds':2.0,'topic_end_pause_seconds':1.5}
    save(P/'chapter_config.json',config)
    (P/'storyboard.md').write_text('# Chapter 3 storyboard\n\nScope: opening through Word Bank. Fresh chapter media only. Two-second heading pauses in the normal scene layout.\n\n'+'\n\n'.join(f"## {s['section_id']}: {s['title']}\n\n{s['narration_script']}\n\nVisual: {s['description']}" for s in plan['sections'])+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
