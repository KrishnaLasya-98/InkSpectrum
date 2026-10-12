"""Run the existing voice stage against a source-validated, authored plan.

No replanning or provider substitution. Keeps revision outputs separate and
persists per-section progress so interrupted local narration can be resumed.
Audio generation is not a pronunciation or final-video QA certificate.
"""
import argparse
import json
from pathlib import Path

from tools.structure.teaching_contract import normalized_text, validate_teaching_contract
from tools.structure.educational_run_tracker import EducationalRunTracker
from tools.voice.voice_synthesis_pipeline import VoiceSynthesisPipeline


def narration_segments(plan, document, timing):
    blocks = {b['block_id']: b for b in document['blocks']}
    result = []
    for section in plan['sections']:
        body = normalized_text(section['narration_script'])
        source_ids = section['source_block_ids']
        title_only = (len(source_ids) == 1
                      and blocks[source_ids[0]]['block_type'] == 'chapter_title')
        if title_only:
            # The spoken grade/subject prefix belongs to the opening, but the
            # complete, source-named title remains alone on screen for the configured hold.
            result.append({
                'section_id': section['section_id'], 'text': body,
                'spoken_headings': [], 'spoken_heading': '',
                'title_card_hold_seconds': 0,
                'topic_end_pause_seconds': float(timing.get('spoken_heading_pause_seconds', 2)),
                'source_block_type': section.get('source_block_type', 'intro'),
                'exercise_questions': [],
                'heading_only_titles': [normalized_text(blocks[source_ids[0]]['source_text'])],
            })
            continue
        headings = []
        for bid in source_ids:
            block = blocks[bid]
            if block['block_type'] not in {'chapter_title', 'section_heading'}:
                break
            heading = normalized_text(block['source_text'])
            if not body.startswith(heading):
                break
            headings.append(heading)
            body = body[len(heading):].lstrip('. ').strip()
        hold = float(timing.get('spoken_heading_pause_seconds', 2))
        item = {
            'section_id': section['section_id'],
            'text': body,
            'spoken_headings': headings,
            'spoken_heading': ' '.join(headings),
            'title_card_hold_seconds': hold if headings else 0,
            'topic_end_pause_seconds': float(timing.get('topic_end_pause_seconds', 1.5)),
            'source_block_type': section.get('source_block_type', 'concept'),
            'exercise_questions': section.get('teaching_contract', {}).get('questions', []),
        }
        if not body:
            # A heading-only card has no synthetic empty body audio.
            item.update(text=' '.join(headings), spoken_headings=[], spoken_heading='',
                        title_card_hold_seconds=0, topic_end_pause_seconds=hold)
            item['heading_only_titles'] = headings
        result.append(item)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--document', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    read = lambda p: json.loads(p.read_text(encoding='utf-8'))
    config, plan, document = read(args.project / 'chapter_config.json'), read(args.plan), read(args.document)
    report = validate_teaching_contract(plan, document['blocks'], subject=config['subject'])
    if report['status'] != 'pass':
        raise SystemExit(json.dumps(report, indent=2))
    if config.get('approval_policy') != 'full-run-preauthorized':
        raise SystemExit('This stage requires recorded full-run authorization.')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    def save(name, payload):
        dest = args.output_dir / name
        temp = dest.with_suffix(dest.suffix + '.tmp')
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
        temp.replace(dest)
    save('text-coverage-check.json', report)
    timing = config['content_policy']['delivery_timing']
    provider = config['providers']['audio']
    items = narration_segments(plan, document, timing)
    save('narration-input.json', {'segments': items, 'plan': str(args.plan.resolve()),
                                'source': str(args.document.resolve())})
    tracker = EducationalRunTracker(args.project, title=plan['title'],
                                    approval_policy=config['approval_policy'])
    tracker.begin('voice_synthesis', metadata={'revision_plan': str(args.plan.resolve())})
    segments = []
    synthesizer = VoiceSynthesisPipeline()
    for item in items:
        print(f"Narrating {len(segments)+1}/{len(items)}: {item['section_id']}", flush=True)
        try:
            output = synthesizer.execute({
                'narration_segments': [item], 'output_dir': str(args.output_dir),
                'provider': provider['provider'], 'voice_profile': {
                    'voice_id': provider['voice_id'], 'model_id': provider['model_id'],
                    'language': provider['language'], 'speed': timing['narration_speed']},
                'enable_stt_qa': provider.get('enable_stt_qa', False),
                'allow_voice_fallback': False,
            })
            if not output.success:
                raise RuntimeError(output.error)
        except Exception as exc:
            tracker.fail('voice_synthesis', str(exc))
            raise
        generated = output.data['narration_manifest']['segments'][0]
        if item.get('heading_only_titles'):
            duration = generated['duration_seconds']
            pause = item['topic_end_pause_seconds']
            generated['heading_holds'] = [{'title': ' '.join(item['heading_only_titles']),
                                          'start_seconds': duration-pause, 'end_seconds': duration}]
            generated['heading_only'] = True
        segments.append(generated)
        manifest = {**output.data['narration_manifest'], 'segments': segments,
                    'total_duration_seconds': round(sum(s['duration_seconds'] for s in segments), 3),
                    'generation_complete': len(segments) == len(items),
                    'pronunciation_qa_status': 'pending', 'word_alignment_status': 'pending'}
        save('narration_manifest.json', manifest)
        tracker.progress('voice_synthesis', partial_progress={
            'completed_sections': len(segments), 'total_sections': len(items),
            'manifest': str((args.output_dir / 'narration_manifest.json').resolve())})
        print(f"Saved {item['section_id']}: {generated['duration_seconds']:.2f}s", flush=True)
    tracker.finish('voice_synthesis', {'narration_manifest': manifest},
                   metadata={'pronunciation_qa_status': 'pending', 'word_alignment_status': 'pending'})
    print(json.dumps({'sections': len(segments), 'duration_seconds': manifest['total_duration_seconds'],
                      'manifest': str(args.output_dir / 'narration_manifest.json')}), flush=True)


if __name__ == '__main__':
    main()
