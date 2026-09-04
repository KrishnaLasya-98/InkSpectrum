"""Visual quality assurance checks."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class VisualQA:
    """Visual QA checks for generated assets."""

    def check_asset_exists(self, asset_path: Path) -> bool:
        """Check that an asset file exists and is non-empty."""
        if not asset_path.exists():
            return False
        return asset_path.stat().st_size > 0

    def check_resolution(self, asset_path: Path, expected_width: int, expected_height: int) -> bool:
        """Check asset resolution using ffprobe."""
        import subprocess
        import json

        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=width,height",
                    "-of", "json",
                    str(asset_path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            info = json.loads(result.stdout)
            stream = info["streams"][0]
            return stream["width"] == expected_width and stream["height"] == expected_height
        except Exception:
            return False

    def run_checks(self, asset_dir: Path, expected_resolution: tuple[int, int] = (1920, 1080)) -> Dict[str, Any]:
        """Run all visual QA checks."""
        report = {
            "total_assets": 0,
            "missing": [],
            "wrong_resolution": [],
            "passes": True,
        }

        for ext in ("*.png", "*.jpg", "*.jpeg", "*.mp4"):
            for asset_path in asset_dir.rglob(ext):
                report["total_assets"] += 1
                if not self.check_asset_exists(asset_path):
                    report["missing"].append(str(asset_path))
                    report["passes"] = False
                elif asset_path.suffix.lower() == ".mp4":
                    if not self.check_resolution(asset_path, *expected_resolution):
                        report["wrong_resolution"].append(str(asset_path))
                        report["passes"] = False

        return report
