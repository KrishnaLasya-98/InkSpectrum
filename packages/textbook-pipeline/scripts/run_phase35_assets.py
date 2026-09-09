#!/usr/bin/env python3
"""Run Phase 3.5: Asset Generation (T2I + I2V) from Phase 2 script scenes."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCRIPT_JSON = REPO_ROOT / "packages/textbook-pipeline/projects/english_pipeline_output/phase2_script_scenes.json"
OUTPUT_DIR = REPO_ROOT / "packages/textbook-pipeline/projects/english_pipeline_output/assets"


def main() -> int:
    if not SCRIPT_JSON.exists():
        logger.error("Script JSON not found: %s", SCRIPT_JSON)
        return 1

    from textbook_pipeline.core.generation.asset_generator import run_phase35

    logger.info("Running Phase 3.5: Asset generation...")
    updated_path = run_phase35(SCRIPT_JSON, OUTPUT_DIR)
    logger.info("Phase 3.5 complete: %s", updated_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
