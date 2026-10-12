"""Add only the missing silence needed for two-second in-scene title pauses.

The approved Eleven v4 utterances stay intact. A quiet, short-faded join is made
between the measured heading and first body word; no full-screen card is added.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from copy import deepcopy
from pathlib import Path

import numpy as np
import soundfile as sf

from tools.analysis.narration_text_syncer import _build_formatted_srt, _build_word_captions


PROJECT = Path(__file__).resolve().parent
ARTIFACTS = PROJECT / "artifacts"
SOURCE = PROJECT / "assets/audio/narration-elevenlabs-continuous-v2/narration_manifest.json"
ALIGNED = ARTIFACTS / "alignment-elevenlabs-continuous-v2/narration_aligned.json"
OUTPUT = PROJECT / "assets/audio/narration-elevenlabs-title-pause-v4"
PAUSE_SECONDS = 2.0


def _heading_silence(source_audio: Path, estimated_heading_end: float) -> tuple[float, float]:
    """Find the real acoustic gap at the heading, not ASR's guessed word gap."""
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(source_audio), "-af",
         "silencedetect=noise=-38dB:d=0.18", "-f", "null", os.devnull],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode:
        raise RuntimeError(f"Silence detection failed: {source_audio}: {result.stderr[-500:]}")
    starts = [float(value) for value in re.findall(r"silence_start:\s*([0-9.]+)", result.stderr)]
    ends = [float(value) for value in re.findall(r"silence_end:\s*([0-9.]+)", result.stderr)]
    gaps = [(start, end) for start, end in zip(starts, ends, strict=True)
            if start <= estimated_heading_end + .40 and end >= estimated_heading_end - .20]
    if not gaps:
        raise ValueError(f"No quiet title-to-body edit point near {estimated_heading_end:.3f}s in {source_audio}")
    return min(gaps, key=lambda pair: abs(pair[0] - estimated_heading_end))


def _splice(raw: np.ndarray, sample_rate: int, cut_seconds: float,
            missing_seconds: float) -> np.ndarray:
    cut = max(0, min(len(raw), round(cut_seconds * sample_rate)))
    pad = max(0, round(missing_seconds * sample_rate))
    before = raw[:cut].copy()
    after = raw[cut:].copy()
    # A short fade prevents a click if the speech has no natural gap here.
    fade = min(round(.008 * sample_rate), len(before), len(after))
    if fade:
        before[-fade:] *= np.linspace(1.0, 0.0, fade, endpoint=True)
        after[:fade] *= np.linspace(0.0, 1.0, fade, endpoint=True)
    return np.concatenate((before, np.zeros(pad, dtype=raw.dtype), after))


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    aligned = json.loads(ALIGNED.read_text(encoding="utf-8"))
    lookup = {s["section_id"]: s for s in aligned["segments"]}
    manifest = deepcopy(source)
    manifest["timing_policy"] = (
        "two seconds total after spoken title; natural gap counted; "
        "inline heading with no duplicate full-screen card"
    )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    cursor = 0.0
    audit = []
    for segment in manifest["segments"]:
        section_id = segment["section_id"]
        timing = lookup[section_id]
        words = timing["words"]
        heading = str(segment.get("spoken_heading") or "").strip()
        heading_count = len(heading.split()) if heading else len(words)
        if not 1 <= heading_count <= len(words):
            raise ValueError(f"Invalid heading count: {section_id}")
        estimated_heading_end = (words[heading_count - 1]["end_ms"] - timing["start_ms"]) / 1000
        source_audio = Path(segment["audio_path"])
        raw, sample_rate = sf.read(source_audio, dtype="float32")
        if raw.ndim != 1 or sample_rate != 24000:
            raise ValueError(f"Expected mono 24kHz source: {source_audio}")
        original_duration = len(raw) / sample_rate
        heading_end, next_onset = _heading_silence(source_audio, estimated_heading_end)
        natural_gap = max(0.0, next_onset - heading_end)
        missing = max(0.0, PAUSE_SECONDS - natural_gap)
        if heading_count == len(words):
            edited = np.concatenate((raw, np.zeros(round(missing * sample_rate), dtype=raw.dtype)))
            body_start = heading_end
            cut = original_duration
        else:
            cut = (heading_end + next_onset) / 2
            edited = _splice(raw, sample_rate, cut, missing)
            body_start = next_onset + missing
        target = OUTPUT / f"{section_id}.wav"
        sf.write(target, edited, sample_rate, subtype="PCM_16")
        acoustic_start, acoustic_end = _heading_silence(target, heading_end)
        acoustic_pause = acoustic_end - acoustic_start
        if not 1.95 <= acoustic_pause <= 2.05:
            raise ValueError(f"Encoded title pause is not two seconds: {section_id}: {acoustic_pause:.3f}")
        duration = len(edited) / sample_rate
        segment.update(
            audio_path=str(target),
            duration_seconds=round(duration, 3),
            start_seconds=round(cursor, 3),
            heading_duration_seconds=round(heading_end, 3),
            body_start_seconds=round(body_start, 3),
            title_card_hold_seconds=0,
            topic_end_pause_seconds=0,
            heading_holds=[],
            heading_pause_presentation="inline",
            measured_title_pause_seconds=round(natural_gap + missing, 3),
        )
        audit.append({"section_id": section_id, "heading_end_seconds": round(heading_end, 3),
                      "first_body_word_seconds": round(body_start, 3),
                      "natural_pause_seconds": round(natural_gap, 3),
                      "inserted_pause_seconds": round(missing, 3),
                      "edit_point_seconds": round(cut, 3),
                      "total_pause_seconds": round(natural_gap + missing, 3),
                      "verified_acoustic_pause_seconds": round(acoustic_pause, 3)})
        cursor += duration
    manifest_path = OUTPUT / "narration_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (ARTIFACTS / "title-pause-audit-elevenlabs-v4.json").write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    # Preserve the measured word positions from the continuous utterance.
    # Re-running ASR across two seconds of new silence can shift the first
    # body word by hundreds of milliseconds even though its waveform did not
    # change. Rebase the unchanged speech analytically instead.
    alignment_dir = ARTIFACTS / "alignment-elevenlabs-title-pause-v4"
    alignment_dir.mkdir(parents=True, exist_ok=True)
    rebased = deepcopy(aligned)
    for segment, record, entry in zip(rebased["segments"], manifest["segments"], audit, strict=True):
        if segment["section_id"] != entry["section_id"]:
            raise ValueError("Narration/alignment section order changed")
        old_start = int(segment["start_ms"])
        new_start = round(float(record["start_seconds"]) * 1000)
        inserted_ms = round(float(entry["inserted_pause_seconds"]) * 1000)
        cut_ms = round(float(entry["edit_point_seconds"]) * 1000)
        heading_count = len(str(record.get("spoken_heading") or "").split()) or len(segment["words"])
        has_body = heading_count < len(segment["words"])
        for word in segment["words"]:
            relative_start = int(word["start_ms"]) - old_start
            relative_end = int(word["end_ms"]) - old_start
            shift_start = inserted_ms if has_body and relative_start >= cut_ms else 0
            shift_end = inserted_ms if has_body and relative_end > cut_ms else 0
            word["start_ms"] = new_start + relative_start + shift_start
            word["end_ms"] = new_start + relative_end + shift_end
        segment["words"][heading_count - 1]["end_ms"] = (
            new_start + round(float(entry["heading_end_seconds"]) * 1000))
        if has_body:
            first_body = segment["words"][heading_count]
            first_body["start_ms"] = new_start + round(float(record["body_start_seconds"]) * 1000)
            first_body["end_ms"] = max(first_body["end_ms"], first_body["start_ms"] + 80)
        segment["start_ms"] = new_start
        segment["end_ms"] = new_start + round(float(record["duration_seconds"]) * 1000)
    (alignment_dir / "narration_aligned.json").write_text(
        json.dumps(rebased, indent=2) + "\n", encoding="utf-8")
    captions = _build_word_captions(rebased["segments"])
    (alignment_dir / "word_captions.json").write_text(
        json.dumps(captions, indent=2) + "\n", encoding="utf-8")
    (alignment_dir / "formatted_subtitles.srt").write_text(
        _build_formatted_srt(rebased["segments"]), encoding="utf-8")
    for segment, record in zip(rebased["segments"], manifest["segments"], strict=True):
        heading_count = len(str(record.get("spoken_heading") or "").split()) or len(segment["words"])
        if heading_count < len(segment["words"]):
            actual_pause = (segment["words"][heading_count]["start_ms"] -
                            segment["words"][heading_count - 1]["end_ms"]) / 1000
            if actual_pause < PAUSE_SECONDS - .02:
                raise ValueError(f"Title pause shorter than two seconds: {segment['section_id']}: {actual_pause}")
    print(json.dumps({"sections": len(audit), "duration_seconds": round(cursor, 3),
                      "min_title_pause_seconds": min(a["total_pause_seconds"] for a in audit),
                      "manifest": str(manifest_path),
                      "alignment_method": "measured original words with exact inserted-sample rebase"}, indent=2))


if __name__ == "__main__":
    main()
