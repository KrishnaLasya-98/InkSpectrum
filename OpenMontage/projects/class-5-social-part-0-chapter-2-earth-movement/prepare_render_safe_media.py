"""Create seek-safe copies of approved Chapter 2 motion clips.

Never modifies the original generated or precision videos. Only the draft
composition consumes these copies after ffprobe verifies their durations.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


PROJECT = Path(__file__).resolve().parent
MANIFEST = PROJECT / "artifacts/clip-manifest-draft-v1.json"
OUTPUT = PROJECT / "assets/video/render-safe-v1"
REPORT = PROJECT / "artifacts/render-safe-media-v1.json"


def duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    records = []
    for clip in manifest["clips"]:
        for index, segment in enumerate(clip.get("visual_segments") or [], 1):
            source = PROJECT / segment["path"]
            if not source.is_file():
                raise FileNotFoundError(source)
            target = OUTPUT / f"{clip['section_id']}-{index:02d}.mp4"
            original_duration = duration(source)
            if not target.is_file():
                subprocess.run([
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
                    "-map", "0:v:0", "-vf", "fps=30", "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "18", "-g", "30",
                    "-keyint_min", "30", "-sc_threshold", "0", "-pix_fmt", "yuv420p",
                    "-an", "-movflags", "+faststart", "-threads", "2", str(target),
                ], check=True)
            safe_duration = duration(target)
            requested = float(segment["duration_seconds"])
            if safe_duration + 0.04 < requested or abs(safe_duration - original_duration) > 0.12:
                raise ValueError(f"Render-safe duration drift for {clip['section_id']}: {original_duration} -> {safe_duration}")
            records.append({
                "section_id": clip["section_id"], "segment_index": index,
                "original_path": segment["path"],
                "render_safe_path": target.relative_to(PROJECT).as_posix(),
                "original_duration_seconds": original_duration,
                "render_safe_duration_seconds": safe_duration,
            })
            print(f"{len(records):02d} {clip['section_id']} {safe_duration:.3f}s", flush=True)
    REPORT.write_text(json.dumps({"status": "prepared_for_draft_review", "records": records}, indent=2) + "\n", encoding="utf-8")
    print(REPORT)


if __name__ == "__main__":
    main()
