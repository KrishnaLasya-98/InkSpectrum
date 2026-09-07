"""Tests for PDF extraction pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from textbook_pipeline.models.chapter import (
    ChapterNode,
    SectionNode,
    SectionType,
    Subject,
    ImageAsset,
)
from textbook_pipeline.core.ingestion.pymupdf_extractor import PyMuPDFExtractor


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _require_fixture_pdf() -> Path:
    pdf = FIXTURE_DIR / "sample.pdf"
    if not pdf.exists():
        pytest.skip(f"Fixture PDF not found: {pdf}")
    return pdf


def test_extract_chapters_returns_chapter_node():
    pdf = _require_fixture_pdf()
    extractor = PyMuPDFExtractor()
    chapter = extractor.extract_chapters(
        pdf_path=pdf,
        subject=Subject.ENGLISH,
        grade=1,
        textbook_id="test_book",
    )

    assert isinstance(chapter, ChapterNode)
    assert chapter.subject == Subject.ENGLISH
    assert chapter.grade == 1
    assert chapter.total_pages() >= 1


def test_sections_have_valid_page_ranges():
    pdf = _require_fixture_pdf()
    extractor = PyMuPDFExtractor()
    chapter = extractor.extract_chapters(
        pdf_path=pdf,
        subject=Subject.ENGLISH,
        grade=1,
        textbook_id="test_book",
    )

    for section in chapter.sections:
        start, end = section.page_range
        assert start <= end, f"Section {section.id} has invalid page range: {section.page_range}"
        assert start >= 1
        assert end <= chapter.total_pages()


def test_no_truncated_titles():
    pdf = _require_fixture_pdf()
    extractor = PyMuPDFExtractor()
    chapter = extractor.extract_chapters(
        pdf_path=pdf,
        subject=Subject.ENGLISH,
        grade=1,
        textbook_id="test_book",
    )

    for section in chapter.sections:
        title = section.title.strip()
        assert len(title) >= 3, f"Section {section.id} title too short: {title!r}"
        assert not title.endswith("-"), f"Section {section.id} title looks truncated: {title!r}"


def test_sections_have_content():
    pdf = _require_fixture_pdf()
    extractor = PyMuPDFExtractor()
    chapter = extractor.extract_chapters(
        pdf_path=pdf,
        subject=Subject.ENGLISH,
        grade=1,
        textbook_id="test_book",
    )

    for section in chapter.sections:
        assert section.content_text.strip(), f"Section {section.id} has empty content_text"


def test_validation_issues_are_detected(tmp_path: Path):
    chapter = ChapterNode(
        id="test_ch1",
        number=1,
        title="Test",
        subject=Subject.ENGLISH,
        grade=1,
        textbook_id="test",
        sections=[
            SectionNode(
                id="sec_1",
                type=SectionType.THEORETICAL,
                title="A",
                content_text="",
                page_range=(2, 1),
            )
        ],
        page_range=(1, 1),
        source_pdf=tmp_path / "x.pdf",
    )

    extractor = PyMuPDFExtractor()
    issues = extractor.validate_extraction(chapter)
    assert any("empty content_text" in issue for issue in issues)
    assert any("invalid page range" in issue for issue in issues)


def test_blueprint_json_is_serializable(tmp_path: Path):
    pdf = _require_fixture_pdf()
    extractor = PyMuPDFExtractor()
    chapter = extractor.extract_chapters(
        pdf_path=pdf,
        subject=Subject.ENGLISH,
        grade=1,
        textbook_id="test_book",
    )

    data = chapter.model_dump(mode="json")
    dumped = json.dumps(data)
    assert isinstance(dumped, str)
    assert len(dumped) > 0
