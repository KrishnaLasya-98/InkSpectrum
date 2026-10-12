"""One-shot, fail-closed ElevenLabs narration for a reviewed chapter plan.

Each charged request is reserved before sending. An ambiguous response is never
retried automatically; operators must reconcile it with the provider first.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

from lib.production_runtime import atomic_json
from tools.structure.teaching_contract import validate_teaching_contract


ROOT = Path(__file__).resolve().parents[2]
VOICE = "zJrRUu1KEcKH8qdpNaPJ"
MODEL = "eleven_v4"
SETTINGS = {"stability": 0.5, "similarity_boost": 0.8, "speed": 0.85}


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fingerprint(text: str) -> str:
    payload = {"text": text, "voice_id": VOICE, "model_id": MODEL,
               "voice_settings": SETTINGS, "output_format": "mp3_44100_128",
               "apply_text_normalization": "on"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def probe_audio(path: Path) -> float:
    proc = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                           "-of", "default=nokey=1:noprint_wrappers=1", str(path)],
                          capture_output=True, text=True, check=True)
    duration = float(proc.stdout.strip())
    if duration < 0.5:
        raise ValueError(f"Implausibly short audio file: {path}")
    return duration


def decode_mp3(source: Path, target: Path) -> float:
    if target.is_file():
        return probe_audio(target)
    temporary = target.with_suffix(".wav.part")
    if temporary.exists():
        raise RuntimeError(f"Unfinished WAV decode requires inspection: {temporary}")
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                           "-i", str(source), "-ar", "48000", "-ac", "1",
                           "-c:a", "pcm_s16le", "-f", "wav", str(temporary)],
                          capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(f"FFmpeg decode failed for {source.name}: {proc.stderr[-1000:]}")
    duration = probe_audio(temporary)
    temporary.replace(target)
    return duration


def run(project: Path, *, max_new: int = 0, dry_run: bool = False) -> dict:
    project = project.resolve()
    config = read(project / "chapter_config.json")
    plan = read(project / "artifacts" / "educational_plan.json")
    document = read(project / "artifacts" / "chapter_document.json")
    review = validate_teaching_contract(plan, document["blocks"], subject=config["subject"])
    if review["status"] != "pass":
        raise RuntimeError(f"Source teaching contract failed: {review['issues'][:5]}")
    if config.get("approval_policy") != "full-run-preauthorized":
        raise RuntimeError("Full-run authorization is not recorded")
    audio = config["providers"]["audio"]
    if (audio["provider"], audio["model_id"], audio["voice_id"], float(audio["speed"])) != (
            "elevenlabs", MODEL, VOICE, 0.85):
        raise RuntimeError("Approved ElevenLabs voice/model/speed lock differs")
    output = project / "assets" / "audio" / "narration-elevenlabs-v1"
    sections = plan["sections"]
    prepared = []
    for section in sections:
        sid = section["section_id"]
        body = str(section["narration_script"]).strip()
        text = ("Social Studies, Class 5. " if section is sections[0] else "") + body
        prepared.append((sid, text, fingerprint(text)))
    prior = [x for x in output.glob("*.request.json")] if output.exists() else []
    planned_ids = {sid for sid, _, _ in prepared}
    if any(path.name.removesuffix(".request.json") not in planned_ids for path in prior):
        raise RuntimeError("Unexpected prior TTS request sidecar in chapter output")
    expected_fingerprints = {sid: digest for sid, _, digest in prepared}
    for path in prior:
        sid = path.name.removesuffix(".request.json")
        prior_state = read(path)
        if prior_state.get("fingerprint") != expected_fingerprints[sid]:
            raise RuntimeError(f"Existing TTS request differs for {sid}; do not overwrite")
        if prior_state.get("status") != "audio_received":
            raise RuntimeError(f"Prior TTS request for {sid} requires reconciliation: {prior_state.get('status')}")
    access_path = project / "artifacts" / "elevenlabs-access-preflight.json"
    access = read(access_path)
    if not (access["status"] == "pass" and access["voice_available"] and access["model_available"]
            and access["voice_id"] == VOICE and access["model_id"] == MODEL):
        raise RuntimeError("Current provider voice/model access preflight did not pass")
    planned_characters = sum(len(text) for _, text, _ in prepared)
    remaining = int(access["character_limit"]) - int(access["character_count"])
    if remaining < planned_characters:
        raise RuntimeError(f"Insufficient existing ElevenLabs allowance: need {planned_characters} characters, available {remaining}")
    if dry_run:
        return {"status": "dry_run_pass", "sections": len(prepared),
                "planned_characters": planned_characters, "allowance_remaining": remaining,
                "existing_request_sidecars": len(prior), "new_requests_sent": 0}
    load_dotenv(ROOT / ".env", override=False)
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY is unavailable")
    output.mkdir(parents=True, exist_ok=True)
    sent = 0
    manifest_segments = []
    cursor = 0.0
    for sid, text, digest in prepared:
        sidecar = output / f"{sid}.request.json"
        mp3 = output / f"{sid}.mp3"
        wav = output / f"{sid}.wav"
        state = read(sidecar) if sidecar.is_file() else None
        if state and state.get("fingerprint") != digest:
            raise RuntimeError(f"Existing TTS request differs for {sid}; do not overwrite")
        if state and state.get("status") == "submission_unknown":
            raise RuntimeError(f"Uncertain charged TTS request for {sid}; provider reconciliation required")
        if state and state.get("status") == "provider_rejected":
            raise RuntimeError(f"Provider rejected prior TTS request for {sid}; review before any retry")
        if state is None:
            if mp3.exists() or wav.exists():
                raise RuntimeError(f"Audio without durable request sidecar for {sid}; reconcile before continuing")
            if max_new and sent >= max_new:
                break
            state = {"status": "submission_unknown", "fingerprint": digest,
                     "voice_id": VOICE, "model_id": MODEL, "speed": 0.85,
                     "characters": len(text), "attempted_at": datetime.now(timezone.utc).isoformat()}
            atomic_json(sidecar, state)
            try:
                response = requests.post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}",
                    params={"output_format": "mp3_44100_128"},
                    headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
                    json={"text": text, "model_id": MODEL, "voice_settings": SETTINGS,
                          "apply_text_normalization": "on"},
                    timeout=(10, 180),
                )
            except requests.RequestException as exc:
                raise RuntimeError(f"Uncertain ElevenLabs submission for {sid}; no automatic retry ({type(exc).__name__})") from exc
            if not response.ok:
                state.update(status="provider_rejected", http_status=response.status_code)
                atomic_json(sidecar, state)
                raise RuntimeError(f"ElevenLabs rejected {sid}: HTTP {response.status_code}; no automatic retry")
            content = response.content
            if len(content) < 1000 or not content.startswith((b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
                raise RuntimeError(f"Ambiguous/non-audio successful response for {sid}; no automatic retry")
            temporary = mp3.with_suffix(".mp3.part")
            if temporary.exists():
                raise RuntimeError(f"Unfinished MP3 part for {sid}; inspect before writing")
            temporary.write_bytes(content)
            temporary.replace(mp3)
            state.update(status="audio_received", sha256=hashlib.sha256(content).hexdigest(),
                         audio_bytes=len(content))
            atomic_json(sidecar, state)
            sent += 1
        if not mp3.is_file() or not state or state.get("status") != "audio_received":
            raise RuntimeError(f"Received audio and sidecar are incomplete for {sid}")
        if hashlib.sha256(mp3.read_bytes()).hexdigest() != state["sha256"]:
            raise RuntimeError(f"Received MP3 hash differs for {sid}")
        duration = decode_mp3(mp3, wav)
        manifest_segments.append({"section_id": sid, "text": text,
                                  "spoken_heading": text if sid == prepared[0][0] else section_heading(section=next(s for s in sections if s["section_id"] == sid)),
                                  "audio_path": str(wav), "voice_used": VOICE,
                                  "duration_seconds": duration, "start_seconds": round(cursor, 6),
                                  "title_card_hold_seconds": 0, "topic_end_pause_seconds": 0,
                                  "heading_holds": []})
        cursor += duration
        atomic_json(output / "narration_manifest.json", {
            "version": "1.0", "engine_used": "elevenlabs", "voice_name": VOICE,
            "model_id": MODEL, "speed": 0.85, "generation_complete": len(manifest_segments) == len(prepared),
            "segments": manifest_segments, "total_duration_seconds": round(cursor, 6),
            "pronunciation_qa_status": "pending", "word_alignment_status": "pending",
        })
    return {"status": "complete" if len(manifest_segments) == len(prepared) else "in_progress",
            "completed_sections": len(manifest_segments), "total_sections": len(prepared),
            "new_requests_sent": sent, "manifest": str(output / "narration_manifest.json")}


def section_heading(section: dict) -> str:
    return str(section["title"]).strip() + "."


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--max-new", type=int, default=0,
                        help="Maximum new charged requests this invocation; zero means all")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.project, max_new=args.max_new, dry_run=args.dry_run), indent=2))


if __name__ == "__main__":
    main()
