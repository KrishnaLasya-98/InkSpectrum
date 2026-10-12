"""Agent-neutral control surface for the educational-video pipeline.

Codex, Claude, Hermes, CI jobs, and ordinary shell users can all call this
module. It intentionally communicates through JSON, files, environment
variables, and exit codes rather than a vendor-specific agent SDK.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any



ROOT = Path(__file__).resolve().parents[2]


def portability_doctor() -> dict[str, Any]:
    """Verify the files and manifest needed by supported coding agents."""

    from lib.pipeline_loader import load_pipeline_readonly

    required = {
        "shared_agent_guide": ROOT / "AGENT_GUIDE.md",
        "codex_agents_entrypoint": ROOT / "AGENTS.md",
        "canonical_skill": ROOT / ".agents/skills/openmontage-educational-video/SKILL.md",
        "codex_adapter": ROOT / "CODEX.md",
        "codex_prompt": ROOT / ".codex/prompts/educational-video.md",
        "claude_adapter": ROOT / "CLAUDE.md",
        "claude_skill": ROOT / ".claude/skills/openmontage-educational-video/SKILL.md",
        "hermes_adapter": ROOT / "HERMES.md",
        "pipeline_manifest": ROOT / "pipeline_defs/educational-video.yaml",
    }
    checks = [
        {"name": name, "passed": path.is_file(), "path": str(path)}
        for name, path in required.items()
    ]
    manifest = load_pipeline_readonly("educational-video")
    for skill in manifest.get("required_skills", []):
        path = ROOT / "skills" / f"{skill}.md"
        checks.append(
            {
                "name": f"manifest_skill:{skill}",
                "passed": path.is_file(),
                "path": str(path),
            }
        )
    failed = [check for check in checks if not check["passed"]]
    return {
        "status": "pass" if not failed else "fail",
        "pipeline_type": "educational-video",
        "stage_count": len(manifest.get("stages", [])),
        "checks": checks,
        "failures": failed,
    }


def _print(payload: dict[str, Any]) -> None:
    import os
    from lib.production_runtime import atomic_json
    if result_path := os.environ.get("OPENMONTAGE_RESULT_PATH"):
        atomic_json(Path(result_path), payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Portable controller for OpenMontage educational videos."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("doctor", help="Verify cross-agent packaging and manifest skills")
    setup = commands.add_parser("setup", help="Check dependencies; optionally install into an isolated environment")
    setup.add_argument("--install-python", action="store_true")
    setup.add_argument("--manager", choices=["auto", "conda", "venv"], default="auto")
    references = commands.add_parser("references", help="Verify portable baselines; full reference MP4s are optional")
    references.add_argument("--require-full-video", action="store_true")
    resume = commands.add_parser("resume", help="Recover the next stage and its instructions without replaying paid work")
    resume.add_argument("project_dir")

    book = commands.add_parser(
        "book", help="Split a full textbook and run one video pipeline per chapter"
    )
    book.add_argument("source")
    book.add_argument("--grade", type=int)
    book.add_argument("--subject")
    book.add_argument("--subject-label")
    book.add_argument("--book-part", type=int)
    book.add_argument(
        "--chapter",
        dest="chapters",
        action="append",
        type=int,
        help="Render only this detected chapter; repeat for multiple chapters",
    )
    book.add_argument("--workspace-root")
    book.add_argument("--delivery-root")
    book.add_argument("--provider-config")
    book.add_argument(
        "--chapter-map",
        help="Reviewed chapter-map JSON for scanned or ambiguous textbooks",
    )
    book.add_argument("--quality", default="standard")
    book.add_argument("--approve-chapter-map", action="store_true")
    book.add_argument("--full-run-preauthorized", action="store_true")
    book.add_argument("--dry-run", action="store_true")

    status = commands.add_parser("status", help="Read ordered Backlot stage state")
    status.add_argument("project_dir")
    status.add_argument("--write", action="store_true", help="Also write artifacts/agent_status.json")

    approve = commands.add_parser("approve", help="Approve one awaiting stage")
    approve.add_argument("project_dir")
    approve.add_argument("stage")

    migrate = commands.add_parser("migrate", help="Add educational Backlot metadata to a legacy project")
    migrate.add_argument("project_dir")
    migrate.add_argument("--title")

    run = commands.add_parser("run", aliases=["start"], help="Ingest a chapter source and run the pipeline")
    run.add_argument("source", nargs="?")
    run.add_argument("--project-id")
    run.add_argument("--subject")
    run.add_argument("--grade", type=int)
    run.add_argument("--chapter", type=int)
    run.add_argument("--book-part", type=int)
    run.add_argument("--title")
    run.add_argument("--quality", default="standard")
    run.add_argument("--delivery-root")
    run.add_argument("--provider-config")
    run.add_argument(
        "--preextracted-dir",
        help="Reviewed directory containing exactly one Markdown file and one structured JSON extraction",
    )
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--full-run-preauthorized", action="store_true")

    args = parser.parse_args()
    try:
        from tools.structure.educational_startup import setup_environment, verify_references, resume_project
        if args.command == "setup":
            result = setup_environment(install_python=args.install_python, manager=args.manager)
            _print(result)
            if result["status"] != "ready":
                raise SystemExit(2)
            return
        if args.command == "references":
            result = verify_references(require_full_video=args.require_full_video)
            _print(result)
            if result["status"] != "pass":
                raise SystemExit(2)
            return
        if args.command == "resume":
            _print(resume_project(Path(args.project_dir)))
            return
        if args.command in {"start", "run"} and not args.source:
            _print({"status": "needs_input", "required": ["source PDF path"],
                    "optional": ["grade", "subject", "chapter", "provider-config"],
                    "message": "Provide the PDF; no installation or paid generation has started."})
            return
        from tools.structure.educational_run_tracker import (
            approve_educational_stage, checkpoint_summary,
            migrate_legacy_educational_project, write_status_json,
        )
        if args.command == "doctor":
            result = portability_doctor()
            _print(result)
            if result["status"] != "pass":
                raise SystemExit(1)
            return
        if args.command == "book":
            from tools.structure.textbook_video_pipeline import (
                run_textbook_to_videos,
            )

            _print(
                run_textbook_to_videos(
                    {
                        key: value
                        for key, value in {
                            "input_path": args.source,
                            "grade": args.grade,
                            "subject": args.subject,
                            "subject_label": args.subject_label,
                            "book_part": args.book_part,
                            "chapters": args.chapters,
                            "workspace_root": args.workspace_root,
                            "delivery_root": args.delivery_root,
                            "provider_config": args.provider_config,
                            "chapter_map": args.chapter_map,
                            "quality": args.quality,
                            "approve_chapter_map": args.approve_chapter_map,
                            "full_run_preauthorized": args.full_run_preauthorized,
                            "dry_run": args.dry_run,
                        }.items()
                        if value is not None
                    }
                )
            )
            return
        if args.command == "status":
            project = Path(args.project_dir).resolve()
            if args.write:
                write_status_json(project)
            _print(checkpoint_summary(project))
            return
        if args.command == "approve":
            path = approve_educational_stage(args.project_dir, args.stage)
            _print(
                {
                    "status": "approved",
                    "stage": args.stage,
                    "checkpoint": str(path),
                }
            )
            return
        if args.command == "migrate":
            marker = migrate_legacy_educational_project(
                args.project_dir, title=args.title
            )
            _print({"status": "migrated", "project_marker": str(marker)})
            return

        inputs = {
            key: value
            for key, value in {
                "input_path": args.source,
                "project_id": args.project_id,
                "subject": args.subject,
                "grade": args.grade,
                "chapter": args.chapter,
                "book_part": args.book_part,
                "title": args.title,
                "quality": args.quality,
                "delivery_root": args.delivery_root,
                "provider_config": args.provider_config,
                "preextracted_dir": args.preextracted_dir,
                "dry_run": args.dry_run,
                "full_run_preauthorized": args.full_run_preauthorized,
            }.items()
            if value is not None
        }
        from tools.structure.pdf_to_video_pipeline import run_pdf_to_video
        if args.command == "start":
            import os
            from tools.structure.pdf_to_video_pipeline import slugify
            project_id = args.project_id or slugify(Path(args.source).stem)
            project = Path(os.environ.get("OPENMONTAGE_PROJECTS_DIR", str(ROOT / "projects"))) / project_id
            if project.exists():
                raise ValueError(f"Project already exists: {project}. Use resume; start will not overwrite it.")
        from contextlib import redirect_stdout
        with redirect_stdout(sys.stderr):
            result = run_pdf_to_video(inputs)
        _print(result)
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
