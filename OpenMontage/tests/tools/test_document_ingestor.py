import json
import zipfile
from pathlib import Path

import pytest

from tools.extract.document_ingestor import ingest_document


def test_markdown_ingestion_uses_canonical_outputs(tmp_path: Path):
    source = tmp_path / "lesson.md"
    source.write_text("# Weather\n\nRain falls from clouds.\n", encoding="utf-8")

    result = ingest_document(source, output_dir=tmp_path / "artifacts")

    assert Path(result["markdown_path"]).read_text(encoding="utf-8").startswith("# Weather")
    artifact = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    assert artifact["source_format"] == "md"
    assert artifact["layout_pages"] == []


def test_plain_text_ingestion_promotes_first_line_to_chapter_heading(tmp_path: Path):
    source = tmp_path / "lesson.txt"
    source.write_text(
        "Weather\nRain falls from clouds.\nWind moves the leaves.\n",
        encoding="utf-8",
    )

    result = ingest_document(source, output_dir=tmp_path / "artifacts")

    assert result["markdown"].startswith("# Weather\n")
    assert "Rain falls from clouds." in result["markdown"]
    artifact = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    assert artifact["source_format"] == "txt"


def test_docx_ingestion_preserves_paragraph_order_and_table_cells(tmp_path: Path):
    source = tmp_path / "lesson.docx"
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body>
        <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Plants</w:t></w:r></w:p>
        <w:p><w:r><w:t>Plants need water.</w:t></w:r></w:p>
        <w:tbl>
          <w:tr><w:tc><w:p><w:r><w:t>Plant</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Use</w:t></w:r></w:p></w:tc></w:tr>
          <w:tr><w:tc><w:p><w:r><w:t>Cotton</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Clothes</w:t></w:r></w:p></w:tc></w:tr>
        </w:tbl>
      </w:body>
    </w:document>"""
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("word/document.xml", document_xml)

    result = ingest_document(source, output_dir=tmp_path / "artifacts")
    markdown = result["markdown"]

    assert markdown.index("# Plants") < markdown.index("Plants need water.")
    assert "| Plant | Use |" in markdown
    assert "| Cotton | Clothes |" in markdown


def test_unsupported_document_format_fails_closed(tmp_path: Path):
    source = tmp_path / "lesson.csv"
    source.write_text("a,b", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported input format"):
        ingest_document(source, output_dir=tmp_path / "artifacts")
