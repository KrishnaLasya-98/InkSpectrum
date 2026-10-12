"""Place measured two-second title holds in the new ElevenLabs narration."""
from __future__ import annotations

import argparse
import json
import subprocess
from copy import deepcopy
from pathlib import Path

from tools.analysis.narration_text_syncer import _align_with_faster_whisper
from tools.voice.elevenlabs_chapter2 import PROJECT, SOURCE, VOICE_ID
from tools.voice.qwen_two_minute_review import probe_seconds, write_json
from tools.voice.finalize_qwen_chapter2 import HOLD, TOPIC_PAUSE, render_with_hold


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    args = parser.parse_args()
    generated = PROJECT / f"assets/audio/narration-elevenlabs-{VOICE_ID}-v1"
    finished = PROJECT / f"assets/audio/narration-elevenlabs-final-{VOICE_ID}-v1"
    finished.mkdir(parents=True, exist_ok=True)
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    progress = json.loads((generated / "generation-progress.json").read_text(encoding="utf-8"))
    if progress["complete"] != 15 or len(source["segments"]) != 15:
        raise ValueError("Full Chapter 2 speech generation is incomplete")
    manifest = deepcopy(source)
    manifest.update(engine_used="elevenlabs", voice_name=VOICE_ID,
                    generation_complete=False)
    for index, section in enumerate(manifest["segments"], 1):
        section_id = section["section_id"]
        mp3 = generated / f"{section_id}.mp3"
        wav = generated / f"{section_id}.wav"
        output = finished / f"{section_id}.wav"
        if not mp3.is_file():
            raise FileNotFoundError(mp3)
        if not wav.is_file():
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3),
                            "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(wav)],
                           check=True, timeout=90)
        words = _align_with_faster_whisper(wav, section["text"])
        if not words or len(words) != len(section["text"].split()):
            raise RuntimeError(f"Cannot locate spoken heading in {section_id}")
        heading = section.get("spoken_heading", "").strip()
        heading_words = len(heading.split()) if heading else len(words)
        boundary = min(probe_seconds(wav), words[heading_words - 1]["end_ms"] / 1000)
        if boundary < 0.25:
            raise ValueError(f"Implausible spoken heading boundary: {section_id}")
        tail = 0.0 if index == 1 else TOPIC_PAUSE
        render_with_hold(wav, output, boundary, tail)
        section.update(audio_path=str(output), duration_seconds=round(probe_seconds(output), 3),
                       voice_used=VOICE_ID,
                       heading_duration_seconds=round(boundary, 3),
                       body_start_seconds=round(boundary + HOLD, 3),
                       title_card_hold_seconds=HOLD,
                       topic_end_pause_seconds=tail,
                       heading_holds=([{"title": "Lesson 2: Earth Movement",
                                        "start_seconds": round(boundary, 3),
                                        "end_seconds": round(boundary + HOLD, 3)}]
                                      if index == 1 else []))
        print(f"ElevenLabs heading timed {index}/15: {section_id}", flush=True)
    manifest["generation_complete"] = True
    write_json(finished / "narration_manifest.json", manifest)
    print(json.dumps({"status": "audio_ready_alignment_pending", "voice_id": VOICE_ID,
                      "sections": len(manifest["segments"]),
                      "duration_seconds": round(sum(s["duration_seconds"] for s in manifest["segments"]), 3),
                      "manifest": str(finished / "narration_manifest.json")}, indent=2))


if __name__ == "__main__":
    main()
