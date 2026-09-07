#!/usr/bin/env python3
"""Test OpenDataLoader PDF extraction on sample PDFs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

OUTPUT_DIR = Path("packages/textbook-pipeline/projects/opendataloader_evaluation")


def test_opendataloader(pdf_path: Path) -> dict:
    """Run OpenDataLoader PDF extraction on a single PDF."""
    try:
        import opendataloader_pdf
    except ImportError:
        return {"error": "opendataloader-pdf not installed. Install with: pip install opendataloader-pdf"}

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
        out_dir = OUTPUT_DIR / pdf_path.stem
        out_dir.mkdir(parents=True, exist_ok=True)

        opendataloader_pdf.convert(
            input_path=[str(pdf_path)],
            output_dir=str(out_dir),
            format="json,html,pdf,markdown",
        )

        # Read generated JSON if available
        json_files = list(out_dir.glob("*.json"))
        if json_files:
            data = json.loads(json_files[0].read_text(encoding="utf-8"))
            result["pages"] = data.get("number of pages", 0)
            kids = data.get("kids", [])
            result["sections"] = len(kids)
            image_count = 0
            table_count = 0
            content_parts = []
            for item in kids:
                content = item.get("content", "")
                if content:
                    content_parts.append(content)
                if item.get("type") == "image":
                    image_count += 1
                if item.get("type") == "table":
                    table_count += 1
            result["images"] = image_count
            result["tables"] = table_count
            result["content_preview"] = " ".join(content_parts)[:500]
        else:
            result["error"] = "No JSON output found in " + str(out_dir)

    except Exception as exc:
        result["error"] = str(exc)

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_opendataloader.py <pdf_path> [pdf_path2 ...]")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for pdf_str in sys.argv[1:]:
        pdf = Path(pdf_str)
        print(f"\n{'='*60}")
        print(f"Testing OpenDataLoader PDF on: {pdf.name}")
        print(f"{'='*60}")
        result = test_opendataloader(pdf)
        results.append(result)

        if result["error"]:
            print(f"ERROR: {result['error']}")
        else:
            print(f"Pages: {result['pages']}")
            print(f"Sections: {result['sections']}")
            print(f"Images: {result['images']}")
            print(f"Tables: {result['tables']}")
            print(f"Content preview: {result['content_preview'][:200]}...")

    output_file = OUTPUT_DIR / "opendataloader_results.json"
    output_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\n✅ Results saved to: {output_file}")

    return 0 if all(r["error"] is None for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
