#!/usr/bin/env python3
"""Run a textbook PDF through the full pipeline: extract → script.

Usage:
    python run_english_pipeline.py --project english_pipeline_output --pdf "path/to/book.pdf"
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from textbook_pipeline.core.ingestion.opendataloader_extractor import OpenDataLoaderExtractor
from textbook_pipeline.core.script.writer import ScriptWriter
from textbook_pipeline.models.chapter import Subject

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[3]


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Run textbook PDF through pipeline")
    parser.add_argument("--project", default="english_pipeline_output",
                        help="Project directory name under packages/textbook-pipeline/projects/")
    parser.add_argument("--pdf", required=True, help="Path to source PDF")
    parser.add_argument("--subject", default="english", choices=["english", "math", "science", "social"],
                        help="Subject type")
    parser.add_argument("--grade", type=int, default=1, help="Grade level")
    parser.add_argument("--textbook-id", required=True, help="Textbook identifier")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        logger.error(f"PDF not found: {pdf_path}")
        return 1

    output_dir = REPO_ROOT / f"packages/textbook-pipeline/projects/{args.project}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Extract ChapterNode from PDF
    logger.info("Extracting ChapterNode from PDF...")
    extractor = OpenDataLoaderExtractor()
    chapter = extractor.extract(
        pdf_path=pdf_path,
        subject=Subject(args.subject),
        grade=args.grade,
        textbook_id=args.textbook_id,
    )

    logger.info(
        "Chapter extracted: %s (%d sections, pages %d-%d)",
        chapter.title,
        len(chapter.sections),
        chapter.page_range[0],
        chapter.page_range[1],
    )

    chapter_json = output_dir / "chapter.json"
    chapter_json.write_text(chapter.model_dump_json(indent=2), encoding="utf-8")
    logger.info("Chapter saved to %s", chapter_json)

    # 2. Generate scripts via AI-driven templates (no LLM API required)
    logger.info("Generating scripts with ScriptWriter...")
    writer = ScriptWriter()
    scenes = writer.generate_chapter_script(chapter)

    logger.info("Generated %d script scenes", len(scenes))

    scenes_json = output_dir / "script_scenes.json"
    scenes_payload = []
    for scene in scenes:
        d = scene.model_dump(mode="json")
        if isinstance(d, list):
            for s in d:
                scenes_payload.append(s)
        else:
            scenes_payload.append(d)
    scenes_json.write_text(json.dumps(scenes_payload, indent=2), encoding="utf-8")
    logger.info("Script scenes saved to %s", scenes_json)

    # 3. Print a short summary
    for i, scene in enumerate(scenes[:3], 1):
        print(f"\n--- Scene {i}: {scene.title} ---")
        print(f"  Duration: {scene.duration_seconds}s")
        print(f"  Voiceover lines: {len(scene.voiceover_lines)}")
        print(f"  Scene steps: {len(scene.scene_steps)}")
        for step in scene.scene_steps[:2]:
            print(f"    - {step.type.value}: {step.text or step.latex or ''}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
