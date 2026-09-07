"""Textbook Pipeline — unified CLI.

Single entry point for the full pipeline. Mirrors video_explainer's CLI design:
you can run individual steps or the full pipeline with --from / --to.

Phase 1 supports: english, math, science, social (EVS)
Phase 2 (deferred): GK

Usage:
    # Full run: PDF → chapter video
    python -m textbook_pipeline generate \\
        --pdf data/textbook_corpus/ENGLISH_V1.pdf \\
        --chapter 3 \\
        --output projects/english_ch3

    # Just ingest: PDF → chapter JSON
    python -m textbook_pipeline ingest \\
        --pdf /path/to/any.pdf \\
        --subject english \\
        --grade 1 \\
        --output projects/lesson1

    # Just render
    python -m textbook_pipeline render \\
        --storyboard projects/english_ch3/storyboard.json

    # List available subjects
    python -m textbook_pipeline subjects

    # Show version
    python -m textbook_pipeline version
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from textbook_pipeline.models.chapter import Subject

logger = logging.getLogger(__name__)


# ───────────────────────────────────────────────────────────────────
# Subcommand handlers (stubs — wired up in subsequent phases)
# ───────────────────────────────────────────────────────────────────

def cmd_generate(args: argparse.Namespace) -> int:
    """Run full pipeline: PDF → chapter video."""
    logger.info(
        "generate: pdf=%s chapter=%d subject=%s output=%s",
        args.pdf, args.chapter, args.subject, args.output,
    )
    logger.warning("Pipeline not yet implemented — this is a stub.")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    """PDF → chapter JSON (uses PyMuPDF extractor)."""
    try:
        from textbook_pipeline.core.ingestion.pymupdf_extractor import PyMuPDFExtractor
    except ImportError as exc:
        logger.error("Failed to import extractor: %s", exc)
        return 1

    pdf_path = args.pdf.resolve()
    if not pdf_path.exists() or not pdf_path.is_file():
        logger.error("PDF not found: %s", pdf_path)
        return 1
    if pdf_path.suffix.lower() != ".pdf":
        logger.error("Not a PDF file: %s", pdf_path)
        return 1

    subject = Subject(args.subject)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    extractor = PyMuPDFExtractor()
    chapter = extractor.extract_chapters(
        pdf_path=pdf_path,
        subject=subject,
        grade=args.grade,
        textbook_id=pdf_path.stem,
    )

    # Validation
    issues = extractor.validate_extraction(chapter)
    if issues:
        for issue in issues:
            logger.warning("Validation issue: %s", issue)

    blueprint_path = output / "blueprint.json"
    blueprint_path.write_text(chapter.model_dump_json(indent=2), encoding="utf-8")
    logger.info("Saved blueprint to %s", blueprint_path)
    print(f"✅ Saved blueprint to {blueprint_path}")
    return 0


def cmd_script(args: argparse.Namespace) -> int:
    """Chapter JSON → script + scene plan."""
    logger.info("script: chapter_json=%s", args.chapter_json)
    logger.warning("Script writer not yet implemented.")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    """Storyboard → final video."""
    logger.info("render: storyboard=%s", args.storyboard)
    logger.warning("Remotion renderer not yet wired up.")
    return 0


def cmd_subjects(args: argparse.Namespace) -> int:
    """List active (Phase 1) and deferred (Phase 2) subjects."""
    print("Active subjects (Phase 1):")
    for s in [Subject.ENGLISH, Subject.MATH, Subject.SCIENCE, Subject.SOCIAL]:
        print(f"  - {s.value:<10} ({s.name.title()})")
    print("\nDeferred subjects (Phase 2):")
    print("  - gk         (General Knowledge)")
    return 0


def cmd_version(args: argparse.Namespace) -> int:
    """Print version."""
    from textbook_pipeline import __version__
    print(f"textbook-pipeline {__version__}")
    return 0


# ───────────────────────────────────────────────────────────────────
# Argument parser
# ───────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="textbook-pipeline",
        description="Transform K-10 textbook PDFs into chapter-by-chapter video lectures.",
    )
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    sub = parser.add_subparsers(dest="command", required=True)

    # generate
    p_gen = sub.add_parser("generate", help="Full pipeline: PDF → chapter video")
    p_gen.add_argument("--pdf", required=True, type=Path, help="Path to textbook PDF")
    p_gen.add_argument("--chapter", required=True, type=int, help="Chapter number to render")
    p_gen.add_argument("--subject", choices=[s.value for s in Subject], help="Override auto-detection")
    p_gen.add_argument("--grade", type=int, choices=range(1, 11), help="Grade (1-10)")
    p_gen.add_argument("--output", required=True, type=Path, help="Output project directory")
    p_gen.add_argument("--from", dest="from_step", choices=["ingest", "script", "audio", "render"], help="Resume from step")
    p_gen.add_argument("--to", dest="to_step", choices=["ingest", "script", "audio", "render"], help="Stop at step")
    p_gen.set_defaults(func=cmd_generate)

    # ingest
    p_ing = sub.add_parser("ingest", help="PDF → chapter JSON")
    p_ing.add_argument("--pdf", required=True, type=Path, help="Path to input PDF")
    p_ing.add_argument("--subject", required=True, choices=[s.value for s in Subject], help="Subject")
    p_ing.add_argument("--grade", required=True, type=int, choices=range(1, 11), help="Grade (1-10)")
    p_ing.add_argument("--output", required=True, type=Path, help="Output directory")
    p_ing.set_defaults(func=cmd_ingest)

    # script
    p_scr = sub.add_parser("script", help="Chapter JSON → script + scene plan")
    p_scr.add_argument("--chapter-json", required=True, type=Path)
    p_scr.set_defaults(func=cmd_script)

    # render
    p_ren = sub.add_parser("render", help="Storyboard → final video")
    p_ren.add_argument("--storyboard", required=True, type=Path)
    p_ren.add_argument("--quality", choices=["480p", "720p", "1080p"], default="720p")
    p_ren.set_defaults(func=cmd_render)

    # subjects
    p_sub = sub.add_parser("subjects", help="List active and deferred subjects")
    p_sub.set_defaults(func=cmd_subjects)

    # version
    p_ver = sub.add_parser("version", help="Print version")
    p_ver.set_defaults(func=cmd_version)

    return parser


# ───────────────────────────────────────────────────────────────────
# Main entry
# ───────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    """CLI entry point registered in pyproject.toml."""
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
