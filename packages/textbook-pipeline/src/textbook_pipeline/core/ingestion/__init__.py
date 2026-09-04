"""PDF ingestion and chapter extraction."""

from __future__ import annotations

from textbook_pipeline.core.ingestion.extractor import ExtractorProtocol
from textbook_pipeline.core.ingestion.pdfmux_extractor import PdfmuxExtractor
from textbook_pipeline.core.ingestion.docling_extractor import DoclingExtractor
from textbook_pipeline.core.ingestion.chapter_builder import ChapterBuilder
from textbook_pipeline.core.ingestion.subject_router import SubjectRouter, SubjectRouteResult

__all__ = [
    "ExtractorProtocol",
    "PdfmuxExtractor",
    "DoclingExtractor",
    "ChapterBuilder",
    "SubjectRouter",
    "SubjectRouteResult",
]