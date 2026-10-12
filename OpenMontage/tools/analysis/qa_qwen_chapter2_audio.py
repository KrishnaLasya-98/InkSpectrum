"""ASR-based listening triage for the full Qwen Chapter 2 narration.

The report highlights possible omissions and pronunciations; ASR disagreement
is not silently converted into a corrected subtitle or a false pass.
"""
from __future__ import annotations

import json
import re
import argparse
from difflib import SequenceMatcher
from pathlib import Path

from faster_whisper import WhisperModel


REPO = Path(__file__).resolve().parents[2]
PROJECT = REPO / "projects/class-5-social-part-0-chapter-2-earth-movement"
ROOT = PROJECT / "assets/audio/narration-qwen-final-v3"


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.casefold())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="small.en")
    parser.add_argument("--sections", nargs="*")
    parser.add_argument("--manifest", type=Path, default=ROOT / "narration_manifest.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    selected = [s for s in manifest["segments"] if not args.sections or s["section_id"] in args.sections]
    if args.sections and len(selected) != len(args.sections):
        raise ValueError("Unknown section in --sections")
    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    records = []
    for index, section in enumerate(selected, 1):
        segments, _ = model.transcribe(section["audio_path"], language="en", beam_size=5,
                                       vad_filter=False, condition_on_previous_text=False)
        heard = " ".join(segment.text.strip() for segment in segments)
        expected_words = tokens(section["text"])
        heard_words = tokens(heard)
        matcher = SequenceMatcher(None, expected_words, heard_words, autojunk=False)
        ratio = matcher.ratio()
        mismatches = []
        for operation, a0, a1, b0, b1 in matcher.get_opcodes():
            if operation != "equal":
                mismatches.append({"operation": operation,
                                   "expected": " ".join(expected_words[a0:a1]),
                                   "heard": " ".join(heard_words[b0:b1])})
        records.append({"section_id": section["section_id"], "lexical_similarity": round(ratio, 4),
                        "expected_words": len(expected_words), "heard_words": len(heard_words),
                        "mismatches": mismatches, "asr_transcript": heard})
        print(f"ASR {index}/{len(selected)}: {section['section_id']} {ratio:.3f}", flush=True)
    report = {"status": "review_required", "model": f"faster-whisper-{args.model}",
              "sections": records, "minimum_similarity": min(r["lexical_similarity"] for r in records),
              "overall_similarity": round(sum(r["lexical_similarity"] * r["expected_words"] for r in records) /
                                          sum(r["expected_words"] for r in records), 4)}
    target = args.output or PROJECT / f"artifacts/qwen-v3-asr-qa-{args.model.replace('.', '-')}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"path": str(target), "overall_similarity": report["overall_similarity"],
                      "minimum_similarity": report["minimum_similarity"]}, indent=2))


if __name__ == "__main__":
    main()
