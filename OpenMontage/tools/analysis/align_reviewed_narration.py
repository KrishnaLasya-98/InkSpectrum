"""Speech-derived word alignment for a source-reviewed chapter narration.

Uses measured section audio lengths as the global timing authority. Linear
interpolation cannot pass this production gate. Pronunciation listening and
encoded video QA remain separate requirements.
"""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path

import soundfile as sf

from lib.production_runtime import atomic_json
from tools.analysis.narration_text_syncer import NarrationTextSyncer
from tools.structure.educational_run_tracker import EducationalRunTracker


def align(project: Path, narration_dir_override: Path | None = None,
          output_dir_override: Path | None = None) -> dict:
    project = project.resolve()
    config = json.loads((project / "chapter_config.json").read_text(encoding="utf-8"))
    plan = json.loads((project / "artifacts" / "educational_plan.json").read_text(encoding="utf-8"))
    narration_dir = (narration_dir_override or project / "assets" / "audio" / "narration-v1").resolve()
    manifest = json.loads((narration_dir / "narration_manifest.json").read_text(encoding="utf-8"))
    sections = plan["sections"]
    if not manifest.get("generation_complete") or len(manifest["segments"]) != len(sections):
        raise ValueError("Narration is not complete for every scoped section")
    if [s["section_id"] for s in sections] != [s["section_id"] for s in manifest["segments"]]:
        raise ValueError("Narration section order differs from the authored plan")
    timeline_manifest = deepcopy(manifest)
    cursor = 0.0
    for segment in timeline_manifest["segments"]:
        audio = Path(segment["audio_path"])
        if not audio.is_file():
            raise ValueError(f"Missing chapter audio: {audio}")
        info = sf.info(str(audio))
        duration = info.frames / info.samplerate
        if abs(duration - float(segment["duration_seconds"])) > 0.12:
            raise ValueError(f"Measured audio duration drift in {segment['section_id']}")
        segment["start_seconds"] = round(cursor, 3)
        cursor += duration
        segment["end_seconds"] = round(cursor, 3)
    output_dir = (output_dir_override or project / "artifacts" / "alignment-v1").resolve()
    tracker = EducationalRunTracker(project, title=plan["title"],
                                    approval_policy=config["approval_policy"])
    alternate_run = narration_dir_override is not None or output_dir_override is not None
    if not alternate_run:
        tracker.begin("text_audio_alignment", metadata={"audio_manifest": str(narration_dir / "narration_manifest.json")})
    result = NarrationTextSyncer().execute({
        "narration_manifest": timeline_manifest,
        "educational_plan": plan,
        "output_dir": str(output_dir),
        "title_offset_seconds": 0.0,
    })
    if not result.success:
        if not alternate_run:
            tracker.fail("text_audio_alignment", result.error or "word alignment failed")
        raise RuntimeError(result.error)
    method = result.data["alignment_method"]
    aligned = result.data["narration_aligned"]
    if "linear_interpolation" in method or len(aligned) != len(sections):
        if not alternate_run:
            tracker.fail("text_audio_alignment", f"Non-speech-derived alignment: {method}")
        raise ValueError("Production requires measured speech-derived word timing")
    errors = []
    for segment, audio in zip(aligned, timeline_manifest["segments"]):
        words = segment["words"]
        expected = audio["text"].split()
        if len(words) != len(expected):
            errors.append(f"word count {segment['section_id']}")
        if any(words[i]["end_ms"] > words[i+1]["start_ms"] + 150 for i in range(len(words)-1)):
            errors.append(f"word overlap {segment['section_id']}")
        if words and (words[0]["start_ms"] < segment["start_ms"] - 150
                      or words[-1]["end_ms"] > segment["end_ms"] + 150):
            errors.append(f"word outside audio {segment['section_id']}")
    if errors:
        if not alternate_run:
            tracker.fail("text_audio_alignment", "; ".join(errors))
        raise ValueError("Word alignment needs repair: " + "; ".join(errors))
    atomic_json(output_dir / "measured_timeline.json", {
        "version": "1.0", "duration_seconds": round(cursor, 3),
        "segments": [{k: s[k] for k in ("section_id", "start_seconds", "end_seconds", "duration_seconds")}
                     for s in timeline_manifest["segments"]],
    })
    report = {"status": "pass", "alignment_method": method,
              "sections": len(sections), "words": sum(len(s["words"]) for s in aligned),
              "duration_seconds": round(cursor, 3),
              "pronunciation_review": "pending", "encoded_video_review": "pending"}
    atomic_json(output_dir / "alignment-qa.json", report)
    if not alternate_run:
        tracker.finish("text_audio_alignment", {
            "narration_aligned_path": str(output_dir / "narration_aligned.json"),
            "word_captions_path": str(output_dir / "word_captions.json"),
            "formatted_srt_path": result.data["formatted_srt_path"],
            "timing_qa_path": str(output_dir / "alignment-qa.json"),
        }, metadata={"method": method, "words": report["words"],
                     "duration_seconds": report["duration_seconds"]})
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--narration-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(align(args.project, args.narration_dir, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
