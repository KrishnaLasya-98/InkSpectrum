"""Format-neutral educational document ingestion.

PDFs use the layout-aware HybridPDFExtractor. Markdown, plain text, and DOCX
are normalized into the same extracted Markdown/artifact pair so the remaining
educational pipeline does not contain format-specific branches.
"""
from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from tools.extract.hybrid_pdf_extractor import HybridPDFExtractor


SUPPORTED_INPUT_SUFFIXES = {".pdf", ".md", ".markdown", ".txt", ".docx"}
_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_NS = {"w": _W_NS}


def _docx_text(path: Path) -> str:
    """Extract DOCX paragraphs and tables in document order."""

    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise ValueError(f"Invalid DOCX file: {path}: {exc}") from exc

    root = ElementTree.fromstring(xml)
    body = root.find("w:body", _NS)
    if body is None:
        raise ValueError(f"DOCX contains no document body: {path}")

    output: list[str] = []
    for child in list(body):
        local_name = child.tag.rsplit("}", 1)[-1]
        if local_name == "p":
            text = "".join(node.text or "" for node in child.findall(".//w:t", _NS)).strip()
            if not text:
                continue
            style_node = child.find("./w:pPr/w:pStyle", _NS)
            style = ""
            if style_node is not None:
                style = style_node.attrib.get(f"{{{_W_NS}}}val", "")
            heading = re.match(r"Heading\s*([1-6])", style, re.I)
            output.append(f"{'#' * int(heading.group(1))} {text}" if heading else text)
        elif local_name == "tbl":
            rows: list[list[str]] = []
            for row in child.findall("./w:tr", _NS):
                cells = []
                for cell in row.findall("./w:tc", _NS):
                    value = " ".join(
                        text.strip()
                        for text in (
                            "".join(node.text or "" for node in paragraph.findall(".//w:t", _NS))
                            for paragraph in cell.findall(".//w:p", _NS)
                        )
                        if text.strip()
                    )
                    cells.append(value)
                if cells:
                    rows.append(cells)
            if rows:
                width = max(len(row) for row in rows)
                padded = [row + [""] * (width - len(row)) for row in rows]
                output.append("| " + " | ".join(padded[0]) + " |")
                output.append("| " + " | ".join(["---"] * width) + " |")
                output.extend("| " + " | ".join(row) + " |" for row in padded[1:])
    return "\n\n".join(output).strip() + "\n"


def _plain_text_to_markdown(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() in {".md", ".markdown"}:
        return text
    nonempty = [line.strip() for line in text.splitlines() if line.strip()]
    if not nonempty:
        return ""
    return f"# {nonempty[0]}\n\n" + "\n\n".join(nonempty[1:]) + "\n"


def ingest_document(
    source_path: str | Path,
    *,
    output_dir: str | Path,
    subject_type: str = "mixed",
    preextracted_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Return the canonical extraction payload for a supported document."""

    source = Path(source_path).resolve()
    suffix = source.suffix.lower()
    if not source.is_file():
        raise ValueError(f"Source document not found: {source}")
    if suffix not in SUPPORTED_INPUT_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_INPUT_SUFFIXES))
        raise ValueError(f"Unsupported input format {suffix!r}; supported: {supported}")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if preextracted_dir:
        prepared = Path(preextracted_dir).expanduser().resolve()
        markdown_files = sorted(prepared.glob("*.md"))
        json_files = sorted(prepared.glob("*.json"))
        if len(markdown_files) != 1 or len(json_files) != 1:
            raise ValueError(
                "Pre-extracted input must contain exactly one Markdown file and one JSON file"
            )
        markdown = markdown_files[0].read_text(encoding="utf-8")
        artifact = json.loads(json_files[0].read_text(encoding="utf-8"))
        markdown_path = output / "extracted_content.md"
        artifact_path = output / "extracted_content.json"
        shutil.copy2(markdown_files[0], markdown_path)
        shutil.copy2(json_files[0], artifact_path)
        source_images = prepared / "images"
        if source_images.is_dir():
            shutil.copytree(source_images, output / "images", dirs_exist_ok=True)
        return {
            "markdown": markdown,
            "structured_json": artifact,
            "extraction_tool_used": "opendataloader_hybrid_preextracted",
            "confidence_score": 1.0,
            "markdown_path": str(markdown_path),
            "artifact_path": str(artifact_path),
        }
    if suffix == ".pdf":
        result = HybridPDFExtractor().execute({
            "pdf_path": str(source),
            "subject_type": subject_type,
            "output_dir": str(output),
        })
        if not result.success:
            raise RuntimeError(result.error or "PDF extraction failed")
        return result.data

    markdown = _docx_text(source) if suffix == ".docx" else _plain_text_to_markdown(source)
    if not markdown.strip():
        raise ValueError(f"Source document contains no readable text: {source}")

    markdown_path = output / "extracted_content.md"
    artifact_path = output / "extracted_content.json"
    markdown_path.write_text(markdown, encoding="utf-8")
    artifact = {
        "version": "1.1",
        "title": source.stem,
        "source_document": str(source),
        "source_format": suffix.lstrip("."),
        "extraction_tool_used": "openmontage-document-ingestor",
        "confidence_score": 1.0,
        "total_pages": 1,
        "pages_extracted": 1,
        "layout_pages": [],
        "sections": [{
            "section_id": "s1",
            "title": source.stem,
            "content": markdown,
            "content_preview": markdown[:500],
            "content_type": subject_type,
        }],
        "metadata": {
            "layout_geometry_available": False,
            "source_format": suffix.lstrip("."),
        },
    }
    artifact_path.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return {
        "markdown": markdown,
        "structured_json": artifact,
        "extraction_tool_used": artifact["extraction_tool_used"],
        "confidence_score": 1.0,
        "markdown_path": str(markdown_path),
        "artifact_path": str(artifact_path),
    }
