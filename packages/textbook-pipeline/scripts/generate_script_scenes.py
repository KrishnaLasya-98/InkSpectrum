#!/usr/bin/env python3
"""Generate phase2_script_scenes.json directly (AI-driven, no LLM API).

This follows the OpenMontage pattern: the AI assistant writes the script
JSON directly based on chapter.json content, without calling an external LLM.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from textbook_pipeline.models.script import ScriptScene, SceneStep, SceneStepType, VoiceoverLine
from textbook_pipeline.models.chapter import ChapterNode
from textbook_pipeline.utils.logger import PipelineLogger, LoggingConfig

REPO_ROOT = Path(__file__).resolve().parents[3]


def get_project_paths(project_name: str) -> tuple[Path, Path]:
    """Resolve project input/output paths."""
    project_dir = REPO_ROOT / f"packages/textbook-pipeline/projects/{project_name}"
    chapter_path = project_dir / "chapter.json"
    output_path = project_dir / "phase2_script_scenes.json"
    return chapter_path, output_path


def get_logging_config(project_name: str) -> LoggingConfig:
    """Get logging config that writes inside the project directory."""
    project_dir = REPO_ROOT / f"packages/textbook-pipeline/projects/{project_name}"
    return LoggingConfig(output_dir=project_dir / "logs")


def sanitize_narration_text(text: str) -> str:
    """Remove markdown image/link syntax from narration text."""
    # Remove markdown images: ![](url) or ![](<url>) or ![]<url>
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'!\[\]\(.*?\)', '', text)
    text = re.sub(r'!\[\]<.*?>', '', text)
    # Remove markdown links: [text](url)
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def make_scene(
    scene_id: str,
    title: str,
    section_ref: str,
    voiceover_texts: list[str],
    steps: list[tuple[str, str, float]],
    duration: float | None = None,
    notes: str = "",
    image_prompt: str | None = None,
    video_prompt: str | None = None,
    storyboard: list[dict] | None = None,
) -> dict:
    """Build a ScriptScene dict.

    Args:
        scene_id: Unique scene ID
        title: Scene title
        section_ref: Section ID this scene belongs to
        voiceover_texts: List of narration texts
        steps: List of (type, text, at_seconds) tuples
        duration: Total scene duration (auto-calculated if None)
        notes: Optional pedagogical notes
        image_prompt: T2I prompt for generating scene background/image
        video_prompt: I2V/T2V motion prompt for animating the scene
        storyboard: Detailed visual sequence for video production
    """
    # Sanitize all voiceover texts to remove markdown artifacts
    cleaned_vo_texts = [sanitize_narration_text(t) for t in voiceover_texts]
    
    vo_lines = []
    cumulative = 0.0
    for i, text in enumerate(cleaned_vo_texts):
        pause = 0.5 if i < len(cleaned_vo_texts) - 1 else 0.0
        vo_lines.append({
            "text": text,
            "duration_seconds": max(2.0, len(text.split()) / 2.5),
            "pause_after": pause,
        })
        cumulative += vo_lines[-1]["duration_seconds"] + pause

    scene_steps = []
    for step_type, text, at in steps:
        scene_steps.append({
            "type": step_type,
            "text": sanitize_narration_text(text),
            "at": at,
            "duration": max(1.0, len(text.split()) / 3.0),
        })

    if duration is None:
        duration = cumulative if cumulative > 0 else 5.0

    scene_dict = {
        "id": scene_id,
        "title": title,
        "section_ref": section_ref,
        "voiceover_lines": vo_lines,
        "scene_steps": scene_steps,
        "duration_seconds": round(duration, 1),
        "notes": notes,
    }
    
    # Add asset generation fields if prompts provided
    if image_prompt:
        scene_dict["image_prompt"] = image_prompt
    if video_prompt:
        scene_dict["video_prompt"] = video_prompt
    if storyboard:
        scene_dict["storyboard"] = storyboard
    
    return scene_dict


def generate_theory_scene(section_id: str, title: str, content: str, context: str = "") -> dict:
    """Generate a theory scene with narration, visual steps, and detailed storyboard."""
    content = sanitize_narration_text(content.strip())
    if not content:
        content = f"Let us learn about {title}."

    # Split content into 2-3 narration chunks
    sentences = content.replace("\n", " ").split(". ")
    chunks = []
    current = ""
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        if len(current.split()) + len(sent.split()) < 25:
            current += sent + ". "
        else:
            if current:
                chunks.append(current.strip())
            current = sent + ". "
    if current:
        chunks.append(current.strip())

    # Ensure at least 2 voiceover lines
    while len(chunks) < 2:
        chunks.append(f"Pay attention to {title}.")

    # Build scene steps
    steps = [
        ("title", title, 0.0),
        ("text", chunks[0][:120], 2.0),
    ]
    if len(chunks) > 1:
        steps.append(("text", chunks[1][:120], steps[-1][2] + 3.0))
    if len(chunks) > 2:
        steps.append(("word_highlight", chunks[2][:80], steps[-1][2] + 3.0))

    # Generate image/video prompts for asset generation
    image_prompt = f"Educational illustration for grade 1 students: {title}. {content[:150]}. Bright, friendly, cartoon style, no text, clean background, suitable for children."
    video_prompt = f"Gentle motion for {title.lower()}. Smooth character movement and environmental animation. NO camera zoom in or out. Static camera, motion-only. Educational style for children."

    # Generate detailed visual storyboard
    storyboard = _generate_theory_storyboard(title, chunks, content)

    return make_scene(
        scene_id=f"scene_{section_id}_0",
        title=title,
        section_ref=section_id,
        voiceover_texts=chunks[:3],
        steps=steps,
        image_prompt=image_prompt,
        video_prompt=video_prompt,
        storyboard=storyboard,
    )


def _generate_theory_storyboard(title: str, chunks: list[str], content: str) -> list[dict]:
    """Generate a detailed visual storyboard for a theory scene.
    
    Creates a shot-by-shot breakdown with timing, visuals, camera motion,
    and asset requirements for video production.
    """
    storyboard = []
    current_time = 0.0
    
    # Shot 1: Title card
    storyboard.append({
        "time": current_time,
        "duration": 3.0,
        "visual": f"Title card: '{title}' centered on screen with colorful background",
        "on_screen_text": title,
        "camera_motion": "static",
        "animation_type": "text_fade_in",
        "transition_in": "fade",
        "transition_out": "fade",
        "asset_requirements": ["background:colorful"],
    })
    current_time += 3.0
    
    # Shots for each narration chunk
    for i, chunk in enumerate(chunks[:3]):
        chunk_duration = max(3.0, len(chunk.split()) / 2.5)
        
        # Determine visual based on content keywords
        visual_type = _classify_visual_type(chunk)
        
        if visual_type == "character_action":
            storyboard.append({
                "time": current_time,
                "duration": chunk_duration,
                "visual": f"Character demonstration: {chunk[:80]}",
                "on_screen_text": chunk[:60] + "..." if len(chunk) > 60 else chunk,
                "camera_motion": "static",
                "animation_type": "character_action",
                "transition_in": "fade",
                "transition_out": "fade",
                "asset_requirements": [f"character:{_extract_character(chunk)}", f"video:{_extract_action(chunk)}"],
            })
        elif visual_type == "environmental":
            storyboard.append({
                "time": current_time,
                "duration": chunk_duration,
                "visual": f"Environmental scene: {chunk[:80]}",
                "on_screen_text": chunk[:60] + "..." if len(chunk) > 60 else chunk,
                "camera_motion": "static",
                "animation_type": "environmental",
                "transition_in": "fade",
                "transition_out": "fade",
                "asset_requirements": [f"background:{_extract_setting(chunk)}", f"video:{_extract_motion(chunk)}"],
            })
        elif visual_type == "diagram":
            storyboard.append({
                "time": current_time,
                "duration": chunk_duration,
                "visual": f"Educational diagram: {chunk[:80]}",
                "on_screen_text": chunk[:60] + "..." if len(chunk) > 60 else chunk,
                "camera_motion": "static",
                "animation_type": "diagram_highlight",
                "transition_in": "fade",
                "transition_out": "fade",
                "asset_requirements": ["diagram:educational", "highlight:key_term"],
            })
        else:
            # Default: text card with gentle motion
            storyboard.append({
                "time": current_time,
                "duration": chunk_duration,
                "visual": f"Narration card with text: {chunk[:80]}",
                "on_screen_text": chunk[:60] + "..." if len(chunk) > 60 else chunk,
                "camera_motion": "static",
                "animation_type": "text_idle",
                "transition_in": "fade",
                "transition_out": "fade",
                "asset_requirements": ["background:colorful"],
            })
        
        current_time += chunk_duration
    
    return storyboard


def _classify_visual_type(text: str) -> str:
    """Classify text into visual type for storyboard generation."""
    text_lower = text.lower()
    
    # Character actions
    if any(word in text_lower for word in ["walk", "run", "jump", "swim", "fly", "eat", "sleep", "play"]):
        return "character_action"
    
    # Environmental scenes
    if any(word in text_lower for word in ["forest", "beach", "sky", "underwater", "savanna", "garden", "farm"]):
        return "environmental"
    
    # Diagrams/educational visuals
    if any(word in text_lower for word in ["diagram", "chart", "graph", "equation", "formula", "cycle"]):
        return "diagram"
    
    return "text_card"


def _extract_character(text: str) -> str:
    """Extract character name from text for asset requirements."""
    text_lower = text.lower()
    characters = ["lion", "elephant", "tiger", "fish", "dolphin", "whale", "bird", "duck", "pigeon", "parrot",
                  "butterfly", "grasshopper", "rabbit", "ant", "dog", "cat", "cow", "horse", "varun", "vidya"]
    for char in characters:
        if char in text_lower:
            return char
    return "generic_character"


def _extract_setting(text: str) -> str:
    """Extract setting/environment from text for asset requirements."""
    text_lower = text.lower()
    settings = ["forest", "beach", "ocean", "savanna", "garden", "farm", "sky", "underwater", "classroom", "home"]
    for setting in settings:
        if setting in text_lower:
            return setting
    return "generic_background"


def _extract_action(text: str) -> str:
    """Extract action/motion from text for asset requirements."""
    text_lower = text.lower()
    actions = ["walk", "run", "jump", "swim", "fly", "eat", "sleep", "play", "build", "talk", "roar", "trunk", "stripe"]
    for action in actions:
        if action in text_lower:
            return action
    return "gentle_motion"


def _extract_motion(text: str) -> str:
    """Extract environmental motion from text for asset requirements."""
    text_lower = text.lower()
    motions = ["wave", "ripple", "sway", "drift", "bubble", "flutter", "buzz", "march"]
    for motion in motions:
        if motion in text_lower:
            return motion
    return "ambient"


def generate_exercise_scene(section_id: str, title: str, content: str) -> dict:
    """Generate an exercise scene with question → steps → answer flow and storyboard."""
    content = sanitize_narration_text(content.strip())
    if not content:
        content = f"Complete the exercise about {title}."

    # Extract questions from content
    lines = [l.strip() for l in content.split("\n") if l.strip()]
    questions = [l for l in lines if l.startswith(("-", "•", "a.", "b.", "c.", "d.", "A.", "B.", "C.", "D."))]
    if not questions:
        questions = lines[:3]

    # Build narration
    vo_texts = [
        f"Now let us practice. {title}.",
        f"Look at the question carefully: {questions[0] if questions else title}",
        "Think about your answer before you respond.",
        "Great job! Let us check the answer together.",
    ]

    # Build scene steps
    steps = [
        ("question_card", questions[0] if questions else title, 0.0),
        ("worked_step", "Read the question carefully and think about what it asks.", 2.0),
        ("answer_reveal", "The correct answer depends on the story you just read. Look back and find the clues!", 5.0),
    ]

    # Generate image/video prompts for exercise scenes
    image_prompt = f"Educational worksheet illustration for grade 1: {title}. Clean, simple, friendly style, no text, white background, suitable for children."
    video_prompt = f"Gentle motion for exercise scene: {title.lower()}. Smooth transitions between question and answer elements. NO camera zoom in or out. Static camera, motion-only."

    # Generate detailed visual storyboard for exercise
    storyboard = _generate_exercise_storyboard(title, questions)

    return make_scene(
        scene_id=f"scene_{section_id}_0",
        title=title,
        section_ref=section_id,
        voiceover_texts=vo_texts,
        steps=steps,
        image_prompt=image_prompt,
        video_prompt=video_prompt,
        storyboard=storyboard,
    )


def _generate_exercise_storyboard(title: str, questions: list[str]) -> list[dict]:
    """Generate a detailed visual storyboard for an exercise scene."""
    storyboard = []
    current_time = 0.0
    
    # Shot 1: Question card
    storyboard.append({
        "time": current_time,
        "duration": 4.0,
        "visual": "Question card with clean, friendly design",
        "on_screen_text": questions[0] if questions else title,
        "camera_motion": "static",
        "animation_type": "text_fade_in",
        "transition_in": "fade",
        "transition_out": "fade",
        "asset_requirements": ["ui:question_card", "icon:pencil"],
    })
    current_time += 4.0
    
    # Shot 2: Working through the answer
    storyboard.append({
        "time": current_time,
        "duration": 4.0,
        "visual": "Step-by-step solution with highlighting",
        "on_screen_text": "Let's think about this together...",
        "camera_motion": "static",
        "animation_type": "highlight_reveal",
        "transition_in": "fade",
        "transition_out": "fade",
        "asset_requirements": ["ui:step_indicator", "highlight:key_clue"],
    })
    current_time += 4.0
    
    # Shot 3: Answer reveal
    storyboard.append({
        "time": current_time,
        "duration": 3.0,
        "visual": "Correct answer with celebration animation",
        "on_screen_text": "Great job! You got it!",
        "camera_motion": "static",
        "animation_type": "celebration",
        "transition_in": "zoom_in",
        "transition_out": "fade",
        "asset_requirements": ["ui:answer_reveal", "particle:stars"],
    })
    
    return storyboard


def generate_all_scenes(project_name: str = "english_pipeline_output") -> list[dict]:
    """Generate scenes for all sections in chapter.json."""
    chapter_path, _ = get_project_paths(project_name)
    chapter = json.loads(chapter_path.read_text(encoding="utf-8"))
    
    logger = PipelineLogger(get_logging_config(project_name), project_name=f"{project_name}_phase2")

    logger.stage_start("script", f"Generating script scenes for {project_name}")
    bar = logger.create_progress_bar("scenes", total=len(chapter["sections"]), desc="Script scenes")

    scenes = []
    for section in chapter["sections"]:
        sid = section["id"]
        title = section["title"]
        stype = section["type"]
        content = section.get("content_text", "") or ""

        if stype == "theoretical":
            scene = generate_theory_scene(sid, title, content)
        else:
            scene = generate_exercise_scene(sid, title, content)

        scenes.append(scene)
        storyboard_shots = len(scene.get('storyboard', []))
        logger.info(f"Generated: {sid:10s} {title[:40]:40s} VO={len(scene['voiceover_lines'])} Steps={len(scene['scene_steps'])} Storyboard={storyboard_shots}")
        logger.update_progress("scenes", 1)

    logger.close_progress("scenes")
    logger.stage_end("script", f"Generated {len(scenes)} script scenes")
    logger.close_all_progress()
    return scenes


def main(project_name: str = "english_pipeline_output"):
    logger = PipelineLogger(get_logging_config(project_name), project_name=f"{project_name}_phase2")
    logger.stage_start("script", f"Generating script scenes for {project_name}")
    
    scenes = generate_all_scenes(project_name)
    _, output_path = get_project_paths(project_name)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        "[\n" + ",\n".join(json.dumps(s, indent=2, ensure_ascii=False) for s in scenes) + "\n]\n",
        encoding="utf-8",
    )
    logger.success(f"Saved {len(scenes)} scenes to {output_path}")
    logger.stage_end("script", "Script generation complete")
    logger.close_all_progress()
    print(f"\nSaved {len(scenes)} scenes to {output_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate Phase 2 script scenes from chapter.json")
    parser.add_argument("--project", default="english_pipeline_output",
                        help="Project directory name under packages/textbook-pipeline/projects/")
    args = parser.parse_args()
    main(project_name=args.project)
