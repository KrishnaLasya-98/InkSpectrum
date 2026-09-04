"""Audio mixing: narration + BGM + SFX."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class AudioMixer:
    """Mixes narration, background music, and sound effects."""

    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.ffmpeg_path = ffmpeg_path

    def mix(
        self,
        narration: Path,
        bgm: Optional[Path] = None,
        sfx: Optional[List[Path]] = None,
        bgm_volume: float = 0.2,
        sfx_volume: float = 0.3,
        output: Optional[Path] = None,
    ) -> Path:
        """Mix narration with optional BGM and SFX."""
        if output is None:
            output = narration.parent / "mixed_audio.wav"

        inputs = ["-i", str(narration.resolve())]
        filter_parts = ["[0:a]volume=1.0[base]"]
        next_index = 1

        if bgm and bgm.exists():
            inputs.extend(["-i", str(bgm.resolve())])
            filter_parts.append(
                f"[{next_index}:a]volume={bgm_volume}[bgm]"
            )
            next_index += 1

        cmd = [
            self.ffmpeg_path,
            *inputs,
            "-filter_complex", ";".join(filter_parts),
            "-map", "[base]",
            "-y",
            str(output.resolve()),
        ]

        subprocess.run(cmd, capture_output=True, text=True, check=True)
        return output
