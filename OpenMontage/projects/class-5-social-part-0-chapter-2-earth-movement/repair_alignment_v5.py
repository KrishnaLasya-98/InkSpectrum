"""Cache measured ElevenLabs forced alignment for the approved chapter audio.

No speech is regenerated. No automatic retries; uncertain requests are logged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT = Path(__file__).resolve().parent
REPO = PROJECT.parents[1]
OUT = PROJECT / "artifacts/alignment-elevenlabs-forced-v5"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--section")
    args = parser.parse_args()
    load_dotenv(REPO / ".env")
    key = os.getenv("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("Set ELEVENLABS_API_KEY locally")
    manifest = json.loads((PROJECT / "assets/audio/narration-elevenlabs-title-pause-v4/narration_manifest.json").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    for segment in manifest["segments"]:
        sid = segment["section_id"]
        if args.section and sid != args.section:
            continue
        target = OUT / f"{sid}.provider.json"
        audio = Path(segment["audio_path"])
        fingerprint = hashlib.sha256(audio.read_bytes() + segment["text"].encode()).hexdigest()
        if target.is_file():
            existing = json.loads(target.read_text(encoding="utf-8"))
            if existing["input_sha256"] != fingerprint:
                raise RuntimeError(f"Existing alignment input mismatch: {sid}")
            print(f"{sid}: cached", flush=True)
            continue
        pending = OUT / f"{sid}.request.json"
        if pending.is_file():
            raise RuntimeError(f"Unresolved request: {sid}; inspect before submitting again")
        pending.write_text(json.dumps({"section_id": sid, "input_sha256": fingerprint, "status": "request_started"}, indent=2), encoding="utf-8")
        with audio.open("rb") as handle:
            response = requests.post(
                "https://api.elevenlabs.io/v1/forced-alignment",
                headers={"xi-api-key": key},
                data={"text": segment["text"]},
                files={"file": (audio.name, handle, "audio/wav")},
                timeout=(15, 180),
            )
        if response.status_code != 200:
            pending.write_text(json.dumps({"section_id": sid, "status": "http_error", "http_status": response.status_code}, indent=2), encoding="utf-8")
            raise RuntimeError(f"Forced alignment HTTP {response.status_code}: {sid}")
        payload = response.json()
        target.write_text(json.dumps({"section_id": sid, "input_sha256": fingerprint, "response": payload}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        pending.write_text(json.dumps({"section_id": sid, "status": "response_saved", "input_sha256": fingerprint}, indent=2), encoding="utf-8")
        print(f"{sid}: measured {len(payload.get('words', []))} words", flush=True)


if __name__ == "__main__":
    main()
