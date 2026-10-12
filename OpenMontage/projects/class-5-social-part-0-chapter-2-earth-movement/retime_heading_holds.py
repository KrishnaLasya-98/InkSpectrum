"""Create a versioned Chapter 2 review encode with two-second heading holds.

Both encoded picture and sound are cut at identical source-time intervals, so
word-highlight subtitles baked into the picture remain paired with narration.
The original HyperFrames v4c review render is preserved.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT / "hyperframes-draft-v1"
SOURCE = WORKSPACE / "renders" / "class5-social-chapter2-earth-movement-v4c.mp4"
OUTPUT = WORKSPACE / "renders" / "class5-social-chapter2-earth-movement-v4d-2s-pauses.mp4"
REPORT = ROOT / "artifacts" / "heading-pause-review-v4d.json"


def main() -> None:
    if OUTPUT.exists():
        raise SystemExit(f"Preserving existing encode: {OUTPUT}")
    timeline = json.loads((WORKSPACE / "timeline.json").read_text(encoding="utf-8"))
    intervals = []
    for section in timeline["sections"]:
        holds = ([section["heading_hold"]] if section.get("heading_hold") else [])
        holds += section.get("heading_holds", [])
        for hold in holds:
            duration = hold["end_seconds"] - hold["start_seconds"]
            if abs(duration - 4) > 0.02:
                raise ValueError(f"Expected a four-second hold in {section['section_id']}")
            intervals.append((round(hold["start_seconds"] + 2, 3),
                              round(hold["end_seconds"], 3), section["section_id"]))
    intervals.sort()
    if len(intervals) != 15:
        raise ValueError(f"Expected 15 heading holds, got {len(intervals)}")
    removed = "+".join(f"between(t,{start:.3f},{end:.3f})" for start, end, _ in intervals)
    filters = (
        f"[0:v]select='not({removed})',setpts=N/(30*TB)[v];"
        f"[0:a]aselect='not({removed})',asetpts=N/SR/TB[a]"
    )
    subprocess.run([
        "ffmpeg", "-hide_banner", "-y", "-i", str(SOURCE),
        "-filter_complex", filters, "-map", "[v]", "-map", "[a]",
        "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(OUTPUT),
    ], check=True, timeout=1800)
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(OUTPUT),
    ], check=True, capture_output=True, text=True, timeout=20)
    duration = float(probe.stdout.strip())
    expected = timeline["duration_seconds"] - 2 * len(intervals)
    if abs(duration - expected) > 0.25:
        raise RuntimeError(f"Encoded duration {duration:.3f} differs from expected {expected:.3f}")
    report = {"status": "encoded_review_only", "source": str(SOURCE),
              "output": str(OUTPUT), "source_duration_seconds": timeline["duration_seconds"],
              "target_heading_pause_seconds": 2, "removed_intervals": [
                  {"section_id": section, "start_seconds": start, "end_seconds": end}
                  for start, end, section in intervals],
              "encoded_duration_seconds": round(duration, 3),
              "note": "Temporal review edit of v4c; HyperFrames source and final semantic QA remain separate."}
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "duration_seconds": duration,
                      "cuts": len(intervals)}, indent=2))


if __name__ == "__main__":
    main()
