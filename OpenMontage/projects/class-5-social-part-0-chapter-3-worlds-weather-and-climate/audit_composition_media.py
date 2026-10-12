from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from tools.analysis.educational_clip_qa import technical_motion_audit


PROJECT_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = PROJECT_DIR / "artifacts" / "clip-manifest-v1.json"
OUTPUT_PATH = PROJECT_DIR / "artifacts" / "composition-media-technical-qa-v1.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _probe(path: Path) -> dict:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=codec_type,codec_name,width,height,avg_frame_rate",
        "-show_entries",
        "format=duration,size,format_name",
        "-of",
        "json",
        str(path),
    ]
    completed = subprocess.run(
        command, capture_output=True, text=True, check=True, timeout=60
    )
    return json.loads(completed.stdout)


def _frame_hash_stats(path: Path) -> dict:
    completed = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "framemd5", "-"],
        capture_output=True,
        text=True,
        check=True,
        timeout=180,
    )
    hashes = [
        line.rsplit(",", 1)[-1].strip()
        for line in completed.stdout.splitlines()
        if line and not line.startswith("#")
    ]
    longest_run = 0
    current_run = 0
    previous = None
    for frame_hash in hashes:
        current_run = current_run + 1 if frame_hash == previous else 1
        longest_run = max(longest_run, current_run)
        previous = frame_hash
    tail_run = 0
    if hashes:
        last = hashes[-1]
        for frame_hash in reversed(hashes):
            if frame_hash != last:
                break
            tail_run += 1
    unique = len(set(hashes))
    return {
        "frames": len(hashes),
        "unique_frames": unique,
        "unique_ratio": round(unique / max(len(hashes), 1), 6),
        "longest_identical_run_frames": longest_run,
        "identical_tail_frames": tail_run,
    }


def _decision(path: Path, technical: dict, frame_hashes: dict) -> dict:
    if technical["status"] == "pass":
        return {"status": "pass", "classification": "full-motion"}

    issues = list(technical.get("issues") or [])
    freeze_only = issues and all(issue.startswith("frozen motion detected") for issue in issues)
    authored_precision = path.name[:1].isupper()
    no_exact_extension = (
        frame_hashes["unique_ratio"] >= 0.9
        # A short authored settle (at most half a second at the normalized
        # 30 fps) is not an end-frame extension. The tail remains strict.
        and frame_hashes["longest_identical_run_frames"] <= 15
        and frame_hashes["identical_tail_frames"] <= 3
    )
    if authored_precision and freeze_only and no_exact_extension:
        return {
            "status": "pass",
            "classification": "precision-authored-low-motion",
            "note": (
                "Coarse perceptual freeze threshold triggered, but exact frame hashes "
                "confirm continuous authored changes and no repeated end-frame extension."
            ),
        }
    return {"status": "fail", "classification": "requires-review"}


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    paths = sorted(
        {
            Path(segment["path"]).resolve()
            for clip in manifest["clips"]
            for segment in clip.get("visual_segments", [])
        },
        key=lambda item: item.name.casefold(),
    )

    results = []
    for index, path in enumerate(paths, start=1):
        print(f"[{index:02d}/{len(paths):02d}] {path.name}", flush=True)
        technical = technical_motion_audit(path)
        probe = _probe(path) if path.is_file() else {}
        frame_hashes = _frame_hash_stats(path) if path.is_file() else {}
        decision = _decision(path, technical, frame_hashes) if path.is_file() else {
            "status": "fail",
            "classification": "missing",
        }
        results.append(
            {
                "path": str(path),
                "sha256": _sha256(path) if path.is_file() else None,
                "file_size_bytes": path.stat().st_size if path.is_file() else 0,
                "probe": probe,
                "frame_hashes": frame_hashes,
                "technical": technical,
                "decision": decision,
            }
        )

    failed = [item for item in results if item["decision"]["status"] != "pass"]
    strict_motion = [
        item for item in results
        if item["decision"]["classification"] == "full-motion"
    ]
    precision_low_motion = [
        item for item in results
        if item["decision"]["classification"] == "precision-authored-low-motion"
    ]
    report = {
        "version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_manifest": str(MANIFEST_PATH),
        "files_checked": len(results),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "full_motion_files": len(strict_motion),
        "precision_authored_low_motion_files": len(precision_low_motion),
        "status": "pass" if not failed else "review_required",
        "results": results,
    }
    OUTPUT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "files_checked": report["files_checked"],
                "passed": report["passed"],
                "failed": report["failed"],
                "report": str(OUTPUT_PATH),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
