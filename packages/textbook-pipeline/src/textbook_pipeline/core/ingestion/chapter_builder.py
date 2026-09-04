"""Chapter builder: assembles ChapterNode from extracted blocks."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from textbook_pipeline.models.chapter import (
    ChapterNode,
    SectionNode,
    SectionType,
    ExerciseNode,
    ExerciseType,
    DoclingRef,
)

logger = logging.getLogger(__name__)


class ChapterBuilder:
    """Builds a complete ChapterNode from raw extracted blocks."""

    def __init__(self):
        self._section_counter = 0

    def build(
        self,
        blocks: List[dict],
        subject: str,
        grade: int,
        textbook_id: str,
        chapter_number: int = 1,
    ) -> ChapterNode:
        """Build ChapterNode from text blocks."""
        self._section_counter = 0
        sections = self._group_into_sections(blocks)

        total_words = sum(s.word_count for s in sections)
        duration = total_words / 140.0 * 60.0

        return ChapterNode(
            id=f"{textbook_id}_ch{chapter_number}",
            title=f"{subject.capitalize()} Chapter {chapter_number}",
            subject=subject,
            grade=grade,
            textbook_id=textbook_id,
            number=chapter_number,
            page_range=self._compute_page_range(blocks),
            sections=sections,
            total_word_count=total_words,
            estimated_duration_minutes=duration / 60.0,
        )

    def _group_into_sections(self, blocks: List[dict]) -> List[SectionNode]:
        """Group text blocks into sections based on headings."""
        sections: List[SectionNode] = []
        current_section: Optional[SectionNode] = None

        for block in blocks:
            text = block.get("text", "").strip()
            block_type = block.get("block_type", "text")
            page = block.get("page_number", 1)

            # Detect exercise patterns
            if self._is_exercise_block(text, block_type):
                if current_section:
                    exercise = self._create_exercise(text, page, block)
                    current_section.exercises.append(exercise)
                continue

            # Detect headings
            if self._is_heading(text, block_type):
                if current_section:
                    sections.append(current_section)

                self._section_counter += 1
                current_section = SectionNode(
                    id=f"sec_{self._section_counter:03d}",
                    title=text,
                    type=SectionType.THEORETICAL,
                    content_text="",
                    page_start=page,
                    page_end=page,
                    word_count=0,
                    docling_refs=[DoclingRef(
                        page=page,
                        item_id=f"heading_{self._section_counter}",
                        item_type=block_type,
                        bbox=block.get("bbox"),
                        text_segment=text,
                    )],
                )
            elif current_section:
                current_section.content_text += text + "\n"
                current_section.page_range = (current_section.page_range[0], max(current_section.page_range[1], page))
                current_section.word_count = len(current_section.content_text.split())

                # Add docling ref
                current_section.docling_refs.append(DoclingRef(
                    page=page,
                    item_id=f"block_{len(current_section.docling_refs)}",
                    item_type=block_type,
                    bbox=block.get("bbox"),
                    text_segment=text[:500],
                ))

        if current_section:
            sections.append(current_section)

        return sections or [self._create_fallback_section(blocks)]

    def _is_heading(self, text: str, block_type: str) -> bool:
        """Heuristic: detect if a block is a section heading."""
        if block_type in ("heading", "title", "section_header"):
            return True
        if text.isupper() and 3 < len(text) < 80:
            return True
        if text.endswith(":") and len(text) < 60:
            return True
        return False

    def _is_exercise_block(self, text: str, block_type: str) -> bool:
        """Heuristic: detect exercise/question blocks."""
        exercise_keywords = ["question", "exercise", "q.", "q:", "problem", "fill in", "mcq"]
        return any(kw in text.lower() for kw in exercise_keywords)

    def _create_exercise(self, text: str, page: int, block: dict) -> ExerciseNode:
        """Create an ExerciseNode from a text block."""
        # Detect MCQ patterns
        options = []
        if any(line.strip().startswith(("a)", "b)", "c)", "d)")) for line in text.split("\n")):
            for line in text.split("\n"):
                line = line.strip()
                if line and line[0].lower() in "abcd" and line[1:2] in (")", "."):
                    options.append(line[2:].strip())

        exercise_type = ExerciseType.MCQ if options else ExerciseType.SHORT_ANSWER

        return ExerciseNode(
            id=f"ex_{self._section_counter:03d}_{len([e for s in [] for e in s.exercises]) + 1}",
            type=exercise_type,
            question_text=text,
            options=options if options else None,
            docling_refs=[DoclingRef(
                page=page,
                item_id=f"exercise_{self._section_counter}",
                item_type=block.get("block_type", "text"),
                bbox=block.get("bbox"),
                text_segment=text[:500],
            )],
        )

    def _create_fallback_section(self, blocks: List[dict]) -> SectionNode:
        """Create a single section when no headings are detected."""
        all_text = "\n".join(b.get("text", "") for b in blocks)
        return SectionNode(
            id="sec_001",
            title="Extracted Content",
            type=SectionType.THEORETICAL,
            content_text=all_text,
            page_start=1,
            page_end=max((b.get("page_number", 1) for b in blocks), default=1),
            word_count=len(all_text.split()),
        )

    def _compute_page_range(self, blocks: List[dict]) -> tuple[int, int]:
        """Compute (start_page, end_page) from blocks."""
        pages = [b.get("page_number", 1) for b in blocks]
        return (min(pages), max(pages)) if pages else (1, 1)