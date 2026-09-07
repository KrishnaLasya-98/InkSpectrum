#!/usr/bin/env python3
"""Test MinerU (magic-pdf) extraction on sample PDFs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

OUTPUT_DIR = Path("packages/textbook-pipeline/projects/mineru_evaluation")


def test_mineru(pdf_path: Path) -> dict:
    """Run MinerU extraction on a single PDF."""
    try:
        from magic_pdf.pdf_parse import parse_pdf
    except ImportError:
        return {"error": "magic-pdf not installed. Install with: pip install magic-pdf"}

    result = {
        "pdf": str(pdf_path),
        "exists": pdf_path.exists(),
        "pages": 0,
        "sections": 0,
        "images": 0,
        "tables": 0,
        "content_preview": "",
        "error": None,
    }

    if not pdf_path.exists():
        result["error"] = f"PDF not found: {pdf_path}"
        return result

    try:
        doc = parse_pdf(pdf_path)
        pages = getattr(doc, "pages", [])
        result["pages"] = len(pages)

        content_parts = []
        image_count = 0
        table_count = 0

        for page in pages:
            if hasattr(page, "blocks"):
                for block in page.blocks:
                    text = getattr(block, "text", "")
                    if text:
                        content_parts.append(text.strip())
                    image_count += len(getattr(block, "images", []))
                    table_count += len(getattr(block, "tables", []))

        result["images"] = image_count
        result["tables"] = table_count
        result["sections"] = len(content_parts)
        result["content_preview"] = " ".join(content_parts)[:500]

    except Exception as exc:
        result["error"] = str(exc)

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_mineru.py <pdf_path> [pdf_path2 ...]")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for pdf_str in sys.argv[1:]:
        pdf = Path(pdf_str)
        print(f"\n{'='*60}")
        print(f"Testing MinerU on: {pdf.name}")
        print(f"{'='*60}")
        result = test_mineru(pdf)
        results.append(result)

        if result["error"]:
            print(f"ERROR: {result['error']}")
        else:
            print(f"Pages: {result['pages']}")
            print(f"Sections: {result['sections']}")
            print(f"Images: {result['images']}")
            print(f"Tables: {result['tables']}")
            print(f"Content preview: {result['content_preview'][:200]}...")

    output_file = OUTPUT_DIR / "mineru_results.json"
    output_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\n✅ Results saved to: {output_file}")

    return 0 if all(r["error"] is None for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
