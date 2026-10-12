import json
from pathlib import Path

import pytest
import yaml

from schemas.artifacts import validate_artifact
from tools.extract.hybrid_pdf_extractor import HybridPDFExtractor
from tools.extract.section_parser import SectionParser
from tools.structure.pdf_to_video_pipeline import infer_metadata
from tools.structure.educational_generator import build_source_grounded_plan
from tools.structure.edustream_orchestrator import EduStreamOrchestrator
from tools.structure.chapter_config import (
    LOCKED_UI_TEMPLATE_PACKAGE_SHA256,
    LOCKED_UI_TEMPLATE_SHA256,
    load_chapter_config,
    locked_ui_template_contract,
    registry_view,
)
from tools.structure.subject_profiles import infer_subject_id, resolve_subject_profile
from tools.video.manim_generator import ManimGenerator


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_subject_profiles_route_known_and_unknown_subjects_without_code_changes():
    subject, profile = infer_subject_id(
        "Birds build nests and fish live in water.",
        filename="RPS EVS Class 1.pdf",
    )
    assert subject == "science"
    assert profile["concept_family"] == "natural_science"
    assert profile["render_modes"]["concept"] == "video_gen"

    custom_subject, custom_profile = infer_subject_id(
        "A friendly introduction to robots.",
        explicit_subject="Robotics",
    )
    assert custom_subject == "robotics"
    assert custom_profile["profile_id"] == "general_theory"
    assert custom_profile["default_render_mode"] == "video_gen"


def test_metadata_inference_uses_data_driven_subject_profiles(tmp_path):
    source = tmp_path / "RPS - ENGLISH - CLASS 1 - Chapter 2.pdf"
    metadata = infer_metadata(
        source,
        "# Chapter 2: My Family\nRead the story and answer the questions.",
        {},
    )
    assert metadata["subject"] == "english"
    assert metadata["subject_profile"] == "language_english"
    assert metadata["subject_type"] == "mixed"

    assert resolve_subject_profile("mathematics")["default_render_mode"] == "manim"


def test_section_parser_accepts_new_subject_with_explicit_markdown(tmp_path):
    source = tmp_path / "chapter.md"
    source.write_text("# Plants\nPlants need water and light.", encoding="utf-8")

    result = SectionParser().execute({
        "subject": "science",
        "md_path": str(source),
        "output_dir": str(tmp_path / "artifacts"),
    })

    assert result.success is True
    assert result.data["blocks"][0]["block_id"].startswith("science_block_")


def test_section_parser_requires_path_for_unregistered_subject():
    result = SectionParser().execute({"subject": "science"})

    assert result.success is False
    assert "Provide md_path" in result.error


def test_pdf_extractor_persists_canonical_outputs(tmp_path, monkeypatch):
    source = tmp_path / "chapter.pdf"
    source.write_bytes(b"placeholder")
    extractor = HybridPDFExtractor()
    monkeypatch.setattr(extractor, "_get_page_count", lambda _path: 1)
    monkeypatch.setattr(
        extractor,
        "_run_opendataloader",
        lambda _path, _pages: ("# Animals\n" + "Animals move and grow. " * 80, {}, 0.01),
    )

    output_dir = tmp_path / "artifacts"
    result = extractor.execute({
        "pdf_path": str(source),
        "subject_type": "theory",
        "output_dir": str(output_dir),
    })

    assert result.success is True
    assert (output_dir / "extracted_content.md").is_file()
    artifact = json.loads((output_dir / "extracted_content.json").read_text(encoding="utf-8"))
    assert artifact["source_pdf"] == str(source)
    assert artifact["sections"][0]["title"] == "Animals"


def test_pdf_extractor_uses_pymupdf_when_optional_engines_are_unavailable(
    tmp_path, monkeypatch
):
    fitz = pytest.importorskip("fitz")
    source = tmp_path / "chapter.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 80), "Plants Around Us", fontsize=20)
    page.insert_text((72, 120), "Plants need sunlight and water.", fontsize=12)
    document.save(source)
    document.close()

    extractor = HybridPDFExtractor()

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("optional extractor unavailable")

    monkeypatch.setattr(extractor, "_run_opendataloader", unavailable)
    monkeypatch.setattr(extractor, "_run_marker", unavailable)

    result = extractor.execute({
        "pdf_path": str(source),
        "subject_type": "theory",
        "output_dir": str(tmp_path / "artifacts"),
    })

    assert result.success is True, result.error
    assert result.data["extraction_tool_used"] == "pymupdf_layout_fallback"
    assert "<!-- page: 1 -->" in result.data["markdown"]
    assert "Plants Around Us" in result.data["markdown"]
    assert "Plants need sunlight and water." in result.data["markdown"]
    artifact = result.data["structured_json"]
    assert artifact["pages_extracted"] == 1
    assert artifact["layout_pages"][0]["blocks"]


def test_narration_manifest_accepts_authoritative_timeline_fields():
    validate_artifact("narration_manifest", {
        "version": "1.0",
        "engine_used": "test",
        "voice_name": "teacher",
        "segments": [{
            "section_id": "s1",
            "text": "Animals move.",
            "audio_path": "audio/s1.wav",
            "duration_seconds": 2.0,
            "start_seconds": 3.0,
            "end_seconds": 5.0,
            "timeline_source": "measured_narration",
        }],
        "total_duration_seconds": 2.0,
    })


def test_dynamic_chapter_config_resolves_relative_source(tmp_path):
    source = tmp_path / "chapter.md"
    source.write_text("# Plants\nPlants need water.", encoding="utf-8")
    config = {
        "project_id": "science-1",
        "subject": "science",
        "subject_label": "Science",
        "chapter": 1,
        "title": "Plants",
        "subject_type": "theory",
        "grade": 2,
        "age_range": "6-8",
        "duration_seconds": 300,
        "source_markdown": "chapter.md",
        "content_policy": {
            "allow_invented_labels": False,
            "max_content_lines_per_screen": 3,
        },
        "render_policy": {"runtime": "hyperframes"},
    }
    path = tmp_path / "chapter_config.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    loaded = load_chapter_config(path)
    assert loaded["source_markdown"] == str(source.resolve())
    assert loaded["render_policy"]["ui_template_id"] == "hyperframes-educational-v1"
    assert loaded["render_policy"]["ui_template_version"] == "1.0.3"
    assert loaded["render_policy"]["ui_template_sha256"] == LOCKED_UI_TEMPLATE_SHA256
    assert (
        loaded["render_policy"]["ui_template_package_sha256"]
        == LOCKED_UI_TEMPLATE_PACKAGE_SHA256
    )
    assert loaded["render_policy"]["template_lock"] == "strict"
    assert loaded["render_policy"]["book_presentation_id"] == "source-faithful-book-v1"
    assert registry_view(loaded)["audience"] == "Class 2, ages 6-8"


def test_grade_delivery_is_carried_into_dynamic_plan_metadata():
    plan = build_source_grounded_plan(
        [{
            "block_id": "p1-b1",
            "block_type": "paragraph",
            "semantic_role": "lesson_content",
            "source_text": "A fraction shows an equal part of a whole.",
        }],
        subject="mathematics",
        subject_type="mathematics",
        complexity_level="middle_school",
        target_audience="Class 6, ages 10-12",
        delivery_profile={
            "wpm_min": 125,
            "wpm_max": 155,
            "sentence_words_target": 20,
            "subtitle_words_max": 11,
            "subtitle_lines_max": 2,
        },
    )

    assert plan["target_audience"] == "Class 6, ages 10-12"
    assert plan["metadata"]["narration_wpm_target"] == 140
    assert plan["metadata"]["grade_delivery"]["sentence_words_target"] == 20
    assert plan["metadata"]["grade_delivery"]["subtitle_words_max"] == 11


def test_orchestrator_never_trims_source_narration_to_fit_provisional_duration():
    source_text = (
        "This complete textbook sentence must remain exactly present, even when "
        "the provisional duration is much too short for clear narration."
    )
    plan = {
        "sections": [{
            "section_id": "s1",
            "title": "Source fidelity",
            "description": source_text,
            "narration_script": source_text,
            "duration_seconds": 3,
            "render_mode": "video_gen",
        }],
    }

    result = EduStreamOrchestrator().execute({
        "educational_plan": plan,
        "subject": "science",
        "delivery_profile": {
            "wpm_min": 105,
            "wpm_max": 125,
            "sentence_words_target": 12,
        },
        "dry_run": True,
    })

    assert result.success is True
    section = result.data["evs_script"]["P"][0]
    assert section["narration_script"] == source_text
    assert section["narration_source_preserved"] is True
    assert section["duration_seconds"] > 3


def test_manim_dry_run_creates_declared_clip_and_contains_source_values(tmp_path):
    result = ManimGenerator().execute({
        "section": {
            "section_id": "math-s1",
            "title": "Place Value",
            "description": "The number 64 has 6 tens and 4 ones.",
            "source_text": "The number 64 has 6 tens and 4 ones.",
            "source_document_block_type": "paragraph",
            "source_block_type": "worked_example",
            "duration_seconds": 8,
            "key_concepts": [],
            "equations": [],
        },
        "subject": "maths",
        "output_dir": str(tmp_path / "manim"),
        "dry_run": True,
    })

    assert result.success is True, result.error
    assert Path(result.data["video_path"]).is_file()
    assert "The number 64 has 6 tens and 4 ones." in result.data["manim_code"]
    assert "Scene_math_s1_Place_Value" in result.data["manim_code"]


def test_dynamic_chapter_config_rejects_unapproved_ui_template(tmp_path):
    source = tmp_path / "chapter.md"
    source.write_text("# Plants\nPlants need water.", encoding="utf-8")
    config = {
        "project_id": "science-1",
        "subject": "science",
        "subject_label": "Science",
        "chapter": 1,
        "title": "Plants",
        "subject_type": "theory",
        "grade": 2,
        "age_range": "6-8",
        "duration_seconds": 300,
        "source_markdown": "chapter.md",
        "content_policy": {
            "allow_invented_labels": False,
            "max_content_lines_per_screen": 3,
        },
        "render_policy": {
            "runtime": "hyperframes",
            "ui_template_id": "unapproved-redesign",
        },
    }
    path = tmp_path / "chapter_config.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(ValueError, match="ui_template_id"):
        load_chapter_config(path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("ui_template_version", "1.1.0", "ui_template_version"),
        ("ui_template_sha256", "0" * 64, "ui_template_sha256"),
        ("ui_template_package_sha256", "0" * 64, "ui_template_package_sha256"),
        ("template_lock", "advisory", "template_lock"),
        ("ui_template_contract_path", "styles/local-copy.yaml", "ui_template_contract_path"),
    ],
)
def test_dynamic_chapter_config_rejects_template_contract_overrides(
    tmp_path, field, value, message
):
    source = tmp_path / "chapter.md"
    source.write_text("# Plants\nPlants need water.", encoding="utf-8")
    config = {
        "project_id": "science-1",
        "subject": "science",
        "subject_label": "Science",
        "chapter": 1,
        "title": "Plants",
        "subject_type": "theory",
        "grade": 2,
        "age_range": "6-8",
        "duration_seconds": 300,
        "source_markdown": "chapter.md",
        "content_policy": {
            "allow_invented_labels": False,
            "max_content_lines_per_screen": 3,
        },
        "render_policy": {"runtime": "hyperframes", field: value},
    }
    path = tmp_path / "chapter_config.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_chapter_config(path)


def test_educational_manifest_pins_the_verified_template_contract():
    contract = locked_ui_template_contract()
    manifest = yaml.safe_load(
        (REPO_ROOT / "pipeline_defs" / "educational-video.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["template_contract"] == {
        **contract,
        "override_policy": "content-slots-only",
    }
