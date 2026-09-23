"""Build verbatim textbook display cards from OpenDataLoader Markdown.

The source document is authoritative for all on-screen educational wording.
Narration may contain separately marked bridge text, but this module never
rewrites, title-cases, or punctuates source lines.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_IMAGE_RE = re.compile(r"^!\[[^\]]*\]\((.+)\)$")


def display_policy(source_manifest_path: Path | None = None) -> dict[str, Any]:
    """Return the shared source-text and motion-first display contract."""
    return {
        "source_authority": str(source_manifest_path) if source_manifest_path else "source_text_manifest.json",
        "display_case": "Tt",
        "preserve_punctuation": True,
        "max_content_lines": 3,
        "title_media_policy": "graphics_only",
        "content_media_policy": "motion_preferred",
        "image_policy": "fallback_only",
        "narration_bridge_policy": "audio_only_not_displayed",
    }


def _item(kind: str, text: str, source_line: int, **extra: Any) -> dict[str, Any]:
    return {
        "kind": kind,
        "source_text": text,
        "source_line": source_line,
        "display_case": "Tt",
        "typography": {
            "case": "Tt",
            "text_transform": "none",
            "preserve_punctuation": True,
        },
        **extra,
    }


def parse_source_markdown(path: Path) -> dict[str, Any]:
    """Extract headings, bullets, paragraphs, and image references verbatim."""
    text = path.read_text(encoding="utf-8")
    items: list[dict[str, Any]] = []
    image_refs: list[dict[str, Any]] = []

    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue

        image_match = _IMAGE_RE.match(line)
        if image_match:
            image_refs.append({"source_line": line_number, "source": image_match.group(1)})
            continue

        heading_match = _HEADING_RE.match(line)
        if heading_match:
            items.append(
                _item(
                    "heading",
                    heading_match.group(2),
                    line_number,
                    level=len(heading_match.group(1)),
                )
            )
            continue

        if line.startswith("-"):
            items.append(_item("bullet", line[1:].lstrip(), line_number))
            continue

        items.append(_item("paragraph", line, line_number))

    cards: list[dict[str, Any]] = []
    current_heading: dict[str, Any] | None = None
    body: list[dict[str, Any]] = []

    def flush() -> None:
        nonlocal body
        if not body:
            return
        for offset in range(0, len(body), 3):
            chunk = body[offset : offset + 3]
            cards.append(
                {
                    "card_type": "content",
                    "title": current_heading["source_text"] if current_heading else None,
                    "title_source_line": current_heading["source_line"] if current_heading else None,
                    "lines": chunk,
                    "line_count": len(chunk),
                    "media_policy": "motion_preferred",
                    "display_case": "Tt",
                    "preserve_punctuation": True,
                }
            )
        body = []

    for item in items:
        if item["kind"] == "heading":
            flush()
            current_heading = item
            cards.append(
                {
                    "card_type": "title",
                    "title": item["source_text"],
                    "source_line": item["source_line"],
                    "level": item["level"],
                    "media_policy": "graphics_only",
                    "display_case": "Tt",
                    "preserve_punctuation": True,
                }
            )
        else:
            body.append(item)
    flush()

    return {
        "version": "1.0",
        "source_file": str(path),
        "source_format": "opendataloader_markdown",
        "text_policy": {
            "authority": "source_markdown",
            "source_lines_verbatim": True,
            "allow_narration_bridge_words": True,
            "bridge_words_are_not_display_text": True,
            "content_lines_per_screen_max": 3,
            "title_line_excluded_from_content_line_limit": True,
            "case_format": "Tt",
            "punctuation": "preserve_source",
        },
        "items": items,
        "cards": cards,
        "image_references": image_refs,
        "validation": {
            "source_item_count": len(items),
            "card_count": len(cards),
            "max_content_lines": max(
                (card["line_count"] for card in cards if card["card_type"] == "content"),
                default=0,
            ),
        },
    }


def write_source_manifest(source_path: Path, output_path: Path) -> dict[str, Any]:
    manifest = parse_source_markdown(source_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build a verbatim source display manifest.")
    parser.add_argument("source_path")
    parser.add_argument("output_path")
    args = parser.parse_args()
    result = write_source_manifest(Path(args.source_path), Path(args.output_path))
    print(json.dumps(result["validation"], indent=2))
