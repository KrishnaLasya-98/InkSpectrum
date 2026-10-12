"""Resumable OpenDataLoader extraction for reviewed textbook chapter maps.

The source PDF remains authoritative. This utility preserves original PDF pages
when splitting, calls the official OpenDataLoader CLI in hybrid OCR mode, keeps
Markdown/JSON/bounding boxes/extracted images per chapter, and writes a compact
validation report suitable for the educational video proposal stage.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Iterable
from urllib.request import urlopen


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "chapter"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def walk_items(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if "type" in value:
            yield value
        for child in value.values():
            yield from walk_items(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_items(child)


def split_chapters(source: Path, chapter_map: dict[str, Any], split_dir: Path) -> list[Path]:
    import pymupdf

    split_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    with pymupdf.open(source) as document:
        page_count = len(document)
        for entry in chapter_map["chapters"]:
            number = int(entry["chapter"])
            start = int(entry["start_pdf_page"])
            end = min(int(entry["end_pdf_page"]), page_count)
            if start < 1 or end < start:
                raise ValueError(f"Invalid page boundary for chapter {number}: {start}-{end}")
            generated_output = split_dir / f"chapter-{number:02d}-{slugify(str(entry['title']))}.pdf"
            recorded_output = Path(str(entry["split_pdf"])) if entry.get("split_pdf") else None
            output = (
                recorded_output
                if recorded_output is not None and recorded_output.parent.resolve() == split_dir.resolve()
                else generated_output
            )
            temporary_output = output.with_suffix(".rebuild.pdf")
            chapter = pymupdf.open()
            chapter.insert_pdf(document, from_page=start - 1, to_page=end - 1)
            chapter.save(temporary_output, garbage=0, deflate=False)
            chapter.close()
            temporary_output.replace(output)
            entry["split_pdf"] = str(output)
            entry["split_page_count"] = end - start + 1
            entry["split_sha256"] = sha256(output)
            outputs.append(output)
    return outputs


def run_opendataloader(
    executable: Path,
    chapter_pdf: Path,
    output_dir: Path,
    hybrid_url: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    image_dir = output_dir / "images"
    image_dir.mkdir(exist_ok=True)
    expected_md = output_dir / f"{chapter_pdf.stem}.md"
    expected_json = output_dir / f"{chapter_pdf.stem}.json"
    if expected_md.is_file() and expected_json.is_file():
        print(f"SKIP {chapter_pdf.name}: extraction already complete", flush=True)
        return
    cmd = [
        str(executable), str(chapter_pdf),
        "--output-dir", str(output_dir),
        "--format", "markdown,json",
        "--hybrid", "docling-fast",
        "--hybrid-mode", "full",
        "--hybrid-url", hybrid_url,
        "--hybrid-timeout", "0",
        "--image-output", "external",
        "--image-format", "png",
        "--image-dir", str(image_dir),
        "--image-resolution", "144",
        "--markdown-with-html",
    ]
    print(f"EXTRACT {chapter_pdf.name}", flush=True)
    subprocess.run(cmd, check=True)


def extraction_complete(chapter_pdf: Path, output_dir: Path) -> bool:
    return (
        (output_dir / f"{chapter_pdf.stem}.md").is_file()
        and (output_dir / f"{chapter_pdf.stem}.json").is_file()
    )


def server_is_ready(hybrid_url: str) -> bool:
    try:
        with urlopen(f"{hybrid_url.rstrip('/')}/health", timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def start_hybrid_server(
    executable: Path,
    hybrid_url: str,
    log_path: Path,
) -> tuple[subprocess.Popen[Any] | None, Any | None]:
    """Start an isolated OCR service unless a healthy external one exists."""

    if server_is_ready(hybrid_url):
        return None, None
    match = re.fullmatch(r"https?://([^:/]+):(\d+)", hybrid_url.rstrip("/"))
    if not match:
        raise ValueError(f"Managed hybrid service requires a host:port URL: {hybrid_url}")
    host, port = match.group(1), match.group(2)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_stream = log_path.open("a", encoding="utf-8")
    env = dict(__import__("os").environ)
    root = Path(__file__).resolve().parents[2]
    cache = root / ".cache"
    env.update({
        "HF_HOME": str(cache / "huggingface"),
        "TORCH_HOME": str(cache / "torch"),
        "EASYOCR_MODULE_PATH": str(cache / "easyocr"),
        "TEMP": str(cache / "tmp"),
        "TMP": str(cache / "tmp"),
    })
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        [
            str(executable), "--host", host, "--port", port,
            "--force-ocr", "--ocr-engine", "easyocr", "--ocr-lang", "en",
            "--device", "cpu",
        ],
        stdout=log_stream,
        stderr=subprocess.STDOUT,
        env=env,
        creationflags=creationflags,
    )
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if server_is_ready(hybrid_url):
            return process, log_stream
        if process.poll() is not None:
            log_stream.close()
            raise RuntimeError(
                f"Hybrid OCR service exited with code {process.returncode}; see {log_path}"
            )
        time.sleep(1)
    process.terminate()
    log_stream.close()
    raise TimeoutError(f"Hybrid OCR service did not become ready; see {log_path}")


def stop_hybrid_server(process: subprocess.Popen[Any] | None, log_stream: Any | None) -> None:
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
    if log_stream is not None:
        log_stream.close()


def validate_chapter(entry: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    md_files = list(output_dir.glob("*.md"))
    json_files = list(output_dir.glob("*.json"))
    if len(md_files) != 1 or len(json_files) != 1:
        return {"status": "failed", "reason": "missing_or_ambiguous_extraction_artifacts"}
    markdown = md_files[0].read_text(encoding="utf-8", errors="replace")
    data = json.loads(json_files[0].read_text(encoding="utf-8"))
    items = list(walk_items(data))
    top_level = data.get("kids", []) if isinstance(data, dict) else []
    type_counts = Counter(str(item.get("type", "unknown")) for item in top_level)
    bbox_items = [item for item in items if item.get("bounding box")]
    page_numbers = sorted({int(item["page number"]) for item in items if item.get("page number")})
    images = sorted((output_dir / "images").glob("*"))
    question_count = len(re.findall(r"\?", markdown))
    exercise_count = len(re.findall(r"(?im)^#{0,4}\s*(?:exercise|activity|review|assessment|let(?:'s| us) recall|fill in|answer|choose|match)\b", markdown))
    map_mentions = len(re.findall(r"\bmap(?:s)?\b", markdown, re.I))
    expected_pages = int(entry["split_page_count"])
    covered = len(page_numbers)
    title_words = {word for word in re.findall(r"[a-z]+", str(entry["title"]).lower()) if len(word) > 2}
    opening = " ".join(markdown.split()[:250]).lower()
    title_hits = sum(word in opening for word in title_words)
    title_ratio = title_hits / max(1, len(title_words))
    status = "passed"
    issues: list[str] = []
    if not markdown.strip():
        issues.append("empty_markdown")
    if not bbox_items:
        issues.append("no_bounding_boxes")
    if covered < expected_pages:
        issues.append(f"page_coverage_{covered}_of_{expected_pages}")
    if title_ratio < 0.5:
        issues.append("chapter_title_not_reliably_detected_near_opening")
    if issues:
        status = "review_required"
    return {
        "status": status,
        "chapter": int(entry["chapter"]),
        "title": entry["title"],
        "markdown": str(md_files[0]),
        "structured_json": str(json_files[0]),
        "markdown_characters": len(markdown),
        "expected_pages": expected_pages,
        "covered_pages": page_numbers,
        "top_level_element_counts": dict(sorted(type_counts.items())),
        "bounding_box_item_count": len(bbox_items),
        "table_count": type_counts.get("table", 0),
        "image_count": len(images),
        "question_mark_count": question_count,
        "exercise_heading_count": exercise_count,
        "map_mention_count": map_mentions,
        "title_match_ratio": round(title_ratio, 3),
        "issues": issues,
        "assets": [
            {"path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size}
            for path in images
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--chapter-map", type=Path, required=True)
    parser.add_argument("--collection-dir", type=Path, required=True)
    parser.add_argument("--opendataloader", type=Path, required=True)
    parser.add_argument("--hybrid-server", type=Path)
    parser.add_argument("--hybrid-url", default="http://127.0.0.1:5002")
    parser.add_argument("--split-only", action="store_true")
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    collection = args.collection_dir.expanduser().resolve()
    map_path = args.chapter_map.expanduser().resolve()
    chapter_map = json.loads(map_path.read_text(encoding="utf-8"))
    if not source.is_file():
        raise FileNotFoundError(source)
    split_dir = collection / "source-chapters"
    extracted_dir = collection / "extracted"
    artifacts_dir = collection / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    chapter_pdfs = split_chapters(source, chapter_map, split_dir)
    map_path.write_text(json.dumps(chapter_map, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.split_only:
        print(json.dumps({"status": "split_complete", "chapters": len(chapter_pdfs)}, indent=2))
        return 0

    validations: list[dict[str, Any]] = []
    for entry, chapter_pdf in zip(chapter_map["chapters"], chapter_pdfs):
        chapter_output = extracted_dir / f"chapter-{int(entry['chapter']):02d}"
        last_error: Exception | None = None
        for attempt in range(1, 4):
            server_process = None
            server_log = None
            try:
                if args.hybrid_server and not extraction_complete(chapter_pdf, chapter_output):
                    server_process, server_log = start_hybrid_server(
                        args.hybrid_server,
                        args.hybrid_url,
                        artifacts_dir / "logs" / f"hybrid-chapter-{int(entry['chapter']):02d}.log",
                    )
                run_opendataloader(args.opendataloader, chapter_pdf, chapter_output, args.hybrid_url)
                last_error = None
                break
            except (subprocess.CalledProcessError, RuntimeError, TimeoutError) as exc:
                last_error = exc
                print(
                    f"RETRY chapter {entry['chapter']}: attempt {attempt}/3 failed: {exc}",
                    flush=True,
                )
            finally:
                stop_hybrid_server(server_process, server_log)
            if attempt < 3:
                time.sleep(10)
        if last_error is not None:
            raise RuntimeError(
                f"Chapter {entry['chapter']} extraction failed after 3 attempts"
            ) from last_error
        validation = validate_chapter(entry, chapter_output)
        validations.append(validation)
        print(
            f"VALIDATE chapter {entry['chapter']}: {validation['status']} "
            f"pages={len(validation.get('covered_pages', []))}/{entry['split_page_count']} "
            f"images={validation.get('image_count', 0)} tables={validation.get('table_count', 0)}",
            flush=True,
        )

    report = {
        "version": "1.0",
        "source_pdf": str(source),
        "source_sha256": sha256(source),
        "chapter_map": str(map_path),
        "chapter_count": len(validations),
        "status": "passed" if all(item["status"] == "passed" for item in validations) else "review_required",
        "chapters": validations,
    }
    report_path = artifacts_dir / "opendataloader_validation.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    from tools.structure.educational_delivery_naming import (
        delivery_folder_name,
        delivery_video_name,
    )

    grade = int(chapter_map["grade"])
    subject_label = str(chapter_map["subject_label"])
    delivery_folder = delivery_folder_name(grade, subject_label)
    delivery_root = Path(__file__).resolve().parents[2] / "final-videos" / delivery_folder
    production_plan = {
        "version": "1.0",
        "status": "ready_for_production_proposals" if report["status"] == "passed" else "source_review_required",
        "execution_policy": {
            "mode": "strictly_sequential",
            "max_concurrent_chapters": 1,
            "next_chapter_requires_previous_encoded_qa": True,
            "stop_on_failure": True,
        },
        "source_pdf": str(source),
        "chapter_map": str(map_path),
        "extraction_validation": str(report_path),
        "delivery_folder": str(delivery_root),
        "chapter_count": len(chapter_map["chapters"]),
        "chapters": [
            {
                "chapter": int(entry["chapter"]),
                "title": entry["title"],
                "source_pdf": entry["split_pdf"],
                "preextracted_dir": str(extracted_dir / f"chapter-{int(entry['chapter']):02d}"),
                "project_id": slugify(
                    f"class-{grade}-{subject_label}-chapter-{int(entry['chapter']):02d}-{entry['title']}"
                ),
                "delivery_video": str(
                    delivery_root / delivery_video_name(
                        grade=grade,
                        subject_label=subject_label,
                        chapter=int(entry["chapter"]),
                        chapter_title=str(entry["title"]),
                        book_part=chapter_map.get("book_part"),
                    )
                ),
                "status": "ready_next" if int(entry["chapter"]) == 1 else "queued",
            }
            for entry in chapter_map["chapters"]
        ],
    }
    production_plan_path = artifacts_dir / "video_production_plan.json"
    production_plan_path.write_text(
        json.dumps(production_plan, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    textbook_manifest = {
        "version": "1.0",
        "collection_id": collection.name,
        "class": grade,
        "subject": chapter_map["subject"],
        "subject_label": subject_label,
        "source": str(source),
        "source_sha256": report["source_sha256"],
        "chapter_count": len(chapter_map["chapters"]),
        "chapter_map": str(map_path),
        "extraction_validation": str(report_path),
        "video_production_plan": str(production_plan_path),
    }
    textbook_path = collection / "textbook.json"
    textbook_path.write_text(
        json.dumps(textbook_manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({
        "status": report["status"],
        "report": str(report_path),
        "production_plan": str(production_plan_path),
        "textbook_manifest": str(textbook_path),
    }, indent=2))
    return 0 if report["status"] in {"passed", "review_required"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
