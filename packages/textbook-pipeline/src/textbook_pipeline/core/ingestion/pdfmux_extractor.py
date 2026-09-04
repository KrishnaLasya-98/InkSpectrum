"""PDF extraction using pdfmux (MIT-licensed, per-page quality scoring)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from textbook_pipeline.core.ingestion.extractor import ExtractorProtocol
from textbook_pipeline.models.chapter import ChapterNode, SectionNode, Subject
from textbook_pipeline.models.chapter import SectionType, ExerciseNode, ExerciseType, DoclingRef

logger = logging.getLogger(__name__)


class PdfmuxExtractor(ExtractorProtocol):
    """PDF extractor using pdfmux for born-digital and scanned PDFs."""

    def __init__(self, dpi: int = 150):
        self.dpi = dpi

    def extract(
        self,
        pdf_path: Path,
        subject: Subject,
        grade: int,
        textbook_id: str,
    ) -> ChapterNode:
        """Extract chapter structure from PDF."""
        blocks = self.extract_text_blocks(pdf_path)
        return self._build_chapter(blocks, subject, grade, textbook_id)

    def extract_text_blocks(self, pdf_path: Path) -> List[dict]:
        """Extract text blocks with page-level quality scores."""
        import pdfmux

        doc = pdfmux.open(pdf_path)
        blocks = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            quality = page.quality_score  # 0.0-1.0

            for block in page.text_blocks:
                blocks.append({
                    "page_number": page_num + 1,
                    "text": block.text,
                    "bbox": {
                        "x": block.bbox.x0,
                        "y": block.bbox.y0,
                        "w": block.bbox.width,
                        "h": block.bbox.height,
                    },
                    "block_type": "text",
                    "quality": quality,
                })

        doc.close()
        return blocks

    def _build_chapter(
        self,
        blocks: List[dict],
        subject: Subject,
        grade: int,
        textbook_id: str,
    ) -> ChapterNode:
        """Build ChapterNode from extracted blocks."""
        # Group blocks by page and detect sections
        sections = []
        current_section = None
        section_counter = 0

        for block in blocks:
            text = block.get("text", "")
            page = block.get("page_number", 1)

            # Simple heuristic: ALL CAPS lines are headings
            if text.isupper() and len(text) < 100:
                if current_section:
                    sections.append(current_section)

                section_counter += 1
                current_section = SectionNode(
                    id=f"sec_{section_counter:03d}",
                    title=text.strip(),
                    type=SectionType.THEORETICAL,
                    content_text="",
                    page_start=page,
                    page_end=page,
                    word_count=0,
                    docling_refs=[DoclingRef(
                        page=page,
                        item_id=f"heading_{section_counter}",
                        item_type="heading",
                        bbox=block.get("bbox"),
                        text_segment=text,
                    )],
                )
            elif current_section:
                current_section.content_text += text + "\n"
                current_section.page_range = (current_section.page_range[0], max(current_section.page_range[1], page))
                current_section.word_count = len(current_section.content_text.split())

        if current_section:
            sections.append(current_section)

        if not sections:
            # Fallback: single section with all content
            all_text = "\n".join(b.get("text", "") for b in blocks)
            sections = [SectionNode(
                id="sec_001",
                title=f"{subject.value.capitalize()} Chapter",
                type=SectionType.THEORETICAL,
                content_text=all_text,
                page_start=1,
                page_end=len(set(b["page_number"] for b in blocks)),
                word_count=len(all_text.split()),
            )]

        total_words = sum(s.word_count for s in sections)
        duration = total_words / 140.0 * 60.0  # 140 WPM

        return ChapterNode(
            id=f"{textbook_id}_ch1",
            title=f"{subject.value.capitalize()} Chapter 1",
            subject=subject.value,
            grade=grade,
            textbook_id=textbook_id,
            number=1,
            page_range=(1, max(b["page_number"] for b in blocks)),
            sections=sections,
            total_word_count=total_words,
            estimated_duration_minutes=duration / 60.0,
        )