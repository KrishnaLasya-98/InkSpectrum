"""OpenDataLoader extractor tool wrapper.

Adopts the OpenMontage `BaseTool` contract. The actual logic lives in
`textbook_pipeline.core.ingestion.opendataloader_extractor.OpenDataLoaderExtractor`,
re-exported here for the top-level tool registry.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from tools.base_tool import BaseTool, ToolMetadata, ToolTier, ToolRuntime, ToolStability
from lib.tool_registry import register_tool
from textbook_pipeline.core.ingestion.opendataloader_extractor import OpenDataLoaderExtractor
from textbook_pipeline.core.ingestion.chapter_builder import ChapterBuilder
from textbook_pipeline.models.chapter import Subject

logger = logging.getLogger(__name__)


class OpenDataLoaderTool(BaseTool):
    metadata = ToolMetadata(
        name="opendataloader_extract",
        version="1.0.0",
        tier=ToolTier.SOURCE,
        capability="pdf_extraction",
        provider="opendataloader",
        runtime=ToolRuntime.LOCAL,
        stability=ToolStability.PRODUCTION,
        estimated_cost_usd=0.0,
        description="Extract structured chapter nodes from OpenDataLoader JSON output",
        dependencies=["python:opendataloader_pdf"],
    )

    def __init__(self):
        self._extractor = OpenDataLoaderExtractor()

    def run(self, input: dict[str, Any]) -> dict[str, Any]:
        pdf_path = Path(input["pdf_path"])
        subject = Subject(input.get("subject", "english"))
        grade = int(input.get("grade", 1))
        textbook_id = input.get("textbook_id", pdf_path.stem)
        output_json = input.get("output_json")

        chapter = self._extractor.extract(
            pdf_path=pdf_path,
            subject=subject,
            grade=grade,
            textbook_id=textbook_id,
        )

        out_path: Path | None = None
        if output_json:
            out_path = Path(output_json)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(chapter.model_dump_json(indent=2), encoding="utf-8")

        return {
            "chapter_id": chapter.id,
            "section_count": len(chapter.sections),
            "page_range": list(chapter.page_range),
            "output_json": str(out_path) if out_path else None,
            "sections": [s.model_dump(mode="json") for s in chapter.sections],
        }


register_tool(OpenDataLoaderTool())
