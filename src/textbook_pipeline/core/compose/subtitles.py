"""Subtitle generation and burn-in."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class SubtitleGenerator:
    """Generates and burns subtitles into video."""

    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.ffmpeg_path = ffmpeg_path

    def generate_srt(
        self,
        segments: List[dict],
        output_path: Path,
    ) -> Path:
        """Generate SRT file from timed segments."""
        lines = []
        for i, seg in enumerate(segments, start=1):
            start = self._seconds_to_srt_time(seg.get("start", 0))
            end = self._seconds_to_srt_time(seg.get("end", 0))
            text = seg.get("text", "").strip()

            lines.append(f"{i}")
            lines.append(f"{start} --> {end}")
            lines.append(text)
            lines.append("")

        output_path.write_text("\n".join(lines), encoding="utf-8")
        return output_path

    def burn_subtitles(
        self,
        video_path: Path,
        srt_path: Path,
        output_path: Path,
        font_size: int = 24,
        font_color: str = "white",
        stroke_color: str = "black",
    ) -> Path:
        """Burn subtitles into video using FFmpeg."""
        srt_path_resolved = srt_path.resolve().as_posix()
        cmd = [
            self.ffmpeg_path,
            "-i", str(video_path.resolve()),
            "-vf", (
                f"subtitles={srt_path_resolved}:"
                f"force_style='FontSize={font_size},"
                f"PrimaryColour=&H{self._color_to_ass(font_color)},"
                f"OutlineColour=&H{self._color_to_ass(stroke_color)},"
                f"Outline=1,Shadow=0,MarginV=30'"
            ),
            "-c:a", "copy",
            "-y",
            str(output_path.resolve()),
        ]

        subprocess.run(cmd, capture_output=True, text=True, check=True)
        return output_path

    def _seconds_to_srt_time(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _color_to_ass(self, color: str) -> str:
        color = color.lstrip("#")
        r, g, b = color[0:2], color[2:4], color[4:6]
        return f"{b}{g}{r}"
