from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw


PROJECT = Path(__file__).resolve().parent
VIDEO = PROJECT.parents[1] / "renders" / "class-5-social-chapter-03-worlds-weather-and-climate-review-v2.mp4"
TIMELINE = PROJECT / "hyperframes-final" / "timeline.json"
MANIFEST = PROJECT / "artifacts" / "clip-manifest-v1.json"
MEDIA_QA = PROJECT / "artifacts" / "composition-media-technical-qa-v1.json"
OUTPUT = PROJECT / "artifacts" / "encoded-semantic-coverage-v2"


def run(command: list[str]) -> None:
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=600)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    timeline = json.loads(TIMELINE.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    media_qa = json.loads(MEDIA_QA.read_text(encoding="utf-8"))
    classifications = {
        str(Path(row["path"]).resolve()).lower(): row["decision"]["classification"]
        for row in media_qa["results"]
    }
    section_starts = {
        section["section_id"]: float(section["start_seconds"])
        for section in timeline["sections"]
    }
    rows = []
    for clip in manifest["clips"]:
        section_id = clip["section_id"]
        section_start = section_starts[section_id]
        for segment in clip.get("visual_segments", []):
            source_path = Path(segment["path"]).resolve()
            classification = classifications[str(source_path).lower()]
            offset = float(segment["offset_seconds"])
            duration = float(segment["duration_seconds"])
            absolute_start = section_start + offset
            rows.append(
                {
                    "section_id": section_id,
                    "source_path": str(source_path),
                    "source_name": source_path.name,
                    "classification": classification,
                    "cue": segment.get("cue", ""),
                    "absolute_start_seconds": round(absolute_start, 3),
                    "absolute_end_seconds": round(absolute_start + duration, 3),
                    "duration_seconds": round(duration, 3),
                    "midpoint_seconds": round(absolute_start + duration / 2, 3),
                }
            )

    full_motion = [row for row in rows if row["classification"] == "full-motion"]
    names = Counter(row["source_name"] for row in full_motion)
    repeated = sorted(name for name, count in names.items() if count > 1)
    frames = []
    for index, row in enumerate(full_motion, start=1):
        frame = OUTPUT / f"full-motion-{index:02d}-{row['section_id']}-{row['midpoint_seconds']:.3f}s.jpg"
        run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-ss",
                f"{row['midpoint_seconds']:.3f}",
                "-i",
                str(VIDEO),
                "-frames:v",
                "1",
                "-vf",
                "scale=960:-2",
                str(frame),
            ]
        )
        row["encoded_frame"] = str(frame)
        frames.append((frame, row))

    sheets = []
    for sheet_index in range(0, len(frames), 9):
        subset = frames[sheet_index : sheet_index + 9]
        canvas = Image.new("RGB", (2880, 1740), "#142238")
        draw = ImageDraw.Draw(canvas)
        for cell, (frame_path, row) in enumerate(subset):
            image = Image.open(frame_path).convert("RGB")
            x = (cell % 3) * 960
            y = (cell // 3) * 580
            canvas.paste(image, (x, y + 40))
            label = f"{row['midpoint_seconds']:.3f}s | {row['section_id']} | {row['cue']} | {row['source_name']}"
            draw.rectangle((x, y, x + 960, y + 40), fill="#142238")
            draw.text((x + 10, y + 11), label, fill="white")
        sheet = OUTPUT / f"full-motion-contact-sheet-{sheet_index // 9 + 1:02d}.jpg"
        canvas.save(sheet, quality=91)
        sheets.append(str(sheet))

    report = {
        "version": "1.0",
        "encoded_video": str(VIDEO),
        "timeline_duration_seconds": timeline["duration_seconds"],
        "composition_media_files": len(media_qa["results"]),
        "full_motion_files": media_qa["full_motion_files"],
        "precision_authored_low_motion_files": media_qa["precision_authored_low_motion_files"],
        "full_motion_timeline_segments": len(full_motion),
        "full_motion_timeline_seconds": round(sum(row["duration_seconds"] for row in full_motion), 3),
        "repeated_full_motion_source_names": repeated,
        "full_motion_segments": full_motion,
        "contact_sheets": sheets,
        "status": "review",
        "review_note": "Encoded midpoint frames require human semantic comparison against cue, narration, and source.",
    }
    (OUTPUT / "semantic-coverage-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: report[key] for key in (
        "composition_media_files",
        "full_motion_files",
        "precision_authored_low_motion_files",
        "full_motion_timeline_segments",
        "full_motion_timeline_seconds",
        "repeated_full_motion_source_names",
        "contact_sheets",
    )}, indent=2))


if __name__ == "__main__":
    main()
