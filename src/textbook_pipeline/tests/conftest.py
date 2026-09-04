"""Pytest configuration and shared fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def sample_pdf_path() -> Path:
    return Path(__file__).parent / "fixtures" / "sample_pdfs" / "sample_chapter.pdf"


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    return tmp_path / "output"
