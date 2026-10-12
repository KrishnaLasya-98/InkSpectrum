"""Resumable same-voice repair for two headings omitted by Qwen paragraph TTS."""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

from tools.voice.qwen_two_minute_review import output_url, probe_seconds, write_json


REPO = Path(__file__).resolve().parents[2]
PROJECT = REPO / "projects/class-5-social-part-0-chapter-2-earth-movement"
ROOT = PROJECT / "assets/audio/qwen-heading-repair-v1"
PROFILE = PROJECT / "assets/audio/qwen-clone-review/two-minute-v1/voice-profile.json"
PROMPTS = {"s06-rotation": "Rotation.", "s08-revolution": "Revolution."}


def make(section_id: str, prompt: str, voice_id: str, key: str) -> Path:
    output = ROOT / f"{section_id}-heading.wav"
    if output.is_file() and probe_seconds(output) > 0.2:
        return output
    state_path = ROOT / f"{section_id}-job.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
    if state and state.get("prompt") != prompt:
        raise ValueError("Saved heading job prompt differs; refusing resubmission")
    if not state:
        response = requests.post("https://modelslab.com/api/v6/voice/text_to_audio",
            json={"key": key, "model_id": "qwen-tts", "language": "english",
                  "voice_id": voice_id, "prompt": prompt}, timeout=120)
        response.raise_for_status()
        data = response.json()
        if data.get("status") in {"error", "failed"}:
            raise RuntimeError(f"Heading job failed: {section_id}: {data.get('message')}")
        state = {"section_id": section_id, "prompt": prompt,
                 "job_id": data.get("id"), "output_url": output_url(data)}
        write_json(state_path, state)
    url = state.get("output_url")
    if not url and state.get("job_id") is not None:
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            response = requests.post(
                f"https://modelslab.com/api/v6/voice/fetch/{state['job_id']}",
                json={"key": key}, timeout=45)
            response.raise_for_status()
            data = response.json()
            if data.get("status") in {"error", "failed"}:
                raise RuntimeError(f"Heading job failed: {section_id}: {data.get('message')}")
            url = output_url(data)
            if url:
                state["output_url"] = url
                write_json(state_path, state)
                break
            time.sleep(5)
    if not url:
        raise RuntimeError(f"Heading {section_id} has no output URL; job state preserved")
    raw = ROOT / f"{section_id}-heading-raw.wav"
    if not raw.is_file():
        for attempt in range(18):
            response = requests.get(url, timeout=90)
            if response.status_code == 404 and attempt < 17:
                time.sleep(5)
                continue
            response.raise_for_status()
            raw.write_bytes(response.content)
            break
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw),
        "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(output)],
        check=True, timeout=60)
    if not 0.2 < probe_seconds(output) < 4:
        raise RuntimeError(f"Implausible heading duration for {section_id}")
    return output


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    load_dotenv(REPO / ".env")
    key = os.environ.get("MODELSLAB_API_KEY")
    if not key:
        raise RuntimeError("MODELSLAB_API_KEY is not configured locally")
    voice_id = json.loads(PROFILE.read_text(encoding="utf-8"))["voice_id"]
    for section_id, prompt in PROMPTS.items():
        path = make(section_id, prompt, voice_id, key)
        print(f"Heading ready: {section_id} ({probe_seconds(path):.3f}s)", flush=True)


if __name__ == "__main__":
    main()
