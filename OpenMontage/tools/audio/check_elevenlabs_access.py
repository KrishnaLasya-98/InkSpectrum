"""Read-only ElevenLabs voice/model/quota preflight without exposing credentials."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", required=True, type=Path)
    parser.add_argument("--voice-id", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    project = args.project_dir.resolve()
    load_dotenv(args.repo_root.resolve() / ".env", override=False)
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY is not available")
    headers = {"xi-api-key": key}
    subscription = requests.get("https://api.elevenlabs.io/v1/user/subscription", headers=headers, timeout=(10, 30))
    voices = requests.get("https://api.elevenlabs.io/v1/voices", headers=headers, timeout=(10, 30))
    models = requests.get("https://api.elevenlabs.io/v1/models", headers=headers, timeout=(10, 30))
    for response in (subscription, voices, models):
        response.raise_for_status()
    sub = subscription.json()
    result = {
        "status": "pass",
        "voice_id": args.voice_id,
        "voice_available": any(row.get("voice_id") == args.voice_id for row in voices.json().get("voices", [])),
        "model_id": args.model_id,
        "model_available": any(row.get("model_id") == args.model_id for row in models.json()),
        "character_count": sub.get("character_count"),
        "character_limit": sub.get("character_limit"),
        "can_extend_character_limit": sub.get("can_extend_character_limit"),
        "next_character_count_reset_unix": sub.get("next_character_count_reset_unix"),
    }
    if not result["voice_available"] or not result["model_available"]:
        result["status"] = "blocked"
    output = project / "artifacts" / "elevenlabs-access-preflight.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
