"""ModelsLab Video Generation client (v7 Video Fusion API)."""

from __future__ import annotations

import os
import time
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class ModelsLabVideo:
    """Text-to-Video and Image-to-Video via ModelsLab v7 Video Fusion API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("MODELSLAB_API_KEY", "")
        self.model_id = model_id or os.getenv("MODELSLAB_VIDEO_MODEL", "h3-minimax-start-end-frame")
        self.base_url = "https://modelslab.com/api/v7/video-fusion"

        if not self.api_key:
            raise ValueError("MODELSLAB_API_KEY not set")

    def text_to_video(
        self,
        prompt: str,
        negative_prompt: str = "low quality, blurry, static, distorted",
        duration: int = 4,
        width: int = 512,
        height: int = 512,
        aspect_ratio: str = "16:9",
        webhook: Optional[str] = None,
        track_id: Optional[str] = None,
    ) -> str:
        """Generate video from text prompt."""
        payload = {
            "key": self.api_key,
            "model_id": self.model_id,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "duration": duration,
            "width": width,
            "height": height,
            "aspect_ratio": aspect_ratio,
        }
        if webhook:
            payload["webhook"] = webhook
        if track_id:
            payload["track_id"] = track_id

        response = httpx.post(
            f"{self.base_url}/text-to-video",
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "success":
            return data["output"][0]
        if data.get("status") == "processing":
            return self._poll(data["id"])

        raise RuntimeError(f"Video generation failed: {data.get('message')}")

    def image_to_video(
        self,
        init_image: str,
        prompt: str,
        negative_prompt: str = "static, still, low quality, blurry",
        duration: int = 4,
        width: int = 512,
        height: int = 512,
        aspect_ratio: str = "16:9",
        webhook: Optional[str] = None,
        track_id: Optional[str] = None,
    ) -> str:
        """Animate a static image."""
        payload = {
            "key": self.api_key,
            "model_id": self.model_id,
            "init_image": [init_image],
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "duration": duration,
            "width": width,
            "height": height,
            "aspect_ratio": aspect_ratio,
        }
        if webhook:
            payload["webhook"] = webhook
        if track_id:
            payload["track_id"] = track_id

        response = httpx.post(
            f"{self.base_url}/image-to-video",
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "success":
            return data["output"][0]
        if data.get("status") == "processing":
            return self._poll(data["id"])

        raise RuntimeError(f"Image-to-video failed: {data.get('message')}")

    def _poll(self, request_id: str, timeout: int = 600) -> str:
        start = time.time()
        while time.time() - start < timeout:
            resp = httpx.post(
                f"{self.base_url}/fetch/{request_id}",
                json={"key": self.api_key},
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "success":
                return data["output"][0]
            if data.get("status") == "failed":
                raise RuntimeError(data.get("message", "Video generation failed"))
            time.sleep(10)
        raise TimeoutError("Video generation polling timed out")
