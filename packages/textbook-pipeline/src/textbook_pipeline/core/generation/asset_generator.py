"""Phase 3.5: Asset Generation Pipeline.

Generates visual assets for script scenes:
1. T2I (Text-to-Image): Generates start-frame images from image_prompt
2. I2V (Image-to-Video): Animates start frames into video clips from video_prompt

Uses ModelsLab as primary provider with fallback to placeholder assets.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Default models
DEFAULT_T2I_MODEL = "hidream-o1"
DEFAULT_I2V_MODEL = "h3-minimax-r2v"
DEFAULT_VOICE_ID = "nova"

# Asset output directories
ASSETS_DIR = Path("packages/textbook-pipeline/projects/english_pipeline_output/assets")
IMAGES_DIR = ASSETS_DIR / "images"
VIDEOS_DIR = ASSETS_DIR / "videos"


class AssetGenerator:
    """Generates T2I and I2V assets for script scenes."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        t2i_model: str = DEFAULT_T2I_MODEL,
        i2v_model: str = DEFAULT_I2V_MODEL,
        output_dir: Path = ASSETS_DIR,
    ):
        self.api_key = api_key or os.getenv("MODELSLAB_API_KEY", "")
        self.t2i_model = t2i_model
        self.i2v_model = i2v_model
        self.output_dir = Path(output_dir)
        self.images_dir = self.output_dir / "images"
        self.videos_dir = self.output_dir / "videos"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.videos_dir.mkdir(parents=True, exist_ok=True)

        if not self.api_key:
            logger.warning("MODELSLAB_API_KEY not set; asset generation will fail")

    async def generate_for_scenes(
        self, scenes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate assets for all scenes that have prompts.

        Args:
            scenes: List of ScriptScene dicts

        Returns:
            Updated scenes with generated_assets populated
        """
        updated = []
        for scene in scenes:
            scene_id = scene.get("id", "unknown")
            image_prompt = scene.get("image_prompt")
            video_prompt = scene.get("video_prompt")

            assets: Dict[str, str] = {}

            # Step 1: Generate T2I image if prompt exists
            if image_prompt:
                image_path = await self._generate_image(scene_id, image_prompt)
                if image_path:
                    assets["image"] = str(image_path)
                    scene["init_image_url"] = str(image_path)

            # Step 2: Generate I2V video if video_prompt exists and we have an image
            if video_prompt and "image" in assets:
                video_path = await self._generate_video(
                    scene_id, video_prompt, assets["image"]
                )
                if video_path:
                    assets["video"] = str(video_path)

            if assets:
                scene["generated_assets"] = assets
                logger.info("Scene %s: generated assets %s", scene_id, list(assets.keys()))

            updated.append(scene)

        return updated

    async def _generate_image(self, scene_id: str, prompt: str) -> Optional[Path]:
        """Generate a T2I image using ModelsLab."""
        output_path = self.images_dir / f"{scene_id}_start.png"

        # Check if already exists
        if output_path.exists():
            logger.info("Reusing existing image: %s", output_path)
            return output_path

        logger.info("Generating T2I image for %s...", scene_id)
        try:
            url = await self._call_t2i_api(prompt)
            if url:
                await self._download_file(url, output_path)
                return output_path
        except Exception as exc:
            logger.error("T2I generation failed for %s: %s", scene_id, exc)

        return None

    async def _generate_video(self, scene_id: str, prompt: str, init_image: str) -> Optional[Path]:
        """Generate an I2V video using ModelsLab h3-minimax-r2v."""
        output_path = self.videos_dir / f"{scene_id}_clip.mp4"

        # Check if already exists
        if output_path.exists():
            logger.info("Reusing existing video: %s", output_path)
            return output_path

        logger.info("Generating I2V video for %s...", scene_id)
        try:
            url = await self._call_i2v_api(prompt, init_image)
            if url:
                await self._download_file(url, output_path)
                return output_path
        except Exception as exc:
            logger.error("I2V generation failed for %s: %s", scene_id, exc)

        return None

    async def _call_t2i_api(self, prompt: str) -> Optional[str]:
        """Call ModelsLab T2I API and return image URL."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_t2i, prompt)

    def _sync_t2i(self, prompt: str) -> Optional[str]:
        """Synchronous T2I API call."""
        payload = {
            "key": self.api_key,
            "model_id": self.t2i_model,
            "prompt": prompt,
            "negative_prompt": "blurry, low quality, distorted, text, words, letters",
            "width": 1024,
            "height": 1024,
            "samples": 1,
            "guidance_scale": 7.5,
        }

        try:
            response = httpx.post(
                "https://modelslab.com/api/v7/images/text-to-image",
                json=payload,
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "success":
                return data["output"][0]
            if data.get("status") == "processing":
                return self._poll_image(data["id"])
        except Exception as exc:
            logger.error("T2I API call failed: %s", exc)

        return None

    async def _call_i2v_api(self, prompt: str, init_image: str) -> Optional[str]:
        """Call ModelsLab I2V API (h3-minimax-r2v) and return video URL."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_i2v, prompt, init_image)

    def _sync_i2v(self, prompt: str, init_image: str) -> Optional[str]:
        """Synchronous I2V API call using h3-minimax-r2v on v6 endpoint."""
        payload = {
            "key": self.api_key,
            "model_id": self.i2v_model,
            "prompt": prompt,
            "init_image": [init_image],
            "duration": "7",
            "resolution": "768P",
        }

        try:
            response = httpx.post(
                "https://modelslab.com/api/v6/video/img2video",
                json=payload,
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "success":
                return data["output"][0]
            if data.get("status") == "processing":
                return self._poll_video(data["id"])
        except Exception as exc:
            logger.error("I2V API call failed: %s", exc)

        return None

    def _poll_image(self, request_id: str, timeout: int = 300) -> Optional[str]:
        """Poll for T2I result."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                response = httpx.post(
                    f"https://modelslab.com/api/v7/images/fetch/{request_id}",
                    json={"key": self.api_key},
                    timeout=60.0,
                )
                response.raise_for_status()
                data = response.json()
                if data.get("status") == "success":
                    return data["output"][0]
                if data.get("status") == "failed":
                    logger.error("Image generation failed: %s", data.get("message"))
                    return None
            except Exception as exc:
                logger.error("Image poll failed: %s", exc)
            time.sleep(10)
        return None

    def _poll_video(self, request_id: str, timeout: int = 600) -> Optional[str]:
        """Poll for I2V result using v6 endpoint."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                response = httpx.post(
                    f"https://modelslab.com/api/v6/video/fetch/{request_id}",
                    json={"key": self.api_key},
                    timeout=60.0,
                )
                response.raise_for_status()
                data = response.json()
                if data.get("status") == "success":
                    return data["output"][0]
                if data.get("status") == "failed":
                    logger.error("Video generation failed: %s", data.get("message"))
                    return None
            except Exception as exc:
                logger.error("Video poll failed: %s", exc)
            time.sleep(10)
        return None

    async def _download_file(self, url: str, output_path: Path) -> None:
        """Download file from URL to output path."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._sync_download, url, output_path)

    def _sync_download(self, url: str, output_path: Path) -> None:
        """Synchronous file download."""
        response = httpx.get(url, follow_redirects=True, timeout=120.0)
        response.raise_for_status()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        logger.info("Downloaded %s -> %s (%d bytes)", url[:80], output_path, len(response.content))


async def run_phase35(
    scenes_json_path: Path,
    output_dir: Path = ASSETS_DIR,
    t2i_model: str = DEFAULT_T2I_MODEL,
    i2v_model: str = DEFAULT_I2V_MODEL,
) -> Path:
    """Run Phase 3.5: Asset generation.

    Args:
        scenes_json_path: Path to phase2_script_scenes.json
        output_dir: Base directory for assets
        t2i_model: ModelsLab T2I model ID
        i2v_model: ModelsLab I2V model ID

    Returns:
        Path to updated scenes JSON with asset paths
    """
    scenes = json.loads(scenes_json_path.read_text(encoding="utf-8"))
    logger.info("Phase 3.5: Generating assets for %d scenes", len(scenes))

    generator = AssetGenerator(
        t2i_model=t2i_model,
        i2v_model=i2v_model,
        output_dir=output_dir,
    )
    updated = await generator.generate_for_scenes(scenes)

    # Save updated scenes
    updated_path = scenes_json_path.parent / "phase2_script_scenes_with_assets.json"
    updated_path.write_text(
        "[\n" + ",\n".join(json.dumps(s, indent=2) for s in updated) + "\n]\n",
        encoding="utf-8",
    )
    logger.info("Phase 3.5 complete: saved to %s", updated_path)
    return updated_path
