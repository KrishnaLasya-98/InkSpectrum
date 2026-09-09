"""Temporary end-to-end pipeline verification per AGENTS.md Phase 3/4 rules."""
import json
import subprocess
from pathlib import Path

OUT = Path("packages/textbook-pipeline/projects/english_pipeline_output")


def probe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    return float(r.stdout.strip())


scenes = json.loads((OUT / "phase2_script_scenes_with_audio.json").read_text(encoding="utf-8"))

missing, real_total, referenced = [], 0.0, 0
for sc in scenes:
    for vo in sc.get("voiceover_lines", []):
        ap = vo.get("audio_path")
        if not ap:
            missing.append(f"{sc['id']}: voiceover line without audio_path")
            continue
        p = Path(ap)
        if not p.exists():
            missing.append(f"{sc['id']}: missing audio file {ap}")
            continue
        referenced += 1
        real_total += probe_duration(p)

mp3_files = list((OUT / "audio").glob("*.mp3"))
video = OUT / "chapter_video.mp4"
video_size_mb = video.stat().st_size / 1e6


def probe_streams(path: Path) -> tuple[float, float, float]:
    """Return (container_duration, video_stream_duration, audio_stream_duration)."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,duration",
         "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    data = json.loads(r.stdout)
    container = float(data["format"]["duration"])
    vdur = adur = 0.0
    for st in data["streams"]:
        if st["codec_type"] == "video":
            vdur = float(st["duration"])
        elif st["codec_type"] == "audio":
            adur = float(st["duration"])
    return container, vdur, adur


container_dur, vdur, adur = probe_streams(video)

man = json.loads((OUT / "audio" / "audio_manifest.json").read_text(encoding="utf-8"))

print(f"=== PHASE 3 VERIFICATION ===")
print(f"Scenes: {man['total_scenes']}  Voiceover lines: {man['total_lines']}")
print(f"Audio files generated (manifest): {man['generated_files']}")
print(f"MP3 files on disk: {len(mp3_files)}")
print(f"Audio files referenced & existing: {referenced}")
print(f"Missing/unreferenced audio problems: {len(missing)}")
for m in missing:
    print("  !", m)

print(f"\n=== PHASE 4 VERIFICATION ===")
print(f"chapter_video.mp4 size: {video_size_mb:.2f} MB  (>1MB: {video_size_mb > 1})")
print(f"Real total audio duration: {real_total:.1f}s")
print(f"Video stream duration: {vdur:.1f}s")
print(f"Audio stream duration: {adur:.1f}s")
print(f"Container (mvhd) duration: {container_dur:.1f}s")
stream_delta = abs(adur - real_total)
container_delta = abs(container_dur - real_total)
print(f"Stream vs audio delta: {stream_delta:.1f}s ({stream_delta / real_total * 100:.1f}%)")
print(f"Container vs audio delta: {container_delta:.1f}s ({container_delta / real_total * 100:.1f}%)")

r = subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height",
     "-of", "compact", str(video)], capture_output=True, text=True,
)
print(f"\nStreams:\n{r.stdout.strip()}")

ok = (
    video_size_mb > 1
    and not missing
    and stream_delta / real_total < 0.02
    and container_delta / real_total < 0.02
)
print(f"\nOVERALL PIPELINE VERIFICATION: {'PASS' if ok else 'FAIL'}")
