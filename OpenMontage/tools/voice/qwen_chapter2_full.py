"""Generate resumable full Chapter 2 narration with the approved Qwen voice.

Each source section is one continuous TTS request. This step creates speech
assets only; heading holds, alignment, composition, and encoded QA follow.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

from tools.voice.qwen_two_minute_review import output_url, probe_seconds, write_json


REPO = Path(__file__).resolve().parents[2]
PROJECT = REPO / "projects" / "class-5-social-part-0-chapter-2-earth-movement"
SOURCE = PROJECT / "assets/audio/narration-v1/narration_manifest.json"
VOICE_PROFILE = PROJECT / "assets/audio/qwen-clone-review/two-minute-v1/voice-profile.json"
ROOT = PROJECT / "assets/audio/narration-qwen-v2"
ENDPOINT = "https://modelslab.com/api/v6/voice/text_to_audio"
TARGET_WPM = 180 / 1.007


def spoken_prompt(section: dict) -> str:
    """Keep textbook panels verbatim while speaking symbols and dates naturally."""
    text = section["text"]
    section_id = section["section_id"]
    if section_id == "s06-rotation":
        text = text.replace(
            "Rotation. Rotation is the movement of the Earth around its own axis is called Rotation.",
            "Rotation. The movement of the Earth around its own axis is called rotation.")
        text = text.replace("Rotation causes day and night.",
                            "This rotation causes day and night.")
    if section_id in {"s08-revolution", "s14-remember"}:
        text = text.replace("365¼ days", "three hundred and sixty-five and one quarter days")
    if section_id == "s10-solstice":
        text = text.replace("On 22 December", "On the twenty-second of December")
        text = text.replace("On 21 June", "On the twenty-first of June")
    return text


def generate_section(index: int, section: dict, voice_id: str, key: str) -> dict:
    section_id = section["section_id"]
    prompt = section["text"].strip()
    if not prompt or len(prompt) > 1000:
        raise ValueError(f"Invalid Qwen prompt length for {section_id}: {len(prompt)}")
    output = ROOT / f"{section_id}.wav"
    raw = ROOT / f"{section_id}-raw.wav"
    job = ROOT / f"{section_id}-job.json"
    state = json.loads(job.read_text(encoding="utf-8")) if job.is_file() else {}
    if state and (state.get("section_id") != section_id or state.get("prompt") != prompt):
        raise ValueError(f"Saved job prompt differs for {section_id}; refusing resubmission")
    if output.is_file() and probe_seconds(output) > 0.5:
        return {"section_id": section_id, "text": prompt, "audio_path": str(output),
                "duration_seconds": round(probe_seconds(output), 3),
                "job_id": state.get("job_id"), "status": "ready"}
    if not state:
        response = requests.post(ENDPOINT, json={"key": key, "model_id": "qwen-tts",
            "language": "english", "voice_id": voice_id, "prompt": prompt}, timeout=120)
        response.raise_for_status()
        data = response.json()
        if data.get("status") in {"error", "failed"}:
            raise RuntimeError(f"Qwen failed for {section_id}: {data.get('message')}")
        state = {"section_id": section_id, "prompt": prompt,
                 "job_id": data.get("id"), "output_url": output_url(data),
                 "model_id": "qwen-tts"}
        write_json(job, state)
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
                raise RuntimeError(f"Qwen job failed for {section_id}: {data.get('message')}")
            url = output_url(data)
            if url:
                state["output_url"] = url
                write_json(job, state)
                break
            time.sleep(5)
    if not url:
        raise RuntimeError(f"No output URL for {section_id}; job state preserved")
    if not raw.is_file():
        for attempt in range(18):
            response = requests.get(url, timeout=90)
            if response.status_code == 404 and attempt < 17:
                time.sleep(5)
                continue
            response.raise_for_status()
            raw.write_bytes(response.content)
            break
    raw_seconds = probe_seconds(raw)
    words = len(re.findall(r"\b[\w'-]+\b", prompt))
    raw_wpm = words * 60 / raw_seconds
    tempo = TARGET_WPM / raw_wpm
    if not 0.5 <= tempo <= 2.0:
        raise RuntimeError(f"{section_id} needs excessive retiming: {tempo:.3f}")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw),
        "-af", f"atempo={tempo:.7f}", "-ar", "24000", "-ac", "1",
        "-c:a", "pcm_s16le", str(output)], check=True, timeout=120)
    return {"section_id": section_id, "text": prompt, "audio_path": str(output),
            "duration_seconds": round(probe_seconds(output), 3),
            "raw_duration_seconds": round(raw_seconds, 3),
            "target_wpm": round(TARGET_WPM, 3), "job_id": state.get("job_id"),
            "status": "ready"}


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(SOURCE.read_text(encoding="utf-8"))
    sections = [{**section, "text": spoken_prompt(section)} for section in manifest["segments"]]
    if len(sections) != 15 or sections[0]["section_id"] != "s01-title" or sections[-1]["section_id"] != "s15-wordbank":
        raise ValueError("Approved Chapter 2 scope changed; review before generation")
    profile = json.loads(VOICE_PROFILE.read_text(encoding="utf-8"))
    load_dotenv(REPO / ".env")
    key = os.environ.get("MODELSLAB_API_KEY")
    if not key:
        raise RuntimeError("MODELSLAB_API_KEY is not configured locally")
    records = []
    for index, section in enumerate(sections, 1):
        records.append(generate_section(index, section, profile["voice_id"], key))
        write_json(ROOT / "generation-progress.json", {"model_id": "qwen-tts",
            "target_wpm": round(TARGET_WPM, 3), "complete": len(records),
            "total": len(sections), "segments": records})
        print(f"Qwen section {index}/{len(sections)} ready: {section['section_id']}", flush=True)


if __name__ == "__main__":
    main()
