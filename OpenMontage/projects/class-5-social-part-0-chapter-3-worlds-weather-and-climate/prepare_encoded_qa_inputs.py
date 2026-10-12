from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
REPOSITORY_DIR = PROJECT_DIR.parents[1]
sys.path.insert(0, str(REPOSITORY_DIR))

from lib.production_runtime import atomic_json
from tools.analysis.chapter_coverage_audit import audit_chapter


ARTIFACTS_DIR = PROJECT_DIR / "artifacts"
TIMELINE_PATH = PROJECT_DIR / "hyperframes-final" / "timeline.json"
NARRATION_PATH = (
    PROJECT_DIR
    / "assets"
    / "audio"
    / "narration-elevenlabs-timed-v1"
    / "narration_manifest.json"
)


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    return []


def main() -> None:
    document = json.loads((ARTIFACTS_DIR / "chapter_document.json").read_text(encoding="utf-8"))
    plan = json.loads((ARTIFACTS_DIR / "educational_plan.json").read_text(encoding="utf-8"))
    narration = json.loads(NARRATION_PATH.read_text(encoding="utf-8"))
    timeline = json.loads(TIMELINE_PATH.read_text(encoding="utf-8"))

    coverage = audit_chapter(document, plan, narration, timeline)
    coverage_path = ARTIFACTS_DIR / "authored-coverage-audit-v2.json"
    atomic_json(coverage_path, coverage)

    required_blocks = [
        block
        for block in document.get("blocks", [])
        if block.get("required_for_coverage", True) and str(block.get("source_text") or "").strip()
    ]
    source_audit = {
        "version": "1.0",
        "textbook_pages": sorted({int(block["page_number"]) for block in required_blocks}),
        # This gate checks spoken/displayed text coverage. Figures and the
        # Word Bank table are verified separately against encoded pixels.
        "required_topics": [
            str(block["source_text"]).strip()
            for block in required_blocks
            if block.get("block_type") not in {"figure", "table"}
        ],
        "required_block_ids": [str(block["block_id"]) for block in required_blocks],
        "visual_review_block_ids": [
            str(block["block_id"])
            for block in required_blocks
            if block.get("block_type") == "figure"
        ],
        "table_review_block_ids": [
            str(block["block_id"])
            for block in required_blocks
            if block.get("block_type") == "table"
        ],
        "scope": "opening through Word Bank inclusive; assessments and later exercises excluded",
        "source_document": str(PROJECT_DIR.parent.parent / "textbook-collections" / "class-5-social" / "source-chapters" / "chapter-03-world-s-weather-and-climate.pdf"),
    }
    source_audit_path = ARTIFACTS_DIR / "encoded-source-audit-v2.json"
    atomic_json(source_audit_path, source_audit)

    production_sections = []
    for section in timeline.get("sections", []):
        panel = section.get("panel") or {}
        production_sections.append(
            {
                "section_id": section.get("section_id"),
                "heading": panel.get("heading") or panel.get("section_label") or "",
                "display": _strings(panel),
                "source_block_ids": section.get("source_block_ids") or [],
                "start_seconds": section.get("start_seconds"),
                "end_seconds": section.get("end_seconds"),
            }
        )

    captions = []
    for group in timeline.get("caption_groups", []):
        captions.append(
            {
                "id": group.get("group_id"),
                "start": float(group.get("start_seconds") or 0),
                "end": float(group.get("end_seconds") or 0),
                "words": [
                    {
                        "word": word.get("word") or "",
                        "start": float(word.get("start_ms") or 0) / 1000.0,
                        "end": float(word.get("end_ms") or 0) / 1000.0,
                    }
                    for word in group.get("words", [])
                ],
            }
        )
    production_data = {
        "version": "1.0",
        "duration_seconds": timeline.get("duration_seconds"),
        "sections": production_sections,
        "captions": captions,
        "source": str(TIMELINE_PATH),
    }
    production_data_path = ARTIFACTS_DIR / "encoded-production-data-v2.json"
    atomic_json(production_data_path, production_data)

    print(
        json.dumps(
            {
                "coverage_status": coverage["status"],
                "required_blocks": coverage["required_blocks"],
                "verified_authored_blocks": coverage["verified_authored_blocks"],
                "unresolved_blocks": coverage["unresolved_blocks"],
                "source_topics": len(source_audit["required_topics"]),
                "production_sections": len(production_sections),
                "captions": len(captions),
                "coverage_report": str(coverage_path),
                "source_audit": str(source_audit_path),
                "production_data": str(production_data_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
