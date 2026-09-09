#!/usr/bin/env python3
"""Run Phase 2 tools end-to-end: script writer → scene planner."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

# Ensure repo root is on sys.path so `lib/` and `tools/` are importable
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

load_dotenv(REPO_ROOT / ".env")

from lib.tool_registry import get_tool
from tools.script.llm_script_writer import LLMScriptWriterTool
from tools.script.scene_planner import ScenePlannerTool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHAPTER_PATH = Path("packages/textbook-pipeline/projects/english_pipeline_output/chapter.json")
SCRIPT_OUTPUT = Path("packages/textbook-pipeline/projects/english_pipeline_output/phase2_script_scenes.json")
SCENE_PLAN_OUTPUT = Path("packages/textbook-pipeline/projects/english_pipeline_output/phase2_scene_plan.json")
CHECKPOINT = Path("packages/textbook-pipeline/projects/english_pipeline_output/phase2_checkpoint.json")


def main() -> int:
    if not CHAPTER_PATH.exists():
        logger.error("Chapter JSON not found: %s", CHAPTER_PATH)
        return 1

    chapter_text = CHAPTER_PATH.read_text(encoding="utf-8")

    # 1. Run script writer with chunking to avoid rate limits
    logger.info("Running groq_llm_script_writer (chunked)...")
    script_tool = get_tool("groq_llm_script_writer")
    script_result = script_tool.run({
        "chapter_json": chapter_text,
        "output_json": str(SCRIPT_OUTPUT),
        "chunk_size": 3,           # 3 sections per batch
        "delay_seconds": 5.0,      # 5s pause between batches
        "checkpoint_path": str(CHECKPOINT),
    })
    logger.info("Script writer result: %d scenes", script_result.get("scene_count", 0))

    # 2. Run scene planner on the script output
    logger.info("Running scene_planner...")
    planner_tool = get_tool("scene_planner")
    plan_result = planner_tool.run({
        "scenes_json": json.dumps(script_result.get("scenes", [])),
        "output_json": str(SCENE_PLAN_OUTPUT),
    })
    logger.info("Scene planner result: %d scenes planned", plan_result.get("scene_count", 0))

    # 3. Print summary
    print("\n=== Phase 2 Results ===")
    print(f"Script scenes: {script_result.get('scene_count', 0)}")
    print(f"Scene plan scenes: {plan_result.get('scene_count', 0)}")
    print(f"Script output: {SCRIPT_OUTPUT}")
    print(f"Scene plan output: {SCENE_PLAN_OUTPUT}")

    if script_result.get("scene_count", 0) > 0:
        first_scene = script_result["scenes"][0]
        print(f"\nFirst scene: {first_scene.get('title', 'untitled')}")
        print(f"  Voiceover lines: {len(first_scene.get('voiceover_lines', []))}")
        print(f"  Scene steps: {len(first_scene.get('scene_steps', []))}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
