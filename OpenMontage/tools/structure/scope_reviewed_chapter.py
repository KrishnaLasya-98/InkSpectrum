"""Apply an explicit user-approved section scope without altering source history."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from lib.production_runtime import atomic_json
from schemas.artifacts import validate_artifact
from tools.structure.source_contract import build_coverage_contract
from tools.structure.teaching_contract import validate_teaching_contract


def scope_chapter(plan, document, manifest, scope):
    if scope.get("user_approved") is not True:
        raise ValueError("A reduced source scope requires explicit user approval")
    ids = [s["section_id"] for s in plan["sections"]]
    start, end = ids.index(scope["start_section_id"]), ids.index(scope["end_section_id"])
    if start > end:
        raise ValueError("Scope boundaries are reversed")
    exclude = set(scope.get("exclude_section_ids", []))
    if exclude - set(ids):
        raise ValueError("Unknown excluded section")
    selected = [deepcopy(s) for s in plan["sections"][start:end + 1] if s["section_id"] not in exclude]
    if not selected:
        raise ValueError("Scope contains no sections")
    if scope.get("exclude_assessments", False) and any(s.get("teaching_contract", {}).get("questions") or s.get("source_block_type") in {"qa_item", "assessment", "exercise"} for s in selected):
        raise ValueError("Assessment remains in assessment-excluded scope")
    allowed = {s["section_id"] for s in selected}
    included_blocks = {bid for s in selected for bid in s["source_block_ids"]}
    scoped_document = deepcopy(document)
    for block in scoped_document["blocks"]:
        if block["block_id"] not in included_blocks:
            block["required_for_coverage"] = False
    scoped_plan = deepcopy(plan)
    scoped_plan["sections"] = selected
    scoped_plan["total_duration_seconds"] = sum(s["duration_seconds"] for s in selected)
    required = {b["block_id"] for b in scoped_document["blocks"] if b.get("required_for_coverage")}
    scoped_plan.setdefault("metadata", {}).update({"production_scope": scope,
        "required_source_block_count": len(required), "mapped_required_source_block_count": len(required & included_blocks)})
    report = validate_teaching_contract(scoped_plan, scoped_document["blocks"], subject="")
    if report["status"] != "pass":
        raise ValueError(f"Scoped source validation failed: {report}")
    contract = build_coverage_contract(scoped_document)
    for entry in contract["entries"]:
        if entry["source_block_id"] not in included_blocks:
            entry["omission_reason"] = "explicit_user_scope_exclusion"
    audio = deepcopy(manifest)
    by_id = {s["section_id"]: s for s in audio["segments"]}
    audio["segments"] = [by_id[s["section_id"]] for s in selected]
    cursor = 0
    for segment in audio["segments"]:
        segment["start_seconds"] = round(cursor, 6)
        cursor += segment["duration_seconds"]
        segment["end_seconds"] = round(cursor, 6)
    audio["total_duration_seconds"] = round(cursor, 6)
    audio["word_alignment_status"] = "pending"
    audit = {"scope": scope, "included_section_ids": [s["section_id"] for s in selected],
             "excluded_section_ids": [sid for sid in ids if sid not in allowed],
             "included_source_block_ids": sorted(included_blocks), "teaching_contract": report,
             "duration_seconds": round(cursor, 6), "full_chapter_coverage_claimed": False}
    for name, value in [("educational_plan", scoped_plan), ("chapter_document", scoped_document), ("narration_manifest", audio)]:
        validate_artifact(name, value)
    return {"educational_plan": scoped_plan, "chapter_document": scoped_document,
            "coverage_contract": contract, "narration_manifest": audio, "scope_audit": audit}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "document", "narration", "scope", "output_dir"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args()
    read = lambda p: json.loads(p.read_text(encoding="utf-8"))
    artifacts = scope_chapter(read(args.plan), read(args.document), read(args.narration), read(args.scope))
    for name, value in artifacts.items():
        atomic_json(args.output_dir / (name + ".json"), value)
    print(json.dumps({"sections": len(artifacts["educational_plan"]["sections"]),
                      "duration_seconds": artifacts["narration_manifest"]["total_duration_seconds"],
                      "output_dir": str(args.output_dir.resolve())}))


if __name__ == "__main__":
    main()
