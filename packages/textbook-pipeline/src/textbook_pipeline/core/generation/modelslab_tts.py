"""ModelsLab TTS client (v7 Voice API)."""

from __future__ import annotations

import os
import time
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class ModelsLabTTS:
    """Text-to-Speech via ModelsLab v7 Voice API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: Optional[str] = None,
        voice_id: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("MODELSLAB_API_KEY", "")
        self.model_id = model_id or os.getenv("MODELSLAB_TTS_MODEL", "text-to-speech")
        self.voice_id = voice_id or os.getenv("MODELSLAB_TTS_VOICE_ID", "")
        self.base_url = "https://modelslab.com/api/v7/voice"

        if not self.api_key:
            raise ValueError("MODELSLAB_API_KEY not set")

    def synthesize(self, text: str, webhook: Optional[str] = None, track_id: Optional[str] = None) -> str:
        """Convert text to speech and return audio URL."""
        payload = {
            "key": self.api_key,
            "prompt": text,
            "voice_id": self.voice_id,
            "model_id": self.model_id,
        }
        if webhook:
            payload["webhook"] = webhook
        if track_id:
            payload["track_id"] = track_id

        response = httpx.post(
            f"{self.base_url}/text-to-speech",
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "success":
            return data["output"][0]
        if data.get("status") == "processing":
            return self._poll(data["id"])

        raise RuntimeError(f"TTS failed: {data.get('message')}")

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
                raise RuntimeError(data.get("message", "TTS generation failed"))
            time.sleep(5)
        raise TimeoutError("TTS polling timed out")
