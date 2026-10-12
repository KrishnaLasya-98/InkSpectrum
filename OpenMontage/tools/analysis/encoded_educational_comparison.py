"""Compare an encoded educational chapter with its source and UI references.

The check is intentionally evidence-based. It validates the encoded container,
word-timing/punctuation data, source-topic coverage in the authored render data,
and the technical envelope of the approved reference videos. It also creates a
candidate contact sheet for the visual review that cannot be inferred from a
hash or DOM artifact alone.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "has", "have", "in", "is", "it", "more", "of", "on", "one", "or", "some",
    "such", "that", "the", "their", "them", "they", "this", "to", "us", "we",
    "with",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _probe(path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format",
         "-show_streams", str(path)], capture_output=True, text=True, timeout=60,
    )
    if completed.returncode:
        return {"error": completed.stderr[-500:]}
    raw = json.loads(completed.stdout)
    streams = raw.get("streams") or []
    video = next((item for item in streams if item.get("codec_type") == "video"), {})
    audio = next((item for item in streams if item.get("codec_type") == "audio"), {})
    rate = str(video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1")
    try:
        numerator, denominator = rate.split("/", 1)
        fps = float(numerator) / max(float(denominator), 1.0)
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    return {
        "duration_seconds": round(float((raw.get("format") or {}).get("duration") or 0), 3),
        "width": int(video.get("width") or 0), "height": int(video.get("height") or 0),
        "fps": round(fps, 3), "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name"), "has_audio": bool(audio),
        "audio_sample_rate": int(audio.get("sample_rate") or 0) if audio else 0,
        "bytes": path.stat().st_size,
    }


def _tokens(value: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", value.casefold())
            if token not in _STOP and len(token) > 1]


def topic_coverage(required_topics: list[str], evidence_text: str) -> list[dict[str, Any]]:
    evidence = set(_tokens(evidence_text))
    results = []
    for topic in required_topics:
        wanted = set(_tokens(topic))
        matched = sorted(wanted & evidence)
        ratio = len(matched) / max(len(wanted), 1)
        results.append({"topic": topic, "keyword_coverage": round(ratio, 3),
                        "matched_keywords": matched, "status": "pass" if ratio >= .7 else "review"})
    return results


def production_evidence(data: dict[str, Any]) -> str:
    values: list[str] = []
    for section in data.get("sections") or []:
        values.extend([str(section.get("heading") or ""), str(section.get("title") or "")])
        values.extend(str(item) for item in section.get("display") or [])
    for caption in data.get("captions") or []:
        values.extend(str(word.get("word") or "") for word in caption.get("words") or [])
    return " ".join(values)


def caption_audit(data: dict[str, Any], duration: float) -> dict[str, Any]:
    issues: list[str] = []
    previous_end = 0.0
    captions = data.get("captions") or []
    nonempty_texts: list[str] = []
    for caption in captions:
        words = caption.get("words") or []
        if not words:
            issues.append(f"{caption.get('id', '?')}: no words")
            continue
        text = " ".join(str(word.get("word") or "") for word in words).strip()
        if text:
            nonempty_texts.append(text)
        start, end = float(caption.get("start") or 0), float(caption.get("end") or 0)
        if start < previous_end - .02 or end <= start or end > duration + .25:
            issues.append(f"{caption.get('id', '?')}: invalid or overlapping timing")
        word_end = start
        for word in words:
            word_start = float(word.get("start") or 0)
            current_end = float(word.get("end") or 0)
            if word_start < word_end - .02 or current_end < word_start:
                issues.append(f"{caption.get('id', '?')}: non-monotonic word timing")
                break
            word_end = current_end
        previous_end = end
    # Captions are deliberately split into short, readable chunks. A chunk may
    # therefore end in the middle of a sentence (for example, "weather and" /
    # "climate."). Requiring punctuation on every chunk produces false
    # failures. Instead, verify that the combined caption stream retains real
    # terminal punctuation and that its final spoken token is terminated.
    terminal_count = sum(text.count(".") + text.count("?") + text.count("!")
                         for text in nonempty_texts)
    if nonempty_texts and terminal_count == 0:
        issues.append("caption stream has no terminal punctuation")
    if nonempty_texts and nonempty_texts[-1][-1] not in ".?!:":
        issues.append("final caption is missing terminal punctuation")
    return {"status": "pass" if not issues else "review", "caption_count": len(captions),
            "terminal_punctuation_count": terminal_count, "issues": issues}


def _contact_sheet(video: Path, duration: float, output: Path, count: int = 12) -> list[str]:
    from PIL import Image, ImageDraw
    output.parent.mkdir(parents=True, exist_ok=True)
    frames_dir = output.parent / (output.stem + "-frames")
    frames_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for index in range(count):
        at = duration * (index + .5) / count
        frame = frames_dir / f"frame-{index + 1:02d}.jpg"
        completed = subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{at:.3f}", "-i", str(video), "-frames:v", "1",
             "-vf", "scale=480:-2", "-q:v", "3", str(frame)],
            capture_output=True, timeout=60,
        )
        if completed.returncode == 0 and frame.is_file():
            paths.append(frame)
    if not paths:
        return []
    with Image.open(paths[0]) as first:
        width, height = first.size
    label_height = 30
    sheet = Image.new("RGB", (width * 3, (height + label_height) * 4), "#142033")
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(paths):
        with Image.open(path) as source:
            image = source.convert("RGB")
        x, y = (index % 3) * width, (index // 3) * (height + label_height)
        sheet.paste(image, (x, y + label_height))
        at = duration * (index + .5) / count
        draw.text((x + 8, y + 7), f"{at:.1f}s", fill="#f8fafc")
    sheet.save(output, quality=90)
    return [str(path) for path in paths]


def compare(candidate: Path, source_pdf: Path, source_audit: Path,
            production_data_path: Path, reference_lock: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_probe = _probe(candidate)
    audit = json.loads(source_audit.read_text(encoding="utf-8"))
    production = json.loads(production_data_path.read_text(encoding="utf-8"))
    lock = json.loads(reference_lock.read_text(encoding="utf-8"))
    references = []
    root = reference_lock.resolve().parents[1]
    for entry in lock.get("references") or []:
        path = (root / entry["path"]).resolve()
        exists = path.is_file()
        actual_sha = _sha256(path) if exists else None
        references.append({"id": entry["id"], "path": str(path), "exists": exists,
                           "sha256_matches": actual_sha == entry.get("sha256") if exists else False,
                           "probe": _probe(path) if exists else {}})

    topics = topic_coverage(list(audit.get("required_topics") or []), production_evidence(production))
    captions = caption_audit(production, float(candidate_probe.get("duration_seconds") or 0))
    contact_path = output_dir / "encoded-contact-sheet.jpg"
    sampled = _contact_sheet(candidate, float(candidate_probe.get("duration_seconds") or 0), contact_path)
    technical_ok = (
        not candidate_probe.get("error") and candidate_probe.get("width") == 1920
        and candidate_probe.get("height") == 1080 and candidate_probe.get("fps", 0) >= 29
        and candidate_probe.get("has_audio") and candidate_probe.get("duration_seconds", 0) > 5
    )
    references_ok = bool(references) and all(item["exists"] and item["sha256_matches"] for item in references)
    topics_ok = bool(topics) and all(item["status"] == "pass" for item in topics)
    report = {
        "version": "1.0", "candidate": str(candidate),
        "candidate_sha256": _sha256(candidate), "candidate_probe": candidate_probe,
        "source": {"pdf": str(source_pdf), "pdf_sha256": _sha256(source_pdf),
                   "source_audit": str(source_audit), "textbook_pages": audit.get("textbook_pages")},
        "source_topic_coverage": topics, "caption_word_timing": captions,
        "reference_videos": references,
        "presentation_contract": lock.get("presentation_contract"),
        "contact_sheet": str(contact_path), "sampled_frames": sampled,
        "automated_status": "pass" if technical_ok and references_ok and topics_ok and captions["status"] == "pass" else "review",
        "gates": {"encoded_technical": technical_ok, "reference_integrity": references_ok,
                  "source_topics": topics_ok, "caption_timing_and_punctuation": captions["status"] == "pass",
                  "contact_sheet_created": contact_path.is_file()},
        "evidence_boundary": (
            "Automation verifies the encoded container, source-topic evidence, caption timing, "
            "and approved reference integrity. A human or VLM must still inspect the generated "
            "contact sheet for semantic visual matching and aesthetic continuity."
        ),
    }
    (output_dir / "encoded-comparison-report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--source-pdf", type=Path, required=True)
    parser.add_argument("--source-audit", type=Path, required=True)
    parser.add_argument("--production-data", type=Path, required=True)
    parser.add_argument("--reference-lock", type=Path, default=Path("config/educational-reference-lock.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = compare(*(value.resolve() for value in (
        args.candidate, args.source_pdf, args.source_audit, args.production_data,
        args.reference_lock, args.output_dir)))
    print(json.dumps({"status": report["automated_status"], "gates": report["gates"],
                      "report": str(args.output_dir / "encoded-comparison-report.json"),
                      "contact_sheet": report["contact_sheet"]}, indent=2))
    return 0 if report["automated_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
