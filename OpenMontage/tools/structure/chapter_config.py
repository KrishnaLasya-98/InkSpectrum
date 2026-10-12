"""Load and validate data-driven educational chapter profiles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


REQUIRED = {
    "project_id", "subject", "subject_label", "chapter", "title",
    "subject_type", "grade", "age_range", "duration_seconds",
    "source_markdown", "content_policy", "render_policy",
}

LOCKED_UI_TEMPLATE_ID = "hyperframes-educational-v1"
LOCKED_UI_TEMPLATE_VERSION = "1.0.3"
LOCKED_UI_TEMPLATE_SHA256 = (
    "75eed8d0e813ef1b6523d247b6b6c49b46cc209930ebdab02a595d24627757fb"
)
LOCKED_UI_TEMPLATE_PACKAGE_SHA256 = (
    "3a2db835b642c19b4231ad00f8117101e8d9878990fb66fd075c9ce0ef8ea3f5"
)
LOCKED_BOOK_PRESENTATION_ID = "source-faithful-book-v1"
LOCKED_UI_TEMPLATE_RELATIVE_PATH = "styles/hyperframes-educational-v1.yaml"


def _canonical_sha256(value: Any) -> str:
    """Hash parsed data so the lock is stable across OS line endings."""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def locked_ui_template_contract() -> dict[str, Any]:
    """Return and verify the immutable educational UI contract.

    A template edit is a production-wide change, not a chapter customization.
    The canonical hash therefore lives in code and in the pipeline manifest;
    changing the YAML without deliberately bumping the contract fails closed.
    """
    template_path = (
        Path(__file__).resolve().parents[2] / LOCKED_UI_TEMPLATE_RELATIVE_PATH
    )
    if not template_path.is_file():
        raise ValueError(f"Locked UI template is missing: {template_path}")

    template = yaml.safe_load(template_path.read_text(encoding="utf-8"))
    if not isinstance(template, dict):
        raise ValueError("Locked UI template must contain a YAML object")

    expected_fields = {
        "id": LOCKED_UI_TEMPLATE_ID,
        "version": LOCKED_UI_TEMPLATE_VERSION,
        "status": "locked",
        "runtime": "hyperframes",
        "presentation_contract": LOCKED_BOOK_PRESENTATION_ID,
    }
    for field, expected in expected_fields.items():
        if template.get(field) != expected:
            raise ValueError(
                f"Locked UI template {field} must be {expected!r}; "
                f"found {template.get(field)!r}"
            )

    digest = _canonical_sha256(template)
    if digest != LOCKED_UI_TEMPLATE_SHA256:
        raise ValueError(
            "Locked UI template content changed without an approved version/hash "
            f"update: expected {LOCKED_UI_TEMPLATE_SHA256}, found {digest}"
        )
    from tools.video.educational_hyperframes_composer import (
        educational_template_package_sha256,
    )

    package_digest = educational_template_package_sha256()
    if package_digest != LOCKED_UI_TEMPLATE_PACKAGE_SHA256:
        raise ValueError(
            "Locked educational template package changed without an approved "
            "version/hash update: expected "
            f"{LOCKED_UI_TEMPLATE_PACKAGE_SHA256}, found {package_digest}"
        )
    return {
        "id": LOCKED_UI_TEMPLATE_ID,
        "version": LOCKED_UI_TEMPLATE_VERSION,
        "status": "locked",
        "runtime": "hyperframes",
        "presentation_contract": LOCKED_BOOK_PRESENTATION_ID,
        "path": LOCKED_UI_TEMPLATE_RELATIVE_PATH,
        "sha256": digest,
        "package_sha256": package_digest,
    }


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

    template_contract = locked_ui_template_contract()
    render = data["render_policy"]
    render.setdefault("ui_template_id", LOCKED_UI_TEMPLATE_ID)
    render.setdefault("ui_template_version", LOCKED_UI_TEMPLATE_VERSION)
    render.setdefault("ui_template_contract_path", LOCKED_UI_TEMPLATE_RELATIVE_PATH)
    render.setdefault("ui_template_sha256", LOCKED_UI_TEMPLATE_SHA256)
    render.setdefault(
        "ui_template_package_sha256", LOCKED_UI_TEMPLATE_PACKAGE_SHA256
    )
    render.setdefault("book_presentation_id", LOCKED_BOOK_PRESENTATION_ID)
    render.setdefault("template_lock", "strict")
    if render.get("runtime") != "hyperframes":
        raise ValueError("Educational chapter render_policy.runtime is locked to hyperframes")
    if render["ui_template_id"] != LOCKED_UI_TEMPLATE_ID:
        raise ValueError(
            f"render_policy.ui_template_id must be {LOCKED_UI_TEMPLATE_ID}"
        )
    if render["ui_template_version"] != LOCKED_UI_TEMPLATE_VERSION:
        raise ValueError(
            "render_policy.ui_template_version must be "
            f"{LOCKED_UI_TEMPLATE_VERSION}"
        )
    if render["ui_template_contract_path"] != LOCKED_UI_TEMPLATE_RELATIVE_PATH:
        raise ValueError(
            "render_policy.ui_template_contract_path must be "
            f"{LOCKED_UI_TEMPLATE_RELATIVE_PATH}"
        )
    if render["ui_template_sha256"] != template_contract["sha256"]:
        raise ValueError(
            "render_policy.ui_template_sha256 does not match the approved "
            f"{LOCKED_UI_TEMPLATE_ID} contract"
        )
    if render["ui_template_package_sha256"] != template_contract["package_sha256"]:
        raise ValueError(
            "render_policy.ui_template_package_sha256 does not match the approved "
            f"{LOCKED_UI_TEMPLATE_ID} package"
        )
    if render["template_lock"] != "strict":
        raise ValueError("render_policy.template_lock must remain strict")
    if render["book_presentation_id"] != LOCKED_BOOK_PRESENTATION_ID:
        raise ValueError(
            "render_policy.book_presentation_id must be "
            f"{LOCKED_BOOK_PRESENTATION_ID}"
        )

    source = Path(data["source_markdown"])
    if not source.is_absolute():
        source = (config_path.parent / source).resolve()
    data["source_markdown"] = str(source)
    for optional_source in (
        "source_input", "source_pdf", "source_extraction_artifact",
        "source_document", "coverage_contract"
    ):
        if data.get(optional_source):
            optional_path = Path(data[optional_source])
            if not optional_path.is_absolute():
                optional_path = (config_path.parent / optional_path).resolve()
            data[optional_source] = str(optional_path)
    data["_config_path"] = str(config_path)
    return data


def registry_view(config: dict[str, Any]) -> dict[str, Any]:
    """Adapt a chapter profile to the runner's legacy subject registry shape."""
    return {
        "label": config["subject_label"],
        "subject_profile": config.get("subject_profile"),
        "chapter": config["chapter"],
        "title": config["title"],
        "subject_type": config["subject_type"],
        "complexity": config.get("complexity", "elementary"),
        "audience": f"Class {config['grade']}, ages {config['age_range']}",
        "duration_s": config["duration_seconds"],
        "source_input": config.get("source_input"),
        "source_pdf": config.get("source_pdf"),
        "source_markdown": config["source_markdown"],
        "source_document": config.get("source_document"),
        "coverage_contract": config.get("coverage_contract"),
        "content_policy": config["content_policy"],
        "grade_delivery": config.get("grade_delivery", {}),
        "render_policy": config["render_policy"],
        "providers": config.get("providers", {}),
        "automation_policy": config.get("automation_policy", {}),
        "qa_policy": config.get("qa_policy", {}),
    }
