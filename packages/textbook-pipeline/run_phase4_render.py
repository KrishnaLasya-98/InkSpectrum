"""Phase 4 Orchestrator: Remotion + Agnes Visual Rendering.

Binds Chapter 1 Script (`lesson1_script.json`) and Audio Manifest (`lesson1_audio_manifest.json`)
with Agnes AI visual generation to produce final scene assets and rendering instructions.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

initialize_environment()

from textbook_pipeline.wrappers.agnes_client import AgnesPipelineClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_phase4():
    project_dir = PROJECT_ROOT / "projects" / "english_class1_pymupdf"
    script_path = project_dir / "lesson1_script.json"
    audio_manifest_path = project_dir / "lesson1_audio_manifest.json"
    
    with open(script_path, "r", encoding="utf-8") as f:
        scenes = json.load(f)
        
    with open(audio_manifest_path, "r", encoding="utf-8") as f:
        audio_manifest = json.load(f)
        
    print(f"=== Phase 4: Rendering Setup for Chapter 1 ===")
    print(f"Loaded {len(scenes)} scenes and audio manifest.")
    
    agnes = AgnesPipelineClient()
    visuals_dir = project_dir / "visuals"
    visuals_dir.mkdir(parents=True, exist_ok=True)
    
    render_manifest = []
    
    for scene in scenes:
        scene_id = scene["id"]
        title = scene["title"]
        print(f"\nProcessing visual asset for: {scene_id} ({title})")
        
        # Find corresponding audio
        audio_entry = next((m for m in audio_manifest if m["scene_id"] == scene_id), None)
        
        # Generate visual prompt for story / theory scenes
        image_path = visuals_dir / f"{scene_id}.jpg"
        video_path = visuals_dir / f"{scene_id}.mp4"
        
        prompt = f"Educational primary school illustration for grade 1: {title}. Bright, friendly, vector art style."
        
        # 1. Generate Image via Agnes
        agnes.generate_scene_image(prompt, image_path)
        
        # 2. Generate Video loop via Agnes (for story sections)
        if "Beach" in title or "Story" in title or "Intro" in title:
            agnes.generate_scene_video(image_path, video_path)
            bg_asset = str(video_path)
        else:
            bg_asset = str(image_path)
            
        render_manifest.append({
            "scene_id": scene_id,
            "title": title,
            "background_asset": bg_asset,
            "audio_lines": audio_entry["audio_lines"] if audio_entry else [],
            "scene_steps": scene["scene_steps"]
        })
        
    # Save final Remotion composition manifest
    composition_manifest_path = project_dir / "remotion_composition_manifest.json"
    with open(composition_manifest_path, "w", encoding="utf-8") as f:
        json.dump(render_manifest, f, indent=2)
        
    print(f"\n✅ Phase 4 Visual Asset Pipeline Ready!")
    print(f"✅ Composition Manifest saved to: {composition_manifest_path}")

if __name__ == "__main__":
    run_phase4()
