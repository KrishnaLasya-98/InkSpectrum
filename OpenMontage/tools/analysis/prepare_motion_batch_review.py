"""Extract encoded evidence for a recovered educational motion batch, without approving it."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from lib.production_runtime import atomic_json
from tools.analysis.educational_clip_qa import technical_motion_audit


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(project: Path, batch_number: int, *, recovered_only: bool = False) -> dict:
    project = project.resolve()
    name = f"motion-batch-{batch_number:02d}"
    batch_path = project / "assets" / "video" / f"{name}.json"
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    destination = project / "artifacts" / f"{name}-review"
    review_path = project / "artifacts" / f"{name}-review.json"
    if review_path.is_file():
        existing = json.loads(review_path.read_text(encoding="utf-8"))
        if existing.get("status") == "reviewed":
            raise FileExistsError("A completed semantic review may not be overwritten")
    destination.mkdir(parents=True, exist_ok=True)
    rows = []
    for shot in batch["shots"]:
        clip = project / "assets" / "video" / name / f"{shot['shot_id']}.mp4"
        if not clip.is_file():
            if recovered_only:
                continue
            raise FileNotFoundError(clip)
        technical = technical_motion_audit(clip)
        if technical["status"] != "pass":
            # Still create evidence for manual rejection; never auto-approve.
            pass
        duration = float(technical["duration_seconds"])
        frames = []
        for label, seconds in (("start", .15), ("mid", duration / 2), ("end", max(.15, duration - .15))):
            target = destination / f"{shot['shot_id']}-{label}.jpg"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{seconds:.3f}", "-i", str(clip),
                            "-frames:v", "1", str(target)], check=True, timeout=60)
            frames.append(str(target))
        dense = destination / f"{shot['shot_id']}-dense20.jpg"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(clip),
                        "-vf", "fps=4,scale=320:180,tile=5x4", "-frames:v", "1", str(dense)],
                       check=True, timeout=60)
        rows.append({"shot_id": shot["shot_id"], "section_id": shot["section_id"],
                     "video_path": str(clip), "video_sha256": sha256_file(clip),
                     "frames": frames, "dense20": str(dense), "technical": technical,
                     "visual_status": "unreviewed", "reason": "Encoded semantic and aesthetic review pending"})
    if not rows:
        raise RuntimeError("No recovered encoded clips to review")
    report = {"version": "1.0", "batch": name, "status": "visual_review_pending",
              "review_method": "encoded original-resolution start/mid/end and dense20 plus technical motion audit",
              "clips": rows, "summary": {"total": len(rows), "accepted": 0, "rejected": 0, "unreviewed": len(rows)}}
    atomic_json(review_path, report)
    return {"status": report["status"], "review": str(review_path), "clips": len(rows)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--batch", type=int, required=True)
    parser.add_argument("--recovered-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.project, args.batch, recovered_only=args.recovered_only), indent=2))


if __name__ == "__main__":
    main()
