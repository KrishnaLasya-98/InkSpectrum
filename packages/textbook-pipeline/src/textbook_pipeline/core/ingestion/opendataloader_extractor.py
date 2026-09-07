"""PDF extraction using OpenDataLoader output JSON."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List

from textbook_pipeline.core.ingestion.extractor import ExtractorProtocol
from textbook_pipeline.core.ingestion.chapter_builder import ChapterBuilder
from textbook_pipeline.models.chapter import ChapterNode, Subject

logger = logging.getLogger(__name__)


class OpenDataLoaderExtractor(ExtractorProtocol):
    """Extracts chapter structure from OpenDataLoader JSON output."""

    def __init__(self):
        self._builder = ChapterBuilder()

    def extract(
        self,
        pdf_path: Path,
        subject: Subject,
        grade: int,
        textbook_id: str,
    ) -> ChapterNode:
        """Extract chapter from OpenDataLoader JSON sidecar."""
        json_path = self._find_json_sidecar(pdf_path)
        if not json_path or not json_path.exists():
            raise FileNotFoundError(
                f"No OpenDataLoader JSON found for {pdf_path.name}. "
                f"Expected: {json_path}"
            )

        blocks = self._json_to_blocks(json_path)
        return self._builder.build(
            blocks=blocks,
            subject=subject.value,
            grade=grade,
            textbook_id=textbook_id,
            source_pdf=pdf_path,
        )

    def extract_text_blocks(self, pdf_path: Path) -> List[dict]:
        """Extract raw text blocks from OpenDataLoader JSON sidecar."""
        json_path = self._find_json_sidecar(pdf_path)
        if not json_path or not json_path.exists():
            return []
        return self._json_to_blocks(json_path)

    def _find_json_sidecar(self, pdf_path: Path) -> Path | None:
        """Find the matching OpenDataLoader JSON for a PDF."""
        stem = pdf_path.stem
        candidates = [
            pdf_path.with_suffix(".json"),
            pdf_path.parent / f"{stem}.json",
        ]
        # Also check common output directories
        for pattern in [pdf_path.parent / "*" / f"{stem}.json"]:
            candidates.extend(pdf_path.parent.glob(f"*/{stem}.json"))
        for c in candidates:
            if c.exists():
                return c
        return None

    def _json_to_blocks(self, json_path: Path) -> List[dict]:
        """Convert OpenDataLoader JSON `kids` into flat text blocks."""
        data = json.loads(json_path.read_text(encoding="utf-8"))
        kids = data.get("kids", [])
        blocks: List[dict] = []

        for item in kids:
            item_type = item.get("type", "paragraph")
            page = item.get("page number", item.get("page_number", 1))
            content = item.get("content", "")

            if not content:
                continue

            if item_type == "heading":
                blocks.append({
                    "text": content.strip(),
                    "block_type": "heading",
                    "page_number": page,
                    "bbox": item.get("bounding box"),
                })
            elif item_type == "paragraph":
                blocks.append({
                    "text": content.strip(),
                    "block_type": "paragraph",
                    "page_number": page,
                    "bbox": item.get("bounding box"),
                })
            elif item_type == "list":
                # Flatten list items into text blocks
                list_items = item.get("list items", [])
                list_text_parts = []
                for li in list_items:
                    li_content = li.get("content", "").strip()
                    if li_content:
                        list_text_parts.append(li_content)
                if list_text_parts:
                    blocks.append({
                        "text": "\n".join(list_text_parts),
                        "block_type": "list",
                        "page_number": page,
                        "bbox": item.get("bounding box"),
                    })
            elif item_type == "image":
                # Images are handled separately; skip for text blocks
                continue

        return blocks
