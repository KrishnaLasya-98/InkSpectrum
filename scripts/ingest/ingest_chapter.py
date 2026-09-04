"""Script: ingest a chapter PDF."""

from __future__ import annotations

from pathlib import Path

from textbook_pipeline.core.ingestion.pdfmux_extractor import PdfmuxExtractor
from textbook_pipeline.core.ingestion.subject_router import SubjectRouter
from textbook_pipeline.models.chapter import Subject

def main():
    pdf_path = Path("input.pdf")
    extractor = PdfmuxExtractor()
    chapter = extractor.extract(pdf_path, Subject.ENGLISH, 1, "test")
    print(f"Extracted: {chapter.title}, {len(chapter.sections)} sections")

if __name__ == "__main__":
    main()
