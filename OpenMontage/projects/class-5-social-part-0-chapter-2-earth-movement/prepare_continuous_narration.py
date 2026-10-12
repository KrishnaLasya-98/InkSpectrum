"""Restore continuous approved Eleven v4 speech without synthetic heading cuts."""
from __future__ import annotations

import json
import subprocess
from copy import deepcopy
from pathlib import Path

from tools.analysis.narration_text_syncer import NarrationTextSyncer


PROJECT = Path(__file__).resolve().parent
SOURCE = PROJECT / "assets/audio/narration-elevenlabs-final-zJrRUu1KEcKH8qdpNaPJ-v1/narration_manifest.json"
RAW = PROJECT / "assets/audio/narration-elevenlabs-zJrRUu1KEcKH8qdpNaPJ-v1"
OUTPUT = PROJECT / "assets/audio/narration-elevenlabs-continuous-v2/narration_manifest.json"
ALIGNMENT = PROJECT / "artifacts/alignment-elevenlabs-continuous-v2"
PLAN = PROJECT / "artifacts/educational_plan.json"


def probe(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True, timeout=30,
    )
    return float(result.stdout.strip())


def main() -> None:
    original = json.loads(SOURCE.read_text(encoding="utf-8"))
    if not original.get("generation_complete") or len(original["segments"]) != 15:
        raise ValueError("Approved Eleven v4 generation is incomplete")
    manifest = deepcopy(original)
    manifest["timing_policy"] = "unaltered continuous speech; no inserted title cuts or topic padding"
    cursor = 0.0
    for segment in manifest["segments"]:
        raw = RAW / f"{segment['section_id']}.wav"
        if not raw.is_file():
            raise FileNotFoundError(raw)
        duration = round(probe(raw), 3)
        heading_end = min(float(segment.get("heading_duration_seconds") or 0), duration)
        segment.update(
            audio_path=str(raw),
            duration_seconds=duration,
            start_seconds=round(cursor, 3),
            heading_duration_seconds=heading_end,
            body_start_seconds=heading_end,
            title_card_hold_seconds=0,
            topic_end_pause_seconds=0,
            heading_holds=[],
        )
        cursor += duration
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    result = NarrationTextSyncer().execute({
        "narration_manifest": manifest,
        "educational_plan": json.loads(PLAN.read_text(encoding="utf-8")),
        "output_dir": str(ALIGNMENT),
        "title_offset_seconds": 0,
    })
    if not result.success:
        raise RuntimeError(result.error)
    print(json.dumps({"sections": len(manifest["segments"]),
                      "duration_seconds": round(cursor, 3),
                      "alignment_method": result.data["alignment_method"],
                      "manifest": str(OUTPUT), "alignment": str(ALIGNMENT)}, indent=2))


if __name__ == "__main__":
    main()
