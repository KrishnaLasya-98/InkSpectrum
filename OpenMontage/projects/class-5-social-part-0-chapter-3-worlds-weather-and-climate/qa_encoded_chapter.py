from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw


PROJECT_DIR = Path(__file__).resolve().parent
REPOSITORY_DIR = PROJECT_DIR.parents[1]
sys.path.insert(0, str(REPOSITORY_DIR))

from lib.production_runtime import atomic_json


VIDEO = (
    REPOSITORY_DIR
    / "renders"
    / "class-5-social-chapter-03-worlds-weather-and-climate-review-v2.mp4"
)
TIMELINE = PROJECT_DIR / "hyperframes-final" / "timeline.json"
NARRATION = (
    PROJECT_DIR
    / "assets"
    / "audio"
    / "narration-elevenlabs-timed-v1"
    / "narration_manifest.json"
)
PAUSE_AUDIT = PROJECT_DIR / "artifacts" / "audio-pause-audit-v1.json"
OUTPUT_DIR = PROJECT_DIR / "artifacts" / "encoded-qa-v3"


def _run(command: list[str], timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, capture_output=True, text=True, timeout=timeout, check=True
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _probe() -> dict:
    raw = json.loads(
        _run(
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(VIDEO),
            ],
            timeout=120,
        ).stdout
    )
    video = next(stream for stream in raw["streams"] if stream["codec_type"] == "video")
    audio = next(stream for stream in raw["streams"] if stream["codec_type"] == "audio")
    fps_num, fps_den = video["avg_frame_rate"].split("/", 1)
    return {
        "duration_seconds": float(raw["format"]["duration"]),
        "file_size_bytes": VIDEO.stat().st_size,
        "video_codec": video["codec_name"],
        "width": int(video["width"]),
        "height": int(video["height"]),
        "fps": float(fps_num) / float(fps_den),
        "frame_count": int(video["nb_frames"]),
        "pixel_format": video.get("pix_fmt"),
        "color_space": video.get("color_space"),
        "audio_codec": audio["codec_name"],
        "audio_sample_rate": int(audio["sample_rate"]),
        "audio_channels": int(audio["channels"]),
        "audio_duration_seconds": float(audio["duration"]),
    }


def _motion_audit() -> dict:
    completed = _run(
        [
            "ffmpeg",
            "-v",
            "info",
            "-i",
            str(VIDEO),
            "-an",
            "-vf",
            "blackdetect=d=0.20:pix_th=0.10,freezedetect=n=0.003:d=1.5",
            "-f",
            "null",
            "NUL",
        ],
        timeout=1800,
    )
    log = completed.stderr
    black = [float(value) for value in re.findall(r"black_duration:([0-9.]+)", log)]
    starts = [float(value) for value in re.findall(r"freeze_start:\s*([0-9.]+)", log)]
    ends = [float(value) for value in re.findall(r"freeze_end:\s*([0-9.]+)", log)]
    durations = [float(value) for value in re.findall(r"freeze_duration:\s*([0-9.]+)", log)]
    return {
        "black_events": black,
        "freeze_starts": starts,
        "freeze_ends": ends,
        "freeze_durations": durations,
        "status": "pass" if not black else "fail",
        "interpretation": (
            "Freeze detections are review cues because readable objectives, Recall, Remember, "
            "and Word Bank cards are intentionally stable. Exact-frame and encoded contact-sheet "
            "evidence determine whether a freeze is unintended."
        ),
    }


def _frame_hash_audit(fps: float) -> dict:
    completed = _run(
        ["ffmpeg", "-v", "error", "-i", str(VIDEO), "-an", "-f", "framemd5", "-"],
        timeout=1800,
    )
    hashes = [
        line.rsplit(",", 1)[-1].strip()
        for line in completed.stdout.splitlines()
        if line and not line.startswith("#")
    ]
    runs: list[dict] = []
    run_start = 0
    for index in range(1, len(hashes) + 1):
        if index == len(hashes) or hashes[index] != hashes[run_start]:
            length = index - run_start
            if length > 1:
                runs.append(
                    {
                        "start_frame": run_start,
                        "end_frame": index - 1,
                        "frames": length,
                        "start_seconds": round(run_start / fps, 3),
                        "duration_seconds": round(length / fps, 3),
                    }
                )
            run_start = index
    longest = max(runs, key=lambda item: item["frames"], default={"frames": 1, "duration_seconds": 1 / fps})
    return {
        "frames": len(hashes),
        "unique_frames": len(set(hashes)),
        "unique_ratio": round(len(set(hashes)) / max(len(hashes), 1), 6),
        "longest_identical_run": longest,
        "identical_runs_over_1_5_seconds": [
            run for run in runs if run["duration_seconds"] >= 1.5
        ],
    }


def _decode_audio() -> tuple[np.ndarray, int, Path]:
    target = OUTPUT_DIR / "encoded-audio-mono-48k.wav"
    _run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(VIDEO),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "48000",
            "-c:a",
            "pcm_s16le",
            str(target),
        ],
        timeout=600,
    )
    data, sample_rate = sf.read(target, dtype="float32", always_2d=False)
    return np.asarray(data, dtype=np.float32), int(sample_rate), target


def _source_audio(
    manifest: dict, timeline: dict, expected_rate: int
) -> tuple[np.ndarray, list[dict]]:
    """Rebuild the authored timeline exactly as independently placed audio tracks.

    HyperFrames decodes/resamples each WAV independently and places it at the
    manifest start time.  Concatenating the 24 kHz files before resampling gives
    every section after the first a different resampler phase and is therefore
    not a valid encoded-audio comparison reference.
    """
    resampled_dir = OUTPUT_DIR / "source-segments-48k"
    resampled_dir.mkdir(parents=True, exist_ok=True)
    rendered_starts = {
        section["section_id"]: float(section["audio"]["start_seconds"])
        for section in timeline["sections"]
    }
    placed: list[tuple[int, np.ndarray, dict]] = []
    timeline_samples = 0
    segment_evidence = []
    for segment in manifest["segments"]:
        source_path = Path(segment["audio_path"])
        target_path = resampled_dir / f"{segment['section_id']}.wav"
        _run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                str(source_path),
                "-ac",
                "1",
                "-ar",
                str(expected_rate),
                "-c:a",
                "pcm_s16le",
                str(target_path),
            ],
            timeout=600,
        )
        audio, actual_rate = sf.read(target_path, dtype="float32", always_2d=False)
        if actual_rate != expected_rate:
            raise RuntimeError(f"Resample failed for {source_path}: {actual_rate}")
        mono = np.asarray(audio, dtype=np.float32)
        rendered_start = rendered_starts[segment["section_id"]]
        start_sample = round(rendered_start * expected_rate)
        end_sample = start_sample + len(mono)
        timeline_samples = max(timeline_samples, end_sample)
        placed.append((start_sample, mono, segment))
        segment_evidence.append(
            {
                "section_id": segment["section_id"],
                "source_path": str(source_path),
                "resampled_path": str(target_path),
                "start_sample": start_sample,
                "rendered_start_seconds": rendered_start,
                "manifest_start_seconds": float(segment["start_seconds"]),
                "samples": len(mono),
            }
        )

    combined = np.zeros(timeline_samples, dtype=np.float32)
    for start_sample, mono, segment in placed:
        end_sample = start_sample + len(mono)
        if np.any(combined[start_sample:end_sample]):
            raise RuntimeError(f"Overlapping narration tracks at {segment['section_id']}")
        combined[start_sample:end_sample] = mono
    reference = OUTPUT_DIR / "source-audio-timeline-mono-48k.wav"
    sf.write(reference, combined, expected_rate, subtype="PCM_16")
    return combined, segment_evidence


def _audio_audit() -> dict:
    manifest = json.loads(NARRATION.read_text(encoding="utf-8"))
    timeline = json.loads(TIMELINE.read_text(encoding="utf-8"))
    pauses = json.loads(PAUSE_AUDIT.read_text(encoding="utf-8"))
    encoded, sample_rate, decoded_path = _decode_audio()
    source, source_segments = _source_audio(manifest, timeline, sample_rate)
    common = min(len(encoded), len(source))
    encoded_common = encoded[:common].astype(np.float64)
    source_common = source[:common].astype(np.float64)
    correlation = float(
        np.dot(encoded_common, source_common)
        / max(np.linalg.norm(encoded_common) * np.linalg.norm(source_common), 1e-12)
    )
    peak = float(np.max(np.abs(encoded)))
    rms = float(np.sqrt(np.mean(np.square(encoded, dtype=np.float64))))

    pause_checks = []
    pause_by_id = {row["section_id"]: row for row in pauses}
    for segment in manifest["segments"]:
        row = pause_by_id[segment["section_id"]]
        start = float(segment["start_seconds"]) + float(row["heading_end"])
        end = start + 2.0
        left = max(0, int((start + 0.03) * sample_rate))
        right = min(len(encoded), int((end - 0.03) * sample_rate))
        window = encoded[left:right]
        window_peak = float(np.max(np.abs(window))) if len(window) else 1.0
        pause_checks.append(
            {
                "section_id": segment["section_id"],
                "start_seconds": round(start, 6),
                "end_seconds": round(end, 6),
                "measured_window_seconds": round(len(window) / sample_rate, 6),
                "peak_dbfs": round(20 * math.log10(max(window_peak, 1e-12)), 3),
                "status": "pass" if window_peak < 0.01 else "review",
            }
        )

    loudness = _run(
        [
            "ffmpeg",
            "-v",
            "info",
            "-i",
            str(VIDEO),
            "-vn",
            "-af",
            "ebur128=peak=true",
            "-f",
            "null",
            "NUL",
        ],
        timeout=600,
    ).stderr
    integrated = re.findall(r"I:\s*(-?[0-9.]+) LUFS", loudness)
    true_peak = re.findall(r"Peak:\s*(-?[0-9.]+) dBFS", loudness)
    length_delta = abs(len(encoded) - len(source)) / sample_rate
    return {
        "decoded_audio": str(decoded_path),
        "sample_rate": sample_rate,
        "encoded_samples": len(encoded),
        "source_samples": len(source),
        "duration_delta_seconds": round(length_delta, 6),
        "source_correlation": round(correlation, 8),
        "source_assembly": "independently_resampled_tracks_at_rendered_timeline_start_samples",
        "source_segments": source_segments,
        "peak_dbfs": round(20 * math.log10(max(peak, 1e-12)), 3),
        "rms_dbfs": round(20 * math.log10(max(rms, 1e-12)), 3),
        "integrated_lufs": float(integrated[-1]) if integrated else None,
        "true_peak_dbfs": float(true_peak[-1]) if true_peak else None,
        "clipped_samples": int(np.count_nonzero(np.abs(encoded) >= 0.999)),
        "heading_pause_checks": pause_checks,
        "heading_pause_failures": sum(row["status"] != "pass" for row in pause_checks),
        "status": "pass"
        if correlation >= 0.99 and length_delta <= 0.05
        and not any(row["status"] != "pass" for row in pause_checks)
        and not np.any(np.abs(encoded) >= 0.999)
        else "review",
    }


def _snapshot_times(timeline: dict) -> list[float]:
    times = []
    for section in timeline["sections"]:
        times.extend(
            [
                round(float(section["start_seconds"]) + 0.1, 3),
                round((float(section["start_seconds"]) + float(section["end_seconds"])) / 2, 3),
            ]
        )
        pause = section.get("inline_title_pause")
        if pause:
            times.append(round((float(pause["start_seconds"]) + float(pause["end_seconds"])) / 2, 3))
        for figure in section.get("figures") or []:
            figure_start = float(figure.get("start_seconds") or 0)
            figure_end = float(figure.get("end_seconds") or figure_start)
            times.append(round((figure_start + figure_end) / 2, 3))
    times.append(round(float(timeline["duration_seconds"]) - 0.1, 3))
    return sorted(set(times))


def _encoded_contact_sheets() -> dict:
    timeline = json.loads(TIMELINE.read_text(encoding="utf-8"))
    times = _snapshot_times(timeline)
    frames_dir = OUTPUT_DIR / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for index, at in enumerate(times):
        path = frames_dir / f"frame-{index:03d}-at-{at:g}s.jpg"
        _run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-ss",
                f"{at:.3f}",
                "-i",
                str(VIDEO),
                "-frames:v",
                "1",
                "-vf",
                "scale=640:-2",
                "-q:v",
                "3",
                str(path),
            ],
            timeout=120,
        )
        frames.append((at, path))

    sheets = []
    per_sheet = 9
    for sheet_index in range(math.ceil(len(frames) / per_sheet)):
        batch = frames[sheet_index * per_sheet : (sheet_index + 1) * per_sheet]
        with Image.open(batch[0][1]) as first:
            width, height = first.size
        label_height = 28
        canvas = Image.new("RGB", (width * 3, (height + label_height) * 3), "#142033")
        draw = ImageDraw.Draw(canvas)
        for index, (at, path) in enumerate(batch):
            with Image.open(path) as source:
                image = source.convert("RGB")
            x = (index % 3) * width
            y = (index // 3) * (height + label_height)
            canvas.paste(image, (x, y + label_height))
            draw.text((x + 8, y + 6), f"{at:g}s", fill="#f8fafc")
        sheet = OUTPUT_DIR / f"encoded-contact-sheet-{sheet_index + 1:02d}.jpg"
        canvas.save(sheet, quality=90)
        sheets.append(str(sheet))
    return {"times": times, "frame_count": len(frames), "contact_sheets": sheets}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    probe = _probe()
    technical_pass = (
        probe["width"] == 1920
        and probe["height"] == 1080
        and abs(probe["fps"] - 30) < 0.001
        and probe["video_codec"] == "h264"
        and probe["audio_codec"] == "aac"
        and probe["audio_sample_rate"] == 48000
        and probe["audio_channels"] == 2
        and abs(probe["audio_duration_seconds"] - 548.234) <= 0.05
    )
    report = {
        "version": "1.0",
        "candidate": str(VIDEO),
        "candidate_sha256": _sha256(VIDEO),
        "probe": {**probe, "status": "pass" if technical_pass else "fail"},
        "motion": _motion_audit(),
        "frame_hashes": _frame_hash_audit(probe["fps"]),
        "audio": _audio_audit(),
        "encoded_visual_sweep": _encoded_contact_sheets(),
    }
    report["automated_status"] = (
        "pass"
        if report["probe"]["status"] == "pass"
        and report["motion"]["status"] == "pass"
        and report["audio"]["status"] == "pass"
        else "review"
    )
    atomic_json(OUTPUT_DIR / "encoded-qa-report.json", report)
    print(
        json.dumps(
            {
                "status": report["automated_status"],
                "probe": report["probe"],
                "black_events": len(report["motion"]["black_events"]),
                "freeze_events": len(report["motion"]["freeze_durations"]),
                "longest_identical_run": report["frame_hashes"]["longest_identical_run"],
                "audio": {
                    key: report["audio"][key]
                    for key in (
                        "status",
                        "duration_delta_seconds",
                        "source_correlation",
                        "integrated_lufs",
                        "true_peak_dbfs",
                        "clipped_samples",
                        "heading_pause_failures",
                    )
                },
                "visual_frames": report["encoded_visual_sweep"]["frame_count"],
                "contact_sheets": len(report["encoded_visual_sweep"]["contact_sheets"]),
                "report": str(OUTPUT_DIR / "encoded-qa-report.json"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
