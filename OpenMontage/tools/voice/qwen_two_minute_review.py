"""Generate a durable, source-grounded Qwen voice review from Chapter 2.

Uses only the first seven approved narration sections. Output is a voice
audition, not a replacement for the chapter's approved audio manifest.
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


REPO = Path(__file__).resolve().parents[2]
PROJECT = REPO / "projects" / "class-5-social-part-0-chapter-2-earth-movement"
ROOT = PROJECT / "assets" / "audio" / "qwen-clone-review" / "two-minute-v1"
REFERENCE = Path(r"C:\Users\user\Downloads\indian_accent.mpeg")
SOURCE_MANIFEST = PROJECT / "assets" / "audio" / "narration-v1" / "narration_manifest.json"
SAMPLE = ROOT / "qwen-chapter2-two-minute-180wpm-v2.mp3"
ENDPOINT = "https://modelslab.com/api/v6/voice/text_to_audio"


def write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def probe_seconds(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True, timeout=20,
    )
    return float(result.stdout.strip())


def output_url(response: dict) -> str | None:
    for field in ("output", "proxy_links", "future_links"):
        value = response.get(field)
        if isinstance(value, list) and value and isinstance(value[0], str):
            return value[0]
        if isinstance(value, str) and value.startswith("https://"):
            return value
    return None


def get_voice_id(key: str) -> str:
    profile = ROOT / "voice-profile.json"
    if profile.is_file():
        return json.loads(profile.read_text(encoding="utf-8"))["voice_id"]
    excerpt = ROOT / "reference-excerpt.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(REFERENCE),
         "-t", "10", "-ar", "24000", "-ac", "1", "-b:a", "128k", str(excerpt)],
        check=True, timeout=60,
    )
    encoded = "data:audio/mpeg;base64," + base64.b64encode(excerpt.read_bytes()).decode("ascii")
    response = requests.post(
        "https://modelslab.com/api/v6/voice/voice_upload",
        json={"key": key, "name": "social-chapter2-two-minute-review",
              "language": "english", "init_audio": encoded, "base64": True},
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("status") != "success" or not data.get("voice_id"):
        raise RuntimeError("Voice profile upload failed: " + str(data.get("message")))
    write_json(profile, {"voice_id": str(data["voice_id"]), "model": "qwen-tts",
                         "reference_excerpt_seconds": 10})
    return str(data["voice_id"])


def generate_chunk(index: int, text: str, voice_id: str, key: str) -> Path:
    path = ROOT / f"chunk-{index:02d}.wav"
    if path.is_file() and probe_seconds(path) > 5:
        return path
    state_path = ROOT / f"chunk-{index:02d}-job.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
    if not state:
        response = requests.post(
            ENDPOINT,
            json={"key": key, "model_id": "qwen-tts", "language": "english",
                  "voice_id": voice_id, "prompt": text},
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("status") in {"error", "failed"}:
            raise RuntimeError(f"Qwen chunk {index} failed: {data.get('message')}")
        state = {"job_id": data.get("id"), "output_url": output_url(data)}
        write_json(state_path, state)
    url = state.get("output_url")
    if not url and state.get("job_id") is not None:
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            poll = requests.post(
                f"https://modelslab.com/api/v6/voice/fetch/{state['job_id']}",
                json={"key": key}, timeout=45,
            )
            poll.raise_for_status()
            data = poll.json()
            if data.get("status") in {"error", "failed"}:
                raise RuntimeError(f"Qwen chunk {index} failed: {data.get('message')}")
            url = output_url(data)
            if url:
                state["output_url"] = url
                write_json(state_path, state)
                break
            time.sleep(5)
    if not url:
        raise RuntimeError(f"Qwen chunk {index} has no output URL; preserved job state")
    for attempt in range(18):
        response = requests.get(url, timeout=90)
        if response.status_code == 404 and attempt < 17:
            time.sleep(5)
            continue
        response.raise_for_status()
        raw = ROOT / f"chunk-{index:02d}-raw.wav"
        raw.write_bytes(response.content)
        break
    else:
        raise RuntimeError(f"Qwen chunk {index} audio URL remained unavailable")
    raw_seconds = probe_seconds(raw)
    words = len(re.findall(r"\b[\w'-]+\b", text))
    raw_wpm = words * 60 / raw_seconds
    tempo = 180 / raw_wpm
    if not 0.5 <= tempo <= 2.0:
        raise RuntimeError(f"Chunk {index} needs excessive retiming: {tempo:.2f}")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw),
         "-af", f"atempo={tempo:.6f}", "-ar", "24000", "-ac", "1",
         "-c:a", "pcm_s16le", str(path)],
        check=True, timeout=90,
    )
    return path


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    if SAMPLE.is_file():
        print(json.dumps({"sample": str(SAMPLE), "duration_seconds": probe_seconds(SAMPLE),
                          "status": "existing"}, indent=2))
        return
    manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    segments = manifest["segments"][:8]
    expected = [f"s{i:02d}" for i in range(1, 8)]
    if [s["section_id"][:3] for s in segments[:7]] != expected or segments[7]["section_id"] != "s08-revolution":
        raise ValueError("Source narration order changed; review before generating")
    groups = [[0, 1, 2], [3, 4], [5, 6]]
    prompts = [" ".join(segments[i]["text"].strip() for i in group) for group in groups]
    revolution_opening = "Revolution. Revolution is the movement of the Earth around the Sun in a fixed path called an orbit."
    if not segments[7]["text"].startswith(revolution_opening):
        raise ValueError("Revolution opening changed in the approved narration")
    prompts.append(revolution_opening)
    if any(len(prompt) > 1000 for prompt in prompts):
        raise ValueError("A Qwen chunk exceeds the 1000-character model limit")
    script = "\n\n".join(prompts)
    script_path = ROOT / "spoken-script-v2.txt"
    script_path.write_text(script, encoding="utf-8")
    load_dotenv(REPO / ".env")
    key = os.environ.get("MODELSLAB_API_KEY")
    if not key:
        raise RuntimeError("MODELSLAB_API_KEY is not configured locally")
    voice_id = get_voice_id(key)
    chunks = []
    for index, prompt in enumerate(prompts, 1):
        chunks.append(generate_chunk(index, prompt, voice_id, key))
        print(f"Completed Qwen passage {index}/{len(prompts)}", flush=True)
    filters = "".join(f"[{i}:a]" for i in range(len(chunks)))
    filters += f"concat=n={len(chunks)}:v=0:a=1,loudnorm=I=-16:TP=-1.5:LRA=11[a]"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *[item for path in chunks for item in ("-i", str(path))],
         "-filter_complex", filters, "-map", "[a]", "-c:a", "libmp3lame", "-b:a", "160k", str(SAMPLE)],
        check=True, timeout=180,
    )
    duration = probe_seconds(SAMPLE)
    report = {"status": "review_sample_not_approved_for_chapter", "model_id": "qwen-tts",
              "section_ids": [s["section_id"] for s in segments], "passages": len(prompts),
              "words": len(re.findall(r"\b[\w'-]+\b", script)),
              "duration_seconds": round(duration, 3), "pace_target_wpm": 180,
              "sample_path": str(SAMPLE), "script_path": str(script_path)}
    write_json(ROOT / "sample-report-v2.json", report)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
