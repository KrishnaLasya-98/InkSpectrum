"""ModelsLab TTS client (v6 Voice API).

Supports two no-cloning models:
- text-to-speech: predefined voices (adam, nova, bella, etc.)
- qwen-voice-design: describe the voice in natural language
"""

from __future__ import annotations

import os
import time
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Default voice for educational content (warm, clear, friendly)
DEFAULT_VOICE_ID = "nova"  # Female, warm, clear — good for primary teacher
DEFAULT_VOICE_DESCRIPTION = (
    "A warm, encouraging primary school teacher voice. Clear pronunciation, "
    "friendly tone, slightly slow pace suitable for 6-7 year old children. "
    "Female voice, American accent."
)
DEFAULT_LANGUAGE = "american english"
DEFAULT_SPEED = 0.9  # Slightly slower for kids


class ModelsLabTTS:
    """Text-to-Speech via ModelsLab v6 Voice API.

    Two modes:
    1. text-to-speech: use predefined voice_id (fast, reliable)
    2. qwen-voice-design: describe voice in natural language (more flexible)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: str = "text-to-speech",
        voice_id: Optional[str] = None,
        voice_description: Optional[str] = None,
        language: str = DEFAULT_LANGUAGE,
        speed: float = DEFAULT_SPEED,
    ):
        self.api_key = api_key or os.getenv("MODELSLAB_API_KEY", "")
        self.model_id = model_id
        self.voice_id = voice_id or os.getenv("MODELSLAB_TTS_VOICE_ID") or DEFAULT_VOICE_ID
        self.voice_description = voice_description or DEFAULT_VOICE_DESCRIPTION
        self.language = language
        self.speed = speed
        self.base_url = "https://modelslab.com/api/v6/voice"

        if not self.api_key:
            raise ValueError("MODELSLAB_API_KEY not set")

    def _headers(self) -> dict:
        return {"Content-Type": "application/json"}

    def synthesize(self, text: str, webhook: Optional[str] = None) -> str:
        """Convert text to speech and return audio URL.

        Args:
            text: Narration text to synthesize
            webhook: Optional webhook URL for async callback

        Returns:
            Audio URL string
        """
        if self.model_id == "qwen-voice-design":
            return self._synthesize_voice_design(text)
        return self._synthesize_standard(text)

    def _synthesize_standard(self, text: str) -> str:
        """Standard TTS with predefined voice_id."""
        payload = {
            "key": self.api_key,
            "model_id": "text-to-speech",
            "prompt": text,
            "voice_id": self.voice_id,
            "language": self.language,
            "speed": str(self.speed),
        }

        response = httpx.post(
            f"{self.base_url}/text_to_speech",
            headers=self._headers(),
            json=payload,
            timeout=120.0,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "success":
            audio_url = data["output"]
            if isinstance(audio_url, list):
                audio_url = audio_url[0]
            logger.info("TTS success: %s", audio_url[:80])
            return audio_url
        if data.get("status") == "processing":
            return self._poll(data["id"])

        raise RuntimeError(f"TTS failed: {data.get('message')}")

    def _synthesize_voice_design(self, text: str) -> str:
        """Voice design TTS with natural language voice description."""
        # qwen-voice-design accepts lowercase language names only
        lang_map = {
            "american english": "english",
            "british": "english",
            "english": "english",
            "hindi": "english",
            "mandarin chinese": "chinese",
            "chinese": "chinese",
            "japanese": "japanese",
            "korean": "korean",
            "german": "german",
            "portuguese": "portuguese",
            "brazilian portuguese": "portuguese",
            "russian": "russian",
            "french": "french",
            "italian": "italian",
            "spanish": "spanish",
        }
        mapped_lang = lang_map.get(self.language.lower(), "english")

        payload = {
            "key": self.api_key,
            "model_id": "qwen-voice-design",
            "prompt": text,
            "voice_description": self.voice_description,
            "language": mapped_lang,
        }

        response = httpx.post(
            f"{self.base_url}/voice_design",
            headers=self._headers(),
            json=payload,
            timeout=120.0,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "success":
            audio_url = data["output"]
            if isinstance(audio_url, list):
                audio_url = audio_url[0]
            logger.info("Voice design TTS success: %s", audio_url[:80])
            return audio_url
        if data.get("status") == "processing":
            return self._poll(data["id"])

        raise RuntimeError(f"Voice design TTS failed: {data.get('message')}")

    def _poll(self, request_id: str, timeout: int = 300) -> str:
        """Poll for async TTS result.

        ModelsLab requires the API key as a query parameter on the
        fetch endpoint, not in the request body.
        """
        start = time.time()
        while time.time() - start < timeout:
            resp = httpx.post(
                f"{self.base_url}/fetch/{request_id}?key={self.api_key}",
                headers=self._headers(),
                json={},
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "success":
                audio_url = data["output"]
                if isinstance(audio_url, list):
                    audio_url = audio_url[0]
                return audio_url
            if data.get("status") == "failed":
                raise RuntimeError(data.get("message", "TTS generation failed"))
            time.sleep(5)
        raise TimeoutError("TTS polling timed out")

    def test_connection(self) -> dict:
        """Test API key validity by synthesizing a short sample and returning the audio URL."""
        try:
            audio_url = self.synthesize("Connection test.")
            return {"status": "success", "audio_url": audio_url}
        except Exception as e:
            return {"status": "error", "message": str(e)}
