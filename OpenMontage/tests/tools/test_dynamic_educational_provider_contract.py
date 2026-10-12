import json
from pathlib import Path

import pytest

from tools.base_tool import ToolResult
from tools.structure.educational_generator import build_source_grounded_plan
from tools.structure.pdf_to_video_pipeline import (
    build_config,
    load_provider_overrides,
    provider_overrides_from_inputs,
    run_pdf_to_video,
)
from tools.structure.source_contract import build_coverage_contract, write_source_contracts
from tools.structure.subject_pipeline_runner import (
    SubjectPipelineRunner,
    _map_plan_to_coverage,
    _source_content_for_planning,
)
from tools.video.render_mode_router import _render_video_gen


def test_planner_receives_complete_source_blocks():
    long_tail = "important-tail-marker"
    body = "word " * 600 + long_tail

    content = _source_content_for_planning([
        {"heading": "Recall", "body_text": body},
    ])

    assert long_tail in content
    assert content.count("word") == 600


def test_zero_shot_plan_maps_every_source_block_without_subject_code():
    blocks = [
        {
            "block_id": "p0001-b0001",
            "block_type": "chapter_title",
            "semantic_role": "lesson_content",
            "source_text": "Plants Around Us",
        },
        {
            "block_id": "p0001-b0002",
            "block_type": "paragraph",
            "semantic_role": "lesson_content",
            "source_text": "Plants need sunlight and water to grow.",
        },
        {
            "block_id": "p0002-b0001",
            "block_type": "assessment",
            "semantic_role": "assessment",
            "source_text": "Name two things a plant needs.",
        },
    ]

    plan = build_source_grounded_plan(
        blocks,
        subject="science",
        subject_type="theory",
        complexity_level="elementary",
        target_audience="Class 1, ages 5-7",
    )

    assert [
        section["source_block_ids"][0] for section in plan["sections"]
    ] == [block["block_id"] for block in blocks]
    assert plan["sections"][1]["render_mode"] == "video_gen"
    assert plan["sections"][2]["render_mode"] == "hyperframes"
    assert plan["metadata"]["plan_origin"] == "deterministic-source-contract"


def test_zero_shot_plan_uses_source_heading_instead_of_generic_ui_label():
    plan = build_source_grounded_plan(
        [{
            "block_id": "p0001-b0001",
            "block_type": "paragraph",
            "semantic_role": "lesson_content",
            "heading": "Animals Are Living Beings",
            "source_text": "Animals need food, water, air, and shelter.",
        }],
        subject="science",
        subject_type="theory",
        complexity_level="elementary",
        target_audience="Class 1, ages 5-7",
    )

    assert plan["sections"][0]["title"] == "Animals Are Living Beings"
    assert plan["sections"][0]["title"] != "Lesson Content"


def test_zero_shot_plan_does_not_render_decorative_page_furniture():
    plan = build_source_grounded_plan(
        [
            {
                "block_id": "p0001-b0001",
                "block_type": "paragraph",
                "semantic_role": "lesson_content",
                "source_text": "Plants need sunlight.",
                "required_for_coverage": True,
            },
            {
                "block_id": "p0001-b0002",
                "block_type": "decorative",
                "semantic_role": "lesson_content",
                "source_text": "17 Rockland English - Class 1",
                "required_for_coverage": False,
            },
        ],
        subject="science",
        subject_type="theory",
        complexity_level="elementary",
        target_audience="Class 1, ages 5-7",
    )

    assert len(plan["sections"]) == 1
    assert "Rockland" not in plan["sections"][0]["narration_script"]


def test_zero_shot_plan_groups_pdf_line_boxes_without_losing_coverage():
    blocks = [
        {
            "block_id": f"p0002-b{index:04d}",
            "page_number": 2,
            "block_type": "paragraph",
            "semantic_role": "lesson_content",
            "heading": "Read and Enjoy",
            "source_text": text,
            "required_for_coverage": True,
        }
        for index, text in enumerate((
            "Being polite means speaking in a kind and humble manner.",
            "We practise polite behaviour first at home.",
            "Our words should never hurt another person.",
        ), 1)
    ]

    plan = build_source_grounded_plan(
        blocks,
        subject="english",
        subject_type="language",
        complexity_level="elementary",
        target_audience="Class 4, ages 8-10",
    )

    mapped_ids = {
        block_id
        for section in plan["sections"]
        for block_id in section["source_block_ids"]
    }
    assert mapped_ids == {block["block_id"] for block in blocks}
    assert plan["metadata"]["planning_group_count"] == 1
    assert all(
        section["source_block_ids"] == [block["block_id"] for block in blocks]
        for section in plan["sections"]
    )
    assert all(len(section["source_fragments"]) == 3 for section in plan["sections"])


def test_source_grounded_plan_closes_coverage_contract():
    blocks = [
        {
            "block_id": "p0001-b0001",
            "page_number": 1,
            "reading_order": 1,
            "block_type": "chapter_title",
            "semantic_role": "lesson_content",
            "source_text": "Our Neighbourhood",
            "required_for_coverage": True,
            "provenance": {
                "source_line_start": 1,
                "source_line_end": 1,
                "extraction_mode": "test",
            },
        },
        {
            "block_id": "p0001-b0002",
            "page_number": 1,
            "reading_order": 2,
            "block_type": "paragraph",
            "semantic_role": "lesson_content",
            "source_text": "A neighbourhood has homes and helpful places.",
            "required_for_coverage": True,
            "provenance": {
                "source_line_start": 2,
                "source_line_end": 2,
                "extraction_mode": "test",
            },
        },
    ]
    document = {
        "source": {
            "text_sha256": "a" * 64,
            "text_artifact": "chapter.md",
        },
        "blocks": blocks,
    }
    coverage = build_coverage_contract(document)
    plan = build_source_grounded_plan(
        blocks,
        subject="social-studies",
        subject_type="theory",
        complexity_level="elementary",
        target_audience="Class 1, ages 5-7",
    )

    summary = _map_plan_to_coverage(coverage, plan)

    assert summary["coverage_ratio"] == 1.0
    assert summary["render_ready"] is True
    assert all(entry["status"] == "mapped" for entry in coverage["entries"])


def test_motion_narration_preserves_sentences_independently_of_shot_duration():
    source_text = " ".join(f"word{index}" for index in range(45)) + "."
    plan = build_source_grounded_plan(
        [{
            "block_id": "p0001-b0001",
            "block_type": "paragraph",
            "semantic_role": "lesson_content",
            "source_text": source_text,
        }],
        subject="evs",
        subject_type="theory",
        complexity_level="elementary",
        target_audience="Class 1, ages 5-7",
    )

    assert len(plan["sections"]) == 1
    assert plan["sections"][0]["narration_script"] == source_text
    # The media/synchronization plan must cover a long sentence with enough
    # motion; the source sentence itself must not be cut into dangling clauses.
    assert plan["sections"][0]["duration_seconds"] > 10
    assert {section["source_block_ids"][0] for section in plan["sections"]} == {
        "p0001-b0001"
    }


def test_zero_shot_plan_preserves_and_paginates_structured_tables():
    cells = [
        {
            "row": 0,
            "column": column,
            "text": text,
            "row_span": 1,
            "column_span": 1,
            "is_header": True,
        }
        for column, text in enumerate(("Plant", "Use"))
    ]
    for row in range(1, 9):
        cells.extend([
            {
                "row": row,
                "column": 0,
                "text": f"Plant {row}",
                "row_span": 1,
                "column_span": 1,
                "is_header": False,
            },
            {
                "row": row,
                "column": 1,
                "text": f"Use {row}",
                "row_span": 1,
                "column_span": 1,
                "is_header": False,
            },
        ])
    plan = build_source_grounded_plan(
        [{
            "block_id": "p0002-b0004",
            "page_number": 2,
            "bbox": [40, 120, 560, 640],
            "block_type": "table",
            "semantic_role": "lesson_content",
            "source_text": "Plant uses table",
            "table": {
                "row_count": 9,
                "column_count": 2,
                "header_rows": 1,
                "cells": cells,
            },
        }],
        subject="science",
        subject_type="theory",
        complexity_level="elementary",
        target_audience="Class 1, ages 5-7",
    )

    assert len(plan["sections"]) == 2
    assert all(section["render_mode"] == "hyperframes" for section in plan["sections"])
    assert all(section["source_block_type"] == "table" for section in plan["sections"])
    assert all(section["source_page_number"] == 2 for section in plan["sections"])
    assert all(section["source_bbox"] == [40, 120, 560, 640] for section in plan["sections"])
    assert [section["source_table"]["row_count"] for section in plan["sections"]] == [7, 3]
    spoken = " ".join(section["narration_script"] for section in plan["sections"])
    assert "Plant: Plant 1" in spoken
    assert "Use: Use 8" in spoken


def test_generated_config_uses_modelslab_for_audio_and_video(tmp_path: Path):
    pdf = tmp_path / "chapter.pdf"
    markdown = tmp_path / "chapter.md"
    structured = tmp_path / "extracted_content.json"
    chapter_document = tmp_path / "chapter_document.json"
    coverage_contract = tmp_path / "coverage_contract.json"
    project = tmp_path / "project"
    for path in (pdf, markdown, structured, chapter_document, coverage_contract):
        path.write_text("source", encoding="utf-8")

    config = build_config(
        pdf,
        project,
        markdown,
        {
            "subject": "science",
            "subject_label": "Science",
            "chapter": 2,
            "title": "Plants",
            "subject_type": "theory",
            "grade": 1,
            "age_range": "5-7",
        },
        extracted_artifact_path=structured,
        chapter_document_path=chapter_document,
        coverage_contract_path=coverage_contract,
    )

    assert config["providers"]["audio"]["provider"] == "modelslab"
    assert config["providers"]["audio"]["lock_voice"] is True
    assert config["providers"]["video"]["provider"] == "modelslab"
    assert config["providers"]["video"]["generate_audio"] is False
    assert config["providers"]["video"]["educational_mode"] is True
    assert config["providers"]["video"]["image_model_id"] == "wan-2.2-i2v"
    assert config["providers"]["video"]["reference_model_id"] == "h3-minimax-r2v"
    assert config["providers"]["video"]["reference_image_model_id"] == "flux"
    assert config["providers"]["video"]["allow_clip_reuse"] is False
    assert config["providers"]["video"]["max_generation_attempts"] == 3
    assert config["providers"]["video"]["semantic_qa"]["required"] is True
    assert config["source_document"] == str(chapter_document.resolve())
    assert config["coverage_contract"] == str(coverage_contract.resolve())


def test_provider_models_and_voice_are_dynamic_but_modelslab_stays_locked(
    tmp_path: Path,
):
    source = tmp_path / "chapter.md"
    source.write_text("# Plants", encoding="utf-8")
    provider_path = tmp_path / "models.yaml"
    provider_path.write_text(
        """
audio:
  provider: modelslab
  model_id: eleven_multilingual_v2
  voice_id: Nila - Tamil
  language: british english
  speed: 0.76
video:
  provider: modelslab
  model_id: seedance-t2v
  image_model_id: seedance-i2v
  reference_model_id: h3-minimax-r2v
  reference_image_model_id: flux-dev
  fallback_model_id: h3-minimax-t2v
  max_generation_attempts: 4
  semantic_qa:
    model: clip
    max_frames: 7
""".strip(),
        encoding="utf-8",
    )
    overrides = provider_overrides_from_inputs({
        "provider_config": str(provider_path),
        "voice_id": "chapter-narrator",
    })
    config = build_config(
        source,
        tmp_path / "project",
        source,
        {
            "subject": "science",
            "subject_label": "Science",
            "chapter": 2,
            "title": "Plants",
            "subject_type": "theory",
            "grade": 1,
            "age_range": "5-7",
        },
        provider_overrides=overrides,
    )

    assert config["providers"]["audio"]["voice_id"] == "chapter-narrator"
    assert config["providers"]["audio"]["model_id"] == "eleven_multilingual_v2"
    assert config["providers"]["audio"]["speed"] == 0.76
    assert config["providers"]["audio"]["provider"] == "modelslab"
    assert config["providers"]["audio"]["lock_voice"] is True
    assert config["providers"]["video"]["model_id"] == "seedance-t2v"
    assert config["providers"]["video"]["image_model_id"] == "seedance-i2v"
    assert config["providers"]["video"]["max_generation_attempts"] == 4
    assert config["providers"]["video"]["semantic_qa"]["max_frames"] == 7
    assert config["providers"]["video"]["generate_audio"] is False
    assert "api_key" not in json.dumps(config).lower()


def test_provider_config_rejects_credentials_and_non_modelslab_video_provider(
    tmp_path: Path,
):
    secret_path = tmp_path / "secret.json"
    secret_path.write_text(
        json.dumps({"audio": {"api_key": "must-not-be-stored"}}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="MODELSLAB_API_KEY"):
        load_provider_overrides(secret_path)

    source = tmp_path / "chapter.md"
    source.write_text("# Plants", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported educational video provider"):
        build_config(
            source,
            tmp_path / "project",
            source,
            {
                "subject": "science",
                "subject_label": "Science",
                "chapter": 2,
                "title": "Plants",
                "subject_type": "theory",
                "grade": 1,
                "age_range": "5-7",
            },
            provider_overrides={"video": {"provider": "other"}},
        )


def test_provider_config_accepts_huggingface_kokoro_narration(tmp_path: Path):
    source = tmp_path / "chapter.md"
    source.write_text("# Basic Shapes", encoding="utf-8")
    config = build_config(
        source,
        tmp_path / "project",
        source,
        {
            "subject": "maths",
            "subject_label": "Maths",
            "chapter": 7,
            "title": "Basic Shapes",
            "subject_type": "mathematics",
            "grade": 4,
            "age_range": "8-10",
        },
        provider_overrides={
            "audio": {
                "provider": "huggingface-kokoro",
                "model_id": "hexgrad/Kokoro-82M",
                "voice_id": "af_heart",
                "language": "en-us",
                "speed": 0.82,
            }
        },
    )

    assert config["providers"]["audio"]["provider"] == "huggingface-kokoro"
    assert config["providers"]["audio"]["voice_id"] == "af_heart"


def test_video_router_forces_silent_models_lab_generation(monkeypatch, tmp_path: Path):
    captured = {}

    def fake_execute(_self, request):
        captured.update(request)
        Path(request["output_path"]).write_bytes(b"video")
        return ToolResult(success=True, data={"output_path": request["output_path"]})

    monkeypatch.setattr(
        "tools.video.modelslab_video.ModelsLabVideo.execute",
        fake_execute,
    )
    monkeypatch.setattr(
        "tools.video.render_mode_router._probe_duration",
        lambda _path: 6.0,
    )
    monkeypatch.setattr(
        "tools.analysis.educational_clip_qa.audit_generated_clip",
        lambda *_args, **_kwargs: {"status": "pass", "issues": []},
    )

    result = _render_video_gen(
        {
            "section_id": "science-s1",
            "title": "How a seed grows",
            "description": "A seed sprouts and grows two leaves",
            "duration_seconds": 6,
        },
        "science",
        tmp_path,
        False,
        {
            "provider": "modelslab",
            "model_id": "wan2.2",
            "generate_audio": True,
        },
    )

    assert result.success is True
    assert captured["model_id"] == "wan2.2"
    assert captured["operation"] == "text_to_video"
    assert captured["generate_audio"] is False
    assert captured["educational_mode"] is True
    assert "3D" in captured["prompt"]


def test_video_router_uses_i2v_model_when_reference_image_exists(
    monkeypatch, tmp_path: Path
):
    captured = {}
    reference = tmp_path / "character-reference.png"
    reference.write_bytes(b"png")

    def fake_execute(_self, request):
        captured.update(request)
        Path(request["output_path"]).write_bytes(b"video")
        return ToolResult(success=True, data={"output_path": request["output_path"]})

    monkeypatch.setattr(
        "tools.video.modelslab_video.ModelsLabVideo.execute",
        fake_execute,
    )
    monkeypatch.setattr(
        "tools.video.render_mode_router._probe_duration",
        lambda _path: 5.0,
    )
    monkeypatch.setattr(
        "tools.analysis.educational_clip_qa.audit_generated_clip",
        lambda *_args, **_kwargs: {"status": "pass", "issues": []},
    )

    result = _render_video_gen(
        {
            "section_id": "story-s1",
            "description": "The same child waves to her friend",
            "duration_seconds": 5,
            "reference_image_path": str(reference),
        },
        "english",
        tmp_path,
        False,
        {
            "provider": "modelslab",
            "model_id": "wan2.2",
            "image_model_id": "wan-2.2-i2v",
        },
    )

    assert result.success is True
    assert captured["operation"] == "image_to_video"
    assert captured["model_id"] == "wan-2.2-i2v"
    assert captured["image_path"] == str(reference)


def test_dynamic_subject_pipeline_dry_run_closes_source_coverage(tmp_path: Path):
    project = tmp_path / "science-chapter"
    artifacts = project / "artifacts"
    artifacts.mkdir(parents=True)
    source = tmp_path / "lesson.md"
    source.write_text(
        "# Plants\n\nPlants need sunlight and water.\n\n"
        "## Plant uses\n| Plant | Use |\n| --- | --- |\n| Cotton | Clothes |\n\n"
        "## Recall\n- Name one thing a plant needs.\n",
        encoding="utf-8",
    )
    chapter_document_path = artifacts / "chapter_document.json"
    coverage_path = artifacts / "coverage_contract.json"
    write_source_contracts(
        source,
        chapter_document_path,
        coverage_path,
        source_input=str(source),
    )
    config = build_config(
        source,
        project,
        source,
        {
            "subject": "science",
            "subject_label": "Science",
            "chapter": 1,
            "title": "Plants",
            "subject_type": "theory",
            "grade": 1,
            "age_range": "5-7",
        },
        chapter_document_path=chapter_document_path,
        coverage_contract_path=coverage_path,
    )
    config_path = project / "chapter_config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = SubjectPipelineRunner().execute({
        "subject": "science",
        "chapter_config_path": str(config_path),
        "output_dir": str(project),
        "dry_run": True,
    })

    assert result.success is True, result.error
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    assert coverage["summary"]["render_ready"] is True
    assert result.data["stages_summary"]["stage_1"]["coverage"]["coverage_ratio"] == 1.0
    for name in (
        "proposal_packet", "scene_plan", "asset_strategy", "asset_manifest"
    ):
        assert (artifacts / f"{name}.json").is_file()
    scene_plan = json.loads((artifacts / "scene_plan.json").read_text(encoding="utf-8"))
    assert all(scene["source_block_ids"] for scene in scene_plan["scenes"])
    asset_manifest = json.loads(
        (artifacts / "asset_manifest.json").read_text(encoding="utf-8")
    )
    assert asset_manifest["ready"] is True
    assert (
        result.data["stages_summary"]["stage_5"]["source_coverage"]["coverage_ratio"]
        == 1.0
    )
    timeline_path = (
        Path(result.data["workspace_path"]) / "timeline.json"
    )
    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    assert any(section["panel"].get("table") for section in timeline["sections"])


def test_unknown_subject_runs_through_general_profile_without_core_code_change(
    tmp_path: Path
):
    project = tmp_path / "robotics-chapter"
    artifacts = project / "artifacts"
    artifacts.mkdir(parents=True)
    source = tmp_path / "robotics.md"
    source.write_text(
        "# Friendly Robots\n\nA sensor helps a robot notice an obstacle.\n",
        encoding="utf-8",
    )
    chapter_document_path = artifacts / "chapter_document.json"
    coverage_path = artifacts / "coverage_contract.json"
    write_source_contracts(
        source, chapter_document_path, coverage_path, source_input=str(source)
    )
    config = build_config(
        source,
        project,
        source,
        {
            "subject": "robotics",
            "subject_label": "Robotics",
            "subject_profile": "general_theory",
            "chapter": 1,
            "title": "Friendly Robots",
            "subject_type": "theory",
            "grade": 3,
            "age_range": "7-9",
        },
        chapter_document_path=chapter_document_path,
        coverage_contract_path=coverage_path,
    )
    config_path = project / "chapter_config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = SubjectPipelineRunner().execute({
        "subject": "robotics",
        "chapter_config_path": str(config_path),
        "output_dir": str(project),
        "dry_run": True,
    })

    assert result.success is True, result.error
    proposal = json.loads(
        (artifacts / "proposal_packet.json").read_text(encoding="utf-8")
    )
    assert proposal["metadata"]["subject"] == "robotics"
    assert proposal["production_plan"]["video_provider"] == "modelslab"


def test_one_command_dry_run_reports_post_planning_coverage(
    tmp_path: Path, monkeypatch
):
    source = tmp_path / "lesson.md"
    source.write_text(
        "# Weather\n\nRain falls from clouds.\n\n## Recall\nName one rainy-day item.\n",
        encoding="utf-8",
    )
    project = tmp_path / "weather-video"
    monkeypatch.setattr(
        "tools.structure.pdf_to_video_pipeline.init_project",
        lambda *_args, **_kwargs: project,
    )

    result = run_pdf_to_video({
        "input_path": str(source),
        "project_id": "weather-video",
        "subject": "science",
        "grade": 1,
        "chapter": 1,
        "title": "Weather",
        "dry_run": True,
    })

    assert result["coverage_render_ready"] is True
    persisted = json.loads(
        Path(result["coverage_contract"]).read_text(encoding="utf-8")
    )
    assert persisted["summary"]["render_ready"] is True
