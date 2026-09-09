#!/usr/bin/env python3
"""Build EVS chapter.json from extracted markdown and summary data.

Creates a proper ChapterNode JSON structure from:
- evs_extracted.md (full markdown content)
- evs_summary.json (section metadata and image inventory)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from textbook_pipeline.models.chapter import ChapterNode, SectionNode, SectionType, Subject
from textbook_pipeline.models.script import SceneStepType

PROJECT_DIR = REPO_ROOT / "packages/textbook-pipeline/projects/evs_class1_output"
MD_PATH = PROJECT_DIR / "evs_extracted.md"
SUMMARY_PATH = PROJECT_DIR / "evs_summary.json"
OUTPUT_PATH = PROJECT_DIR / "chapter.json"


def parse_markdown_sections(md_path: Path) -> dict[str, str]:
    """Parse markdown into section_id -> content_text mapping using heading hierarchy."""
    text = md_path.read_text(encoding="utf-8")
    lines = text.split("\n")
    
    sections: dict[str, str] = {}
    current_heading = ""
    current_content: list[str] = []
    heading_stack: list[str] = []
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            # Save previous section
            if current_heading and current_content:
                sections[current_heading] = "\n".join(current_content).strip()
            # New heading
            level = len(stripped) - len(stripped.lstrip("#"))
            heading = stripped.lstrip("#").strip()
            # Update stack
            heading_stack = heading_stack[:level - 1] + [heading]
            current_heading = " > ".join(heading_stack)
            current_content = []
        else:
            current_content.append(line)
    
    # Save last section
    if current_heading and current_content:
        sections[current_heading] = "\n".join(current_content).strip()
    
    return sections


def classify_section(title: str, content: str, heading_level: int) -> str:
    """Classify section as theoretical or exercise using dynamic rules."""
    title_lower = title.lower()
    content_lower = content.lower()
    word_count = len(content_lower.split())

    # H1 is chapter title -> theoretical
    if heading_level == 1:
        return "theoretical"

    # Detect explicit exercise patterns
    exercise_patterns = re.compile(
        r"\b(tick|answer|discuss|fill|write|match|choose|correct|false|true|question|exercise|comprehen|speak|grammar|vocabulary|pronunciation|creative|listening|life skills|self assessment|assessment|activity)\b",
        re.IGNORECASE,
    )

    # Detect narrative/instructional content patterns
    narrative_indicators = re.compile(
        r"\b(there are|there is|this is|a story|once upon|let us read|read and enjoy|listen to|look at the|glossary|animals are|living beings|food|shelter|air|water|grow|survive)\b",
        re.IGNORECASE,
    )

    # Count question marks
    question_marks = content_lower.count("?")

    # Decision logic
    if word_count > 200:
        narrative_score = len(narrative_indicators.findall(content_lower))
        exercise_score = len(exercise_patterns.findall(content_lower))
        if narrative_score >= 2 and exercise_score < 3:
            return "theoretical"
        if exercise_score >= 3 and question_marks >= 2:
            return "exercise"
        if question_marks >= 2 and exercise_score >= 2:
            return "exercise"

    if word_count >= 50:
        if exercise_patterns.search(title_lower):
            return "exercise"
        if exercise_patterns.search(content_lower) and question_marks >= 1:
            return "exercise"

    # Short content or H3+ headings
    if heading_level >= 3:
        if exercise_patterns.search(title_lower):
            return "exercise"
        if len(content_lower.split()) < 80 and exercise_patterns.search(content_lower):
            return "exercise"

    # Hardcoded fallbacks for known patterns
    hardcoded = re.compile(
        r"(warm|saying|colour|smiley|comprehen|speaking ability|grammar|vocabulary|pronunciation|creative ability|listening ability|life skills|self assessment|assessment|answer the following|fill in the blanks|choose the correct answer|activity|let's recall|glossary)",
        re.IGNORECASE,
    )
    if hardcoded.search(title):
        return "exercise"

    return "theoretical"


def build_chapter():
    """Build chapter.json from EVS extracted data."""
    print("Loading EVS extraction data...")
    
    # Load markdown
    md_sections = parse_markdown_sections(MD_PATH)
    print(f"  Found {len(md_sections)} markdown sections")
    
    # Load summary for image inventory
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    image_map: dict[str, str] = {}
    for img in summary.get("images", []):
        image_map[img["filename"]] = img["path"]
    
    # Build sections
    sections = []
    section_id_counter = 1
    
    for sec_title, sec_content in md_sections.items():
        # Skip very short non-content headings (usually just page numbers or metadata)
        if len(sec_content.strip()) < 10 and not re.search(r'[a-zA-Z]{3,}', sec_content):
            continue
            
        # Determine heading level from title
        heading_level = 1
        if sec_title.startswith("#"):
            heading_level = len(sec_title) - len(sec_title.lstrip("#"))
            sec_title = sec_title.lstrip("#").strip()
        
        # Classify section
        section_type = classify_section(sec_title, sec_content, heading_level)
        
        # Sanitize content
        content_text = sec_content
        content_text = re.sub(r'!\[.*?\]\(.*?\)', '', content_text)
        content_text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', content_text)
        content_text = re.sub(r'\s+', ' ', content_text).strip()
        
        # Extract image references
        image_refs = []
        for img_filename in image_map.keys():
            if img_filename in sec_content:
                image_refs.append({
                    "item_id": img_filename,
                    "page_number": 0,  # Will be filled if we can parse it
                    "label": "image"
                })
        
        # Create section
        section = {
            "id": f"sec_{section_id_counter:03d}",
            "type": section_type,
            "title": sec_title,
            "content_text": content_text[:5000],  # Cap at 5000 chars
            "page_range": [0, 0],  # Will be updated if we can determine page
            "docling_refs": image_refs[:10],  # Limit to 10 refs per section
            "equations": [],
            "tables": [],
            "figures": [],
            "exercises": [],
            "estimated_duration_seconds": 0,
            "raw_blocks": None
        }
        sections.append(section)
        section_id_counter += 1
    
    # Build chapter
    chapter = {
        "id": "evs_class1_animal_life_ch8",
        "number": 8,
        "title": "EVS Chapter 8: Animal Life",
        "subject": "social",  # EVS maps to social
        "grade": 1,
        "textbook_id": "evs_class1_animal_life",
        "learning_objectives": [],
        "sections": sections,
        "page_range": [1, 8],
        "source_pdf": str(summary.get("source_pdf_path", "")),
        "total_estimated_duration_seconds": 0,
        "metadata": {
            "total_pages": summary.get("total_pages", 8),
            "total_images": summary.get("total_images", 39),
            "extraction_methods": summary.get("extraction_methods", {})
        }
    }
    
    # Save backup and updated chapter
    backup = OUTPUT_PATH.with_suffix(".json.bak")
    if not backup.exists():
        backup.write_text(json.dumps(chapter, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  Backup saved to: {backup}")
    
    OUTPUT_PATH.write_text(
        json.dumps(chapter, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  Saved chapter.json to: {OUTPUT_PATH}")
    
    # Print summary
    print("\nChapter structure:")
    theoretical_count = sum(1 for s in sections if s["type"] == "theoretical")
    exercise_count = sum(1 for s in sections if s["type"] == "exercise")
    print(f"  Total sections: {len(sections)}")
    print(f"  Theoretical: {theoretical_count}")
    print(f"  Exercise: {exercise_count}")
    print("\nSection details:")
    for s in sections:
        ct_len = len(s.get("content_text", "") or "")
        print(f"  {s['id']:10s} type={s['type']:12s} title={s['title'][:50]:50s} content={ct_len:4d}")


if __name__ == "__main__":
    build_chapter()
