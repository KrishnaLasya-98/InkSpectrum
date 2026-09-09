#!/usr/bin/env python3
"""Run Phase 4: Video Composition from Phase 2 script + Phase 3 audio.

Supports two rendering backends:
- remotion: Remotion (React-based, high quality)
- pillow: FFmpeg + Pillow (fast, no Node.js dependency)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")

from textbook_pipeline.utils.logger import PipelineLogger, LoggingConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OUTPUT_DIR = REPO_ROOT / "packages/textbook-pipeline/projects/english_pipeline_output"
SCENES_JSON = OUTPUT_DIR / "phase2_script_scenes_with_audio.json"
AUDIO_DIR = OUTPUT_DIR / "audio"
FINAL_VIDEO = OUTPUT_DIR / "chapter_video.mp4"


def get_project_paths(project_name: str) -> tuple[Path, Path, Path]:
    project_dir = REPO_ROOT / f"packages/textbook-pipeline/projects/{project_name}"
    scenes_json = project_dir / "phase2_script_scenes_with_audio.json"
    audio_dir = project_dir / "audio"
    final_video = project_dir / "chapter_video.mp4"
    return scenes_json, audio_dir, final_video


def get_logging_config(project_name: str) -> LoggingConfig:
    project_dir = REPO_ROOT / f"packages/textbook-pipeline/projects/{project_name}"
    return LoggingConfig(output_dir=project_dir / "logs")


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 4: Video Composition")
    parser.add_argument(
        "--backend",
        choices=["remotion", "pillow"],
        default="pillow",
        help="Rendering backend (default: pillow)",
    )
    parser.add_argument(
        "--remotion-root",
        type=Path,
        default=REPO_ROOT / "packages/textbook-pipeline/remotion_renderer",
        help="Remotion project root directory",
    )
    parser.add_argument("--project", default="english_pipeline_output",
                        help="Project directory name under packages/textbook-pipeline/projects/")
    args = parser.parse_args()

    scenes_json, audio_dir, final_video = get_project_paths(args.project)

    if not scenes_json.exists():
        logger.error("Scenes JSON not found: %s", scenes_json)
        logger.error("Run Phase 3 first to generate audio.")
        return 1

    pipeline_logger = PipelineLogger(get_logging_config(args.project), project_name=f"{args.project}_phase4")
    pipeline_logger.stage_start("render", f"Running Phase 4 render for {args.project}")
    
    if args.backend == "remotion":
        try:
            from textbook_pipeline.core.composition.remotion_renderer import RemotionRenderer

            pipeline_logger.info(f"Running Phase 4 with Remotion backend for {args.project}...")
            renderer = RemotionRenderer(
                remotion_root=args.remotion_root,
                output_dir=final_video.parent / "remotion_output",
            )
            renderer.render_chapter(scenes_json, audio_dir, final_video)
        except (ImportError, RuntimeError) as exc:
            logger.error("Remotion backend unavailable: %s", exc)
            logger.error("Falling back to Pillow backend.")
            _render_pillow(scenes_json, audio_dir, final_video, pipeline_logger)
        else:
            pipeline_logger.info("Remotion render completed successfully")
    else:
        pipeline_logger.info(f"Running Phase 4 with Pillow backend for {args.project}...")
        _render_pillow(scenes_json, audio_dir, final_video, pipeline_logger)
    
    pipeline_logger.stage_end("render", "Phase 4 complete")
    pipeline_logger.close_all_progress()
    logger.info("Phase 4 complete: %s", final_video)
    return 0


def _render_pillow(scenes_json: Path, audio_dir: Path, final_video: Path, pipeline_logger: Optional[PipelineLogger] = None) -> None:
    """Render using Pillow + FFmpeg backend."""
    from textbook_pipeline.core.composition.renderer import render_chapter

    log = pipeline_logger or logger
    log.info("Running Phase 4 with Pillow backend...")
    render_chapter(scenes_json, audio_dir, final_video)


if __name__ == "__main__":
    sys.exit(main())
