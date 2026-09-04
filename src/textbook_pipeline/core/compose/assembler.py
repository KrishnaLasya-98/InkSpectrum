"""FFmpeg-based scene compositor."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class Compositor:
    """Assembles final video from scene clips."""

    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.ffmpeg_path = ffmpeg_path
        self._validate_ffmpeg()

    def _validate_ffmpeg(self) -> None:
        try:
            subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("ffmpeg not found. Install ffmpeg and ensure it's in PATH.")

    def concat(
        self,
        clips: List[Path],
        output: Path,
        transition: str = "cut",
        transition_duration: float = 0.3,
    ) -> Path:
        """Concatenate video clips with optional transitions."""
        if len(clips) == 1:
            clips[0].rename(output)
            return output

        concat_file = output.parent / "concat_list.txt"
        with open(concat_file, "w") as f:
            for clip in clips:
                f.write(f"file '{clip.resolve()}'\n")

        cmd = [
            self.ffmpeg_path,
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file.resolve()),
            "-c", "copy",
            "-y",
            str(output.resolve()),
        ]

        subprocess.run(cmd, capture_output=True, text=True, check=True)
        return output
