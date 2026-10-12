"""Create a short, paced ModelsLab Qwen voice-clone review sample.

This is an audition only; it does not replace a chapter's approved narrator.
The reference audio and API key stay local and are never printed.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


ENDPOINT = "https://modelslab.com/api/v6/voice/text_to_audio"
FETCH = "https://modelslab.com/api/v6/voice/fetch"


def _duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True, timeout=20,
    )
    return float(result.stdout.strip())


def _audio_url(data: dict) -> str | None:
    for field in ("output", "proxy_links", "future_links"):
        value = data.get(field)
        if isinstance(value, list) and value and isinstance(value[0], str):
            return value[0]
        if isinstance(value, str) and value.startswith("http"):
            return value
    return None


def generate(reference: Path, output_dir: Path, prompt: str, target_wpm: float) -> dict:
    if not reference.is_file():
        raise FileNotFoundError(reference)
    if len(prompt) > 1000:
        raise ValueError("Qwen prompt is limited to 1000 characters")
    report_path = output_dir / "sample-report.json"
    if report_path.is_file() and (output_dir / "qwen-indian-reference-paced.mp3").is_file():
        return json.loads(report_path.read_text(encoding="utf-8"))
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    key = os.environ.get("MODELSLAB_API_KEY")
    if not key:
        raise RuntimeError("MODELSLAB_API_KEY is not configured locally")
    output_dir.mkdir(parents=True, exist_ok=True)
    clean_ref = output_dir / "reference-private.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(reference),
         "-t", "10", "-ar", "24000", "-ac", "1", "-b:a", "128k", str(clean_ref)],
        check=True, timeout=60,
    )
    reference_data = "data:audio/mpeg;base64," + base64.b64encode(clean_ref.read_bytes()).decode("ascii")
    upload = requests.post(
        "https://modelslab.com/api/v6/voice/voice_upload",
        json={"key": key, "name": "social-chapter2-qwen-review", "language": "english",
              "init_audio": reference_data, "base64": True},
        timeout=120,
    )
    upload.raise_for_status()
    upload_result = upload.json()
    if upload_result.get("status") != "success" or not upload_result.get("voice_id"):
        raise RuntimeError("ModelsLab voice profile upload failed: " +
                           str(upload_result.get("message", "no voice ID")))
    reference_input = {"voice_id": str(upload_result["voice_id"])}
    response = requests.post(
        ENDPOINT,
        json={"key": key, "model_id": "qwen-tts", "language": "english",
              "prompt": prompt, **reference_input},
        timeout=120,
    )
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError(f"ModelsLab returned non-JSON HTTP {response.status_code}") from exc
    if response.status_code >= 400 or data.get("status") in {"error", "failed"}:
        raise RuntimeError(f"Qwen generation rejected: HTTP {response.status_code}; "
                           f"status={data.get('status')}; message={data.get('message') or data.get('error')}")
    url = _audio_url(data)
    job_id = data.get("id")
    if not url and job_id is not None:
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            time.sleep(5)
            poll = requests.post(f"{FETCH}/{job_id}", json={"key": key}, timeout=45)
            poll.raise_for_status()
            data = poll.json()
            if data.get("status") in {"error", "failed"}:
                raise RuntimeError(f"Qwen job {job_id} failed: {data.get('message')}")
            url = _audio_url(data)
            if url:
                break
    if not url:
        raise RuntimeError(f"Qwen job {job_id} produced no audio URL within 300 seconds")
    # The generation may finish before its object-storage URL is readable.
    # Save the URL and job ID first so a later run can recover without resubmission.
    (output_dir / "qwen-job.json").write_text(
        json.dumps({"job_id": job_id, "output_url": url}, indent=2), encoding="utf-8")
    raw = output_dir / ("qwen-raw.wav" if url.lower().split("?")[0].endswith(".wav") else "qwen-raw.mp3")
    for attempt in range(12):
        with requests.get(url, stream=True, timeout=90) as download:
            if download.status_code == 404 and attempt < 11:
                time.sleep(5)
                continue
            download.raise_for_status()
            with raw.open("wb") as stream:
                for chunk in download.iter_content(65536):
                    stream.write(chunk)
            break
    words = len(re.findall(r"\b[\w'-]+\b", prompt))
    raw_seconds = _duration(raw)
    raw_wpm = words * 60 / raw_seconds
    tempo = target_wpm / raw_wpm
    if not 0.5 <= tempo <= 2.0:
        raise RuntimeError(f"Required tempo {tempo:.2f} is outside safe sample range")
    paced = output_dir / "qwen-indian-reference-paced.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw),
         "-af", f"atempo={tempo:.6f},loudnorm=I=-16:TP=-1.5:LRA=11",
         "-ar", "24000", "-ac", "1", "-b:a", "128k", str(paced)],
        check=True, timeout=90,
    )
    report = {"model_id": "qwen-tts", "reference": str(reference), "prompt": prompt,
              "target_wpm": target_wpm, "raw_wpm": round(raw_wpm, 1),
              "raw_duration_seconds": round(raw_seconds, 2),
              "sample_duration_seconds": round(_duration(paced), 2),
              "tempo_factor": round(tempo, 4), "job_id": job_id,
              "sample_path": str(paced)}
    (output_dir / "sample-report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--target-wpm", type=float, default=120.0)
    parser.add_argument("--prompt", required=True)
    args = parser.parse_args()
    print(json.dumps(generate(args.reference, args.output_dir, args.prompt, args.target_wpm), indent=2))


if __name__ == "__main__":
    main()
