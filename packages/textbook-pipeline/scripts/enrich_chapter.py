#!/usr/bin/env python3
"""Enrich chapter.json from opendataloader markdown output.

Fixes:
- Populates empty content_text from opendataloader markdown
- Classifies sections as theoretical vs exercise based on dynamic markdown structure
  (H1-H6 heading hierarchy) and contextual patterns, minimizing hardcoded rules.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

# Paths
CHAPTER_JSON = REPO_ROOT / "packages/textbook-pipeline/projects/english_pipeline_output/chapter.json"
OPENDATALOADER_MD = REPO_ROOT / "packages/textbook-pipeline/projects/opendataloader_evaluation/RPS - ENGLISH - CLASS 1 - INDIVIDUAL - A (2026) PRINTFILE (2)-pages-2/RPS - ENGLISH - CLASS 1 - INDIVIDUAL - A (2026) PRINTFILE (2)-pages-2.md"


@dataclass
class MarkdownBlock:
    """Represents a parsed markdown block with structural context."""

    heading_level: int  # 0 for non-heading, 1-6 for H1-H6
    text: str
    content: str = ""
    children: List["MarkdownBlock"] = field(default_factory=list)


class MarkdownStructureParser:
    """Dynamically identifies structural elements from markdown heading hierarchy.

    Instead of relying solely on hardcoded section titles, this parser uses:
    - Heading depth (H1-H6) to infer document structure
    - Sibling/child relationships to identify introductions, activities, summaries
    - Lightweight contextual cues (activity verbs, assessment keywords) as hints
    """

    # Lightweight contextual hints (not exhaustive, just guidance)
    _ACTIVITY_VERBS = re.compile(
        r"\b(tick|answer|discuss|fill|write|match|choose|correct|speak|read|listen|colour|color|draw|look|talk|think|ask|introduce|complete|practice|identify|differentiate|recognise|recognize)\b",
        re.IGNORECASE,
    )
    _SUMMARY_HINTS = re.compile(
        r"\b(summary|recap|what we learnt|what we learned|key points|revision|assessment|self assessment|evaluation)\b",
        re.IGNORECASE,
    )
    _INTRO_HINTS = re.compile(
        r"\b(introduction|preview|before you read|warm up|begin|let us begin|look at the picture|guess what|pre-reading)\b",
        re.IGNORECASE,
    )

    def __init__(self, md_path: Path) -> None:
        self.md_path = md_path
        self.blocks: List[MarkdownBlock] = []
        self.root: Optional[MarkdownBlock] = None

    def parse(self) -> List[MarkdownBlock]:
        """Parse markdown into hierarchical blocks."""
        text = self.md_path.read_text(encoding="utf-8")
        lines = text.split("\n")

        self.blocks = []
        stack: List[MarkdownBlock] = []  # tracks current heading ancestry

        current_heading: Optional[MarkdownBlock] = None
        current_content: List[str] = []

        def _flush_content() -> None:
            nonlocal current_content
            if current_heading is not None and current_content:
                current_heading.content = "\n".join(current_content).strip()
            current_content = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                _flush_content()
                level = len(stripped) - len(stripped.lstrip("#"))
                heading_text = stripped.lstrip("#").strip()
                block = MarkdownBlock(heading_level=level, text=heading_text)

                # Maintain hierarchy: pop stack until parent found
                while stack and stack[-1].heading_level >= level:
                    stack.pop()

                if stack:
                    stack[-1].children.append(block)
                else:
                    self.blocks.append(block)

                stack.append(block)
                current_heading = block
                current_content = []
            else:
                if current_heading is not None:
                    current_content.append(line)

        _flush_content()
        self.root = self.blocks[0] if self.blocks else None
        return self.blocks

    def classify_block(self, block: MarkdownBlock) -> str:
        """Classify a markdown block as 'theoretical' or 'exercise'.

        Decision tree:
        1. Use heading level + position in tree as primary signal
        2. Use content hints as secondary signal
        3. Default to 'theoretical' for ambiguous content
        """
        level = block.heading_level
        text_lower = block.text.lower()
        content_lower = (block.content or "").lower()

        # H1 is usually chapter title -> theoretical
        if level == 1:
            return "theoretical"

        # H2 is typically a major section
        if level == 2:
            if self._INTRO_HINTS.search(text_lower) or self._INTRO_HINTS.search(content_lower):
                return "exercise"
            if self._SUMMARY_HINTS.search(text_lower) or self._SUMMARY_HINTS.search(content_lower):
                return "exercise"
            # Check if content is activity-heavy
            activity_matches = len(self._ACTIVITY_VERBS.findall(content_lower))
            if activity_matches >= 3:
                return "exercise"
            return "theoretical"

        # H3-H6 are usually subsections, activities, or exercises
        if level >= 3:
            if self._SUMMARY_HINTS.search(text_lower) or self._SUMMARY_HINTS.search(content_lower):
                return "exercise"
            if self._INTRO_HINTS.search(text_lower) or self._INTRO_HINTS.search(content_lower):
                return "exercise"
            # Activity-heavy content
            activity_matches = len(self._ACTIVITY_VERBS.findall(content_lower))
            if activity_matches >= 2:
                return "exercise"
            # Short imperative text often indicates an exercise/activity
            if len(block.content.split()) < 80 and self._ACTIVITY_VERBS.search(text_lower):
                return "exercise"
            return "theoretical"

        return "theoretical"

    def get_section_hints(self, title: str) -> Dict[str, Any]:
        """Extract lightweight structural hints for a section title."""
        title_lower = title.lower()
        hints: Dict[str, Any] = {
            "is_intro": bool(self._INTRO_HINTS.search(title_lower)),
            "is_summary": bool(self._SUMMARY_HINTS.search(title_lower)),
            "is_activity": bool(self._ACTIVITY_VERBS.search(title_lower)),
        }
        return hints


def is_exercise_section(title: str, content: str = "", heading_level: int = 0) -> bool:
    """Classify section as exercise using dynamic markdown structure first.

    Priority:
    1. Markdown heading hierarchy (H1-H6) via structural parser
    2. Content-based analysis (narrative vs imperative vs questions)
    3. Lightweight title keyword hints (minimal hardcoding)
    """
    text_lower = title.lower()
    content_lower = (content or "").lower()
    word_count = len(content_lower.split())

    # H1 is chapter title -> theoretical
    if heading_level == 1:
        return False

    # H2-H6: analyze content style first
    # Narrative content (stories, explanations) -> theoretical
    # Short imperative prompts/questions -> exercise

    # Detect explicit exercise patterns in content
    explicit_exercise = re.compile(
        r"\b(tick|answer|discuss|fill|write|match|choose|correct|false|true|question|exercise|comprehen|speak|grammar|vocabulary|pronunciation|creative|listening|life skills|self assessment|assessment)\b",
        re.IGNORECASE,
    )

    # Detect narrative/instructional content patterns
    narrative_indicators = re.compile(
        r"\b(there are|there is|this is|a story|once upon|let us read|read and enjoy|listen to|look at the|glossary|shovel|basement|staircase|letters in the|alphabets|vowel|consonant|word forming|joined words|pronunciation|read the words|short /a/|favourite)\b",
        re.IGNORECASE,
    )

    # Count question marks (indicates exercises/questions)
    question_marks = content_lower.count("?")

    # Count bullet points with exercise-like patterns
    exercise_bullets = len(re.findall(r"^[-*]\s*(a\.|b\.|c\.|d\.|\d+\.)\s*", content_lower, re.MULTILINE))

    # Decision logic based on content analysis
    if word_count > 200:
        # Long content: check if it's narrative/instructional or exercise-heavy
        narrative_score = len(narrative_indicators.findall(content_lower))
        exercise_score = len(explicit_exercise.findall(content_lower))
        if narrative_score >= 2 and exercise_score < 3:
            return False  # Theoretical content
        if exercise_score >= 3 and question_marks >= 2:
            return True  # Exercise-heavy content
        # Long content with questions and bullet options -> exercise
        if question_marks >= 2 and exercise_bullets >= 2:
            return True

    # Medium content (50-200 words): check for explicit exercise patterns
    if word_count >= 50:
        if explicit_exercise.search(text_lower):
            return True
        if explicit_exercise.search(content_lower) and question_marks >= 1:
            return True

    # Short content (<50 words) or empty: use heading level + title
    # H3+ short content is often an exercise/activity header
    if heading_level >= 3:
        if explicit_exercise.search(text_lower):
            return True
        if len(content_lower.split()) < 80 and explicit_exercise.search(content_lower):
            return True

    # Fallback: minimal hardcoded title keywords (only for known unavoidable patterns)
    hardcoded = re.compile(
        r"(warm|saying|colour|smiley|comprehen|speaking ability|grammar|vocabulary|pronunciation|creative ability|listening ability|life skills|self assessment|assessment)",
        re.IGNORECASE,
    )
    return bool(hardcoded.search(title))


def parse_markdown_sections(md_path: Path) -> dict[str, str]:
    """Parse markdown into section_id -> content_text mapping.
    
    Uses heading hierarchy (##, ###) to identify sections.
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


def find_best_match(title: str, md_sections: dict[str, str]) -> str | None:
    """Find the best matching markdown section for a chapter section title."""
    title_lower = title.lower().strip()
    
    # Exact match
    for key in md_sections:
        if title_lower in key.lower():
            return md_sections[key]
    
    # Partial match - check if key words overlap
    title_words = set(re.findall(r'\w+', title_lower))
    best_key = None
    best_score = 0
    for key in md_sections:
        key_words = set(re.findall(r'\w+', key.lower()))
        overlap = len(title_words & key_words)
        if overlap > best_score:
            best_score = overlap
            best_key = key
    
    if best_key and best_score >= 2:
        return md_sections[best_key]
    
    return None


def enrich_chapter():
    """Main enrichment logic."""
    print("Loading chapter.json...")
    chapter = json.loads(CHAPTER_JSON.read_text(encoding="utf-8"))

    print("Loading opendataloader markdown...")
    md_sections = parse_markdown_sections(OPENDATALOADER_MD)
    print(f"  Found {len(md_sections)} markdown sections")

    # Dynamic structural analysis of the markdown document
    print("Parsing markdown structure (H1-H6 hierarchy)...")
    structure_parser = MarkdownStructureParser(OPENDATALOADER_MD)
    markdown_blocks = structure_parser.parse()
    print(f"  Parsed {len(markdown_blocks)} top-level markdown blocks")

    enriched = 0
    reclassified = 0

    for section in chapter["sections"]:
        old_type = section["type"]
        title = section["title"]

        # Fix empty content_text
        if not section.get("content_text"):
            content = find_best_match(title, md_sections)
            if content:
                section["content_text"] = content[:5000]  # Cap at 5000 chars
                enriched += 1
                print(f"  Enriched: {title[:40]} ({len(content)} chars)")

        # Reclassify exercise sections using dynamic structure
        # First try to find matching markdown block for this section title
        matched_block: Optional[MarkdownBlock] = None
        for block in markdown_blocks:
            if title.lower().strip() in block.text.lower().strip():
                matched_block = block
                break
            # Check children recursively
            stack = list(block.children)
            while stack:
                child = stack.pop()
                if title.lower().strip() in child.text.lower().strip():
                    matched_block = child
                    break
                stack.extend(child.children)
            if matched_block:
                break

        heading_level = matched_block.heading_level if matched_block else 0
        matched_content = matched_block.content if matched_block else ""

        if is_exercise_section(title, content=matched_content, heading_level=heading_level) and old_type == "theoretical":
            section["type"] = "exercise"
            reclassified += 1
            print(f"  Reclassified: {title[:40]} -> exercise (level={heading_level})")

    print(f"\nSummary:")
    print(f"  Enriched sections: {enriched}")
    print(f"  Reclassified sections: {reclassified}")

    # Save backup and updated chapter
    backup = CHAPTER_JSON.with_suffix(".json.bak")
    if not backup.exists():
        backup.write_text(CHAPTER_JSON.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"  Backup saved to: {backup}")

    CHAPTER_JSON.write_text(
        json.dumps(chapter, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  Updated chapter.json saved")

    # Print final section summary
    print("\nFinal section structure:")
    for s in chapter["sections"]:
        ct_len = len(s.get("content_text", "") or "")
        print(f"  {s['id']:10s} type={s['type']:12s} title={s['title'][:40]:40s} content={ct_len:4d}")


if __name__ == "__main__":
    enrich_chapter()
