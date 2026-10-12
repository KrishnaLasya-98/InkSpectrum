"""Dynamic full-textbook to chapter-video orchestration.

This module performs only book-level work: filename metadata, chapter boundary
detection, lossless PDF splitting, per-chapter pipeline dispatch, and aggregate
delivery indexing. Each chapter still runs through the canonical
``pdf_to_video_pipeline`` and therefore receives its own source contract,
Backlot checkpoints, HyperFrames HTML workspace, render, and encoded-output QA.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from tools.structure.educational_delivery_naming import (
    delivery_folder_name,
    infer_book_part,
)
from tools.structure.pdf_to_video_pipeline import (
    infer_metadata,
    run_pdf_to_video,
    slugify,
)


_TOC_ENTRY_RE = re.compile(
    r"\b(?:lesson|chapter)\s*(\d+)\s*(?:[-:.)]\s*|\s+)"
    r"(.{2,120}?)\s+(\d+)\s*[-–]\s*(\d+)\b",
    re.IGNORECASE,
)
_NOISE_WORDS = {
    "lesson", "chapter", "poem", "the", "and", "of", "a", "an", "to",
}
_ROOT = Path(__file__).resolve().parents[2]


def resolve_collections_root(inputs: dict[str, Any]) -> Path:
    configured = inputs.get("workspace_root") or os.environ.get(
        "OPENMONTAGE_COLLECTIONS_DIR"
    )
    return (
        Path(configured).expanduser().resolve()
        if configured
        else _ROOT / "textbook-collections"
    )


def _pdf_module():
    try:
        import pymupdf as fitz  # type: ignore
    except ImportError:
        try:
            import fitz  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "Full-textbook PDF splitting requires PyMuPDF (pip install pymupdf)."
            ) from exc
    return fitz


def _normalized(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def _title_words(value: str) -> set[str]:
    return {
        word for word in _normalized(value).split()
        if len(word) >= 2 and word not in _NOISE_WORDS and not word.isdigit()
    }


def _clean_title(value: str) -> str:
    value = re.sub(r"\(\s*poem\s*\)\s*\d*\s*[-:]?", "", value, flags=re.I)
    value = re.sub(r"\s+", " ", value).strip(" -:.)")
    return value or "Untitled Chapter"


def detect_chapters_from_page_texts(page_texts: list[str]) -> list[dict[str, Any]]:
    """Detect ordered lesson boundaries from a textbook's contents pages.

    Printed page numbers are treated as hints. Actual PDF indices are resolved
    by matching each title and lesson number against page text, which handles
    front-matter offsets without hardcoded arithmetic.
    """

    candidates: dict[int, dict[str, Any]] = {}
    for toc_index, text in enumerate(page_texts[: min(20, len(page_texts))]):
        compact = re.sub(r"[\t\r\n]+", " ", text)
        compact = re.sub(r"\s+", " ", compact)
        for match in _TOC_ENTRY_RE.finditer(compact):
            number = int(match.group(1))
            title = _clean_title(match.group(2))
            printed_start = int(match.group(3))
            printed_end = int(match.group(4))
            if printed_end < printed_start:
                continue
            current = candidates.get(number)
            if current is None or len(title) > len(current["title"]):
                candidates[number] = {
                    "chapter": number,
                    "title": title,
                    "printed_start_page": printed_start,
                    "printed_end_page": printed_end,
                    "toc_pdf_page": toc_index + 1,
                }

    if len(candidates) < 2:
        return []

    ordered = [candidates[number] for number in sorted(candidates)]
    previous_index = 0
    for entry in ordered:
        words = _title_words(entry["title"])
        best_index = None
        best_score = 0.0
        for index, text in enumerate(page_texts):
            # Never resolve a chapter opening to the contents page that merely
            # lists its title. ``toc_pdf_page`` is one-based, so the first
            # eligible zero-based index is numerically equal to it.
            if index < max(previous_index, int(entry["toc_pdf_page"])):
                continue
            normalized_page = _normalized(text)
            page_words = set(normalized_page.split())
            title_score = len(words & page_words) / max(1, len(words))
            number_signal = bool(
                re.search(
                    rf"\b(?:lesson|chapter)\s*{entry['chapter']}\b|"
                    rf"\b{entry['chapter']}\s*(?:lesson|chapter)\b",
                    normalized_page,
                )
            )
            score = title_score + (0.2 if number_signal else 0.0)
            # A chapter heading should appear near the top of its opening page.
            if words and all(word in set(_normalized(" ".join(text.splitlines()[:12])).split()) for word in words):
                score += 0.15
            if score > best_score:
                best_index, best_score = index, score
        hinted = entry["printed_start_page"] - 1
        if best_index is None or best_score < 0.55:
            if 0 <= hinted < len(page_texts):
                best_index = hinted
                best_score = 0.45
            else:
                raise ValueError(
                    f"Could not resolve PDF start page for chapter {entry['chapter']}: "
                    f"{entry['title']}"
                )
        entry["start_pdf_page"] = best_index + 1
        entry["boundary_confidence"] = round(min(1.0, best_score), 3)
        previous_index = best_index + 1

    for index, entry in enumerate(ordered):
        next_start = (
            ordered[index + 1]["start_pdf_page"]
            if index + 1 < len(ordered)
            else len(page_texts) + 1
        )
        entry["end_pdf_page"] = next_start - 1
        if entry["end_pdf_page"] < entry["start_pdf_page"]:
            raise ValueError("Detected chapter boundaries overlap or are out of order")
    return ordered


def inspect_textbook(source: str | Path) -> dict[str, Any]:
    source_path = Path(source).expanduser().resolve()
    if not source_path.is_file() or source_path.suffix.lower() != ".pdf":
        raise ValueError("Full-textbook orchestration currently requires a PDF file")
    fitz = _pdf_module()
    with fitz.open(source_path) as document:
        page_texts = [page.get_text("text") for page in document]
    chapters = detect_chapters_from_page_texts(page_texts)
    if len(chapters) < 2:
        raise ValueError(
            "The input does not expose at least two reliable chapter boundaries. "
            "Provide a reviewed chapter-map JSON instead of guessing."
        )
    metadata = infer_metadata(source_path, "\n".join(page_texts[:12]), {})
    metadata["book_part"] = infer_book_part(source_path)
    return {
        "version": "1.0",
        "source": str(source_path),
        "page_count": len(page_texts),
        "grade": metadata["grade"],
        "subject": metadata["subject"],
        "subject_label": metadata["subject_label"],
        "book_part": metadata.get("book_part"),
        "chapter_count": len(chapters),
        "chapters": chapters,
        "status": "detected",
    }


def _split_chapter_pdf(source: Path, output: Path, start_page: int, end_page: int) -> None:
    fitz = _pdf_module()
    output.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(source) as document:
        chapter = fitz.open()
        chapter.insert_pdf(
            document,
            from_page=start_page - 1,
            to_page=end_page - 1,
        )
        chapter.save(output)
        chapter.close()


def _write_collection_html(path: Path, manifest: dict[str, Any]) -> None:
    cards = []
    for chapter in manifest.get("chapters", []):
        title = html.escape(str(chapter["title"]))
        number = int(chapter["chapter"])
        status = html.escape(str(chapter.get("status", "pending")))
        delivery = chapter.get("delivery_video")
        link = (
            f'<a href="{html.escape(Path(delivery).name)}">Open video</a>'
            if delivery else "<span>Not rendered</span>"
        )
        cards.append(
            f'<article><div class="number">{number:02d}</div>'
            f'<div><h2>{title}</h2><p>{status}</p>{link}</div></article>'
        )
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(str(manifest['collection_name']))}</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#f5f1e8;color:#163247;font-family:system-ui,sans-serif}}
main{{max-width:1100px;margin:auto;padding:56px 28px}}header{{border-bottom:3px solid #df9b32;margin-bottom:28px}}
h1{{font-family:Georgia,serif;font-size:clamp(2.2rem,5vw,4.8rem);line-height:1;margin:0 0 18px}}
.meta{{font-size:1.05rem;margin-bottom:24px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px}}
article{{display:flex;gap:18px;min-height:150px;padding:24px;background:#fffdf7;border:1px solid #d9d1c2;border-radius:20px;box-shadow:0 10px 30px #16324712}}
.number{{font:900 2.6rem/1 Georgia,serif;color:#b14f37}}h2{{font:800 1.35rem/1.15 Georgia,serif;margin:0 0 10px}}
p{{text-transform:capitalize;color:#597080}}a{{display:inline-block;margin-top:8px;color:#8d3424;font-weight:800}}span{{color:#74838c}}
</style></head><body><main><header><h1>{html.escape(str(manifest['collection_name']))}</h1>
<p class="meta">{manifest['chapter_count']} chapter videos - Part {manifest.get('book_part') or 'unspecified'}</p></header>
<section class="grid">{''.join(cards)}</section></main></body></html>"""
    path.write_text(document, encoding="utf-8")


def run_textbook_to_videos(inputs: dict[str, Any]) -> dict[str, Any]:
    source = Path(inputs.get("input_path") or inputs["pdf_path"]).expanduser().resolve()
    reviewed_map = inputs.get("chapter_map")
    reviewed_map_path: Path | None = None
    if reviewed_map:
        reviewed_map_path = Path(reviewed_map).expanduser().resolve()
        detected = json.loads(reviewed_map_path.read_text(encoding="utf-8"))
        if not isinstance(detected.get("chapters"), list) or not detected["chapters"]:
            raise ValueError("Reviewed chapter map has no chapters")
        fitz = _pdf_module()
        with fitz.open(source) as document:
            page_count = len(document)
        for entry in detected["chapters"]:
            start = int(entry["start_pdf_page"])
            end = int(entry["end_pdf_page"])
            if start < 1 or end < start or end > page_count:
                raise ValueError(
                    f"Reviewed chapter map has invalid pages for chapter "
                    f"{entry.get('chapter')}: {start}-{end} of {page_count}"
                )
        detected["source"] = str(source)
        detected["page_count"] = page_count
        detected["chapter_count"] = len(detected["chapters"])
        detected["status"] = "reviewed_chapter_map"
        detected["reviewed_chapter_map"] = str(reviewed_map_path)
    else:
        detected = inspect_textbook(source)
    for key in ("grade", "subject", "subject_label", "book_part"):
        if inputs.get(key) is not None:
            detected[key] = inputs[key]

    requested_chapters = {
        int(value)
        for value in (inputs.get("chapters") or [])
    }
    if requested_chapters:
        available = {
            int(entry["chapter"]) for entry in detected["chapters"]
        }
        missing = sorted(requested_chapters - available)
        if missing:
            raise ValueError(
                "Requested chapters are not present in the detected textbook: "
                + ", ".join(str(value) for value in missing)
            )
        detected["selected_chapters"] = sorted(requested_chapters)

    grade = int(detected["grade"])
    subject = str(detected["subject"])
    subject_label = str(detected["subject_label"])
    book_part = detected.get("book_part")
    folder_name = delivery_folder_name(grade, subject_label)
    collection_name = f"{folder_name}-Part-{int(book_part):02d}" if book_part else folder_name
    collection_id = slugify(collection_name)
    workspace_root = resolve_collections_root(inputs)
    collection_dir = workspace_root / collection_id
    artifacts_dir = collection_dir / "artifacts"
    split_dir = collection_dir / "source-chapters"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    split_dir.mkdir(parents=True, exist_ok=True)

    chapter_map_path = artifacts_dir / "chapter_map.json"
    chapter_map_path.write_text(
        json.dumps(detected, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    textbook_path = collection_dir / "textbook.json"
    textbook_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "collection_id": collection_id,
                "class": grade,
                "subject": subject,
                "subject_label": subject_label,
                "book_part": book_part,
                "source": str(source),
                "chapter_count": detected["chapter_count"],
                "chapter_map": str(chapter_map_path),
                "delivery_folder_name": folder_name,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    approved = bool(
        inputs.get("approve_chapter_map")
        or inputs.get("full_run_preauthorized")
        or inputs.get("dry_run")
    )
    if not approved:
        return {
            "status": "awaiting_chapter_map_approval",
            "collection_id": collection_id,
            "collection_dir": str(collection_dir),
            "chapter_map": str(chapter_map_path),
            "textbook_manifest": str(textbook_path),
            "chapter_count": detected["chapter_count"],
            "chapters": detected["chapters"],
        }

    results: list[dict[str, Any]] = []
    for entry in detected["chapters"]:
        if requested_chapters and int(entry["chapter"]) not in requested_chapters:
            continue
        number = int(entry["chapter"])
        title = str(entry["title"])
        recorded_chapter_pdf = Path(str(entry.get("split_pdf", ""))).expanduser()
        if entry.get("split_pdf") and recorded_chapter_pdf.is_file():
            chapter_pdf = recorded_chapter_pdf.resolve()
        else:
            chapter_pdf = split_dir / (
                f"{folder_name}-Part-{int(book_part or 0):02d}-"
                f"Chapter-{number:02d}-{slugify(title)}.pdf"
            )
            _split_chapter_pdf(
                source,
                chapter_pdf,
                int(entry["start_pdf_page"]),
                int(entry["end_pdf_page"]),
            )
        explicit_preextracted = entry.get("preextracted_dir")
        reviewed_preextracted = (
            reviewed_map_path.parent.parent / "extracted" / f"chapter-{number:02d}"
            if reviewed_map_path is not None
            else None
        )
        local_preextracted = collection_dir / "extracted" / f"chapter-{number:02d}"
        preextracted_dir = None
        for candidate in (
            Path(str(explicit_preextracted)).expanduser() if explicit_preextracted else None,
            reviewed_preextracted,
            local_preextracted,
        ):
            if candidate is not None and candidate.is_dir():
                preextracted_dir = candidate.resolve()
                break
        project_id = slugify(
            f"{folder_name}-Part-{book_part or 0}-Chapter-{number}-{title}"
        )
        result = run_pdf_to_video(
            {
                "input_path": str(chapter_pdf),
                "project_id": project_id,
                "subject": subject,
                "subject_label": subject_label,
                "grade": grade,
                "book_part": book_part,
                "chapter": number,
                "title": title,
                "preextracted_dir": str(preextracted_dir) if preextracted_dir else None,
                "quality": inputs.get("quality", "standard"),
                "provider_config": inputs.get("provider_config"),
                "delivery_root": inputs.get("delivery_root"),
                "dry_run": bool(inputs.get("dry_run", False)),
                "full_run_preauthorized": bool(
                    inputs.get("full_run_preauthorized", False)
                ),
            }
        )
        results.append(
            {
                "chapter": number,
                "title": title,
                "source_pdf": str(chapter_pdf),
                "start_pdf_page": entry["start_pdf_page"],
                "end_pdf_page": entry["end_pdf_page"],
                "status": result.get("status", "completed"),
                "project_id": result["project_id"],
                "chapter_config": result["chapter_config"],
                "hyperframes_workspace": result.get("workspace_path", ""),
                "delivery_video": result.get("delivery_video", ""),
                "final_video": result.get("final_video", ""),
            }
        )

    manifest = {
        "version": "1.0",
        "collection_id": collection_id,
        "collection_name": collection_name,
        "source": str(source),
        "grade": grade,
        "subject": subject,
        "subject_label": subject_label,
        "book_part": book_part,
        "chapter_count": len(results),
        "chapters": results,
    }
    manifest_path = collection_dir / "textbook_video_index.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    html_path = collection_dir / "index.html"
    _write_collection_html(html_path, manifest)
    return {
        "status": (
            "completed"
            if all(item["status"] == "completed" for item in results)
            else "awaiting_chapter_stages"
        ),
        "collection_id": collection_id,
        "collection_dir": str(collection_dir),
        "chapter_map": str(chapter_map_path),
        "textbook_manifest": str(textbook_path),
        "textbook_video_index": str(manifest_path),
        "html_index": str(html_path),
        "chapters": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split a complete textbook PDF and run one video pipeline per chapter."
    )
    parser.add_argument("source")
    parser.add_argument("--grade", type=int)
    parser.add_argument("--subject")
    parser.add_argument("--subject-label")
    parser.add_argument("--book-part", type=int)
    parser.add_argument("--chapter", dest="chapters", action="append", type=int)
    parser.add_argument("--workspace-root")
    parser.add_argument("--delivery-root")
    parser.add_argument("--provider-config")
    parser.add_argument(
        "--chapter-map",
        help="Reviewed chapter-map JSON; required when a scanned PDF has no embedded text",
    )
    parser.add_argument("--quality", default="standard")
    parser.add_argument("--approve-chapter-map", action="store_true")
    parser.add_argument("--full-run-preauthorized", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = vars(parser.parse_args())
    args["input_path"] = args.pop("source")
    try:
        print(json.dumps(run_textbook_to_videos(args), indent=2, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
