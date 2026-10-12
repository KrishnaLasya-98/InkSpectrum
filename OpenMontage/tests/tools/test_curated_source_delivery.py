from tools.structure.compile_curated_educational_plan import compile_plan
from tools.voice.narrate_reviewed_plan import narration_segments


def test_matching_reads_columns_without_false_pairs():
    block = {'block_id': 'p0001-b0001', 'page_number': 1, 'block_type': 'table',
             'required_for_coverage': True, 'source_text': 'Original matching table',
             'table': {'cells': [
                 {'row': 0, 'column': 0, 'text': 'Column A'},
                 {'row': 0, 'column': 1, 'text': 'Column B'},
                 {'row': 1, 'column': 0, 'text': 'Asia'},
                 {'row': 1, 'column': 1, 'text': 'Largest ocean'},
                 {'row': 2, 'column': 0, 'text': 'Pacific'},
                 {'row': 2, 'column': 1, 'text': 'Largest continent'}]}}
    spec = {'sections': [{'section_id': 'matching', 'source_delivery': True,
                          'table_reading': 'columns', 'description': 'Match columns',
                          'animation_action': 'Connect answers', 'source_selectors': [{'page': 1}]}]}
    section = compile_plan({'blocks': [block]}, spec)['sections'][0]
    assert section['narration_script'] == 'Column A. Asia. Pacific. Column B. Largest ocean. Largest continent.'
    assert section['teaching_contract']['source_excerpts'][0]['display_text'] == block['source_text']


def test_source_headings_are_not_repeated_or_invented():
    doc = {'blocks': [{'block_id': 'h', 'block_type': 'section_heading', 'source_text': 'Recall'},
                      {'block_id': 'q', 'block_type': 'assessment', 'source_text': 'Which ocean?'}]}
    plan = {'sections': [
        {'section_id': 's1', 'title': 'Ignore invented label', 'source_block_ids': ['h'], 'narration_script': 'Recall.'},
        {'section_id': 's2', 'title': 'Question 1', 'source_block_ids': ['q'], 'narration_script': 'Which ocean? Answer. Pacific.'}]}
    items = narration_segments(plan, doc, {'spoken_heading_pause_seconds': 4})
    assert items[0]['text'] == 'Recall'
    assert items[0]['heading_only_titles'] == ['Recall']
    assert items[0]['topic_end_pause_seconds'] == 4
    assert not items[1]['spoken_headings']
