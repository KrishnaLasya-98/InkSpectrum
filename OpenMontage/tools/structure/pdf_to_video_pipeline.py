"""One-command educational PDF to final video pipeline.

This is a thin ingestion adapter around OpenMontage's existing educational
pipeline. It creates canonical project/config artifacts, then delegates the
actual production stages to SubjectPipelineRunner.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from lib.checkpoint import init_project
from tools.extract.hybrid_pdf_extractor import HybridPDFExtractor
from tools.structure.subject_pipeline_runner import SubjectPipelineRunner


ROOT = Path(__file__).resolve().parents[2]


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value[:80] or "educational-chapter"


def infer_metadata(pdf: Path, markdown: str, overrides: dict[str, Any]) -> dict[str, Any]:
    first_heading = re.search(r"^#{1,6}\s+(.+)$", markdown, re.MULTILINE)
    lesson = re.search(r"(?:lesson|chapter)\s*[:.-]?\s*(\d+)\s*([^\n]*)", markdown, re.I)
    class_match = re.search(r"class\s*[-:]?\s*(\d+)", f"{pdf.stem}\n{markdown[:1500]}", re.I)
    equation_count = len(re.findall(r"\$[^$]+\$|\b(?:add|subtract|multiply|divide|number)\b", markdown, re.I))

    title = overrides.get("title")
    if not title:
        if lesson and lesson.group(2).strip():
            title = lesson.group(2).strip(" :-")
        elif first_heading:
            title = first_heading.group(1).strip()
        else:
            title = pdf.stem

    grade = int(overrides.get("grade") or (class_match.group(1) if class_match else 1))
    chapter = int(overrides.get("chapter") or (lesson.group(1) if lesson else 1))
    subject_type = overrides.get("subject_type") or ("mathematics" if equation_count >= 5 else "theory")
    subject = overrides.get("subject") or ("maths" if subject_type == "mathematics" else "general")
    age_low = max(4, grade + 4)

    return {
        "title": title,
        "grade": grade,
        "chapter": chapter,
        "subject": subject,
        "subject_label": overrides.get("subject_label") or subject.replace("-", " ").title(),
        "subject_type": subject_type,
        "age_range": f"{age_low}-{age_low + 2}",
    }


def build_config(pdf: Path, project_dir: Path, markdown_path: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    grade = metadata["grade"]
    if grade <= 2:
        delivery = {"wpm_min": 105, "wpm_max": 125, "subtitle_words_max": 7, "sentence_words_target": 12}
    elif grade <= 5:
        delivery = {"wpm_min": 115, "wpm_max": 140, "subtitle_words_max": 9, "sentence_words_target": 16}
    else:
        delivery = {"wpm_min": 125, "wpm_max": 155, "subtitle_words_max": 11, "sentence_words_target": 20}

    return {
        "version": "1.0",
        "project_id": project_dir.name,
        "subject": metadata["subject"],
        "subject_label": metadata["subject_label"],
        "chapter": metadata["chapter"],
        "title": metadata["title"],
        "subject_type": metadata["subject_type"],
        "complexity": "elementary" if grade <= 5 else "secondary",
        "grade": grade,
        "age_range": metadata["age_range"],
        "duration_seconds": 480,
        "source_pdf": str(pdf.resolve()),
        "source_markdown": str(markdown_path.resolve()),
        "pipeline": "educational-video",
        "approval_policy": "full-run-preauthorized",
        "content_policy": {
            "source_fidelity": "complete-topic-coverage",
            "allow_teacher_bridges": True,
            "allow_invented_labels": False,
            "allowed_overlay_types": [
                "chapter_title", "source_section_heading", "narration_subtitle",
                "assessment_prompt", "answer_reveal",
            ],
            "max_content_lines_per_screen": 3,
            "remove_redundant_text": True,
            "display_only_labels_are_not_spoken": True,
        },
        "grade_delivery": {
            **delivery,
            "subtitle_lines_max": 2,
            "explanation_style": "clear, concrete, age-appropriate, and question-led",
        },
        "providers": {
            "script": "modelslab",
            "audio": "modelslab",
            "video_primary": "agnes",
            "video_fallback": "modelslab",
        },
        "render_policy": {
            "runtime": "hyperframes",
            "ui_template_id": "hyperframes-educational-v1",
            "book_presentation_id": "source-faithful-book-v1",
            "template_lock": "strict",
            "composition_mode": "atelier",
            "visual_media": "animated-video-only",
            "embedded_media_text": False,
            "subtitle_timing": "word-aligned",
            "sync_authority": "measured-narration",
            "reject_linear_subtitle_alignment": True,
            "shared_timing_map": ["audio", "word_subtitles", "visual_cues", "teaching_ui"],
            "required_opening_cards": ["we_learn", "lesson_highlights"],
            "teaching_ui_style": {
                "badge": "cream-top-left",
                "content_card": "cream-top-right",
                "subtitle_lane": "cream-bottom-word-highlight",
                "background": "full-frame-animated-video",
                "assessment_mode": "source-faithful-stable-reading-screen",
            },
        },
    }


def run_pdf_to_video(inputs: dict[str, Any]) -> dict[str, Any]:
    pdf = Path(inputs["pdf_path"]).resolve()
    if not pdf.is_file() or pdf.suffix.lower() != ".pdf":
        raise ValueError(f"PDF not found: {pdf}")

    provisional_id = inputs.get("project_id") or slugify(pdf.stem)
    project_dir = init_project(
        provisional_id,
        title=inputs.get("title") or pdf.stem,
        pipeline_type="educational-video",
        style_playbook="clean-professional",
    )
    artifacts = project_dir / "artifacts"
    extraction = HybridPDFExtractor().execute({
        "pdf_path": str(pdf),
        "subject_type": inputs.get("subject_type", "mixed"),
        "output_dir": str(artifacts),
    })
    if not extraction.success:
        raise RuntimeError(f"PDF extraction failed: {extraction.error}")

    markdown_path = Path(extraction.data["markdown_path"])
    metadata = infer_metadata(pdf, extraction.data["markdown"], inputs)
    config = build_config(pdf, project_dir, markdown_path, metadata)
    config_path = project_dir / "chapter_config.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    result = SubjectPipelineRunner().execute({
        "subject": metadata["subject"],
        "chapter_config_path": str(config_path),
        "output_dir": str(project_dir),
        "quality": inputs.get("quality", "standard"),
        "dry_run": bool(inputs.get("dry_run", False)),
    })
    if not result.success:
        raise RuntimeError(result.error)
    return {
        "project_id": provisional_id,
        "chapter_config": str(config_path),
        "extracted_content": str(markdown_path),
        "final_video": result.data["final_video"],
        "stages_summary": result.data["stages_summary"],
        "cost_usd": result.data["cost_usd"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert an educational PDF into a complete video.")
    parser.add_argument("pdf")
    parser.add_argument("--project-id")
    parser.add_argument("--subject")
    parser.add_argument("--subject-label")
    parser.add_argument("--subject-type", choices=["theory", "mathematics", "mixed"])
    parser.add_argument("--grade", type=int)
    parser.add_argument("--chapter", type=int)
    parser.add_argument("--title")
    parser.add_argument("--quality", default="standard")
    parser.add_argument("--dry-run", action="store_true")
    args = vars(parser.parse_args())
    args["pdf_path"] = args.pop("pdf")
    try:
        print(json.dumps(run_pdf_to_video(args), indent=2))
    except Exception as exc:
        print(f"PDF-to-video failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
