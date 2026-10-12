"""Publish one encoded-QA-passed chapter to its textbook delivery folder.

Never overwrites a different MP4 and never advances past an incomplete earlier
chapter. The collection index is rebuilt from the durable production plan.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from lib.production_runtime import atomic_json


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _index(plan: dict, delivery: Path) -> dict:
    chapters = []
    for chapter in plan["chapters"]:
        target = Path(chapter["delivery_video"])
        if target.parent.resolve() != delivery.resolve():
            raise ValueError("A chapter delivery path escapes the collection folder")
        completed = chapter.get("status") == "completed" and target.is_file()
        chapters.append({
            "chapter": chapter["chapter"], "title": chapter["title"],
            "status": "completed" if completed else chapter.get("status", "queued"),
            "video": str(target) if completed else None,
        })
    return {"version": "1.0", "collection": delivery.name,
            "total_chapters": len(chapters),
            "completed_chapters": sum(x["status"] == "completed" for x in chapters),
            "chapters": chapters}


def publish(collection: Path, chapter_number: int, project: Path) -> dict:
    collection = collection.resolve()
    project = project.resolve()
    plan_path = collection / "artifacts" / "video_production_plan.json"
    plan = _read(plan_path)
    chapters = sorted(plan["chapters"], key=lambda row: row["chapter"])
    entry = next((x for x in chapters if int(x["chapter"]) == chapter_number), None)
    if entry is None:
        raise ValueError(f"Chapter {chapter_number} is absent from the collection plan")
    for earlier in chapters:
        if int(earlier["chapter"]) >= chapter_number:
            break
        if earlier.get("status") != "completed" or not Path(earlier["delivery_video"]).is_file():
            raise ValueError(f"Earlier chapter {earlier['chapter']} is not delivered and verified")
    config = _read(project / "chapter_config.json")
    if int(config["chapter"]) != chapter_number or config["project_id"] != project.name:
        raise ValueError("Project configuration does not match the requested chapter")
    if Path(config["source_pdf"]).resolve() != Path(entry["source_pdf"]).resolve():
        raise ValueError("Project source PDF differs from the chapter map")
    checkpoint_path = project / "checkpoint_quality_assurance.json"
    if not checkpoint_path.is_file():
        raise ValueError("Final quality-assurance checkpoint does not exist")
    checkpoint = _read(checkpoint_path)
    if checkpoint.get("status") != "completed":
        raise ValueError("Final quality-assurance checkpoint is not complete")
    evidence_dir = Path(checkpoint["metadata"]["evidence_dir"])
    review = _read(evidence_dir / "final-review.json")
    if review.get("status") != "pass":
        raise ValueError("Final-review status is not pass")
    sheets = review.get("metadata", {}).get("contact_sheets_reviewed") or []
    if not sheets or any(not Path(path).is_file() for path in sheets):
        raise ValueError("Encoded contact sheets were not reviewed or are missing")
    comparison_path = Path(review["metadata"]["encoded_comparison_ref"])
    comparison = _read(comparison_path)
    if comparison.get("automated_status") != "pass" or not all(comparison.get("gates", {}).values()):
        raise ValueError("Encoded textbook/reference comparison did not pass")
    candidate = Path(review["output_path"])
    if not candidate.is_file() or candidate.resolve() != Path(comparison["candidate"]).resolve():
        raise ValueError("QA review and comparison refer to different output files")
    fingerprint = _sha256(candidate)
    if fingerprint != comparison["candidate_sha256"]:
        raise ValueError("Encoded candidate changed after QA")
    target = Path(entry["delivery_video"])
    delivery = Path(plan["delivery_folder"])
    if target.parent.resolve() != delivery.resolve() or target.name != config["delivery_video_name"]:
        raise ValueError("Delivery filename does not match the chapter contract")
    delivery.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        if _sha256(target) != fingerprint:
            raise ValueError("A different video already occupies the delivery filename")
    else:
        temporary = target.with_suffix(target.suffix + ".copying")
        if temporary.exists():
            raise ValueError("An unfinished delivery copy exists; inspect it before retrying")
        shutil.copy2(candidate, temporary)
        if _sha256(temporary) != fingerprint:
            temporary.unlink(missing_ok=True)
            raise ValueError("Delivery copy hash differs from the QA-approved source")
        temporary.replace(target)
    entry["status"] = "completed"
    entry["final_video"] = str(target)
    entry["qa_evidence"] = str(comparison_path)
    entry["sha256"] = fingerprint
    atomic_json(plan_path, plan)
    index = _index(plan, delivery)
    atomic_json(delivery / "index.json", index)
    return {"chapter": chapter_number, "video": str(target), "sha256": fingerprint,
            "completed_chapters": index["completed_chapters"],
            "total_chapters": index["total_chapters"], "index": str(delivery / "index.json")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", required=True, type=Path)
    parser.add_argument("--chapter", required=True, type=int)
    parser.add_argument("--project", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(publish(args.collection, args.chapter, args.project), indent=2))


if __name__ == "__main__":
    main()
