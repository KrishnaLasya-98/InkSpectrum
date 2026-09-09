"""Remotion-based video renderer for InkSpectrum.

Provides programmatic video creation using Remotion (React-based).
Each ScriptScene is rendered as a Remotion composition with:
- Deterministic scene steps (title, text, word_highlight, etc.)
- AI-generated or Pillow-generated assets
- Synchronized TTS audio
- Motion-only animations (no camera zoom)
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Remotion project root
REMOTION_ROOT = Path(__file__).resolve().parents[3] / "remotion_renderer"
DEFAULT_COMPOSITION = "SceneComposition"


class RemotionRenderer:
    """Renders video using Remotion via subprocess CLI."""

    def __init__(
        self,
        remotion_root: Path = REMOTION_ROOT,
        composition: str = DEFAULT_COMPOSITION,
        output_dir: Optional[Path] = None,
    ):
        self.remotion_root = Path(remotion_root)
        self.composition = composition
        self.output_dir = Path(output_dir) if output_dir else self.remotion_root / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Verify Remotion is available
        self._verify_remotion()

    def _verify_remotion(self) -> None:
        """Check if Remotion CLI is available."""
        try:
            subprocess.run(
                ["npx", "remotion", "--version"],
                capture_output=True,
                check=True,
                timeout=30,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("Remotion CLI not found. Install with: npm install -g @remotion/cli")
            raise RuntimeError("Remotion CLI not available")

    def render_scene(
        self,
        scene: Dict[str, Any],
        output_path: Path,
        audio_path: Optional[Path] = None,
        asset_paths: Optional[Dict[str, str]] = None,
    ) -> Path:
        """Render a single scene using Remotion.

        Args:
            scene: ScriptScene dict
            output_path: Where to save the rendered MP4
            audio_path: Optional audio file to sync
            asset_paths: Optional dict of asset type → file path

        Returns:
            Path to rendered video
        """
        # Prepare props for Remotion composition
        props = {
            "scene": scene,
            "audioPath": str(audio_path) if audio_path else None,
            "assets": asset_paths or {},
            "width": 1280,
            "height": 720,
            "fps": 24,
        }

        # Write props to temp file
        import tempfile
        props_file = Path(tempfile.mktemp(suffix=".json"))
        props_file.write_text(json.dumps(props), encoding="utf-8")

        try:
            cmd = [
                "npx", "remotion", "render",
                str(self.remotion_root / "src/index.ts"),
                "--composition", self.composition,
                "--props", str(props_file),
                "--output", str(output_path),
                "--codec", "h264",
                "--quality", "90",
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(self.remotion_root),
            )

            if result.returncode != 0:
                logger.error("Remotion render failed: %s", result.stderr)
                raise RuntimeError(f"Remotion render failed: {result.stderr}")

            logger.info("Rendered scene %s -> %s", scene.get("id"), output_path)
            return output_path

        finally:
            # Cleanup temp props file
            if props_file.exists():
                props_file.unlink()

    def render_chapter(
        self,
        scenes_json_path: Path,
        audio_dir: Path,
        output_video_path: Path,
        temp_dir: Optional[Path] = None,
    ) -> Path:
        """Render all scenes into a final chapter video using Remotion.

        Args:
            scenes_json_path: Path to phase2_script_scenes_with_audio.json
            audio_dir: Directory containing generated audio files
            output_video_path: Final MP4 output path
            temp_dir: Temporary directory for intermediate files

        Returns:
            Path to the final video file
        """
        scenes = json.loads(scenes_json_path.read_text(encoding="utf-8"))
        logger.info("Rendering %d scenes with Remotion -> %s", len(scenes), output_video_path)

        temp_dir = temp_dir or Path(tempfile.mkdtemp(prefix="ink_remotion_"))
        temp_dir.mkdir(parents=True, exist_ok=True)

        output_video_path.parent.mkdir(parents=True, exist_ok=True)
        segments: List[Path] = []

        for idx, scene in enumerate(scenes):
            scene_id = scene.get("id", f"scene_{idx}")
            segment_path = temp_dir / f"{scene_id}_segment.mp4"

            # Collect audio files for this scene
            audio_files: List[Path] = []
            for vo in scene.get("voiceover_lines", []):
                ap = vo.get("audio_path")
                if ap:
                    p = Path(ap)
                    if p.exists():
                        audio_files.append(p)
                    else:
                        candidate = audio_dir / p.name
                        if candidate.exists():
                            audio_files.append(candidate)

            if not audio_files:
                logger.warning("No audio for scene %s; creating silent placeholder", scene_id)
                silent = temp_dir / f"{scene_id}_silent.mp3"
                subprocess.run(
                    ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                     "-t", "3", str(silent)],
                    capture_output=True, timeout=10,
                )
                audio_files = [silent]

            # Get asset paths if available
            assets = scene.get("generated_assets", {})

            logger.info("Rendering scene %d/%d: %s (%d audio files)", idx + 1, len(scenes), scene_id, len(audio_files))
            try:
                self.render_scene(scene, segment_path, audio_files[0], assets)
                if segment_path.exists():
                    segments.append(segment_path)
            except Exception as exc:
                logger.error("Failed to render scene %s: %s", scene_id, exc)
                continue

        if not segments:
            raise RuntimeError("No video segments were created")

        # Concatenate all segments using FFmpeg
        logger.info("Concatenating %d segments...", len(segments))
        self._concat_segments(segments, output_video_path)
        logger.info("Final video: %s (%d bytes)", output_video_path, output_video_path.stat().st_size)

        return output_video_path

    def _concat_segments(self, video_files: List[Path], output_path: Path) -> None:
        """Concatenate video segments using FFmpeg."""
        if len(video_files) == 1:
            video_files[0].rename(output_path)
            return

        concat_list = output_path.parent / "concat_list.txt"
        concat_list.write_text(
            "\n".join(f"file '{p.resolve()}'" for p in video_files),
            encoding="utf-8",
        )

        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_list),
                "-c", "copy",
                str(output_path),
            ],
            capture_output=True, timeout=300,
        )
