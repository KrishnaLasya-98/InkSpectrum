import json
import sys
from pathlib import Path

results = {}

# Step 1: Tool Registry Discovery
print('=== STEP 1: Tool Registry Discovery ===', flush=True)
try:
    from tools.tool_registry import registry
    registry.discover()
    envelope = registry.support_envelope()
    skills_prefix = ['hybrid_pdf', 'educational_gen', 'scene_plan', 'voice_synth', 'manim_gen', 'av_compos', 'quality_ass']
    edustream_tools = {k: v for k, v in envelope.items() if any(s in k.lower() for s in skills_prefix)}
    print(json.dumps(edustream_tools, indent=2))
    results['step1'] = 'PASSED'
except Exception as e:
    print(f'FAILED: {e}')
    results['step1'] = f'FAILED: {e}'

# Step 2: Pipeline Validation
print('\n=== STEP 2: Pipeline Validation ===', flush=True)
try:
    from lib.pipeline_loader import load_pipeline, get_stage_order
    manifest = load_pipeline('educational-video')
    stages = get_stage_order(manifest)
    print('Stage order:', stages)
    print('Total stages:', len(stages))
    results['step2'] = 'PASSED'
except Exception as e:
    print(f'FAILED: {e}')
    results['step2'] = f'FAILED: {e}'

# Step 3: Checkpoint Integration Test
print('\n=== STEP 3: Checkpoint Integration Test ===', flush=True)
try:
    from lib.checkpoint import init_project, write_checkpoint, read_checkpoint, get_next_stage
    project_dir = init_project('test-run-1', title='Test Educational Video', pipeline_type='educational-video')
    cp_path = write_checkpoint(
        pipeline_dir=Path('projects'),
        project_id='test-run-1',
        stage='input_ingestion',
        status='completed',
        artifacts={
            'extracted_content': {
                'version': '1.0',
                'title': 'Test Chapter',
                'extraction_tool_used': 'opendataloader_local',
                'confidence_score': 0.92,
                'sections': []
            }
        },
        pipeline_type='educational-video'
    )
    print(f'Checkpoint written: {cp_path}')
    cp = read_checkpoint(Path('projects'), 'test-run-1', 'input_ingestion')
    stage_val = cp['stage']
    status_val = cp['status']
    print(f'Checkpoint read back: stage={stage_val}, status={status_val}')
    next_stage = get_next_stage(Path('projects'), 'test-run-1', 'educational-video')
    print(f'Next stage: {next_stage}')
    results['step3'] = 'PASSED'
except Exception as e:
    print(f'FAILED: {e}')
    results['step3'] = f'FAILED: {e}'

# Step 4: Artifact Schema Validation
print('\n=== STEP 4: Artifact Schema Validation ===', flush=True)
try:
    from schemas.artifacts import validate_artifact
    
    test_plan = {
        'version': '1.0',
        'title': 'Introduction to Fractions',
        'subject_classification': 'mathematics',
        'domain': 'mathematics',
        'complexity_level': 'middle_school',
        'target_audience': 'Grade 6-7',
        'total_duration_seconds': 480,
        'learning_objectives': ['Understand fraction representation', 'Compare fractions'],
        'sections': [
            {
                'section_id': 'sec_1',
                'title': 'What Are Fractions?',
                'description': 'Introduction to fractions as parts of a whole',
                'narration_script': 'Welcome to fractions! Today we will learn...',
                'duration_seconds': 90,
                'equations': [],
                'key_concepts': ['numerator', 'denominator'],
                'visual_elements': {
                    'diagrams': ['pie chart'],
                    'animations': ['fade in', 'highlight'],
                    'color_scheme': ['blue', 'orange']
                },
                'transition_to_next': 'Now let us compare fractions...'
            }
        ],
        'assessment': {
            'quiz_questions': [],
            'thought_experiments': []
        },
        'metadata': {}
    }
    
    test_extracted = {
        'version': '1.1',
        'title': 'Test Chapter',
        'source_pdf': '/fake/path.pdf',
        'extraction_tool_used': 'opendataloader_local',
        'confidence_score': 0.92,
        'total_pages': 10,
        'pages_extracted': 10,
        'sections': [
            {
                'section_id': 's1',
                'title': 'Introduction',
                'content': 'Sample extracted body text for the chapter.',
                'content_preview': 'Sample extracted body text for the chapter.',
                'content_type': 'theory',
            }
        ],
        'metadata': {}
    }
    
    test_narration = {
        'version': '1.0',
        'engine_used': 'omnivoce',
        'voice_name': 'en_US-lessac-medium',
        'voice_characteristics': {
            'child_friendly': True,
            'gender': 'female',
            'accent': 'american',
            'pace': 'measured',
            'energy': 'moderate'
        },
        'segments': [
            {
                'section_id': 'sec_1',
                'text': 'Welcome to fractions!',
                'audio_path': 'projects/test-run-1/assets/audio/sec_1.mp3',
                'duration_seconds': 12.5,
                'cost_usd': 0.001
            }
        ],
        'total_duration_seconds': 12.5,
        'total_cost_usd': 0.001,
        'metadata': {}
    }
    
    try:
        validate_artifact('educational_plan', test_plan)
        print('educational_plan schema validation: PASSED')
    except Exception as e:
        print(f'educational_plan schema validation: FAILED - {e}')
        results['step4_plan'] = f'FAILED: {e}'
    
    try:
        validate_artifact('extracted_content', test_extracted)
        print('extracted_content schema validation: PASSED')
    except Exception as e:
        print(f'extracted_content schema validation: FAILED - {e}')
        results['step4_extracted'] = f'FAILED: {e}'
    
    try:
        validate_artifact('narration_manifest', test_narration)
        print('narration_manifest schema validation: PASSED')
    except Exception as e:
        print(f'narration_manifest schema validation: FAILED - {e}')
        results['step4_narration'] = f'FAILED: {e}'
    
    if all(k not in results for k in ['step4_plan', 'step4_extracted', 'step4_narration']):
        results['step4'] = 'PASSED'
except Exception as e:
    print(f'FAILED: {e}')
    results['step4'] = f'FAILED: {e}'

print('\n=== SUMMARY ===', flush=True)
for k, v in results.items():
    print(f'{k}: {v}')
