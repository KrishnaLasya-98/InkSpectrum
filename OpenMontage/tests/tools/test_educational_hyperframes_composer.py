import json
from pathlib import Path

import yaml

from tools.video.educational_hyperframes_composer import (
    EducationalHyperFramesComposer,
    _panel_content,
    educational_template_package_sha256,
)


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "styles" / "hyperframes-educational-v1.yaml"


def test_panel_uses_pdf_text_not_visual_production_direction():
    section = {
        "title": "Rotation",
        "description": "Show one child spinning a ball, then animate the Earth.",
        "source_text": "Rotation\nThe Earth spins on its axis.",
        "source_fragments": [
            {"block_type": "section_heading", "source_text": "Rotation"},
            {"block_type": "paragraph", "source_text": "The Earth spins on its axis."},
        ],
    }
    assert _panel_content(section, {}) == (
        "Rotation", "The Earth spins on its axis.", []
    )


def test_recall_panels_exclude_figure_alt_text_from_teaching_prose():
    for title, alt in (("Recall", "Original textbook Recall icon"),
                       ("Let's Remember", "Original textbook Let's Remember icon")):
        section = {
            "title": title,
            "source_block_type": "recall",
            "source_fragments": [
                {"block_type": "section_heading", "source_text": title},
                {"block_type": "figure", "source_text": alt},
                {"block_type": "paragraph", "source_text": "Reformers promoted education."},
                {"block_type": "bullet", "source_text": "They encouraged unity."},
            ],
        }
        assert _panel_content(section, {}) == (
            title, "Reformers promoted education.", ["They encouraged unity."]
        )


def test_class5_remember_list_does_not_depend_on_chapter2_section_number(tmp_path):
    inputs = _inputs(tmp_path)
    inputs['presentation_variant'] = 'class5-social-chapter1-v4'
    section = inputs['educational_plan']['sections'][2]
    section.update(title="Let's Remember", source_block_type='recall', source_fragments=[
        {'block_type':'section_heading','source_text':"Let's Remember"},
        {'block_type':'bullet','source_text':'Weather changes every day.'},
        {'block_type':'bullet','source_text':'Climate is measured over many years.'},
    ])
    result = EducationalHyperFramesComposer().execute(inputs)
    assert result.success, result.error
    source = Path(result.data['index_html']).read_text(encoding='utf-8')
    assert 'class="v4-reading-list"' in source
    assert 'Weather changes every day.</p>' in source
    assert 'Climate is measured over many years.</p>' in source


def test_class5_visual_scenes_dissolve_at_video_start_or_within_stable_card_pause(tmp_path):
    inputs = _inputs(tmp_path)
    inputs['presentation_variant'] = 'class5-social-chapter1-v4'
    inputs['clip_manifest'][2]['output_path'] = ''  # source-stable recall scene
    result = EducationalHyperFramesComposer().execute(inputs)
    assert result.success, result.error
    source = Path(result.data['index_html']).read_text(encoding='utf-8')
    assert 'tl.to("#scene-s1", { opacity: 0, duration: 0.1, ease: "sine.inOut" }, 2)' in source
    assert 'tl.set("#scene-s2", { opacity: 0 }, 2)' in source
    assert 'tl.to("#scene-s2", { opacity: 1, duration: 0.1, ease: "sine.inOut" }, 2)' in source
    assert 'tl.to("#scene-s2 .teaching-panel, #scene-s2 .opening-card, #scene-s2 .heading-label", { opacity: 0, duration: 0.15, ease: "sine.in" }, 3.45)' in source
    assert 'tl.to("#scene-s3", { opacity: 1, duration: 0.55, ease: "sine.inOut" }, 3.45)' in source


def test_no_unwanted_decorative_rule(tmp_path):
    result = EducationalHyperFramesComposer().execute(_inputs(tmp_path))
    assert result.success, result.error
    assert 'panel-rule' not in Path(result.data['index_html']).read_text(encoding='utf-8')


def test_long_paragraph_shows_current_source_sentences_not_entire_block():
    from tools.video.educational_hyperframes_composer import _source_fragments_for_chunk
    sentences = [f'Continent {letter} has mountains and rivers with many different plants and animals.'
                 for letter in 'ABCDEFG']
    paragraph = ' '.join(sentences)
    section = {'source_fragments': [{'block_type': 'paragraph', 'source_text': paragraph}]}
    displayed = []
    for sentence in sentences:
        result = _source_fragments_for_chunk(section, sentence)
        assert result == [{'block_type': 'paragraph', 'text': sentence}]
        displayed.append(result[0]['text'])
    assert ' '.join(displayed) == paragraph


def test_exercise_cards_use_aligned_reveal_and_thinking_pause(tmp_path):
    inputs = _inputs(tmp_path)
    section = inputs["educational_plan"]["sections"][0]
    section["source_block_type"] = "assessment"
    section["teaching_contract"] = {"questions": [{
        "question": "Which colour?", "answer": "Blue.", "thinking_pause_seconds": .4}]}
    inputs["word_captions"] = [w for w in inputs["word_captions"] if w["startMs"] >= 2000]
    inputs["word_captions"][:0] = [
        {"word": "Which", "startMs": 0, "endMs": 200},
        {"word": "colour?", "startMs": 200, "endMs": 400},
        {"word": "Blue.", "startMs": 800, "endMs": 1000}]
    result = EducationalHyperFramesComposer().execute(inputs)
    assert result.success, result.error
    source = Path(result.data["index_html"]).read_text(encoding="utf-8")
    assert 'id="exercise-s1-0-answer"' in source
    assert 'tl.set("#exercise-s1-0-answer", {opacity:1}, 0.8)' in source
    assert 'tl.set("#exercise-s1-0-think", {opacity:1}, 0.4)' in source
    section["teaching_contract"]["questions"][0]["answer"] = "Green."
    failed = EducationalHyperFramesComposer().execute(inputs)
    assert not failed.success
    assert "Exercise timing" in failed.error


def test_reference_opening_and_no_early_topic_text(tmp_path):
    inputs = _inputs(tmp_path)
    inputs["educational_plan"].update(grade=1, chapter_number=8)
    result = EducationalHyperFramesComposer().execute(inputs)
    assert result.success, result.error
    source = Path(result.data["index_html"]).read_text(encoding="utf-8")
    assert "Environmental Studies · Class 1" not in source
    assert '<span>LESSON</span>' not in source
    assert 'rgba(18,50,71,0.88)' in source
    assert 'tl.set("#scene-s2", { opacity: 0 }, 2)' in source


def test_source_lines_become_integrated_box_label_and_separate_text_lines(tmp_path):
    inputs = _inputs(tmp_path)
    section = inputs["educational_plan"]["sections"][2]
    section.update({
        "title": "II. Answer the following short questions",
        "source_block_type": "qa_item",
        "source_text": (
            "II. Answer the following short questions\n"
            "Define latitude.\n"
            "Why is the Prime Meridian important?"
        ),
        "source_fragments": [
            {"block_type": "section_heading", "source_text": "II. Answer the following short questions"},
            {"block_type": "assessment", "source_text": "Define latitude."},
            {"block_type": "assessment", "source_text": "Why is the Prime Meridian important?"},
        ],
    })

    result = EducationalHyperFramesComposer().execute(inputs)

    assert result.success, result.error
    source = Path(result.data["index_html"]).read_text(encoding="utf-8")
    assert '<div class="panel-label">II. Answer the following short questions</div>' in source
    assert '<p class="panel-line">Define latitude.</p>' in source
    assert '<p class="panel-line">Why is the Prime Meridian important?</p>' in source


def test_chunked_decimal_text_uses_complete_exact_source_line(tmp_path):
    inputs = _inputs(tmp_path)
    section = inputs["educational_plan"]["sections"][1]
    exact = "Tropic of Cancer (23.5° N): It marks the northernmost point of the tropics."
    section.update({
        "description": "Tropic of Cancer (23.",
        "source_text": exact,
        "source_fragments": [{"block_type": "bullet", "source_text": exact}],
    })

    result = EducationalHyperFramesComposer().execute(inputs)

    assert result.success, result.error
    source = Path(result.data["index_html"]).read_text(encoding="utf-8")
    assert exact in source
    assert '<p class="panel-body">Tropic of Cancer (23.</p>' not in source


def test_chunk_crossing_source_heading_uses_exact_label_and_body(tmp_path):
    inputs = _inputs(tmp_path)
    section = inputs["educational_plan"]["sections"][1]
    section.update({
        "title": "Lines on the Globe",
        "description": "Latitudes or Parallels Latitudes are horizontal imaginary lines across the globe.",
        "source_text": (
            "Lines on the Globe\nLatitudes or Parallels\n"
            "Latitudes are horizontal imaginary lines across the globe."
        ),
        "source_fragments": [
            {"block_type": "section_heading", "source_text": "Lines on the Globe"},
            {"block_type": "section_heading", "source_text": "Latitudes or Parallels"},
            {"block_type": "paragraph", "source_text": "Latitudes are horizontal imaginary lines across the globe."},
        ],
    })

    result = EducationalHyperFramesComposer().execute(inputs)

    assert result.success, result.error
    source = Path(result.data["index_html"]).read_text(encoding="utf-8")
    assert '<div class="panel-label">Latitudes or Parallels</div>' in source
    assert '<p class="panel-body">Latitudes are horizontal imaginary lines across the globe.</p>' in source
    assert "Latitudes or Parallels Latitudes are horizontal" not in source


def test_we_learn_never_falls_back_to_generic_objectives(tmp_path):
    inputs = _inputs(tmp_path)
    inputs["educational_plan"]["sections"][1]["source_block_type"] = "we_learn"
    result = EducationalHyperFramesComposer().execute(inputs)
    assert not result.success
    assert "source_questions" in result.error
    inputs["educational_plan"]["sections"][1]["source_questions"] = ["Do you have any pet animals?"]
    result = EducationalHyperFramesComposer().execute(inputs)
    assert result.success, result.error
    assert "Do you have any pet animals?" in Path(result.data["index_html"]).read_text(encoding="utf-8")


def test_title_hold_has_mask_and_delays_visual_clip(tmp_path):
    inputs = _inputs(tmp_path)
    inputs["narration_manifest"]["segments"][0].update({
        "heading_duration_seconds": 0.2, "body_start_seconds": 1.2,
        "topic_end_pause_seconds": 0.2,
        "heading_holds": [{"title": "Animal Life", "start_seconds": 0.2, "end_seconds": 1.2}],
    })
    result = EducationalHyperFramesComposer().execute(inputs)
    assert result.success, result.error
    workspace = Path(result.data["workspace_path"])
    source = (workspace / "index.html").read_text(encoding="utf-8")
    timeline = json.loads((workspace / "timeline.json").read_text(encoding="utf-8"))
    assert 'class="heading-hold" data-layout-allow-overlap data-layout-allow-occlusion><h1>Animal Life</h1>' in source
    assert 'tl.set("#heading-hold-s1-0", {opacity:1}, 0.2)' in source
    assert 'tl.set("#heading-hold-s1-0", {opacity:0}, 1.2)' in source
    # Opening footage is visible while its title is spoken; the hold mask alone
    # covers it during the requested title-only pause.
    assert timeline["sections"][0]["video"]["start_seconds"] == 0


def test_inline_title_pause_keeps_scene_without_duplicate_mask(tmp_path):
    inputs = _inputs(tmp_path)
    inputs["narration_manifest"]["segments"][1].update({
        "heading_duration_seconds": 0.2,
        "body_start_seconds": 1.2,
        "heading_holds": [],
        "heading_pause_presentation": "inline",
    })
    result = EducationalHyperFramesComposer().execute(inputs)
    assert result.success, result.error
    workspace = Path(result.data["workspace_path"])
    source = (workspace / "index.html").read_text(encoding="utf-8")
    timeline = json.loads((workspace / "timeline.json").read_text(encoding="utf-8"))
    assert timeline["sections"][1]["heading_hold"] is None
    assert timeline["sections"][1]["inline_title_pause"] == {
        "start_seconds": 2.2, "end_seconds": 3.2,
    }
    assert "heading-hold-s2" not in source
    assert "Animals need care" in source


def _inputs(tmp_path: Path) -> dict:
    media = tmp_path / "source-media"
    media.mkdir(parents=True)
    clips = []
    narration = []
    sections = []
    timeline = []
    words = []
    cursor = 0.0
    specifications = [
        ("s1", "opening", "Animal Life", "Animals share our world.", "pdf-p3-b1"),
        ("s2", "concept", "Animals need care", "They need food, water, air, and shelter.", "pdf-p4-b2"),
        ("s3", "recall", "Recall", "Animals are living beings.", "pdf-p8-b4"),
    ]
    for index, (section_id, kind, title, description, source_id) in enumerate(specifications):
        duration = 2.0
        video = media / f"{section_id}.mp4"
        audio = media / f"{section_id}.wav"
        video.write_bytes(f"video-{section_id}".encode())
        audio.write_bytes(f"audio-{section_id}".encode())
        clips.append({
            "section_id": section_id,
            "output_path": str(video),
            "duration_seconds": duration,
            "render_mode": "video_gen" if kind != "recall" else "hyperframes",
            "success": True,
        })
        narration.append({
            "section_id": section_id,
            "audio_path": str(audio),
            "duration_seconds": duration,
            "voice_used": "class-one-narrator",
        })
        sections.append({
            "section_id": section_id,
            "title": title,
            "description": description,
            "source_block_type": kind,
            "source_block_ids": [source_id],
            "render_mode": "video_gen",
        })
        timeline.append({
            "section_id": section_id,
            "start_seconds": cursor,
            "end_seconds": cursor + duration,
            "audio_duration_seconds": duration,
            "clip_duration_seconds": duration,
            "visual_duration_policy": "as_is",
        })
        section_words = title.split()
        for word_index, word in enumerate(section_words):
            start_ms = int((cursor + 0.2 + word_index * 0.45) * 1000)
            words.append({
                "word": word + ("." if word_index == len(section_words) - 1 else ""),
                "startMs": start_ms,
                "endMs": start_ms + 350,
                "pageBreakAfter": word_index == len(section_words) - 1,
            })
        cursor += duration
    return {
        "workspace_path": str(tmp_path / "workspace"),
        "template_contract": str(TEMPLATE),
        "educational_plan": {
            "version": "1.0",
            "title": "Animal Life",
            "domain": "Environmental Studies",
            "target_audience": "Class 1",
            "learning_objectives": ["Know animals", "Care for animals"],
            "sections": sections,
        },
        "clip_manifest": clips,
        "narration_manifest": {"segments": narration},
        "multimedia_sync_plan": {
            "status": "pass",
            "issues": [],
            "total_duration_seconds": cursor,
            "timeline": timeline,
        },
        "word_captions": words,
    }


def test_composer_emits_locked_deterministic_hyperframes_workspace(tmp_path):
    inputs = _inputs(tmp_path)
    result = EducationalHyperFramesComposer().execute(inputs)
    assert result.success, result.error

    workspace = Path(result.data["workspace_path"])
    html = (workspace / "index.html").read_text(encoding="utf-8")
    design = (workspace / "DESIGN.md").read_text(encoding="utf-8")
    timeline = json.loads((workspace / "timeline.json").read_text(encoding="utf-8"))
    hyperframes_config = json.loads(
        (workspace / "hyperframes.json").read_text(encoding="utf-8")
    )

    assert html.count("<video ") == 3
    assert html.count(" muted playsinline ") == 3
    assert html.count("<audio ") == 3
    assert 'data-track-index="10" data-volume="1"' in html
    assert 'window.__timelines["educational-main"] = tl;' in html
    assert 'data-composition-id="educational-main"' in html
    assert 'data-template-id="hyperframes-educational-v1"' in html
    assert (
        f'data-template-package-sha256="{educational_template_package_sha256()}"'
        in html
    )
    assert "crossorigin=" not in html
    assert "Math.random" not in html
    assert "Date.now" not in html
    assert "repeat: -1" not in html
    assert "pdf-p3-b1" in html and "pdf-p8-b4" in html
    assert "Animals are living beings." in html
    assert "caption-word" in html
    assert "highlight_active" not in html
    assert 'ease: "sine.inOut"' in html
    assert timeline["audio_is_timing_authority"] is True
    assert timeline["template"]["status"] == "locked"
    assert timeline["transition"] == {"type": "crossfade", "duration_seconds": 0.55}
    assert result.data["video_count"] == 3
    assert result.data["audio_count"] == 3
    assert (
        result.data["template_package_sha256"]
        == educational_template_package_sha256()
    )
    assert hyperframes_config["duration"] == timeline["duration_seconds"]
    assert hyperframes_config["fps"] == 30
    assert "Canonical SHA-256" in design

    first_html = html
    first_timeline = (workspace / "timeline.json").read_text(encoding="utf-8")
    repeated = EducationalHyperFramesComposer().execute(inputs)
    assert repeated.success, repeated.error
    assert (workspace / "index.html").read_text(encoding="utf-8") == first_html
    assert (workspace / "timeline.json").read_text(encoding="utf-8") == first_timeline


def test_composer_rejects_unlocked_template_or_chapter_overrides(tmp_path):
    inputs = _inputs(tmp_path)
    contract = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
    contract["override_policy"]["chapter_css_overrides"] = True
    inputs["template_contract"] = contract
    result = EducationalHyperFramesComposer().execute(inputs)
    assert not result.success
    assert "chapter_css_overrides must remain false" in result.error

    inputs = _inputs(tmp_path / "package-hash")
    inputs["template_package_sha256"] = "0" * 64
    result = EducationalHyperFramesComposer().execute(inputs)
    assert not result.success
    assert "template package" in result.error.lower()


def test_composer_rejects_blocked_sync_or_missing_motion_clip(tmp_path):
    inputs = _inputs(tmp_path)
    inputs["multimedia_sync_plan"]["status"] = "blocked"
    result = EducationalHyperFramesComposer().execute(inputs)
    assert not result.success
    assert "sync plan is blocked" in result.error.lower()

    inputs = _inputs(tmp_path / "missing")
    inputs["clip_manifest"][0].pop("output_path")
    result = EducationalHyperFramesComposer().execute(inputs)
    assert not result.success
    assert "requires a rendered visual clip" in result.error


def test_composer_keeps_multiple_visual_segments_at_source_timed_lengths(tmp_path):
    inputs = _inputs(tmp_path)
    first = inputs["clip_manifest"][0]
    original = Path(first.pop("output_path"))
    second = original.with_name("s1-detail.mp4")
    second.write_bytes(b"second-video")
    first["visual_segments"] = [
        {"path": str(original), "offset_seconds": 0, "duration_seconds": 0.9},
        {"path": str(second), "offset_seconds": 1.0, "duration_seconds": 0.8},
    ]
    result = EducationalHyperFramesComposer().execute(inputs)
    assert result.success, result.error
    html = Path(result.data["index_html"]).read_text(encoding="utf-8")
    assert 'id="video-s1-seg-1"' in html
    assert 'id="video-s1-seg-2"' in html
    assert 'data-start="0" data-duration="0.9"' in html
    assert 'data-start="1" data-duration="0.8"' in html
    assert 'id="video-s1"' not in html
    assert result.data["video_count"] == 4


def test_composer_rejects_visual_segment_past_section_end(tmp_path):
    inputs = _inputs(tmp_path)
    first = inputs["clip_manifest"][0]
    original = first.pop("output_path")
    first["visual_segments"] = [
        {"path": original, "offset_seconds": 1.5, "duration_seconds": 1.0}
    ]
    result = EducationalHyperFramesComposer().execute(inputs)
    assert not result.success
    assert "timing exceeds s1" in result.error


def test_precise_visual_cut_avoids_ghost_background(tmp_path):
    inputs = _inputs(tmp_path)
    first = inputs['clip_manifest'][0]
    original = first.pop('output_path')
    first['visual_segments'] = [
        {'path': original, 'offset_seconds': 0.2,
         'duration_seconds': 1.5, 'transition': 'cut'}
    ]
    result = EducationalHyperFramesComposer().execute(inputs)
    assert result.success, result.error
    html = Path(result.data['index_html']).read_text(encoding='utf-8')
    assert 'tl.set("#video-s1-seg-1", { opacity: 1 }, 0.2);' in html
    assert 'tl.set("#video-s1-seg-1", { opacity: 0 }, 1.7);' in html
    assert 'tl.fromTo("#video-s1-seg-1"' not in html
    first['visual_segments'][0]['transition'] = 'unknown'
    result = EducationalHyperFramesComposer().execute(inputs)
    assert not result.success
    assert 'Unsupported visual transition' in result.error


def test_caption_phrases_survive_natural_acoustic_word_gaps():
    from tools.video.educational_hyperframes_composer import _caption_groups
    words = [
        {'word': text, 'start_ms': start, 'end_ms': end,
         'page_break_after': False, 'section_id': 'rotation'}
        for text, start, end in [
            ('and', 0, 150), ('one', 450, 650), ('quarter', 900, 1200),
            ('days.', 1300, 1650), ('Next', 2400, 2700), ('topic.', 2750, 3100)
        ]
    ]
    groups = _caption_groups(words)
    assert [g['text'] for g in groups] == ['and one quarter days.', 'Next topic.']
    assert groups[0]['words'][1]['start_ms'] == 450


def test_composer_pages_exact_source_text_without_overflowing_one_card(tmp_path):
    inputs = _inputs(tmp_path)
    section = inputs["educational_plan"]["sections"][1]
    section["source_fragments"] = [
        {"block_type": "section_heading", "source_text": "Animals need care"},
        {"block_type": "paragraph", "source_text": "They need food, water,"},
        {"block_type": "paragraph", "source_text": "air, and shelter."},
    ]
    inputs["clip_manifest"][1]["teaching_pages"] = [
        {"text": "They need food, water,", "start_offset_seconds": 0, "end_offset_seconds": 1},
        {"text": "air, and shelter.", "start_offset_seconds": 1, "end_offset_seconds": 2},
    ]
    result = EducationalHyperFramesComposer().execute(inputs)
    assert result.success, result.error
    output = Path(result.data["index_html"]).read_text(encoding="utf-8")
    assert 'id="panel-page-s2-0"' in output
    assert 'id="panel-page-s2-1"' in output
    assert 'tl.set("#panel-page-s2-1", { opacity: 1 }, 3)' in output

    inputs["clip_manifest"][1]["teaching_pages"][1]["text"] = "and shelter."
    failed = EducationalHyperFramesComposer().execute(inputs)
    assert not failed.success
    assert "preserve all source panel text" in failed.error


def test_composer_places_source_figure_only_at_its_teaching_cue(tmp_path):
    inputs = _inputs(tmp_path)
    figure = tmp_path / "source-figure.png"
    figure.write_bytes(b"source-figure")
    inputs["clip_manifest"][1]["source_figure_overlays"] = [
        {"path": str(figure), "offset_seconds": 0.5, "duration_seconds": 1.0,
         "authored_caption": "Original textbook figure: A & B"}
    ]
    result = EducationalHyperFramesComposer().execute(inputs)
    assert result.success, result.error
    output = Path(result.data["index_html"]).read_text(encoding="utf-8")
    assert 'id="source-figure-s2-0"' in output
    assert 'src="assets/images/002-s2-01.png"' in output
    assert '<figcaption class="source-figure-caption">Original textbook figure: A &amp; B</figcaption>' in output
    assert 'tl.fromTo("#source-figure-s2-0"' in output
    timeline = json.loads(Path(result.data["timeline_json"]).read_text(encoding="utf-8"))
    assert timeline["sections"][1]["figures"][0]["start_seconds"] == 2.5
    assert timeline["sections"][1]["figures"][0]["authored_caption"] == "Original textbook figure: A & B"

    inputs["clip_manifest"][1]["source_figure_overlays"][0]["duration_seconds"] = 2.0
    failed = EducationalHyperFramesComposer().execute(inputs)
    assert not failed.success
    assert "Source figure timing exceeds s2" in failed.error


def test_composer_rejects_voice_changes_asset_reuse_and_caption_gaps(tmp_path):
    inputs = _inputs(tmp_path)
    inputs["narration_manifest"]["segments"][1]["voice_used"] = "different-voice"
    result = EducationalHyperFramesComposer().execute(inputs)
    assert not result.success
    assert "Narrator identity changes" in result.error

    inputs = _inputs(tmp_path / "reuse")
    inputs["clip_manifest"][1]["output_path"] = inputs["clip_manifest"][0]["output_path"]
    result = EducationalHyperFramesComposer().execute(inputs)
    assert not result.success
    assert "Visual asset reuse is forbidden" in result.error

    inputs = _inputs(tmp_path / "captions")
    inputs["word_captions"] = inputs["word_captions"][:1]
    result = EducationalHyperFramesComposer().execute(inputs)
    assert not result.success
    assert "No word captions overlap" in result.error


def test_composer_renders_structured_source_table_without_markdown_pipes(tmp_path):
    inputs = _inputs(tmp_path)
    section = inputs["educational_plan"]["sections"][1]
    section.update({
        "source_block_type": "table",
        "source_document_block_type": "table",
        "source_page_number": 4,
        "source_bbox": [40, 120, 560, 640],
        "source_table": {
            "row_count": 3,
            "column_count": 2,
            "header_rows": 1,
            "cells": [
                {"row": 0, "column": 0, "text": "Animal", "row_span": 1, "column_span": 1, "is_header": True},
                {"row": 0, "column": 1, "text": "Home", "row_span": 1, "column_span": 1, "is_header": True},
                {"row": 1, "column": 0, "text": "Lion", "row_span": 1, "column_span": 1, "is_header": False},
                {"row": 1, "column": 1, "text": "Den", "row_span": 1, "column_span": 1, "is_header": False},
                {"row": 2, "column": 0, "text": "Bee", "row_span": 1, "column_span": 1, "is_header": False},
                {"row": 2, "column": 1, "text": "Hive", "row_span": 1, "column_span": 1, "is_header": False},
            ],
        },
        "render_mode": "hyperframes",
    })
    inputs["clip_manifest"][1].pop("output_path")
    inputs["clip_manifest"][1]["render_mode"] = "hyperframes"

    result = EducationalHyperFramesComposer().execute(inputs)
    assert result.success, result.error
    html = Path(result.data["index_html"]).read_text(encoding="utf-8")
    timeline = json.loads(Path(result.data["timeline_json"]).read_text(encoding="utf-8"))

    assert '<table class="source-table">' in html
    assert "<th" in html and "Animal</th>" in html
    assert "Lion</td>" in html and "Hive</td>" in html
    assert "| Animal | Home |" not in html
    table_section = timeline["sections"][1]
    assert table_section["source_page_number"] == 4
    assert table_section["source_bbox"] == [40, 120, 560, 640]
    assert table_section["panel"]["table"]["row_count"] == 3
