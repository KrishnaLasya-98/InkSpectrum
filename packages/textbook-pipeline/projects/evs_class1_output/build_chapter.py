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
# Fix: parents[3] from packages/textbook-pipeline/projects/evs_class1_output = D:\new_video_pip
# But if running from archive, parents[3] would be wrong. Use absolute path.
if not (REPO_ROOT / "packages").exists():
    REPO_ROOT = Path(r"D:\new_video_pip")
sys.path.insert(0, str(REPO_ROOT))

from textbook_pipeline.models.chapter import ChapterNode, SectionNode, SectionType, Subject
from textbook_pipeline.models.script import SceneStepType
from textbook_pipeline.utils.logger import PipelineLogger, LoggingConfig, run_with_logging

PROJECT_DIR = Path(r"D:\new_video_pip\packages\textbook-pipeline\projects\evs_class1_output")
MD_PATH = PROJECT_DIR / "evs_extracted.md"
SUMMARY_PATH = PROJECT_DIR / "evs_summary.json"
OUTPUT_PATH = PROJECT_DIR / "chapter.json"


def parse_markdown_sections(md_path: Path) -> dict[str, str]:
    """Parse markdown into section_id -> content_text mapping using heading hierarchy.
    
    Returns dict with full hierarchical titles as keys.
    """
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


def get_heading_level(title: str) -> int:
    """Extract heading level from a markdown title string.
    
    Handles both raw markdown headings ('# Title') and hierarchical titles ('H1 > H2 > H3').
    Returns 1-6 for known levels, defaults to 1.
    """
    # Check if it's a raw markdown heading
    if title.startswith("#"):
        return len(title) - len(title.lstrip("#"))
    
    # Count ">" separators to estimate depth in hierarchy
    # Each ">" adds one level of nesting
    depth = title.count(" > ") + 1
    return min(max(depth, 1), 6)


def classify_section(title: str, content: str, heading_level: int) -> str:
    """Classify section as theoretical or exercise using dynamic rules.
    
    Priority:
    1. Metadata/content-type detection (previews, TOC, summaries)
    2. Content-based analysis (narrative vs questions/exercises)
    3. Title-based exercise keyword detection
    4. Heading level as hint (H3+ more likely to be exercises/subsections)
    """
    title_lower = title.lower()
    content_lower = content.lower()
    word_count = len(content_lower.split())

    # FIRST: Detect metadata/non-content sections that should be theoretical
    metadata_patterns = re.compile(
        r"(section content previews|table of contents|preview|document structure|page-by-page|full structured content|odl_output|extraction method)",
        re.IGNORECASE,
    )
    if metadata_patterns.search(title_lower):
        return "theoretical"
    
    # Detect explicit exercise patterns in title and content
    exercise_patterns = re.compile(
        r"\b(tick|answer|discuss|fill|write|match|choose|correct|false|true|question|exercise|comprehen|speak|grammar|vocabulary|pronunciation|creative|listening|life skills|self assessment|assessment|activity)\b",
        re.IGNORECASE,
    )

    # Detect narrative/instructional content patterns
    narrative_indicators = re.compile(
        r"\b(there are|there is|this is|a story|once upon|let us read|read and enjoy|listen to|look at the|glossary|animals are|living beings|food|shelter|air|water|grow|survive)\b",
        re.IGNORECASE,
    )

    # Count question marks and exercise-like bullets
    question_marks = content_lower.count("?")
    exercise_bullets = len(re.findall(r"^[-*]\s*(a\.|b\.|c\.|d\.|\d+\.)\s*", content_lower, re.MULTILINE))

    # Content-based classification for longer text
    if word_count > 200:
        narrative_score = len(narrative_indicators.findall(content_lower))
        exercise_score = len(exercise_patterns.findall(content_lower))
        
        # Strong narrative signal -> theoretical
        if narrative_score >= 3 and exercise_score < 2:
            return "theoretical"
        
        # Strong exercise signal -> exercise
        if exercise_score >= 3 and (question_marks >= 1 or exercise_bullets >= 2):
            return "exercise"
        
        # Questions + bullets = exercise
        if question_marks >= 2 and exercise_bullets >= 2:
            return "exercise"

    # Medium content: check for explicit exercise patterns
    if word_count >= 50:
        if exercise_patterns.search(title_lower):
            return "exercise"
        if exercise_patterns.search(content_lower) and question_marks >= 1:
            return "exercise"

    # Short content / subsections: check title for exercise keywords
    # This catches "Glossary > I. Answer the following", "Glossary > II. Fill in the blanks", etc.
    if exercise_patterns.search(title_lower):
        return "exercise"
    
    # Check for numbered questions in title
    if re.search(r'\b(i+\.|ii+\.|iii+\.|iv+\.)\s*(answer|fill|choose|tick|write|match)\b', title_lower):
        return "exercise"

    # Heading level hint: H3+ are often subsections like exercises, activities, summaries
    if heading_level >= 4:
        # Check if content looks like exercise instructions
        if len(content_lower.split()) < 100 and (question_marks >= 1 or exercise_bullets >= 1):
            return "exercise"

    # Hardcoded fallbacks for known unavoidable patterns
    hardcoded = re.compile(
        r"(warm|saying|colour|smiley|comprehen|speaking ability|grammar|vocabulary|pronunciation|creative ability|listening ability|life skills|self assessment|assessment|answer the following|fill in the blanks|choose the correct answer|activity|let's recall)",
        re.IGNORECASE,
    )
    if hardcoded.search(title):
        return "exercise"
    
    # "Glossary" alone is not an exercise, but "Glossary > I. Answer..." is
    if "glossary" in title_lower:
        # Only classify as exercise if it contains actual exercise content
        if exercise_bullets >= 2 or question_marks >= 2:
            return "exercise"
        return "theoretical"

    return "theoretical"


def build_chapter():
    """Build chapter.json from EVS extracted data."""
    logger = PipelineLogger(LoggingConfig(output_dir=PROJECT_DIR / "logs"), project_name="evs_build_chapter")
    
    logger.stage_start("ingestion", "Building EVS chapter.json from extracted data")
    
    print("Loading EVS extraction data...")
    
    # Load markdown
    md_sections = parse_markdown_sections(MD_PATH)
    logger.info(f"Found {len(md_sections)} markdown sections")
    print(f"  Found {len(md_sections)} markdown sections")
    
    # Load summary for image inventory
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    image_map: dict[str, str] = {}
    for img in summary.get("images", []):
        image_map[img["filename"]] = img["path"]
    
    logger.info(f"Loaded {len(image_map)} images from summary")
    
    # Build sections with progress bar
    sections = []
    section_id_counter = 1
    skipped_metadata = 0
    
    bar = logger.create_progress_bar("sections", total=len(md_sections), desc="Processing sections")
    for sec_title, sec_content in md_sections.items():
        # Skip metadata/extraction artifacts that don't represent actual lesson sections
        metadata_titles = {
            "document structure", "sections / headings", "key sections identified",
            "page-by-page content", "full structured content (opendataloader markdown)",
            "section content previews", "odl_output", "evs class 1 - lesson 8: animal life"
        }
        title_lower = sec_title.lower()
        if any(meta in title_lower for meta in metadata_titles):
            skipped_metadata += 1
            logger.update_progress("sections", 1)
            continue
        
        # Skip very short non-content headings (usually just page numbers or metadata)
        if len(sec_content.strip()) < 10 and not re.search(r'[a-zA-Z]{3,}', sec_content):
            skipped_metadata += 1
            logger.update_progress("sections", 1)
            continue
        
        # Skip metadata-only sections (contain only source/format info)
        if re.search(r'\*\*Source PDF:\*\*|\*\*Total Pages:\*\*|\*\*Extraction Method:\*\*|\*\*Extracted Images:\*\*', sec_content):
            skipped_metadata += 1
            logger.update_progress("sections", 1)
            continue
        
        # Determine heading level from hierarchical title
        heading_level = get_heading_level(sec_title)
        
        # Classify section
        section_type = classify_section(sec_title, sec_content, heading_level)
        
        # Sanitize content
        content_text = sec_content
        # Remove standard markdown images: ![](url) or ![]<url>
        content_text = re.sub(r'!\[.*?\]\(.*?\)', '', content_text)
        content_text = re.sub(r'!\[\]\(.*?\)', '', content_text)
        content_text = re.sub(r'!\[\]<.*?>', '', content_text)
        # Remove partial/broken image references (filename-only remnants)
        content_text = re.sub(r'PRINTFILE-pages-2_images/[^\s)>]*', '', content_text)
        content_text = re.sub(r'imageFile\d+\.png[>)]*', '', content_text)
        # Remove stray image syntax remnants like ">)" or ">)"
        content_text = re.sub(r'>\s*\)', '', content_text)
        content_text = re.sub(r'\)\s*>', '', content_text)
        # Remove markdown links: [text](url) -> keep text
        content_text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', content_text)
        # Remove bold markers used as metadata
        content_text = re.sub(r'\*\*Source PDF:\*\*.*$', '', content_text, flags=re.MULTILINE)
        content_text = re.sub(r'\*\*Total Pages:\*\*.*$', '', content_text, flags=re.MULTILINE)
        content_text = re.sub(r'\*\*Extraction Method:\*\*.*$', '', content_text, flags=re.MULTILINE)
        content_text = re.sub(r'\*\*Extracted Images:\*\*.*$', '', content_text, flags=re.MULTILINE)
        # Clean up whitespace
        content_text = re.sub(r'\s+', ' ', content_text).strip()
        
        # Extract image references
        image_refs = []
        for img_filename in image_map.keys():
            if img_filename in sec_content:
                image_refs.append({
                    "item_id": img_filename,
                    "page_number": 0,
                    "label": "image"
                })
        
        # Create section
        section = {
            "id": f"sec_{section_id_counter:03d}",
            "type": section_type,
            "title": sec_title,
            "content_text": content_text[:5000],
            "page_range": [0, 0],
            "docling_refs": image_refs[:10],
            "equations": [],
            "tables": [],
            "figures": [],
            "exercises": [],
            "estimated_duration_seconds": 0,
            "raw_blocks": None
        }
        sections.append(section)
        section_id_counter += 1
        logger.update_progress("sections", 1)
    
    logger.close_progress("sections")
    logger.info(f"Skipped {skipped_metadata} metadata/artifact sections")
    
    # Build chapter
    chapter = {
        "id": "evs_class1_animal_life_ch8",
        "number": 8,
        "title": "EVS Chapter 8: Animal Life",
        "subject": "social",
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
        logger.info(f"Backup saved to: {backup}")
    
    OUTPUT_PATH.write_text(
        json.dumps(chapter, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(f"Saved chapter.json to: {OUTPUT_PATH}")
    
    # Print summary
    theoretical_count = sum(1 for s in sections if s["type"] == "theoretical")
    exercise_count = sum(1 for s in sections if s["type"] == "exercise")
    logger.info(f"Chapter structure: {len(sections)} sections ({theoretical_count} theoretical, {exercise_count} exercise)")
    
    print("\nChapter structure:")
    print(f"  Total sections: {len(sections)}")
    print(f"  Theoretical: {theoretical_count}")
    print(f"  Exercise: {exercise_count}")
    print("\nSection details:")
    for s in sections:
        ct_len = len(s.get("content_text", "") or "")
        print(f"  {s['id']:10s} type={s['type']:12s} title={s['title'][:50]:50s} content={ct_len:4d}")
    
    logger.stage_end("ingestion", "chapter.json built successfully")
    logger.close_all_progress()


if __name__ == "__main__":
    build_chapter()
