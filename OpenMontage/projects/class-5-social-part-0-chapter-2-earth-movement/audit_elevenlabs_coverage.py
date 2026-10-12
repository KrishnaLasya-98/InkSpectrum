"""Verify scoped Chapter 2 source-block continuity into the final composition."""
from __future__ import annotations

import copy
import argparse
import json
import re
from pathlib import Path

from tools.structure.source_contract import coverage_summary, validate_final_source_coverage


ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / "artifacts"
VOICE = ROOT / "assets/audio/narration-elevenlabs-final-zJrRUu1KEcKH8qdpNaPJ-v1/narration_manifest.json"
TIMELINE = ROOT / "hyperframes-elevenlabs-v4/timeline.json"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="elevenlabs-v4")
    parser.add_argument("--narration-manifest", type=Path, default=VOICE)
    parser.add_argument("--timeline", type=Path, default=TIMELINE)
    args = parser.parse_args()
    contract = copy.deepcopy(read(ARTIFACTS / "coverage_contract.json"))
    plan = read(ARTIFACTS / "educational_plan.json")
    narration = read(args.narration_manifest)
    clips = read(ARTIFACTS / f"clip-manifest-{args.version}.json")["clips"]
    timeline = read(args.timeline)
    block_to_section: dict[str, str] = {}
    for section in plan["sections"]:
        for block_id in section.get("source_block_ids") or []:
            if block_id in block_to_section:
                raise ValueError(f"Source block assigned to multiple sections: {block_id}")
            block_to_section[block_id] = section["section_id"]
    for entry in contract["entries"]:
        block_id = entry["source_block_id"]
        section_id = block_to_section.get(block_id)
        if entry["required"] and section_id is None:
            raise ValueError(f"Unmapped required source block: {block_id}")
        if section_id:
            entry["status"] = "mapped"
            entry["mappings"] = {
                "narration_segment_ids": [section_id],
                "screen_ids": [section_id],
                "visual_cue_ids": [section_id],
            }
    contract["summary"] = coverage_summary(contract["entries"])
    report = validate_final_source_coverage(
        contract,
        educational_plan=plan,
        narration_manifest=narration,
        clip_manifest=clips,
        composition_timeline=timeline,
    )
    blocks = {block["block_id"]: block for block in read(ARTIFACTS / "chapter_document.json")["blocks"]}
    composed = {section["section_id"]: section for section in timeline["sections"]}
    text_issues: list[str] = []
    for block_id, section_id in block_to_section.items():
        block = blocks[block_id]
        section = composed[section_id]
        if block["block_type"] == "figure":
            if not section.get("figures"):
                text_issues.append(f"{block_id}:missing_figure")
            continue
        panel = section.get("panel") or {}
        visible = " ".join(
            [str(panel.get(key) or "") for key in ("section_label", "heading", "body")]
            + [str(item) for item in panel.get("items") or []]
            + [str(page.get("text") or "") for page in section.get("panel_pages") or []]
            + [json.dumps(panel.get("table") or {}, ensure_ascii=False)]
        )
        source_text = re.sub(r"\s+", " ", block.get("source_text") or "").strip()
        if source_text not in re.sub(r"\s+", " ", visible):
            text_issues.append(f"{block_id}:source_text_not_visible")
    report["verbatim_panel_or_figure_blocks"] = len(block_to_section) - len(text_issues)
    report["verbatim_panel_or_figure_issues"] = text_issues
    if text_issues:
        report["status"] = "fail"
        raise ValueError("Source text/figure coverage failed: " + ", ".join(text_issues))
    (ARTIFACTS / f"coverage_contract-{args.version}.json").write_text(
        json.dumps(contract, indent=2) + "\n", encoding="utf-8"
    )
    (ARTIFACTS / f"source-coverage-{args.version}.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
