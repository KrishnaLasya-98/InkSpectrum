#!/usr/bin/env python3
"""Analyze OpenDataLoader PDF output and compare with baseline."""

from __future__ import annotations

import json
import sys
from pathlib import Path

OUTPUT_DIR = Path("C:/Users/user/Downloads/opendataloader_output")


def analyze_pdf(json_path: Path) -> dict:
    """Analyze a single OpenDataLoader JSON output."""
    if not json_path.exists():
        return {"error": f"File not found: {json_path}"}

    data = json.loads(json_path.read_text(encoding="utf-8"))
    kids = data.get("kids", [])

    analysis = {
        "pdf": data.get("file name", json_path.stem),
        "pages": data.get("number of pages", 0),
        "total_elements": len(kids),
        "headings": 0,
        "paragraphs": 0,
        "images": 0,
        "lists": 0,
        "list_items": 0,
        "pages_with_content": set(),
        "heading_levels": {},
        "sample_headings": [],
        "sample_paragraphs": [],
        "image_sources": [],
        "issues": [],
    }

    for item in kids:
        item_type = item.get("type")
        page = item.get("page number")
        analysis["pages_with_content"].add(page)

        if item_type == "heading":
            analysis["headings"] += 1
            level = item.get("heading level", "unknown")
            analysis["heading_levels"][level] = analysis["heading_levels"].get(level, 0) + 1
            if len(analysis["sample_headings"]) < 5:
                analysis["sample_headings"].append({
                    "page": page,
                    "level": level,
                    "content": item.get("content", "")[:80],
                })

        elif item_type == "paragraph":
            analysis["paragraphs"] += 1
            if len(analysis["sample_paragraphs"]) < 3:
                analysis["sample_paragraphs"].append({
                    "page": page,
                    "content": item.get("content", "")[:120],
                })

        elif item_type == "image":
            analysis["images"] += 1
            source = item.get("source", "")
            if source:
                analysis["image_sources"].append(source)

        elif item_type == "list":
            analysis["lists"] += 1
            items = item.get("list items", [])
            analysis["list_items"] += len(items)

    # Detect issues
    if analysis["images"] == 0:
        analysis["issues"].append("No images extracted")
    if analysis["headings"] == 0:
        analysis["issues"].append("No headings detected")
    if len(analysis["pages_with_content"]) < data.get("number of pages", 0):
        analysis["issues"].append(f"Only {len(analysis['pages_with_content'])} of {data.get('number of pages', 0)} pages have content")

    return analysis


def main():
    pdfs = [
        "RPS - ENGLISH - CLASS 1 - INDIVIDUAL - A (2026) PRINTFILE (2)-pages-2.json",
        "RPS - MATHS - CLASS 1 - INDIVIDUAL - B (2026) PRINTFILE-pages-2.json",
        "RPS - EVS - CLASS 1 - INDIVIDUAL - B (2026) PRINTFILE-pages-2.json",
    ]

    print("=" * 70)
    print("OpenDataLoader PDF Extraction Analysis")
    print("=" * 70)

    for pdf_name in pdfs:
        json_path = OUTPUT_DIR / pdf_name
        print(f"\nAnalyzing: {pdf_name}")
        print("-" * 70)

        analysis = analyze_pdf(json_path)
        if "error" in analysis:
            print(f"  ERROR: {analysis['error']}")
            continue

        print(f"  Pages: {analysis['pages']}")
        print(f"  Total elements: {analysis['total_elements']}")
        print(f"  Headings: {analysis['headings']}")
        print(f"  Paragraphs: {analysis['paragraphs']}")
        print(f"  Images: {analysis['images']}")
        print(f"  Lists: {analysis['lists']} (items: {analysis['list_items']})")
        print(f"  Pages with content: {len(analysis['pages_with_content'])}/{analysis['pages']}")

        if analysis["heading_levels"]:
            print(f"  Heading levels: {analysis['heading_levels']}")

        if analysis["sample_headings"]:
            print(f"  Sample headings:")
            for h in analysis["sample_headings"][:3]:
                print(f"    p{h['page']} [{h['level']}]: {h['content']}")

        if analysis["issues"]:
            print(f"  ISSUES:")
            for issue in analysis["issues"]:
                print(f"    - {issue}")
        else:
            print(f"  ✅ No obvious issues detected")

    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)

    total_images = 0
    total_headings = 0
    for pdf_name in pdfs:
        json_path = OUTPUT_DIR / pdf_name
        if json_path.exists():
            analysis = analyze_pdf(json_path)
            total_images += analysis.get("images", 0)
            total_headings += analysis.get("headings", 0)

    print(f"Total images extracted across all PDFs: {total_images}")
    print(f"Total headings detected across all PDFs: {total_headings}")


if __name__ == "__main__":
    main()
