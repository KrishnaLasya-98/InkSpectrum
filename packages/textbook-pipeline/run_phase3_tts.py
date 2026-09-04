"""Phase 3: TTS Audio Generation for Chapter 1 Lesson 1 Script.

Generates voiceover audio files using Edge TTS (free, natural-sounding voices).
Sinks timing with ScriptScene voiceover lines.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import List

import edge_tts

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Voice selection for Primary Teacher (warm, clear English)
VOICE_NAME = "en-US-AriaNeural"  # Professional, friendly female voice

async def generate_audio_for_line(text: str, output_path: Path) -> float:
    """Generate TTS audio file for a single voiceover line and return duration."""
    communicate = edge_tts.Communicate(text, VOICE_NAME)
    await communicate.save(str(output_path))
    
    # Estimate or measure duration (Edge TTS creates .mp3)
    # A rough estimate for speech is ~150 words per minute (2.5 words per second)
    words = len(text.split())
    estimated_duration = max(2.0, words / 2.5)
    return estimated_duration

async def process_script(script_path: Path, output_audio_dir: Path):
    output_audio_dir.mkdir(parents=True, exist_ok=True)
    
    with open(script_path, "r", encoding="utf-8") as f:
        scenes = json.load(f)
        
    print(f"Loaded {len(scenes)} scenes from {script_path}")
    
    total_audio_files = 0
    manifest = []
    
    for scene_idx, scene in enumerate(scenes):
        scene_id = scene["id"]
        print(f"\nProcessing Scene {scene_idx + 1}: {scene_id} ({scene['title']})")
        
        scene_audio_entries = []
        for line_idx, vo_line in enumerate(scene["voiceover_lines"]):
            text = vo_line["text"]
            audio_filename = f"{scene_id}_line_{line_idx + 1}.mp3"
            audio_path = output_audio_dir / audio_filename
            
            print(f"  Generating TTS [{line_idx + 1}/{len(scene['voiceover_lines'])}]: \"{text[:50]}...\"")
            
            try:
                duration = await generate_audio_for_line(text, audio_path)
                # Update line duration
                vo_line["duration_seconds"] = duration
                scene_audio_entries.append({
                    "line_index": line_idx,
                    "text": text,
                    "audio_file": str(audio_path),
                    "duration_seconds": duration,
                    "pause_after": vo_line.get("pause_after", 0.5)
                })
                total_audio_files += 1
            except Exception as e:
                logger.error(f"Failed to generate TTS for line: {e}")
                
        manifest.append({
            "scene_id": scene_id,
            "scene_title": scene["title"],
            "audio_lines": scene_audio_entries
        })
        
    # Save audio manifest
    manifest_path = output_audio_dir.parent / "lesson1_audio_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        
    print(f"\n✅ Generated {total_audio_files} audio files!")
    print(f"✅ Saved audio manifest to: {manifest_path}")

if __name__ == "__main__":
    script_p = Path("D:/new_video_pip/textbook-pipeline/projects/english_class1_pymupdf/lesson1_script.json")
    audio_dir = Path("D:/new_video_pip/textbook-pipeline/projects/english_class1_pymupdf/audio")
    
    asyncio.run(process_script(script_p, audio_dir))
