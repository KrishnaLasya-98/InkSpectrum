"""Abstract base for PDF extractors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from textbook_pipeline.models.chapter import ChapterNode, Subject


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