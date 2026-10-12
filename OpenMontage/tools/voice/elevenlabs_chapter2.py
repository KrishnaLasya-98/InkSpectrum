"""ElevenLabs voice probe and durable Chapter 2 speech generation.

Reads the key from the local ignored .env or process environment. Never writes
the key to a project artifact. Charged POST requests are never retried blindly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv


REPO = Path(__file__).resolve().parents[2]
PROJECT = REPO / "projects/class-5-social-part-0-chapter-2-earth-movement"
SOURCE = PROJECT / "assets/audio/narration-qwen-final-v3/narration_manifest.json"
REVIEW = PROJECT / "assets/audio/elevenlabs-voice-review-v1"
VOICE_ID = "zJrRUu1KEcKH8qdpNaPJ"
MODEL = "eleven_v4"
VOICE_SETTINGS = {"stability": 0.5, "similarity_boost": 0.8}


def key() -> str:
    load_dotenv(REPO / ".env", override=False)
    value = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not value:
        raise RuntimeError("Set ELEVENLABS_API_KEY locally in the ignored OpenMontage .env")
    return value


def get_voice(voice_id: str, api_key: str) -> dict:
    response = requests.get(f"https://api.elevenlabs.io/v1/voices/{voice_id}",
                            headers={"xi-api-key": api_key}, timeout=30)
    if not response.ok:
        raise RuntimeError(f"ElevenLabs voice lookup failed for {voice_id}: HTTP {response.status_code}")
    data = response.json()
    return {field: data.get(field) for field in
            ("voice_id", "name", "category", "description", "labels",
             "available_for_tiers", "high_quality_base_model_ids", "verified_languages")}


def synthesize(text: str, voice_id: str, api_key: str, target: Path,
               previous_text: str = "", next_text: str = "") -> dict:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    context_digest = hashlib.sha256((previous_text + "\n---\n" + next_text).encode("utf-8")).hexdigest()
    settings_digest = hashlib.sha256(json.dumps(
        {"model": MODEL, "voice_settings": VOICE_SETTINGS, "normalization": "on"},
        sort_keys=True).encode("utf-8")).hexdigest()
    state_path = target.with_suffix(".json")
    if target.is_file() != state_path.is_file():
        raise RuntimeError(f"Incomplete local ElevenLabs checkpoint; inspect before resubmitting: {target}")
    if target.is_file() and state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if (state.get("text_sha256") != digest or state.get("voice_id") != voice_id
                or state.get("context_sha256") != context_digest
                or state.get("settings_sha256") != settings_digest):
            raise ValueError(f"Existing audio provenance differs: {target}")
        if target.stat().st_size > 1000:
            return state
        raise RuntimeError(f"Existing ElevenLabs audio is too short; inspect before resubmitting: {target}")
    # The synchronous API charges a successful request. A timeout has an
    # unknown outcome, so this code deliberately does not retry it.
    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": api_key, "Content-Type": "application/json",
                 "Accept": "audio/mpeg"},
        json={"text": text, "model_id": MODEL, "voice_settings": VOICE_SETTINGS,
              "apply_text_normalization": "on",
              **({"previous_text": previous_text[-500:]} if previous_text else {}),
              **({"next_text": next_text[:500]} if next_text else {})},
        timeout=180,
    )
    if not response.ok:
        raise RuntimeError(f"ElevenLabs speech request failed: HTTP {response.status_code}; "
                           "no automatic retry or provider fallback")
    if len(response.content) < 1000:
        raise RuntimeError("ElevenLabs returned implausibly short audio")
    if not response.content.startswith((b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
        raise RuntimeError("ElevenLabs response is not recognizable MP3 audio")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".mp3.part")
    temporary.write_bytes(response.content)
    temporary.replace(target)
    state = {"voice_id": voice_id, "model_id": MODEL, "text_sha256": digest,
             "context_sha256": context_digest, "settings_sha256": settings_digest,
             "characters": len(text), "output_path": str(target),
             "status": "audio_received"}
    temporary_state = state_path.with_suffix(".json.part")
    temporary_state.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary_state.replace(state_path)
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("probe", "sample", "full"))
    args = parser.parse_args()
    api_key = key()
    if args.mode == "probe":
        print(json.dumps(get_voice(VOICE_ID, api_key), indent=2, ensure_ascii=False))
        return
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    if len(source["segments"]) != 15:
        raise ValueError("Approved Chapter 2 source scope changed")
    if args.mode == "sample":
        sample_text = " ".join(s["text"] for s in source["segments"][:3])
        target = REVIEW / "selected-voice-chapter2-sample.mp3"
        synthesize(sample_text, VOICE_ID, api_key, target)
        print(json.dumps({"voice_id": VOICE_ID, "sample_path": str(target)}, indent=2))
        return
    root = PROJECT / f"assets/audio/narration-elevenlabs-{VOICE_ID}-v1"
    records = []
    for index, section in enumerate(source["segments"], 1):
        target = root / f"{section['section_id']}.mp3"
        previous_text = source["segments"][index - 2]["text"] if index > 1 else ""
        next_text = source["segments"][index]["text"] if index < len(source["segments"]) else ""
        records.append({"section_id": section["section_id"],
                        **synthesize(section["text"], VOICE_ID, api_key, target,
                                     previous_text, next_text)})
        progress = {"status": "speech_generated_alignment_pending", "voice_id": VOICE_ID,
                    "complete": len(records), "total": len(source["segments"]), "segments": records}
        (root / "generation-progress.json").write_text(
            json.dumps(progress, indent=2) + "\n", encoding="utf-8")
        print(f"ElevenLabs section {index}/15 ready: {section['section_id']}", flush=True)


if __name__ == "__main__":
    main()
