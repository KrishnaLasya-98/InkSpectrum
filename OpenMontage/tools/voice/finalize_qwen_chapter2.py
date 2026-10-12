"""Insert measured two-second heading holds into approved Chapter 2 Qwen speech."""
from __future__ import annotations

import json
import subprocess
from copy import deepcopy
from pathlib import Path

from tools.analysis.narration_text_syncer import _align_with_faster_whisper
from tools.voice.qwen_two_minute_review import probe_seconds, write_json


REPO = Path(__file__).resolve().parents[2]
PROJECT = REPO / "projects/class-5-social-part-0-chapter-2-earth-movement"
SOURCE = PROJECT / "assets/audio/narration-v1/narration_manifest.json"
RAW_DIR = PROJECT / "assets/audio/narration-qwen-v2"
FINAL_DIR = PROJECT / "assets/audio/narration-qwen-final-v3"
HEADING_DIR = PROJECT / "assets/audio/qwen-heading-repair-v1"
HOLD = 2.0
TOPIC_PAUSE = 1.5


def render_with_hold(source: Path, target: Path, boundary: float, tail: float) -> None:
    duration = probe_seconds(source)
    if boundary >= duration - 0.12:
        graph = f"[0:a]apad=pad_dur={HOLD + tail:.3f}[a]"
    else:
        graph = (
            f"[0:a]atrim=end={boundary:.5f},asetpts=PTS-STARTPTS[pre];"
            f"[0:a]atrim=start={boundary:.5f},asetpts=PTS-STARTPTS[post];"
            f"anullsrc=r=24000:cl=mono:d={HOLD:.3f}[hold];"
            f"anullsrc=r=24000:cl=mono:d={tail:.3f}[tail];"
            "[pre][hold][post][tail]concat=n=4:v=0:a=1[a]"
        )
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(source),
        "-filter_complex", graph, "-map", "[a]", "-ar", "24000", "-ac", "1",
        "-c:a", "pcm_s16le", str(target)], check=True, timeout=120)


def render_with_spoken_heading(heading: Path, body: Path, target: Path, tail: float) -> None:
    graph = (
        f"anullsrc=r=24000:cl=mono:d={HOLD:.3f}[hold];"
        f"anullsrc=r=24000:cl=mono:d={tail:.3f}[tail];"
        "[0:a][hold][1:a][tail]concat=n=4:v=0:a=1[a]"
    )
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(heading),
        "-i", str(body), "-filter_complex", graph, "-map", "[a]",
        "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(target)],
        check=True, timeout=120)


def main() -> None:
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    base = json.loads(SOURCE.read_text(encoding="utf-8"))
    generation = json.loads((RAW_DIR / "generation-progress.json").read_text(encoding="utf-8"))
    spoken = {s["section_id"]: s["text"] for s in generation["segments"]}
    if generation["complete"] != len(base["segments"]):
        raise ValueError("Full Qwen generation is incomplete")
    output = deepcopy(base)
    output.update(engine_used="modelslab-qwen-tts", voice_name="approved-indian-reference-clone",
                  generation_complete=False)
    for index, section in enumerate(output["segments"], 1):
        section_id = section["section_id"]
        section["source_text"] = section["text"]
        section["text"] = spoken[section_id]
        source = RAW_DIR / f"{section_id}.wav"
        target = FINAL_DIR / f"{section_id}.wav"
        if not source.is_file():
            raise FileNotFoundError(source)
        if section_id in {"s06-rotation", "s08-revolution"}:
            heading_path = HEADING_DIR / f"{section_id}-heading.wav"
            if not heading_path.is_file():
                raise FileNotFoundError(heading_path)
            boundary = probe_seconds(heading_path)
            render_with_spoken_heading(heading_path, source, target, TOPIC_PAUSE)
            tail = TOPIC_PAUSE
        else:
            # Align continuous speech before introducing silence. This is the
            # measured end of the pronounced heading, not a proportional estimate.
            words = _align_with_faster_whisper(source, section["text"])
            if not words or len(words) != len(section["text"].split()):
                raise RuntimeError(f"Measured heading alignment failed: {section_id}")
            heading = section.get("spoken_heading", "").strip()
            heading_words = len(heading.split()) if heading else len(words)
            if heading_words < 1 or heading_words > len(words):
                raise ValueError(f"Bad heading token count: {section_id}")
            boundary = words[heading_words - 1]["end_ms"] / 1000
            raw_duration = probe_seconds(source)
            if not 0.3 <= boundary <= raw_duration + 0.1:
                raise ValueError(f"Invalid measured heading end: {section_id}: {boundary}")
            boundary = min(boundary, raw_duration)
            tail = 0.0 if index == 1 else TOPIC_PAUSE
            render_with_hold(source, target, boundary, tail)
        section.update(audio_path=str(target), duration_seconds=round(probe_seconds(target), 3),
                       voice_used="approved-indian-reference-clone",
                       heading_duration_seconds=round(boundary, 3),
                       body_start_seconds=round(boundary + HOLD, 3),
                       title_card_hold_seconds=HOLD,
                       topic_end_pause_seconds=tail,
                       heading_holds=([{"title": "Lesson 2: Earth Movement",
                                        "start_seconds": round(boundary, 3),
                                        "end_seconds": round(boundary + HOLD, 3)}]
                                      if index == 1 else []))
        print(f"Held heading {index}/{len(output['segments'])}: {section_id}", flush=True)
    output["generation_complete"] = True
    write_json(FINAL_DIR / "narration_manifest.json", output)
    print(json.dumps({"status": "audio_ready_alignment_pending", "sections": len(output["segments"]),
                      "duration_seconds": round(sum(s["duration_seconds"] for s in output["segments"]), 3),
                      "manifest": str(FINAL_DIR / "narration_manifest.json")}, indent=2))


if __name__ == "__main__":
    main()
