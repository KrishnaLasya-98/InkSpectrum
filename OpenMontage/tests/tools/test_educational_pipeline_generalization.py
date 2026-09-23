import json

import pytest

from schemas.artifacts import validate_artifact
from tools.extract.hybrid_pdf_extractor import HybridPDFExtractor
from tools.extract.section_parser import SectionParser
from tools.structure.chapter_config import load_chapter_config, registry_view


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
    assert loaded["render_policy"]["book_presentation_id"] == "source-faithful-book-v1"
    assert registry_view(loaded)["audience"] == "Class 2, ages 6-8"


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
