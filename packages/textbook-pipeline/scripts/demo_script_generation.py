#!/usr/bin/env python3
"""Detailed script generation demo for InkSpectrum.

Demonstrates:
1. English/EVS/Social → Remotion + ModelsLab image/video assets
2. Math → Manim + LaTeX equations
3. LLM script generation aligned with renderer constraints
4. ModelsLab model integration (hidream-o1, h3-minimax-r2v, text-to-speech)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "packages/textbook-pipeline/src"))

from textbook_pipeline.models.chapter import ChapterNode, SectionNode, SectionType, Subject, DoclingRef
from textbook_pipeline.core.script.writer import ScriptWriter
from textbook_pipeline.core.script.planner import ScenePlanner


def print_banner(text: str):
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_scene_summary(scene, index: int):
    print(f"\n--- Scene {index}: {scene.title} ---")
    print(f"  ID: {scene.id}")
    print(f"  Duration: {scene.duration_seconds}s")
    print(f"  Render mode: {scene.render_mode}")
    print(f"  Voiceover lines: {len(scene.voiceover_lines)}")
    for vl in scene.voiceover_lines[:3]:
        print(f"    - {vl.text[:120]}...")
    print(f"  Scene steps: {len(scene.scene_steps)}")
    for step in scene.scene_steps[:8]:
        detail = step.text or step.latex or ""
        print(f"    - [{step.type.value}] {detail[:80]}")
    if hasattr(scene, 'visual_prompts') and scene.visual_prompts:
        print(f"  Visual prompts: {len(scene.visual_prompts)}")
        for vp in scene.visual_prompts[:2]:
            print(f"    - [{vp.get('type', '?')}] {vp.get('prompt', '')[:80]}")


def demo_english():
    print_banner("DEMO 1: English Lesson - Remotion + ModelsLab Assets")
    
    chapter = ChapterNode(
        id="english_ch1",
        number=1,
        title="Lesson 1 - At the Beach",
        subject=Subject.ENGLISH,
        grade=1,
        textbook_id="english_class1",
        sections=[
            SectionNode(
                id="sec_001",
                type=SectionType.THEORETICAL,
                title="At the Beach",
                content_text="Varun and Vidya build a sandcastle together. It is a lovely day. The sun is shining. The waves are small. They play in the sand. Mom and Dad are calling. We have to leave now!",
                page_range=(1, 3),
                docling_refs=[DoclingRef(item_id="p1", page_number=1, label="TEXT")],
            ),
            SectionNode(
                id="sec_002",
                type=SectionType.EXERCISE,
                title="Comprehending Ability",
                content_text="A. Tick the correct sentences. 1. Varun and Vidya are at a park. 2. They build a sandcastle. 3. The sun is shining.",
                page_range=(4, 5),
                exercises=[],
                docling_refs=[DoclingRef(item_id="p4", page_number=4, label="TEXT")],
            ),
        ],
        page_range=(1, 5),
    )
    
    writer = ScriptWriter()
    scenes = writer.generate_chapter_script(chapter)
    
    print(f"Generated {len(scenes)} scenes for English")
    for i, scene in enumerate(scenes, 1):
        print_scene_summary(scene, i)
    
    return scenes


def demo_math():
    print_banner("DEMO 2: Math Lesson - Manim + LaTeX Equations")
    
    chapter = ChapterNode(
        id="math_ch1",
        number=1,
        title="Lesson 1 - Numbers 1 to 50",
        subject=Subject.MATH,
        grade=1,
        textbook_id="math_class1",
        sections=[
            SectionNode(
                id="sec_001",
                type=SectionType.THEORETICAL,
                title="Counting 1 to 10",
                content_text="We can count from 1 to 10. One, two, three, four, five, six, seven, eight, nine, ten. 1 + 1 = 2. 2 + 3 = 5.",
                page_range=(1, 2),
                docling_refs=[DoclingRef(item_id="p1", page_number=1, label="TEXT")],
            ),
            SectionNode(
                id="sec_002",
                type=SectionType.EXERCISE,
                title="Addition Practice",
                content_text="Add the numbers: 5 + 3 = ? , 7 + 2 = ? , 4 + 4 = ?",
                page_range=(3, 4),
                exercises=[],
                docling_refs=[DoclingRef(item_id="p3", page_number=3, label="TEXT")],
            ),
        ],
        page_range=(1, 4),
    )
    
    writer = ScriptWriter()
    scenes = writer.generate_chapter_script(chapter)
    
    print(f"Generated {len(scenes)} scenes for Math")
    for i, scene in enumerate(scenes, 1):
        print_scene_summary(scene, i)
    
    return scenes


def demo_evs():
    print_banner("DEMO 3: EVS Lesson - Remotion + Diagrams + Images")
    
    chapter = ChapterNode(
        id="evs_ch1",
        number=1,
        title="Lesson 1 - Our Body",
        subject=Subject.SCIENCE,
        grade=1,
        textbook_id="evs_class1",
        sections=[
            SectionNode(
                id="sec_001",
                type=SectionType.THEORETICAL,
                title="Parts of Our Body",
                content_text="Our body has many parts. We have two eyes, two ears, one nose, and one mouth. We use our hands to hold things. We use our legs to walk.",
                page_range=(1, 2),
                docling_refs=[DoclingRef(item_id="p1", page_number=1, label="TEXT")],
            ),
        ],
        page_range=(1, 2),
    )
    
    writer = ScriptWriter()
    scenes = writer.generate_chapter_script(chapter)
    
    print(f"Generated {len(scenes)} scenes for EVS")
    for i, scene in enumerate(scenes, 1):
        print_scene_summary(scene, i)
    
    return scenes


def main():
    print_banner("InkSpectrum Script Generation Demo")
    print("LLM: Groq openai/gpt-oss-120b")
    print("Models: hidream-o1 (image), h3-minimax-r2v (video), text-to-speech (TTS)")
    print("Renderers: Remotion (English/EVS/Social), Manim (Math)")
    
    try:
        english_scenes = demo_english()
        math_scenes = demo_math()
        evs_scenes = demo_evs()
        
        print_banner("SUMMARY")
        print(f"English scenes: {len(english_scenes)}")
        print(f"Math scenes: {len(math_scenes)}")
        print(f"EVS scenes: {len(evs_scenes)}")
        print(f"Total scenes: {len(english_scenes) + len(math_scenes) + len(evs_scenes)}")
        
        print("\n✅ Script generation demo complete")
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
