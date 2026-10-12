"""Read-only textbook collection progress for the Backlot dashboard.

The delivery index can lag behind an active render. This view combines the
collection plan with project checkpoints, but never treats a draft render as a
delivered video or advances the sequential chapter gate on its own.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

from lib.paths import PROJECTS_DIR, REPO_ROOT


COLLECTIONS_DIR = Path(os.environ.get("OPENMONTAGE_COLLECTIONS_DIR") or REPO_ROOT / "textbook-collections")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def list_collections(root: Path | None = None) -> list[dict[str, Any]]:
    base = root or COLLECTIONS_DIR
    if not base.is_dir():
        return []
    result = []
    for folder in sorted(base.iterdir()):
        if not folder.is_dir():
            continue
        plan = _read_json(folder / "artifacts" / "video_production_plan.json")
        if not isinstance(plan.get("chapters"), list):
            continue
        result.append({"id": folder.name, "chapter_count": len(plan["chapters"])})
    return result


def _project_for(chapter: dict[str, Any], projects_root: Path, collection_id: str) -> Path | None:
    project_id = chapter.get("project_id")
    if isinstance(project_id, str) and (projects_root / project_id).is_dir():
        return projects_root / project_id
    number = chapter.get("chapter")
    if not isinstance(number, int):
        return None
    matches = sorted(projects_root.glob(f"{collection_id}-*-chapter-{number}-*")) if projects_root.is_dir() else []
    matches = [path for path in matches if path.is_dir()]
    return matches[0] if len(matches) == 1 else None


def _review_render(project: Path | None) -> dict[str, Any] | None:
    """Expose an explicitly recorded review MP4 without calling it delivered."""
    if project is None:
        return None
    record = _read_json(project / "artifacts" / "latest-review-render.json")
    if record.get("status") != "review_ready":
        return None
    relative = record.get("path")
    if not isinstance(relative, str) or not relative:
        return None
    try:
        target = (project / relative).resolve()
        relative_path = target.relative_to(project.resolve())
        if target.suffix.lower() != ".mp4" or not target.is_file() or target.stat().st_size == 0:
            return None
    except (OSError, ValueError):
        return None
    return {
        "url": f"/media/{quote(project.name)}/{quote(relative_path.as_posix(), safe='/')}",
        "updated_at": (project / "artifacts" / "latest-review-render.json").stat().st_mtime,
        "qa_status": "Full textbook and audio QA pending",
    }


def load_collection_state(
    collection_dir: Path, projects_root: Path | None = None
) -> dict[str, Any]:
    from backlot.state import summarize_project

    plan = _read_json(collection_dir / "artifacts" / "video_production_plan.json")
    chapters = plan.get("chapters")
    if not isinstance(chapters, list):
        raise FileNotFoundError("collection production plan is missing")
    projects_root = projects_root or PROJECTS_DIR
    rows: list[dict[str, Any]] = []
    prior_verified = True
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        number = chapter.get("chapter")
        if not isinstance(number, int):
            continue
        project = _project_for(chapter, projects_root, collection_dir.name)
        summary = None
        if project:
            try:
                summary = summarize_project(project)
            except (OSError, ValueError, KeyError):
                pass
        video_path = Path(chapter["final_video"]) if chapter.get("final_video") else None
        qa_path = Path(chapter["qa_evidence"]) if chapter.get("qa_evidence") else None
        delivered = bool(
            chapter.get("status") == "completed"
            and video_path and video_path.is_file() and video_path.stat().st_size > 0
            and qa_path and qa_path.is_file()
        )
        review_render = None if delivered else _review_render(project)
        if delivered:
            status = "completed"
        elif summary or chapter.get("status") not in (None, "queued"):
            status = "in_progress" if prior_verified else "waiting_for_previous_chapter"
        else:
            status = "ready" if prior_verified else "queued"
        rows.append({
            "chapter": number,
            "title": str(chapter.get("title") or f"Chapter {number}"),
            "status": status,
            "plan_status": chapter.get("status"),
            "project_id": project.name if project else None,
            "active_stage": summary.get("active_stage") if summary else None,
            "last_activity": summary.get("last_activity") if summary else None,
            "video": str(video_path) if delivered else None,
            "review_render": review_render,
            "qa_verified": delivered,
        })
        prior_verified = delivered
    next_chapter = next((row["chapter"] for row in rows if not row["qa_verified"]), None)
    return {
        "id": collection_dir.name,
        "chapter_count": len(rows),
        "completed_count": sum(row["qa_verified"] for row in rows),
        "next_chapter": next_chapter,
        "execution_policy": plan.get("execution_policy") or {},
        "chapters": rows,
    }
