"""Seal an already reviewed motion batch to exact bytes before paid admission.

This command performs no provider calls. It upgrades a human/agent-authored
pre-generation review only when its existing checks say the references and
source routing were reviewed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from lib.production_runtime import atomic_json


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seal(project: Path, batch_path: Path) -> dict:
    project = project.resolve()
    batch_path = batch_path.resolve()
    if not batch_path.is_relative_to(project) or not batch_path.is_file():
        raise ValueError("Batch must be an existing file inside the chapter project")
    match = re.search(r"motion-batch-(\d+)$", batch_path.stem)
    if not match:
        raise ValueError("Batch filename must end in motion-batch-N")
    review_path = project / "artifacts" / f"motion-batch-{int(match.group(1)):02d}-pre-generation-review.json"
    if not review_path.is_file():
        raise FileNotFoundError(review_path)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    old_checks = review.get("checks") or {}
    legacy_required = {
        "unique_shot_ids", "unique_reference_hashes", "source_matched_sections",
        "no_generated_text_requested", "authored_lesson2_labels_retained",
    }
    if any(old_checks.get(key) is not True for key in legacy_required):
        raise ValueError("Legacy review does not prove all required pre-generation checks")
    reference_review_value = review.get("reference_review")
    reference_review_path = (project / str(reference_review_value or "")).resolve()
    if not reference_review_path.is_relative_to(project) or not reference_review_path.is_file():
        raise ValueError("Legacy review does not point to an existing reference review artifact")
    reference_review = json.loads(reference_review_path.read_text(encoding="utf-8"))
    if int(reference_review.get("review_rounds", 0)) < 2:
        raise ValueError("Reference images were not recorded as reviewed twice")
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    plan = json.loads((project / "artifacts" / "educational_plan.json").read_text(encoding="utf-8"))
    plan_by_id = {row["section_id"]: row for row in plan["sections"]}
    shots = batch.get("shots") or []
    if not shots or len({row["shot_id"] for row in shots}) != len(shots):
        raise ValueError("Batch shot IDs are empty or duplicated")
    sealed_shots = []
    reference_hashes = []
    for shot in shots:
        section = plan_by_id.get(shot.get("section_id"))
        if not section:
            raise ValueError(f"Unknown source section: {shot.get('section_id')}")
        row = {
            "shot_id": shot["shot_id"],
            "section_id": shot["section_id"],
            "source_block_ids": section["source_block_ids"],
        }
        if batch.get("operation") == "image_to_video":
            reference = (project / shot["reference_image"]).resolve()
            if not reference.is_relative_to(project) or not reference.is_file():
                raise ValueError(f"Invalid reference: {shot['shot_id']}")
            row["reference_path"] = str(reference)
            row["reference_sha256"] = sha256(reference)
            reference_hashes.append(row["reference_sha256"])
        sealed_shots.append(row)
    if reference_hashes and len(reference_hashes) != len(set(reference_hashes)):
        raise ValueError("Reference hashes are not unique")
    sealed = {
        "version": "1.1",
        "status": "approved_exact_batch_not_submitted",
        "batch_path": str(batch_path),
        "batch_sha256": sha256(batch_path),
        "target_count": len(shots),
        "reference_review": str(reference_review_path),
        "approved_shots": sealed_shots,
        "checks": {
            "two_visual_review_rounds": True,
            "unique_shot_ids": True,
            "unique_reference_hashes": True,
            "source_matched_sections": True,
            "generated_text_forbidden": True,
            "authored_labels_retained": True,
        },
        "policy": "Exact bytes and source routes sealed before any paid submission.",
    }
    atomic_json(review_path, sealed)
    return {"status": "sealed", "review": str(review_path), "shots": len(shots),
            "batch_sha256": sealed["batch_sha256"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--batch", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(seal(args.project, args.batch), indent=2))


if __name__ == "__main__":
    main()
