"""Build Chapter 2 HyperFrames from new Qwen audio and measured captions.

The earlier Kokoro review composition remains untouched. Teaching text, diagrams,
and one-use moving clips come from the reviewed Chapter 2 source artifacts.
"""
from __future__ import annotations

import json
import argparse
import re
from copy import deepcopy
from difflib import SequenceMatcher
from pathlib import Path

from tools.video.educational_hyperframes_composer import EducationalHyperFramesComposer

from build_teaching_pages import build as build_teaching_pages


PROJECT = Path(__file__).resolve().parent
REPO = PROJECT.parents[1]
ARTIFACTS = PROJECT / "artifacts"
def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def map_time(value: float, old_heading: float, old_duration: float,
             new_heading: float, new_duration: float) -> float:
    if value <= old_heading:
        return value * new_heading / max(old_heading, .001)
    body_ratio = (new_duration - new_heading) / max(old_duration - old_heading, .001)
    return new_heading + (value - old_heading) * body_ratio


def _tokens(value: str) -> list[str]:
    return [re.sub(r"[^a-z0-9]", "", word.casefold())
            for word in value.split() if re.sub(r"[^a-z0-9]", "", word.casefold())]


def cue_start_seconds(cue: str, aligned: dict, *, section_id: str) -> tuple[float, float]:
    """Locate a visual's narrated cue instead of scaling old clip offsets."""
    cue_words = _tokens(cue)
    words = aligned.get("words") or []
    heard = [_tokens(str(word["word"])) for word in words]
    heard = [item[0] if item else "" for item in heard]
    if not cue_words or not words:
        raise ValueError(f"Missing spoken cue/alignment: {section_id}: {cue}")
    best = (0.0, 0)
    for index in range(len(heard)):
        if not heard[index]:
            continue
        for width in range(max(1, len(cue_words) - 2), len(cue_words) + 4):
            candidate = heard[index:index + width]
            if not candidate:
                continue
            score = SequenceMatcher(None, cue_words, candidate, autojunk=False).ratio()
            if score > best[0]:
                best = (score, index)
    if best[0] < 0.64:
        raise ValueError(f"Visual cue not grounded in speech: {section_id}: {cue} ({best[0]:.2f})")
    relative = (float(words[best[1]]["start_ms"]) - float(aligned["start_ms"])) / 1000
    return max(0.0, relative - 0.15), round(best[0], 3)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="qwen-v3")
    parser.add_argument("--narration-manifest", type=Path)
    parser.add_argument("--alignment-dir", type=Path)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--safe-media-manifest", type=Path)
    parser.add_argument("--cue-align", action="store_true")
    args = parser.parse_args()
    version = args.version
    old_audio = read(PROJECT / "assets/audio/narration-v1/narration_manifest.json")
    new_audio_path = args.narration_manifest or PROJECT / "assets/audio/narration-qwen-final-v3/narration_manifest.json"
    new_audio = read(new_audio_path)
    old_by_id = {s["section_id"]: s for s in old_audio["segments"]}
    new_by_id = {s["section_id"]: s for s in new_audio["segments"]}
    if list(old_by_id) != list(new_by_id) or len(new_by_id) != 15:
        raise ValueError("Approved Chapter 2 section order changed")
    clips = deepcopy(read(ARTIFACTS / "clip-manifest-draft-v1.json"))
    safe = read(args.safe_media_manifest or ARTIFACTS / "render-safe-media-v1.json")
    safe_paths = {(r["section_id"], r["segment_index"]): r for r in safe["records"]}
    spoken_sections = {}
    cue_report = []
    if args.cue_align:
        alignment_dir = args.alignment_dir or ARTIFACTS / "alignment-qwen-v3"
        spoken_sections = {segment["section_id"]: segment for segment in
                           read(alignment_dir / "narration_aligned.json")["segments"]}
    timeline = []
    cursor = 0.0
    for clip in clips["clips"]:
        section_id = clip["section_id"]
        old = old_by_id[section_id]
        new = new_by_id[section_id]
        old_duration = float(old["duration_seconds"])
        new_duration = float(new["duration_seconds"])
        old_heading = float(old.get("body_start_seconds") or 0)
        new_heading = float(new.get("body_start_seconds") or 0)
        def mapped(t: float) -> float:
            return max(0.0, min(new_duration, map_time(t, old_heading,
                                                       old_duration, new_heading, new_duration)))
        for index, segment in enumerate(clip.get("visual_segments") or [], 1):
            record = safe_paths[(section_id, index)]
            if segment["path"] != record["original_path"]:
                raise ValueError(f"Render-safe provenance mismatch: {section_id} #{index}")
            segment["path"] = record["render_safe_path"]
            old_start = float(segment["offset_seconds"])
            old_end = old_start + float(segment["duration_seconds"])
            if args.cue_align:
                cue = str(segment.get("cue") or "")
                if section_id == "s01-title":
                    start, score = 0.0, 1.0
                elif section_id == "s05-two-movements":
                    start, score = new_heading, 1.0
                else:
                    start, score = cue_start_seconds(
                        cue, spoken_sections[section_id], section_id=section_id)
                available = float(record["render_safe_duration_seconds"])
                end = min(new_duration - .08, start + min(available - .08, mapped(old_end) - mapped(old_start)))
                # Chapter 2's approved opening and blue-ball Start-Up are
                # visual context for their headings, not examples introduced
                # later. Keep those moving scenes present through the spoken
                # title and its pause instead of exposing an empty canvas.
                if section_id == "s01-title":
                    end = min(new_duration - .08, available - .08)
                elif section_id in {"s02-objectives", "s03-startup"} and index == 1:
                    start = 0.0
                    end = min(new_duration - .08, available - .08)
                elif section_id in {"s05-two-movements", "s06-rotation", "s08-revolution"} and index == 1:
                    # These long single-use concept clips still cover their
                    # named spoken cue when led from the in-scene heading.
                    if end - start >= start + 1.0:
                        end -= start
                        start = 0.0
                if end - start < 1.5:
                    start = max(0.0, new_duration - 1.9)
                    end = new_duration - .08
                cue_report.append({"section_id": section_id, "cue": cue,
                                   "start_seconds": round(start, 3), "match_score": score})
            else:
                start = mapped(old_start)
                end = mapped(old_end)
            segment["offset_seconds"] = round(start, 3)
            segment["duration_seconds"] = round(end - start, 3)
            if segment["duration_seconds"] < 1.5:
                raise ValueError(f"Visual clip too short after retiming: {section_id} #{index}")
        for figure in clip.get("source_figure_overlays") or []:
            old_start = float(figure["offset_seconds"])
            old_end = old_start + float(figure["duration_seconds"])
            figure["offset_seconds"] = round(mapped(old_start), 3)
            figure["duration_seconds"] = round(mapped(old_end) - mapped(old_start), 3)
        clip["source_card_intervals"] = [[0, round(new_duration, 3)]]
        timeline.append({"section_id": section_id, "start_seconds": round(cursor, 3),
                         "end_seconds": round(cursor + new_duration, 3),
                         "visual_duration_policy": "as_is"})
        cursor += new_duration
    sync = {"version": "1.0", "status": "pass", "review_state": "timed_visual_qa_pending",
            "issues": [], "total_duration_seconds": round(cursor, 3), "timeline": timeline}
    sync_path = ARTIFACTS / f"multimedia-sync-{version}.json"
    sync_path.write_text(json.dumps(sync, indent=2) + "\n", encoding="utf-8")
    if args.cue_align:
        (ARTIFACTS / f"visual-cue-alignment-{version}.json").write_text(
            json.dumps(cue_report, indent=2) + "\n", encoding="utf-8")
    captions_path = (args.alignment_dir or ARTIFACTS / "alignment-qwen-v3") / "word_captions.json"
    pages_path = ARTIFACTS / f"teaching-pages-{version}.json"
    pages = build_teaching_pages(sync_path, captions_path, pages_path)
    if pages.get("unmatched_anchors"):
        raise ValueError("Teaching-page speech anchors unmatched; inspect before composition")
    for clip in clips["clips"]:
        if clip["section_id"] in pages["sections"]:
            clip["teaching_pages"] = pages["sections"][clip["section_id"]]
    clips_path = ARTIFACTS / f"clip-manifest-{version}.json"
    clips_path.write_text(json.dumps(clips, indent=2) + "\n", encoding="utf-8")
    result = EducationalHyperFramesComposer().execute({
        "workspace_path": str(args.workspace or PROJECT / "hyperframes-qwen-v3"),
        "asset_base_dir": str(PROJECT),
        "template_contract": str(REPO / "styles/hyperframes-educational-v1.yaml"),
        "educational_plan": str(ARTIFACTS / "educational_plan.json"),
        "clip_manifest": clips,
        "narration_manifest": str(new_audio_path),
        "multimedia_sync_plan": sync,
        "word_captions": str(captions_path),
        "presentation_variant": read(PROJECT / "chapter_config.json")["presentation_variant"],
    })
    if not result.success:
        raise RuntimeError(result.error)
    print(json.dumps({"duration_seconds": round(cursor, 3), "composition": result.data}, indent=2))


if __name__ == "__main__":
    main()
