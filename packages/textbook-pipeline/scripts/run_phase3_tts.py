#!/usr/bin/env python3
"""Run Phase 3: TTS Audio Generation from Phase 2 script scenes.

Supports two TTS providers:
- modelslab: ModelsLab cloud TTS (high quality, requires API key)
- edge: Edge TTS (free, no key required, word-level timestamps)

Usage:
    python run_phase3_tts.py                          # ModelsLab (default)
    python run_phase3_tts.py --provider edge           # Edge TTS fallback
    python run_phase3_tts.py --model qwen-voice-design # ModelsLab voice design
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")

from textbook_pipeline.utils.logger import PipelineLogger, LoggingConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_project_paths(project_name: str) -> tuple[Path, Path]:
    project_dir = REPO_ROOT / f"packages/textbook-pipeline/projects/{project_name}"
    script_json = project_dir / "phase2_script_scenes.json"
    audio_dir = project_dir / "audio"
    return script_json, audio_dir


def get_logging_config(project_name: str) -> LoggingConfig:
    project_dir = REPO_ROOT / f"packages/textbook-pipeline/projects/{project_name}"
    return LoggingConfig(output_dir=project_dir / "logs")


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3: TTS Audio Generation")
    parser.add_argument("--provider", choices=["modelslab", "edge"], default="modelslab",
                        help="TTS provider (default: modelslab)")
    parser.add_argument("--model", default="text-to-speech",
                        help="ModelsLab model_id (default: text-to-speech)")
    parser.add_argument("--voice", default="nova",
                        help="ModelsLab voice_id or Edge TTS voice name")
    parser.add_argument("--speed", type=float, default=0.9,
                        help="Speech speed (default: 0.9)")
    parser.add_argument("--project", default="english_pipeline_output",
                        help="Project directory name under packages/textbook-pipeline/projects/")
    args = parser.parse_args()

    script_json, audio_dir = get_project_paths(args.project)

    if not script_json.exists():
        logger.error("Script JSON not found: %s", script_json)
        return 1

    pipeline_logger = PipelineLogger(get_logging_config(args.project), project_name=f"{args.project}_phase3")
    pipeline_logger.stage_start("tts", f"Running Phase 3: TTS generation for {args.project} (provider={args.provider}, model={args.model})")
    
    from textbook_pipeline.core.generation.tts_generator import run_phase3

    pipeline_logger.info("Starting TTS generation", provider=args.provider, model=args.model, voice=args.voice)
    scenes_path, manifest_path = asyncio.run(run_phase3(
        script_json_path=script_json,
        output_audio_dir=audio_dir,
        provider=args.provider,
        voice=args.voice,
        modelslab_model=args.model,
        modelslab_voice_id=args.voice,
        modelslab_speed=args.speed,
    ))

    pipeline_logger.info("Phase 3 complete")
    pipeline_logger.info("Updated scenes", path=str(scenes_path))
    pipeline_logger.info("Audio manifest", path=str(manifest_path))

    # Print summary
    import json
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pipeline_logger.info("Generated audio files", count=manifest["generated_files"], lines=manifest["total_lines"], scenes=manifest["total_scenes"])
    
    pipeline_logger.stage_end("tts", "TTS generation complete")
    pipeline_logger.close_all_progress()

    return 0


if __name__ == "__main__":
    sys.exit(main())
