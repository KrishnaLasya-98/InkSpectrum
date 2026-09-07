"""Abstract base for PDF extractors."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from textbook_pipeline.models.chapter import ChapterNode, Subject, SectionNode

logger = logging.getLogger(__name__)


class ExtractorProtocol(ABC):
    """Protocol for PDF-to-ChapterNode extractors."""

    @abstractmethod
    def extract(
        self,
        pdf_path: Path,
        subject: Subject,
        grade: int,
        textbook_id: str,
    ) -> ChapterNode:
        """Extract chapter structure from a PDF.

        Args:
            pdf_path: Path to PDF file
            subject: Detected or inferred subject
            grade: Grade level
            textbook_id: Source textbook identifier

        Returns:
            ChapterNode with sections and exercises
        """
        raise NotImplementedError

    @abstractmethod
    def extract_text_blocks(self, pdf_path: Path) -> List[dict]:
        """Extract raw text blocks from PDF pages.

        Returns:
            List of dicts with page_number, text, bbox, block_type
        """
        raise NotImplementedError

    def validate_extraction(self, chapter: ChapterNode) -> list[str]:
        """Validate extracted chapter structure and return list of issues."""
        issues: list[str] = []

        if not chapter.sections:
            issues.append("No sections extracted")
            return issues

        seen_ids: set[str] = set()
        for section in chapter.sections:
            if section.id in seen_ids:
                issues.append(f"Duplicate section ID: {section.id}")
            seen_ids.add(section.id)

            start, end = section.page_range
            if start > end:
                issues.append(f"Section {section.id} has invalid page range: {section.page_range}")

            if not section.title or len(section.title.strip()) < 3:
                issues.append(f"Section {section.id} has truncated/empty title")

            if section.title.endswith(("-", ":", ".")) and len(section.title) < 30:
                issues.append(f"Section {section.id} title looks truncated: {section.title!r}")

            if not section.content_text.strip():
                issues.append(f"Section {section.id} has empty content_text")

            toc_like = (
                any(chunk.strip().isdigit() for chunk in section.content_text.split()[:4])
                and len(section.content_text.split()) < 20
            )
            if toc_like:
                issues.append(f"Section {section.id} content looks like TOC/noise")

        return issues
