"""Audio quality assurance checks."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class AudioQA:
    """Audio QA checks for generated narration."""

    def check_duration(self, audio_path: Path, expected_duration: float, tolerance: float = 0.5) -> bool:
        """Check that audio duration matches expected within tolerance."""
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(audio_path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            actual = float(result.stdout.strip())
            return abs(actual - expected_duration) <= tolerance
        except Exception:
            return False

    def check_silence(self, audio_path: Path, threshold: float = -50.0) -> bool:
        """Check for excessive silence in audio."""
        try:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-i", str(audio_path),
                    "-af", "silencedetect=noise=-50dB:d=0.5",
                    "-f", "null",
                    "-",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return "silence_start" not in result.stderr
        except Exception:
            return False

    def run_checks(self, audio_dir: Path) -> Dict[str, Any]:
        """Run all audio QA checks."""
        report = {
            "total_audio": 0,
            "duration_mismatch": [],
            "silence_issues": [],
            "passes": True,
        }

        for audio_path in audio_dir.rglob("*.wav"):
            report["total_audio"] += 1
            if not self.check_duration(audio_path, 0.0):
                report["duration_mismatch"].append(str(audio_path))
                report["passes"] = False

        return report
