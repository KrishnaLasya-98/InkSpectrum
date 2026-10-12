from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from lib.production_runtime import atomic_json
from tools.analysis.educational_clip_qa import technical_motion_audit


PROJECT = Path(__file__).resolve().parent

REVIEW_DECISIONS = {
    "climate-factors-landscape": ("accepted", "Accurate varied coast, plain, and mountain context; clean continuous aerial motion."),
    "climate-types-montage": ("rejected", "Persistent three-way split-screen contradicts the requested seamless journey and collection presentation."),
    "earth-equator-to-poles": ("accepted", "Useful unlabeled globe context for the zones overview; the exact textbook zone diagram remains authoritative."),
    "equator-strong-sunlight": ("accepted", "Clear warm tropical sunlight context with clean vegetation and continuous motion."),
    "lut-heat-shimmer": ("accepted", "Clean rocky hot-desert context with visible airborne heat/dust motion."),
    "lut-scorched-ridges": ("accepted", "Clean scorched ridge context with strong heat lighting and smooth camera movement."),
    "polar-low-sunlight": ("accepted", "Clear low-angle polar sunlight, long shadows, and continuous snow motion."),
    "startup-warm-place": ("rejected", "A prominent storefront contains generated pseudo-text, violating the no-text requirement."),
    "startup-cold-place": ("accepted", "Clean cold mountain-town context with bundled children and continuous snow motion."),
    "weather-cloud-cover": ("accepted", "Cloud cover visibly gathers over a clean landscape with continuous natural motion."),
    "weather-change-rain-to-sun": ("accepted", "Clearly shows rain and emerging sunlight during one changing-weather scene."),
    "climate-long-term-seasons": ("accepted", "The same landscape and tree transition cleanly through four distinct seasons."),
    "climate-wet-dry-contrast": ("accepted", "Strong continuous dry-to-wet climate contrast with clear rainfall and vegetation change."),
    "altitude-foothill-to-peak": ("accepted", "Smooth ascent from green lower slopes to a snow-covered high summit."),
    "coast-day-thermal-lag": ("accepted", "Clean daytime coastal context with visibly moving waves and windblown vegetation."),
    "coast-night-thermal-lag": ("accepted", "Clean matching night-coast context with continuous waves, clouds, and vegetation motion."),
    "humidity-lush-coast": ("accepted", "Clear damp, lush coastal environment without text or misleading steam effects."),
    "warm-current-coast": ("accepted", "Warm-lit green coastline provides clean contextual support for the warm-current sentence."),
    "cold-current-coast": ("accepted", "Cold rocky coast and distant ice provide clean contextual support for the cold-current sentence."),
    "monsoon-rice-fields": ("accepted", "Heavy monsoon rain over rice fields and a tropical village matches the narration precisely."),
    "equatorial-rainforest-river": ("accepted", "Dense equatorial rainforest, flowing river, and heavy rain match the climate description."),
    "temperate-four-seasons-tree": ("accepted", "One consistent tree transitions clearly through spring, summer, autumn, and winter."),
}


def main(batch_name: str = "motion-batch-05") -> None:
    if not batch_name.startswith("motion-batch-") or not batch_name[13:].isdigit():
        raise ValueError("Batch name must look like motion-batch-05")
    batch_path = PROJECT / "assets" / "video" / f"{batch_name}.json"
    video_dir = PROJECT / "assets" / "video" / batch_name
    status_path = PROJECT / "assets" / "video" / f"{batch_name}-status.json"
    output_dir = PROJECT / "artifacts" / f"{batch_name}-review"
    spec = json.loads(batch_path.read_text(encoding="utf-8"))
    provider_status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.is_file() else {}
    provider_jobs = {
        row.get("shot_id"): row
        for row in provider_status.get("jobs", [])
        if row.get("shot_id")
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    unavailable = []
    for shot in spec["shots"]:
        source = video_dir / f"{shot['shot_id']}.mp4"
        if not source.is_file() or source.stat().st_size == 0:
            job = provider_jobs.get(shot["shot_id"], {})
            unavailable.append(
                {
                    "shot_id": shot["shot_id"],
                    "section_id": shot["section_id"],
                    "provider_status": job.get("status", "not_downloaded"),
                    "request_id": job.get("request_id"),
                    "output_path": str(source),
                }
            )
            continue
        technical = technical_motion_audit(source, freeze_duration_seconds=1.5)
        duration = float(technical["duration_seconds"])
        times = [0.15 + (duration - 0.3) * index / 7 for index in range(8)]
        frame_paths = []
        for index, timestamp in enumerate(times):
            frame = output_dir / f"{shot['shot_id']}-{index:02d}-{timestamp:.3f}s.jpg"
            subprocess.run(
                [
                    "ffmpeg", "-y", "-v", "error", "-ss", f"{timestamp:.3f}",
                    "-i", str(source), "-frames:v", "1", "-vf", "scale=480:270", str(frame),
                ],
                check=True,
                timeout=60,
            )
            frame_paths.append(str(frame))
        records.append(
            {
                "shot_id": shot["shot_id"],
                "section_id": shot["section_id"],
                "prompt": shot["prompt"],
                "source_path": str(source),
                "technical": technical,
                "sample_times_seconds": [round(value, 3) for value in times],
                "frame_paths": frame_paths,
                "semantic_status": REVIEW_DECISIONS.get(
                    shot["shot_id"], ("pending_human_review", "")
                )[0],
                "review_notes": REVIEW_DECISIONS.get(
                    shot["shot_id"], ("pending_human_review", "")
                )[1],
            }
        )

    sheets = []
    for record in records:
        canvas = Image.new("RGB", (1920, 620), "#142238")
        draw = ImageDraw.Draw(canvas)
        draw.text(
            (12, 10),
            f"{record['shot_id']} | {record['section_id']} | technical={record['technical']['status']}",
            fill="white",
        )
        for index, frame_path in enumerate(record["frame_paths"]):
            image = Image.open(frame_path).convert("RGB")
            x = (index % 4) * 480
            y = 40 + (index // 4) * 290
            canvas.paste(image, (x, y))
            draw.rectangle((x, y + 270, x + 480, y + 290), fill="#142238")
            draw.text((x + 8, y + 273), f"{record['sample_times_seconds'][index]:.3f}s", fill="white")
        sheet = output_dir / f"{record['shot_id']}-contact-sheet.jpg"
        canvas.save(sheet, quality=92)
        record["contact_sheet"] = str(sheet)
        sheets.append(str(sheet))

    report = {
        "version": "1.0",
        "batch": str(batch_path),
        "shots": records,
        "technical_passed": sum(row["technical"]["status"] == "pass" for row in records),
        "technical_failed": sum(row["technical"]["status"] != "pass" for row in records),
        "semantic_status": (
            "partial_review_complete"
            if unavailable
            else "complete"
        ),
        "semantic_accepted": sum(row["semantic_status"] == "accepted" for row in records),
        "semantic_rejected": sum(row["semantic_status"] == "rejected" for row in records),
        "contact_sheets": sheets,
        "unavailable": unavailable,
        "batch_complete": len(records) == len(spec["shots"]),
    }
    atomic_json(output_dir / "review.json", report)
    print(
        json.dumps(
            {
                "shots": len(records),
                "technical_passed": report["technical_passed"],
                "technical_failed": report["technical_failed"],
                "contact_sheets": len(sheets),
                "unavailable": len(unavailable),
                "batch_complete": report["batch_complete"],
                "report": str(output_dir / "review.json"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", default="motion-batch-05")
    main(parser.parse_args().batch)
