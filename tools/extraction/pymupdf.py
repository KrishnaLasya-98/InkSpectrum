"""PDF-to-ChapterNode via local layout analysis (PyMuPDF)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.base_tool import BaseTool, ToolMetadata, ToolTier, ToolRuntime, ToolStability
from lib.tool_registry import register_tool
from textbook_pipeline.core.ingestion.pymupdf_extractor import PyMuPDFExtractor
from textbook_pipeline.models.chapter import Subject


class PyMuPDFTool(BaseTool):
    metadata = ToolMetadata(
        name="pymupdf_extract",
        version="1.0.0",
        tier=ToolTier.SOURCE,
        capability="pdf_extraction",
        provider="pymupdf",
        runtime=ToolRuntime.LOCAL,
        stability=ToolStability.BETA,
        estimated_cost_usd=0.0,
        description="Local PyMuPDF extractor for fallback PDF parsing",
        dependencies=["python:fitz"],
    )

    def __init__(self):
        self._extractor = PyMuPDFExtractor()

    def run(self, input: dict[str, Any]) -> dict[str, Any]:
        chapter = self._extractor.extract_chapters(
            pdf_path=Path(input["pdf_path"]),
            subject=Subject(input.get("subject", "english")),
            grade=int(input.get("grade", 1)),
            textbook_id=input.get("textbook_id", "unknown"),
        )
        out_path = input.get("output_json")
        if out_path:
            p = Path(out_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(chapter.model_dump_json(indent=2), encoding="utf-8")
        return {
            "chapter_id": chapter.id,
            "section_count": len(chapter.sections),
            "page_range": list(chapter.page_range),
        }


register_tool(PyMuPDFTool())
