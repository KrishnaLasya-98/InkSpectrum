"""Agnes Video Integration Wrapper for Phase 4.

Bridges textbook pipeline script scenes with Agnes Video Generator API
for automated image-to-video / text-to-video rendering using Agnes endpoints.
"""

from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Try importing Agnes API from sibling repo agnes-video-generator
try:
    from core.api.agnes_image import AgnesImageAPI
    from core.api.agnes_video import AgnesVideoAPI
    HAS_AGNES = True
except ImportError:
    HAS_AGNES = False
    logger.warning("agnes-video-generator not found in sys.path. Agnes wrapper will operate in mock mode.")


class AgnesPipelineClient:
    """Client for generating story visuals and scene videos using Agnes API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("AGNES_API_KEY")
        if not self.api_key:
            logger.warning("AGNES_API_KEY not found in environment.")

        if HAS_AGNES and self.api_key:
            self.image_api = AgnesImageAPI(api_key=self.api_key)
            self.video_api = AgnesVideoAPI(api_key=self.api_key)
        else:
            self.image_api = None
            self.video_api = None

    def generate_scene_image(self, prompt: str, output_path: Path) -> bool:
        """Generate a story background image using Agnes image model."""
        if not self.image_api:
            logger.info(f"[Mock] Generating image for prompt: {prompt}")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"MOCK_IMAGE_BYTES")
            return True

        try:
            logger.info(f"Generating Agnes image for: {prompt}")
            # Agnes image generation call
            result = self.image_api.generate(prompt=prompt, model="agnes-image-2.1-flash")
            if result and hasattr(result, "save"):
                result.save(output_path)
                return True
            return False
        except Exception as e:
            logger.error(f"Agnes image generation failed: {e}")
            return False

    def generate_scene_video(self, image_path: Path, output_video_path: Path) -> bool:
        """Animate an image into a video background using Agnes video model."""
        if not self.video_api:
            logger.info(f"[Mock] Animating video from image: {image_path}")
            output_video_path.parent.mkdir(parents=True, exist_ok=True)
            output_video_path.write_bytes(b"MOCK_VIDEO_BYTES")
            return True

        try:
            logger.info(f"Generating Agnes video from image: {image_path}")
            result = self.video_api.animate(image_path=str(image_path), model="agnes-video-v2.0")
            if result and hasattr(result, "save"):
                result.save(output_video_path)
                return True
            return False
        except Exception as e:
            logger.error(f"Agnes video generation failed: {e}")
            return False
