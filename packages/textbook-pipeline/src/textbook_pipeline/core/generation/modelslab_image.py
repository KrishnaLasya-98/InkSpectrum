"""ModelsLab Image Generation client (v7 API)."""

from __future__ import annotations

import os
import time
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class ModelsLabImage:
    """Text-to-Image and Image-to-Image via ModelsLab v7 API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("MODELSLAB_API_KEY", "")
        self.model_id = model_id or os.getenv("MODELSLAB_IMAGE_MODEL", "hidream-o1")
        self.base_url = "https://modelslab.com/api/v7/images"

        if not self.api_key:
            raise ValueError("MODELSLAB_API_KEY not set")

    def text_to_image(
        self,
        prompt: str,
        negative_prompt: str = "blurry, low quality, distorted, deformed",
        width: int = 1024,
        height: int = 1024,
        samples: int = 1,
        guidance_scale: float = 7.5,
        seed: Optional[int] = None,
        webhook: Optional[str] = None,
        track_id: Optional[str] = None,
    ) -> str:
        """Generate image from text prompt."""
        payload = {
            "key": self.api_key,
            "model_id": self.model_id,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "samples": samples,
            "guidance_scale": guidance_scale,
        }
        if seed is not None:
            payload["seed"] = seed
        if webhook:
            payload["webhook"] = webhook
        if track_id:
            payload["track_id"] = track_id

        response = httpx.post(
            f"{self.base_url}/text-to-image",
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "success":
            return data["output"][0]
        if data.get("status") == "processing":
            return self._poll(data["id"])

        raise RuntimeError(f"Image generation failed: {data.get('message')}")

    def image_to_image(
        self,
        init_image: str,
        prompt: str,
        negative_prompt: str = "blurry, low quality, distorted",
        strength: float = 0.7,
        width: int = 1024,
        height: int = 1024,
        webhook: Optional[str] = None,
        track_id: Optional[str] = None,
    ) -> str:
        """Transform an existing image based on a prompt."""
        payload = {
            "key": self.api_key,
            "model_id": self.model_id,
            "prompt": prompt,
            "init_image": [init_image],
            "strength": strength,
            "width": width,
            "height": height,
            "negative_prompt": negative_prompt,
        }
        if webhook:
            payload["webhook"] = webhook
        if track_id:
            payload["track_id"] = track_id

        response = httpx.post(
            f"{self.base_url}/image-to-image",
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "success":
            return data["output"][0]
        if data.get("status") == "processing":
            return self._poll(data["id"])

        raise RuntimeError(f"Image-to-image failed: {data.get('message')}")

    def _poll(self, request_id: str, timeout: int = 300) -> str:
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
                raise RuntimeError(data.get("message", "Image generation failed"))
            time.sleep(5)
        raise TimeoutError("Image generation polling timed out")
