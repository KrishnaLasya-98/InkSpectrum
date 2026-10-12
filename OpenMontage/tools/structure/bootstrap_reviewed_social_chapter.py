"""Resume-safe source bootstrap for a visually reviewed Social textbook chapter.

This performs no paid media generation and does not certify the OCR/transcript.
It leaves input_ingestion in progress until the page-by-page source audit passes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from schemas.artifacts import validate_artifact
from tools.extract.document_ingestor import ingest_document
from tools.extract.section_parser import SectionParser
from tools.structure.educational_run_tracker import EducationalRunTracker
from tools.structure.source_contract import write_source_contracts


ROOT = Path(__file__).resolve().parents[2]
COLLECTION = ROOT / "textbook-collections" / "class-5-social"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bootstrap(chapter_number: int, *, complete_source_review: bool = False) -> dict:
    chapter_map = json.loads((COLLECTION / "artifacts" / "chapter_map.json").read_text(encoding="utf-8"))
    entry = next(x for x in chapter_map["chapters"] if int(x["chapter"]) == chapter_number)
    source_pdf = Path(entry["split_pdf"])
    if sha256(source_pdf) != entry["split_sha256"]:
        raise ValueError("Split PDF differs from the reviewed chapter map")
    reviewed_dir = COLLECTION / "reviewed" / f"chapter-{chapter_number:02d}"
    markdown_files = sorted(reviewed_dir.glob("*.md"))
    json_files = sorted(path for path in reviewed_dir.glob("*.json") if path.name != "source-audit.json")
    if len(markdown_files) != 1 or len(json_files) != 1:
        raise ValueError("Reviewed chapter requires exactly one Markdown and one layout JSON file")
    markdown = markdown_files[0].read_text(encoding="utf-8")
    if not re.search(r"(?im)^##\s+Word Bank\s*$", markdown):
        raise ValueError("Reviewed pre-assessment scope must end at Word Bank")
    if re.search(r"(?im)^#{1,6}\s+(?:Assessment|Exercises?)\b", markdown):
        raise ValueError("Post-Word-Bank assessment leaked into the teaching source")
    images = re.findall(r"!\[[^]]*]\((images/[^)]+)\)", markdown)
    if not images or any(not (reviewed_dir / image).is_file() for image in images):
        raise ValueError("Required textbook figure paths are missing")
    slug = re.sub(r"[^a-z0-9]+", "-", str(entry["title"]).lower()).strip("-")
    project = ROOT / "projects" / f"class-5-social-part-0-chapter-{chapter_number}-{slug}"
    tracker = EducationalRunTracker(project, title=f"Class 5 Social: {entry['title']}",
                                    approval_policy="full-run-preauthorized")
    current = project / "checkpoint_input_ingestion.json"
    if current.is_file():
        prior = json.loads(current.read_text(encoding="utf-8"))
        if prior["status"] == "completed":
            return {"status": "already_completed", "project": str(project)}
    tracker.begin("input_ingestion", metadata={"source_pdf": str(source_pdf),
                                                "source_review": "pending-final-page-audit"})
    artifacts = project / "artifacts"
    extracted = ingest_document(source_pdf, output_dir=artifacts, preextracted_dir=reviewed_dir)
    document, coverage = write_source_contracts(
        Path(extracted["markdown_path"]), artifacts / "chapter_document.json",
        artifacts / "coverage_contract.json", source_pdf=str(source_pdf),
        source_input=str(source_pdf), extraction_artifact_path=Path(extracted["artifact_path"]),
    )
    validate_artifact("chapter_document", document)
    validate_artifact("coverage_contract", coverage)
    parsed = SectionParser().execute({"subject": "social_studies",
                                      "md_path": extracted["markdown_path"],
                                      "output_dir": str(artifacts)})
    if not parsed.success:
        raise RuntimeError(parsed.error)
    progress = {
        "reviewed_markdown": str(markdown_files[0]),
        "source_pdf": str(source_pdf),
        "source_sha256": entry["split_sha256"],
        "source_blocks": document["validation"]["block_count"],
        "sections": parsed.data["block_count"],
        "textbook_figures": len(images),
        "page_audit_status": "pending-final-page-audit",
    }
    if complete_source_review:
        audit_path = reviewed_dir / "audits" / "source-audit.json"
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        expected_pages = sorted({int(x) for x in audit["page_review"]})
        actual_pages = list(range(1, max(int(page["page_number"]) for page in document["pages"]) + 1))
        if audit["status"] != "pass" or expected_pages != actual_pages:
            raise ValueError("Page-level source audit is not complete")
        if sorted(audit["required_figure_files"]) != sorted(set(images)):
            raise ValueError("Source figure audit disagrees with reviewed Markdown")
        if document["blocks"][-1].get("heading") != "Word Bank":
            raise ValueError("Last scoped source block is not Word Bank")
        progress["page_audit_status"] = "pass"
        tracker.finish("input_ingestion", {
            "extracted_content_path": extracted["markdown_path"],
            "chapter_document_path": str(artifacts / "chapter_document.json"),
            "coverage_contract_path": str(artifacts / "coverage_contract.json"),
            "section_blocks_path": parsed.data["output_path"],
        }, metadata={**progress, "source_audit": str(audit_path)})
    else:
        tracker.progress("input_ingestion", partial_progress=progress)
    return {"status": "source_review_completed" if complete_source_review else "source_bootstrapped_awaiting_final_audit",
            "project": str(project),
            "source_blocks": document["validation"]["block_count"],
            "sections": parsed.data["block_count"], "figures": len(images)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("chapter", type=int)
    parser.add_argument("--complete-source-review", action="store_true")
    args = parser.parse_args()
    print(json.dumps(bootstrap(args.chapter, complete_source_review=args.complete_source_review), indent=2))
