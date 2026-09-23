"""Load and validate data-driven educational chapter profiles."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED = {
    "project_id", "subject", "subject_label", "chapter", "title",
    "subject_type", "grade", "age_range", "duration_seconds",
    "source_markdown", "content_policy", "render_policy",
}

LOCKED_UI_TEMPLATE_ID = "hyperframes-educational-v1"
LOCKED_BOOK_PRESENTATION_ID = "source-faithful-book-v1"


def load_chapter_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path).resolve()
    data = json.loads(config_path.read_text(encoding="utf-8"))
    missing = sorted(REQUIRED - set(data))
    if missing:
        raise ValueError(f"Chapter config missing required fields: {', '.join(missing)}")

    content = data["content_policy"]
    if content.get("allow_invented_labels", False):
        raise ValueError("content_policy.allow_invented_labels must remain false")
    if content.get("max_content_lines_per_screen", 0) not in range(1, 4):
        raise ValueError("max_content_lines_per_screen must be between 1 and 3")

    render = data["render_policy"]
    render.setdefault("ui_template_id", LOCKED_UI_TEMPLATE_ID)
    render.setdefault("book_presentation_id", LOCKED_BOOK_PRESENTATION_ID)
    if render.get("runtime") != "hyperframes":
        raise ValueError("Educational chapter render_policy.runtime is locked to hyperframes")
    if render["ui_template_id"] != LOCKED_UI_TEMPLATE_ID:
        raise ValueError(
            f"render_policy.ui_template_id must be {LOCKED_UI_TEMPLATE_ID}"
        )
    if render["book_presentation_id"] != LOCKED_BOOK_PRESENTATION_ID:
        raise ValueError(
            "render_policy.book_presentation_id must be "
            f"{LOCKED_BOOK_PRESENTATION_ID}"
        )

    source = Path(data["source_markdown"])
    if not source.is_absolute():
        source = (config_path.parent / source).resolve()
    data["source_markdown"] = str(source)
    data["_config_path"] = str(config_path)
    return data


def registry_view(config: dict[str, Any]) -> dict[str, Any]:
    """Adapt a chapter profile to the runner's legacy subject registry shape."""
    return {
        "label": config["subject_label"],
        "chapter": config["chapter"],
        "title": config["title"],
        "subject_type": config["subject_type"],
        "complexity": config.get("complexity", "elementary"),
        "audience": f"Class {config['grade']}, ages {config['age_range']}",
        "duration_s": config["duration_seconds"],
        "source_markdown": config["source_markdown"],
        "content_policy": config["content_policy"],
        "render_policy": config["render_policy"],
        "providers": config.get("providers", {}),
    }
