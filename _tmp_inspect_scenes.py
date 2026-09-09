import json

scenes = json.load(open('packages/textbook-pipeline/projects/english_pipeline_output/phase2_script_scenes.json'))
print(f"Total scenes: {len(scenes)}")
for s in scenes:
    is_fallback = '_fallback' in s['id']
    nv = len(s.get('voiceover_lines', []))
    ns = len(s.get('scene_steps', []))
    print(f"{s['id']:30s} | fallback={is_fallback} | voiceover={nv} | steps={ns} | title={s['title'][:40]}")
