"""PDF extraction using Docling (for table-heavy pages)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from textbook_pipeline.core.ingestion.extractor import ExtractorProtocol
from textbook_pipeline.models.chapter import ChapterNode, SectionNode, Subject
from textbook_pipeline.models.chapter import SectionType, DoclingRef

logger = logging.getLogger(__name__)


class DoclingExtractor(ExtractorProtocol):
    """Docling-based extractor for complex PDFs with tables and figures."""

    def __init__(self):
        try:
            from docling.document_converter import DocumentConverter
            self._converter = DocumentConverter()
        except ImportError:
            logger.warning("Docling not installed. Install with: pip install docling")
            self._converter = None

    def extract(
        self,
        pdf_path: Path,
        subject: Subject,
        grade: int,
        textbook_id: str,
    ) -> ChapterNode:
        """Extract chapter using Docling."""
        if not self._converter:
            raise ImportError("Docling is required for this extractor")

        result = self._converter.convert(pdf_path)
        doc = result.document

        sections = []
        section_counter = 0

        for item in doc.iterate_items():
            if hasattr(item, "prov") and item.prov:
                page_no = item.prov[0].page_no
            else:
                page_no = 1

            text = item.text if hasattr(item, "text") else ""
            if not text:
                continue

            # Detect headings
            if item.label in ("title", "section_header", "heading"):
                section_counter += 1
                sections.append(SectionNode(
                    id=f"sec_{section_counter:03d}",
                    title=text.strip(),
                    type=SectionType.THEORETICAL,
                    content_text="",
                    page_start=page_no,
                    page_end=page_no,
                    word_count=0,
                    docling_refs=[DoclingRef(
                        page=page_no,
                        item_id=getattr(item, "id", f"item_{section_counter}"),
                        item_type=item.label,
                        text_segment=text,
                    )],
                ))
            elif item.label in ("paragraph", "text", "list_item") and sections:
                sections[-1].content_text += text + "\n"
                sections[-1].page_range = (sections[-1].page_range[0], max(sections[-1].page_range[1], page_no))
                sections[-1].word_count = len(sections[-1].content_text.split())

        if not sections:
            raise ValueError("No sections found in PDF")

        total_words = sum(s.word_count for s in sections)
        return ChapterNode(
            id=f"{textbook_id}_ch1",
            title=f"{subject.value.capitalize()} Chapter 1",
            subject=subject.value,
            grade=grade,
            textbook_id=textbook_id,
            number=1,
            page_range=(1, doc.num_pages()),
            sections=sections,
            total_word_count=total_words,
            estimated_duration_minutes=total_words / 140.0 / 60.0 * 60.0,
        )

    def extract_text_blocks(self, pdf_path: Path) -> List[dict]:
        """Extract text blocks using Docling."""
        if not self._converter:
            raise ImportError("Docling is required")

        result = self._converter.convert(pdf_path)
        blocks = []

        for item in result.document.iterate_items():
            if hasattr(item, "text") and item.text:
                page_no = 1
                if hasattr(item, "prov") and item.prov:
                    page_no = item.prov[0].page_no

                blocks.append({
                    "page_number": page_no,
                    "text": item.text,
                    "bbox": {"x": 0, "y": 0, "w": 1, "h": 1},
                    "block_type": item.label,
                    "quality": 1.0,
                })

        return blocks