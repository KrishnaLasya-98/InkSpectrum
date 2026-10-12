"""Extend one-use Chapter 2 motion clips to measured ElevenLabs narration slots.

Motion interpolation creates new in-between frames. It never loops footage or
silently holds a last frame. Outputs are resumable and keep source provenance.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


PROJECT = Path(__file__).resolve().parent
ARTIFACTS = PROJECT / "artifacts"
SOURCE_MANIFEST = ARTIFACTS / "render-safe-media-v1.json"
CLIP_MANIFEST = ARTIFACTS / "clip-manifest-elevenlabs-v4.json"
OUTPUT_MANIFEST = ARTIFACTS / "render-safe-media-elevenlabs-v4.json"
MEDIA_DIR = PROJECT / "assets/video/retimed-elevenlabs-v4"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True, timeout=30,
    )
    return float(result.stdout.strip())


def main() -> None:
    source = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    clips = json.loads(CLIP_MANIFEST.read_text(encoding="utf-8"))
    requests = {
        (clip["section_id"], index): float(segment["duration_seconds"])
        for clip in clips["clips"]
        for index, segment in enumerate(clip.get("visual_segments") or [], 1)
    }
    records = []
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    for record in source["records"]:
        section_id = record["section_id"]
        index = record["segment_index"]
        requested = requests[(section_id, index)]
        original = PROJECT / record["render_safe_path"]
        original_duration = duration(original)
        if requested <= original_duration - 0.05:
            records.append(record)
            continue
        target = MEDIA_DIR / f"{section_id}-{index:02d}.mp4"
        receipt = target.with_suffix(".json")
        interpolation = (
            "minterpolate=fps=30:mi_mode=blend" if original_duration > 6.0
            else "minterpolate=fps=30:mi_mode=mci:mc_mode=obmc:me_mode=bidir"
        )
        identity_filter = (
            "setpts+minterpolate-blend-30fps" if original_duration > 6.0
            else "setpts+minterpolate-mci-30fps"
        )
        identity = {"source_sha256": sha256(original),
                    "requested_seconds": requested, "filter": identity_filter}
        if target.is_file() != receipt.is_file():
            raise RuntimeError(f"Incomplete retiming checkpoint: {target}")
        if target.is_file():
            saved = json.loads(receipt.read_text(encoding="utf-8"))
            if saved["identity"] != identity or duration(target) < requested - 0.04:
                raise RuntimeError(f"Retimed clip provenance/duration mismatch: {target}")
        else:
            factor = (requested + 0.12) / original_duration
            temporary = target.with_suffix(".part.mp4")
            subprocess.run(
                ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(original),
                 "-vf", f"setpts={factor:.8f}*(PTS-STARTPTS),{interpolation}",
                 "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                 "-g", "30", "-keyint_min", "30", "-sc_threshold", "0",
                 "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(temporary)],
                check=True, timeout=600,
            )
            measured = duration(temporary)
            if measured < requested - 0.04:
                raise RuntimeError(f"Retimed clip ended early: {temporary}: {measured:.3f} < {requested:.3f}")
            temporary.replace(target)
            receipt.write_text(json.dumps({"identity": identity, "duration_seconds": measured},
                                          indent=2) + "\n", encoding="utf-8")
        updated = dict(record)
        updated["render_safe_path"] = target.relative_to(PROJECT).as_posix()
        updated["render_safe_duration_seconds"] = round(duration(target), 6)
        updated["retime_factor"] = round((requested + 0.12) / original_duration, 6)
        records.append(updated)
        print(f"Retimed {section_id} clip {index}: {original_duration:.2f}s -> {updated['render_safe_duration_seconds']:.2f}s", flush=True)
    if len(records) != len(requests):
        raise ValueError("Retimed media manifest does not cover all requested clips")
    result = dict(source)
    result["records"] = records
    result["retiming_policy"] = "one-use optical-flow interpolation; no loops or still-frame holds"
    OUTPUT_MANIFEST.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(records), "manifest": str(OUTPUT_MANIFEST)}, indent=2))


if __name__ == "__main__":
    main()
