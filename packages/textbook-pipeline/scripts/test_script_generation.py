#!/usr/bin/env python3
"""Test script generation on extracted English/EVS PDFs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add package src to path from script location
PACKAGE_SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(PACKAGE_SRC))

from textbook_pipeline.models.chapter import ChapterNode, SectionNode, SectionType, Subject, DoclingRef
from textbook_pipeline.core.script.writer import ScriptWriter
from textbook_pipeline.core.script.planner import ScenePlanner


def load_opendataloader_json(json_path: Path) -> dict:
    """Load OpenDataLoader JSON output."""
    return json.loads(json_path.read_text(encoding="utf-8"))


def convert_to_chapter_node(data: dict, subject: Subject, grade: int, json_path: Path) -> ChapterNode:
    """Convert OpenDataLoader JSON to ChapterNode."""
    sections = []
    section_counter = 0
    
    current_section = None
    current_content = []
    
    for item in data.get("kids", []):
        item_type = item.get("type")
        page = item.get("page number", 1)
        content = item.get("content", "").strip()
        
        if not content:
            continue
        
        if item_type == "heading":
            if current_section and current_content:
                current_section.content_text = " ".join(current_content)
                sections.append(current_section)
                current_content = []
            
            section_counter += 1
            current_section = SectionNode(
                id=f"sec_{section_counter:03d}",
                type=SectionType.THEORETICAL,  # Will be reclassified later
                title=content,
                content_text="",
                page_range=(page, page),
                docling_refs=[DoclingRef(
                    item_id=f"odl_{item.get('id', section_counter)}",
                    page_number=page,
                    label=item_type.upper(),
                )],
            )
        elif item_type in ("paragraph", "list"):
            current_content.append(content)
            if current_section:
                current_section.page_range = (
                    current_section.page_range[0],
                    max(current_section.page_range[1], page),
                )
    
    if current_section and current_content:
        current_section.content_text = " ".join(current_content)
        sections.append(current_section)
    
    if not sections:
        # Fallback: create one section with all text
        all_text = " ".join(
            item.get("content", "").strip()
            for item in data.get("kids", [])
            if item.get("content", "").strip()
        )
        sections.append(SectionNode(
            id="sec_001",
            type=SectionType.THEORETICAL,
            title=data.get("file name", "Extracted Content"),
            content_text=all_text,
            page_range=(1, data.get("number of pages", 1)),
            docling_refs=[],
        ))
    
    # Infer PDF path from JSON path
    pdf_path = json_path.with_suffix(".pdf")
    if not pdf_path.exists():
        pdf_path = Path("C:/Users/user/Downloads") / json_path.name.replace(".json", ".pdf")
    
    return ChapterNode(
        id=f"{subject.value}_ch1",
        number=1,
        title=sections[0].title if sections else "Extracted Chapter",
        subject=subject,
        grade=grade,
        textbook_id=data.get("file name", "unknown"),
        sections=sections,
        page_range=(1, data.get("number of pages", 1)),
        source_pdf=pdf_path,
    )


def main():
    if len(sys.argv) < 4:
        print("Usage: python test_script_generation.py <json_path> <subject> <grade>")
        print("Example: python test_script_generation.py 'RPS - ENGLISH...json' english 1")
        sys.exit(1)
    
    json_path = Path(sys.argv[1])
    subject_str = sys.argv[2].lower()
    grade = int(sys.argv[3])
    
    if not json_path.exists():
        print(f"ERROR: File not found: {json_path}")
        sys.exit(1)
    
    try:
        subject = Subject(subject_str)
    except ValueError:
        print(f"ERROR: Invalid subject '{subject_str}'. Choose: english, math, science, social")
        sys.exit(1)
    
    print(f"Loading: {json_path.name}")
    data = load_opendataloader_json(json_path)
    
    print(f"Converting to ChapterNode...")
    chapter = convert_to_chapter_node(data, subject, grade, json_path)
    print(f"  Sections: {len(chapter.sections)}")
    for sec in chapter.sections:
        print(f"    - {sec.title} ({sec.type.value}, pages {sec.page_range[0]}-{sec.page_range[1]})")
    
    print(f"\nInitializing ScriptWriter...")
    try:
        writer = ScriptWriter()
    except ValueError as e:
        print(f"ERROR: {e}")
        print("Set GROQ_API_KEY environment variable")
        sys.exit(1)
    
    print(f"Generating script with Groq...")
    try:
        scenes = writer.generate_chapter_script(chapter)
        print(f"✅ Generated {len(scenes)} scenes")
        
        for i, scene in enumerate(scenes, 1):
            print(f"\n--- Scene {i}: {scene.title} ---")
            print(f"  Duration: {scene.duration_seconds}s")
            print(f"  Voiceover lines: {len(scene.voiceover_lines)}")
            for vl in scene.voiceover_lines[:3]:
                print(f"    - {vl.text[:100]}...")
            print(f"  Scene steps: {len(scene.scene_steps)}")
            for step in scene.scene_steps[:5]:
                print(f"    - [{step.type.value}] {step.text or step.latex or '...'}")
        
        # Save output
        output_path = json_path.parent / f"{json_path.stem}_script.json"
        output_data = [scene.model_dump() for scene in scenes]
        output_path.write_text(json.dumps(output_data, indent=2, default=str), encoding="utf-8")
        print(f"\n✅ Script saved to: {output_path}")
        
    except Exception as e:
        print(f"ERROR during script generation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
