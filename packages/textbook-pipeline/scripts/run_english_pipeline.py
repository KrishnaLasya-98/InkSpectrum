#!/usr/bin/env python3
"""Run the English textbook PDF through the full pipeline: extract → script."""

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

ENGLISH_PDF = Path(
    r"C:\Users\user\Downloads\RPS - ENGLISH - CLASS 1 - INDIVIDUAL - A (2026) PRINTFILE (2)-pages-2.pdf"
)
ENGLISH_JSON = Path(
    r"C:\Users\user\Downloads\opendataloader_output\RPS - ENGLISH - CLASS 1 - INDIVIDUAL - A (2026) PRINTFILE (2)-pages-2.json"
)
OUTPUT_DIR = Path("packages/textbook-pipeline/projects/english_pipeline_output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main() -> int:
    if not ENGLISH_PDF.exists():
        logger.error(f"PDF not found: {ENGLISH_PDF}")
        return 1
    if not ENGLISH_JSON.exists():
        logger.error(f"OpenDataLoader JSON not found: {ENGLISH_JSON}")
        return 1

    # 1. Extract ChapterNode from OpenDataLoader JSON
    logger.info("Extracting ChapterNode from OpenDataLoader JSON...")
    extractor = OpenDataLoaderExtractor()
    chapter = extractor.extract(
        pdf_path=ENGLISH_PDF,
        subject=Subject.ENGLISH,
        grade=1,
        textbook_id="english_class1_at_the_beach",
    )

    logger.info(
        "Chapter extracted: %s (%d sections, pages %d-%d)",
        chapter.title,
        len(chapter.sections),
        chapter.page_range[0],
        chapter.page_range[1],
    )

    chapter_json = OUTPUT_DIR / "chapter.json"
    chapter_json.write_text(chapter.model_dump_json(indent=2), encoding="utf-8")
    logger.info("Chapter saved to %s", chapter_json)

    # 2. Generate scripts via LLM
    logger.info("Generating scripts with ScriptWriter...")
    writer = ScriptWriter()
    scenes = writer.generate_chapter_script(chapter)

    logger.info("Generated %d script scenes", len(scenes))

    scenes_json = OUTPUT_DIR / "script_scenes.json"
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
