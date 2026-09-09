import json
ch = json.load(open('packages/textbook-pipeline/projects/english_pipeline_output/chapter.json'))
for s in ch['sections']:
    ct = (s.get('content_text') or '').strip()
    # Clean image refs for readability
    ct = ct.replace('![](<RPS', '[image: RPS').replace('_images/imageFile', 'img').replace('>)', ']')
    print(f'{s["id"]}|{s["type"]}|{s["title"]}|{ct[:500]}')
    print('---END---')