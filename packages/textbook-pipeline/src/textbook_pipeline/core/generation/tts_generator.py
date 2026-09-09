"""Phase 3: TTS Audio Generation.

Generates voiceover audio files from ScriptScene voiceover_lines using
ModelsLab TTS (primary) or Edge TTS (fallback).

Outputs:
- audio/<scene_id>_line_<n>.mp3  — per-voiceover-line audio files
- audio_manifest.json             — mapping of scene_id → audio files + durations
- phase2_script_scenes_updated.json — script with real audio paths and durations
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Default voice: warm, clear primary teacher voice
DEFAULT_VOICE = "en-US-AriaNeural"
ALT_VOICE = "en-IN-NeerjaNeural"  # Alternative if Aria is unavailable


def _normalize_text(text: str) -> str:
    """Clean text for TTS: remove markdown, extra whitespace, special chars."""
    import re
    # Remove markdown bold/italic
    text = re.sub(r'\*+([^*]+)\*+', r'\1', text)
    text = re.sub(r'_+([^_]+)_+', r'\1', text)
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove chars that break TTS
    text = text.replace('"', "'").replace('"', "'").replace('"', "'")
    text = text.replace('"', "'").replace('"', "'")
    return text.strip()


class TTSGenerator:
    """Generates TTS audio from ScriptScene voiceover_lines.

    Provider priority:
    1. ModelsLab TTS (cloud, high quality, requires API key)
    2. Edge TTS (free, no key required, word-level timestamps)
    """

    def __init__(
        self,
        output_dir: Path,
        provider: str = "modelslab",
        voice: str = DEFAULT_VOICE,
        alt_voice: str = ALT_VOICE,
        modelslab_model: str = "text-to-speech",
        modelslab_voice_id: str = "nova",
        modelslab_speed: float = 0.9,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.provider = provider
        self.voice = voice
        self.alt_voice = alt_voice
        self.modelslab_model = modelslab_model
        self.modelslab_voice_id = modelslab_voice_id
        self.modelslab_speed = modelslab_speed

        # Initialize ModelsLab client if needed
        self._modelslab_client = None
        if provider == "modelslab":
            try:
                from textbook_pipeline.core.generation.modelslab_tts import ModelsLabTTS
                self._modelslab_client = ModelsLabTTS(
                    model_id=modelslab_model,
                    voice_id=modelslab_voice_id,
                    speed=modelslab_speed,
                )
                logger.info("ModelsLab TTS initialized: model=%s voice=%s", modelslab_model, modelslab_voice_id)
            except Exception as exc:
                logger.warning("ModelsLab init failed (%s); falling back to Edge TTS", exc)
                self.provider = "edge"

    async def _synthesize_line(self, text: str, output_path: Path) -> float:
        """Generate audio for one line and return duration in seconds."""
        cleaned = _normalize_text(text)
        if not cleaned:
            raise ValueError("Empty text after normalization")

        # Try ModelsLab first, fall back to Edge TTS
        if self._modelslab_client:
            try:
                return await self._synthesize_modelslab(cleaned, output_path)
            except Exception as exc:
                logger.warning("ModelsLab failed for %s: %s", output_path.name, exc)
                self._modelslab_client = None  # Disable for rest of session

        # Edge TTS fallback
        return await self._synthesize_edge(cleaned, output_path)

    async def _synthesize_modelslab(self, text: str, output_path: Path) -> float:
        """Synthesize using ModelsLab TTS and download the result."""
        loop = asyncio.get_event_loop()
        audio_url = await loop.run_in_executor(None, self._modelslab_client.synthesize, text)

        # Download audio file
        response = await loop.run_in_executor(
            None,
            lambda: httpx.get(audio_url, follow_redirects=True, timeout=120.0),
        )
        response.raise_for_status()
        output_path.write_bytes(response.content)

        # Estimate duration
        words = len(text.split())
        duration = max(1.5, words / 2.5)
        return duration

    async def _synthesize_edge(self, text: str, output_path: Path) -> float:
        """Synthesize using Edge TTS (free fallback)."""
        # Try primary voice, fall back to alt
        for voice in [self.voice, self.alt_voice]:
            try:
                from edge_tts import Communicate
                communicate = Communicate(text, voice)
                await communicate.save(str(output_path))
                break
            except Exception as exc:
                logger.warning("Edge voice %s failed for %s: %s", voice, output_path.name, exc)
                if voice == self.alt_voice:
                    raise

        # Estimate duration: ~150 words/min = 2.5 words/sec
        words = len(text.split())
        duration = max(1.5, words / 2.5)
        return duration

    async def generate_for_scenes(
        self, scenes: List[Dict[str, Any]]
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Generate audio for all scenes.

        Returns:
            (updated_scenes, manifest)
        """
        updated: List[Dict[str, Any]] = []
        manifest: Dict[str, Any] = {
            "total_scenes": len(scenes),
            "total_lines": 0,
            "generated_files": 0,
            "scenes": [],
            "provider": self.provider,
        }

        for scene in scenes:
            scene_id = scene.get("id", "unknown")
            scene_audio: List[Dict[str, Any]] = []

            for line_idx, vo_line in enumerate(scene.get("voiceover_lines", [])):
                text = vo_line.get("text", "")
                if not text:
                    continue

                audio_filename = f"{scene_id}_line_{line_idx + 1}.mp3"
                audio_path = self.output_dir / audio_filename

                try:
                    duration = await self._synthesize_line(text, audio_path)
                    vo_line["duration_seconds"] = round(duration, 2)
                    vo_line["audio_path"] = str(audio_path)
                    scene_audio.append({
                        "line_index": line_idx,
                        "text": text[:80],
                        "audio_file": str(audio_path),
                        "duration_seconds": round(duration, 2),
                        "pause_after": vo_line.get("pause_after", 0.5),
                    })
                    manifest["generated_files"] += 1
                except Exception as exc:
                    logger.error("TTS failed for %s line %d: %s", scene_id, line_idx, exc)
                    vo_line["duration_seconds"] = 5.0
                    vo_line["audio_path"] = None

            manifest["total_lines"] += len(scene_audio)
            manifest["scenes"].append({
                "scene_id": scene_id,
                "scene_title": scene.get("title", ""),
                "audio_lines": scene_audio,
            })
            updated.append(scene)

        return updated, manifest

    def save(self, updated_scenes: List[Dict[str, Any]], manifest: Dict[str, Any]) -> tuple[Path, Path]:
        """Save updated scenes and manifest to disk."""
        scenes_path = self.output_dir.parent / "phase2_script_scenes_with_audio.json"
        manifest_path = self.output_dir / "audio_manifest.json"

        scenes_path.write_text(
            "[\n" + ",\n".join(json.dumps(s, indent=2) for s in updated_scenes) + "\n]\n",
            encoding="utf-8",
        )
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        logger.info("Saved %d audio files, manifest at %s", manifest["generated_files"], manifest_path)
        return scenes_path, manifest_path


async def run_phase3(
    script_json_path: Path,
    output_audio_dir: Path,
    provider: str = "modelslab",
    voice: str = DEFAULT_VOICE,
    modelslab_model: str = "text-to-speech",
    modelslab_voice_id: str = "nova",
    modelslab_speed: float = 0.9,
) -> tuple[Path, Path]:
    """Run Phase 3: TTS generation.

    Args:
        script_json_path: Path to phase2_script_scenes.json
        output_audio_dir: Directory for audio files
        provider: TTS provider ("modelslab" or "edge")
        voice: Edge TTS voice name (fallback)
        modelslab_model: ModelsLab model_id ("text-to-speech" or "qwen-voice-design")
        modelslab_voice_id: Predefined voice for text-to-speech model
        modelslab_speed: Speech speed (0.5-2.0)

    Returns:
        (updated_scenes_path, manifest_path)
    """
    scenes = json.loads(script_json_path.read_text(encoding="utf-8"))
    logger.info("Loaded %d scenes from %s", len(scenes), script_json_path)

    generator = TTSGenerator(
        output_audio_dir,
        provider=provider,
        voice=voice,
        modelslab_model=modelslab_model,
        modelslab_voice_id=modelslab_voice_id,
        modelslab_speed=modelslab_speed,
    )
    updated, manifest = await generator.generate_for_scenes(scenes)
    return generator.save(updated, manifest)
