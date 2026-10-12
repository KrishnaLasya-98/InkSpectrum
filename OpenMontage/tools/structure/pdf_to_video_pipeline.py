"""One-command educational document to final video pipeline.

This is a thin ingestion adapter around OpenMontage's existing educational
pipeline. It creates canonical project/config artifacts, then delegates the
actual production stages to SubjectPipelineRunner.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

from lib.checkpoint import init_project
from tools.extract.document_ingestor import ingest_document
from tools.structure.source_contract import write_source_contracts
from tools.structure.subject_pipeline_runner import SubjectPipelineRunner
from tools.structure.chapter_config import LOCKED_UI_TEMPLATE_PACKAGE_SHA256
from tools.structure.subject_profiles import infer_subject_id, resolve_subject_profile
from tools.structure.educational_delivery_naming import (
    delivery_folder_name,
    delivery_video_name,
    infer_book_part,
)


ROOT = Path(__file__).resolve().parents[2]


_AUDIO_PROVIDER_FIELDS = {
    "provider", "model_id", "voice_id", "language", "speed",
    "lock_voice", "enable_stt_qa",
}
_VIDEO_PROVIDER_FIELDS = {
    "provider", "model_id", "image_model_id", "reference_model_id",
    "reference_image_model_id", "fallback_model_id",
    "max_generation_attempts", "semantic_qa",
}
_SEMANTIC_QA_FIELDS = {
    "required", "model", "max_frames", "minimum_match_ratio",
}
_SECRET_FIELD_RE = re.compile(
    r"(?:^|_)(?:api_?key|access_?key|secret|token|password|credential)(?:$|_)",
    re.I,
)


def _reject_embedded_secrets(value: Any, path: str = "provider_config") -> None:
    """Keep credentials out of chapter configs and generated artifacts."""

    if isinstance(value, dict):
        for key, child in value.items():
            if _SECRET_FIELD_RE.search(str(key)):
                raise ValueError(
                    f"{path}.{key} is a credential field. Set MODELSLAB_API_KEY "
                    "in the environment instead of storing secrets in provider config."
                )
            _reject_embedded_secrets(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_embedded_secrets(child, f"{path}[{index}]")


def load_provider_overrides(path: str | Path) -> dict[str, Any]:
    """Load allowlisted ModelsLab model/voice choices from JSON or YAML."""

    config_path = Path(path).resolve()
    if not config_path.is_file():
        raise ValueError(f"Provider config not found: {config_path}")
    text = config_path.read_text(encoding="utf-8")
    if config_path.suffix.lower() == ".json":
        data = json.loads(text)
    elif config_path.suffix.lower() in {".yaml", ".yml"}:
        data = yaml.safe_load(text)
    else:
        raise ValueError("Provider config must be a .json, .yaml, or .yml file")
    if not isinstance(data, dict):
        raise ValueError("Provider config must contain an object")
    _reject_embedded_secrets(data)
    if "providers" in data:
        data = data["providers"]
    if not isinstance(data, dict):
        raise ValueError("provider_config.providers must contain an object")
    unexpected = sorted(set(data) - {"audio", "video"})
    if unexpected:
        raise ValueError(
            "Provider config only supports audio and video sections; unknown: "
            + ", ".join(unexpected)
        )
    return data


def provider_overrides_from_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Build safe per-run provider overrides without accepting credentials."""

    overrides: dict[str, Any] = {}
    provider_config_path = inputs.get("provider_config")
    if provider_config_path:
        overrides = load_provider_overrides(provider_config_path)

    audio_map = {
        "audio_model_id": "model_id",
        "voice_id": "voice_id",
        "audio_language": "language",
        "audio_speed": "speed",
    }
    video_map = {
        "video_model_id": "model_id",
        "image_video_model_id": "image_model_id",
        "reference_video_model_id": "reference_model_id",
        "reference_image_model_id": "reference_image_model_id",
        "fallback_video_model_id": "fallback_model_id",
        "max_generation_attempts": "max_generation_attempts",
        "semantic_qa_model": "semantic_qa_model",
    }
    for source, target in audio_map.items():
        if inputs.get(source) is not None:
            overrides.setdefault("audio", {})[target] = inputs[source]
    for source, target in video_map.items():
        if inputs.get(source) is not None:
            if target == "semantic_qa_model":
                overrides.setdefault("video", {}).setdefault("semantic_qa", {})[
                    "model"
                ] = inputs[source]
            else:
                overrides.setdefault("video", {})[target] = inputs[source]
    _reject_embedded_secrets(overrides)
    return overrides


def apply_provider_overrides(
    config: dict[str, Any], overrides: dict[str, Any] | None
) -> dict[str, Any]:
    """Merge allowlisted model choices while preserving production invariants."""

    if not overrides:
        return config
    _reject_embedded_secrets(overrides)
    providers = config["providers"]
    for section, allowed in (
        ("audio", _AUDIO_PROVIDER_FIELDS),
        ("video", _VIDEO_PROVIDER_FIELDS),
    ):
        values = overrides.get(section, {})
        if not isinstance(values, dict):
            raise ValueError(f"Provider override {section} must be an object")
        unexpected = sorted(set(values) - allowed)
        if unexpected:
            raise ValueError(
                f"Unsupported {section} provider fields: {', '.join(unexpected)}"
            )
        provider = str(values.get("provider", "modelslab"))
        allowed_providers = (
            {"modelslab", "kokoro", "huggingface-kokoro", "hyperframes-kokoro", "elevenlabs"}
            if section == "audio"
            else {"modelslab"}
        )
        if provider not in allowed_providers:
            raise ValueError(
                f"Unsupported educational {section} provider: {provider}"
            )
        if section == "video" and "semantic_qa" in values:
            semantic = values["semantic_qa"]
            if not isinstance(semantic, dict):
                raise ValueError("video.semantic_qa must be an object")
            semantic_unknown = sorted(set(semantic) - _SEMANTIC_QA_FIELDS)
            if semantic_unknown:
                raise ValueError(
                    "Unsupported video.semantic_qa fields: "
                    + ", ".join(semantic_unknown)
                )
            providers[section]["semantic_qa"].update(semantic)
            values = {key: value for key, value in values.items() if key != "semantic_qa"}
        providers[section].update(values)

    audio = providers["audio"]
    video = providers["video"]
    speed = float(audio["speed"])
    if not 0.5 <= speed <= 1.5:
        raise ValueError("ModelsLab narration speed must be between 0.5 and 1.5")
    audio["speed"] = speed
    attempts = int(video["max_generation_attempts"])
    if not 1 <= attempts <= 5:
        raise ValueError("max_generation_attempts must be between 1 and 5")
    video["max_generation_attempts"] = attempts

    # These are safety and editorial invariants, not user-selectable model
    # options. Generated clip audio is always discarded in favour of the
    # chapter narration, and cross-chapter asset reuse remains disabled.
    audio["provider"] = str(audio.get("provider") or "modelslab")
    audio["lock_voice"] = True
    video.update({
        "provider": "modelslab",
        "generate_audio": False,
        "educational_mode": True,
        "fresh_assets_only": True,
        "allow_clip_reuse": False,
    })
    return config


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value[:80] or "educational-chapter"


def resolve_delivery_root(inputs: dict[str, Any]) -> Path:
    """Resolve a cloud-safe final-video root.

    Deployments can mount local, network, or object-storage-backed volumes and
    point ``OPENMONTAGE_DELIVERY_DIR`` at that mount. A per-run
    ``delivery_root`` override takes precedence. No Windows path is embedded in
    generated configs or HTML.
    """

    configured = inputs.get("delivery_root") or os.environ.get(
        "OPENMONTAGE_DELIVERY_DIR"
    )
    return Path(configured).expanduser().resolve() if configured else ROOT / "final-videos"


def infer_metadata(pdf: Path, markdown: str, overrides: dict[str, Any]) -> dict[str, Any]:
    first_heading = re.search(r"^#{1,6}\s+(.+)$", markdown, re.MULTILINE)
    lesson = re.search(r"(?:lesson|chapter)\s*[:.-]?\s*(\d+)\s*([^\n]*)", markdown, re.I)
    class_match = re.search(r"class\s*[-:]?\s*(\d+)", f"{pdf.stem}\n{markdown[:1500]}", re.I)
    equation_count = len(re.findall(r"\$[^$]+\$|\b(?:add|subtract|multiply|divide|number)\b", markdown, re.I))

    title = overrides.get("title")
    if not title:
        if lesson and lesson.group(2).strip():
            title = lesson.group(2).strip(" :-")
        elif first_heading:
            title = first_heading.group(1).strip()
        else:
            title = pdf.stem

    grade = int(overrides.get("grade") or (class_match.group(1) if class_match else 1))
    chapter = int(overrides.get("chapter") or (lesson.group(1) if lesson else 1))
    subject, profile = infer_subject_id(
        markdown,
        filename=pdf.stem,
        explicit_subject=overrides.get("subject"),
    )
    if not overrides.get("subject") and equation_count >= 5:
        subject = "maths"
        profile = resolve_subject_profile("mathematics")
    subject_type = overrides.get("subject_type") or profile.get("subject_type", "theory")
    age_low = max(4, grade + 4)
    book_part = overrides.get("book_part")
    if book_part is None:
        book_part = infer_book_part(pdf)
    if book_part is not None:
        book_part = int(book_part)

    return {
        "title": title,
        "grade": grade,
        "chapter": chapter,
        "subject": subject,
        "subject_label": overrides.get("subject_label") or subject.replace("-", " ").title(),
        "subject_profile": profile["profile_id"],
        "subject_type": subject_type,
        "age_range": f"{age_low}-{age_low + 2}",
        "book_part": book_part,
    }


def build_config(
    pdf: Path,
    project_dir: Path,
    markdown_path: Path,
    metadata: dict[str, Any],
    *,
    extracted_artifact_path: Path | None = None,
    chapter_document_path: Path | None = None,
    coverage_contract_path: Path | None = None,
    provider_overrides: dict[str, Any] | None = None,
    approval_policy: str = "guided",
) -> dict[str, Any]:
    grade = metadata["grade"]
    if grade <= 2:
        delivery = {"wpm_min": 105, "wpm_max": 125, "subtitle_words_max": 7, "sentence_words_target": 12}
    elif grade <= 5:
        delivery = {"wpm_min": 115, "wpm_max": 140, "subtitle_words_max": 9, "sentence_words_target": 16}
    else:
        delivery = {"wpm_min": 125, "wpm_max": 155, "subtitle_words_max": 11, "sentence_words_target": 20}

    config = {
        "version": "1.0",
        "project_id": project_dir.name,
        "subject": metadata["subject"],
        "subject_label": metadata["subject_label"],
        "subject_profile": metadata.get("subject_profile"),
        "chapter": metadata["chapter"],
        "title": metadata["title"],
        "subject_type": metadata["subject_type"],
        "complexity": "elementary" if grade <= 5 else "secondary",
        "grade": grade,
        "age_range": metadata["age_range"],
        "book_part": metadata.get("book_part"),
        "delivery_folder_name": delivery_folder_name(
            grade, metadata["subject_label"]
        ),
        "delivery_video_name": delivery_video_name(
            grade=grade,
            subject_label=metadata["subject_label"],
            book_part=metadata.get("book_part"),
            chapter=metadata["chapter"],
            chapter_title=metadata["title"],
        ),
        "duration_seconds": 480,
        "source_input": str(pdf.resolve()),
        "source_pdf": str(pdf.resolve()) if pdf.suffix.lower() == ".pdf" else None,
        "source_markdown": str(markdown_path.resolve()),
        "source_extraction_artifact": (
            str(extracted_artifact_path.resolve())
            if extracted_artifact_path is not None
            else None
        ),
        "source_document": (
            str(chapter_document_path.resolve())
            if chapter_document_path is not None
            else None
        ),
        "coverage_contract": (
            str(coverage_contract_path.resolve())
            if coverage_contract_path is not None
            else None
        ),
        "pipeline": "educational-video",
        "approval_policy": approval_policy,
        "content_policy": {
            "require_authored_coverage_audit": True,
            "source_fidelity": "complete-topic-coverage",
            "allow_teacher_bridges": True,
            "allow_invented_labels": False,
            "allowed_overlay_types": [
                "chapter_title", "source_section_heading", "narration_subtitle",
                "assessment_prompt", "answer_reveal",
            ],
            "max_content_lines_per_screen": 3,
            "remove_redundant_text": True,
            "display_only_labels_are_not_spoken": True,
            "delivery_timing": {
                "narration_speed": 0.85,
                "spoken_heading_pause_seconds": 2.0,
                "topic_end_pause_seconds": 1.5,
            },
        },
        "grade_delivery": {
            **delivery,
            "subtitle_lines_max": 2,
            "explanation_style": "clear, concrete, age-appropriate, and question-led",
        },
        # Provider selection is data, not chapter code.  ModelsLab generates
        # the narration and motion assets; OpenMontage remains responsible for
        # source-grounded planning, timing, composition, and final QA.
        "providers": {
            "planning": {"provider": "openmontage"},
            "audio": {
                "provider": "modelslab",
                "model_id": "text-to-speech",
                "voice_id": "nova",
                "language": "english",
                "speed": 0.85,
                "lock_voice": True,
                "enable_stt_qa": True,
            },
            "video": {
                "provider": "modelslab",
                "model_id": "wan2.2",
                "image_model_id": "wan-2.2-i2v",
                "reference_model_id": "h3-minimax-r2v",
                "reference_image_model_id": "flux",
                "fallback_model_id": "h3-minimax-t2v",
                "generate_audio": False,
                "educational_mode": True,
                "fresh_assets_only": True,
                "allow_clip_reuse": False,
                "max_generation_attempts": 3,
                "semantic_qa": {
                    "required": True,
                    "model": "clip",
                    "max_frames": 5,
                    "minimum_match_ratio": 0.4,
                },
            },
        },
        "automation_policy": {
            "resume_from_checkpoints": True,
            "max_repair_attempts": 3,
            "fail_on_missing_source_coverage": True,
            "fail_on_final_qa": True,
        },
        "qa_policy": {
            "required_source_coverage": 1.0,
            "max_subtitle_drift_ms": 150,
            "max_av_boundary_drift_ms": 100,
            "reject_black_frames": True,
            "reject_frozen_story_clips": True,
            "reject_reused_assets": True,
            "require_semantic_av_match": True,
        },
        "render_policy": {
            "runtime": "hyperframes",
            "ui_template_id": "hyperframes-educational-v1",
            "ui_template_package_sha256": LOCKED_UI_TEMPLATE_PACKAGE_SHA256,
            "book_presentation_id": "source-faithful-book-v1",
            "template_lock": "strict",
            "composition_mode": "atelier",
            "visual_media": "animated-video-only",
            "embedded_media_text": False,
            "subtitle_timing": "word-aligned",
            "minimum_free_disk_gb": 8.0,
            "workers": 1,
            "low_memory_mode": True,
            "require_streaming_encode": True,
            "sync_authority": "measured-narration",
            "reject_linear_subtitle_alignment": True,
            "shared_timing_map": ["audio", "word_subtitles", "visual_cues", "teaching_ui"],
            "required_opening_cards": [],
            "optional_source_opening_cards": ["we_learn", "lesson_highlights"],
            "opening_cards_policy": "only-if-present-in-source",
            "teaching_ui_style": {
                "badge": "cream-top-left",
                "content_card": "cream-top-right",
                "subtitle_lane": "cream-bottom-word-highlight",
                "background": "full-frame-animated-video",
                "assessment_mode": "source-faithful-stable-reading-screen",
            },
        },
    }
    return apply_provider_overrides(config, provider_overrides)


def run_pdf_to_video(inputs: dict[str, Any]) -> dict[str, Any]:
    pdf = Path(inputs.get("input_path") or inputs["pdf_path"]).resolve()
    if not pdf.is_file():
        raise ValueError(f"Source document not found: {pdf}")

    provisional_id = inputs.get("project_id") or slugify(pdf.stem)
    project_dir = init_project(
        provisional_id,
        title=inputs.get("title") or pdf.stem,
        pipeline_type="educational-video",
        style_playbook="clean-professional",
    )
    artifacts = project_dir / "artifacts"
    extraction = ingest_document(
        pdf,
        subject_type=inputs.get("subject_type", "mixed"),
        output_dir=artifacts,
        preextracted_dir=inputs.get("preextracted_dir"),
    )

    markdown_path = Path(extraction["markdown_path"])
    artifact_path = extraction.get("artifact_path")
    chapter_document_path = artifacts / "chapter_document.json"
    coverage_contract_path = artifacts / "coverage_contract.json"
    chapter_document, coverage_contract = write_source_contracts(
        markdown_path,
        chapter_document_path,
        coverage_contract_path,
        source_pdf=str(pdf) if pdf.suffix.lower() == ".pdf" else None,
        source_input=str(pdf),
        extraction_artifact_path=Path(artifact_path) if artifact_path else None,
    )
    metadata = infer_metadata(pdf, extraction["markdown"], inputs)
    config = build_config(
        pdf,
        project_dir,
        markdown_path,
        metadata,
        extracted_artifact_path=Path(artifact_path) if artifact_path else None,
        chapter_document_path=chapter_document_path,
        coverage_contract_path=coverage_contract_path,
        provider_overrides=provider_overrides_from_inputs(inputs),
        approval_policy=(
            "full-run-preauthorized"
            if bool(inputs.get("full_run_preauthorized"))
            or bool(inputs.get("dry_run", False))
            else "guided"
        ),
    )
    config_path = project_dir / "chapter_config.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    result = SubjectPipelineRunner().execute({
        "subject": metadata["subject"],
        "chapter_config_path": str(config_path),
        "output_dir": str(project_dir),
        "quality": inputs.get("quality", "standard"),
        "dry_run": bool(inputs.get("dry_run", False)),
    })
    if not result.success:
        raise RuntimeError(result.error)
    if result.data.get("status") == "awaiting_human":
        delivery_dir = resolve_delivery_root(inputs) / config["delivery_folder_name"]
        return {
            "project_id": provisional_id,
            "status": "awaiting_human",
            "stage": result.data.get("stage"),
            "project_dir": str(project_dir),
            "chapter_config": str(config_path),
            "extracted_content": str(markdown_path),
            "chapter_document": str(chapter_document_path),
            "coverage_contract": str(coverage_contract_path),
            "source_blocks": chapter_document["validation"]["block_count"],
            "final_video": "",
            "workspace_path": result.data.get("workspace_path", ""),
            "delivery_folder": str(delivery_dir),
            "delivery_video": str(delivery_dir / config["delivery_video_name"]),
            "cost_usd": result.data.get("cost_usd", result.cost_usd or 0.0),
        }
    # The runner closes and persists the coverage ledger during planning. The
    # object created before execution is intentionally immutable evidence of
    # the initial pending state, so reload the authoritative post-run artifact
    # instead of returning its stale render_ready=False value.
    try:
        final_coverage_contract = json.loads(
            coverage_contract_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Final coverage contract could not be read: {exc}"
        ) from exc
    delivery_dir = resolve_delivery_root(inputs) / config["delivery_folder_name"]
    delivery_path = delivery_dir / config["delivery_video_name"]
    final_video = str(result.data["final_video"] or "")
    if final_video:
        rendered_path = Path(final_video)
        if not rendered_path.is_file():
            raise RuntimeError(
                f"Runner reported a final video that does not exist: {rendered_path}"
            )
        delivery_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(rendered_path, delivery_path)
    return {
        "project_id": provisional_id,
        "status": "dry_run_complete" if inputs.get("dry_run") else "completed",
        "chapter_config": str(config_path),
        "extracted_content": str(markdown_path),
        "chapter_document": str(chapter_document_path),
        "coverage_contract": str(coverage_contract_path),
        "source_blocks": chapter_document["validation"]["block_count"],
        "coverage_render_ready": final_coverage_contract["summary"]["render_ready"],
        "final_video": final_video,
        "workspace_path": result.data.get("workspace_path", ""),
        "delivery_folder": str(delivery_dir),
        "delivery_video": str(delivery_path) if final_video else "",
        "stages_summary": result.data["stages_summary"],
        "cost_usd": result.data["cost_usd"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert an educational PDF, Markdown, text, or DOCX document into a complete video."
    )
    parser.add_argument("source")
    parser.add_argument("--project-id")
    parser.add_argument("--subject")
    parser.add_argument("--subject-label")
    parser.add_argument("--subject-type", choices=["theory", "mathematics", "mixed"])
    parser.add_argument("--grade", type=int)
    parser.add_argument("--chapter", type=int)
    parser.add_argument("--book-part", type=int)
    parser.add_argument("--title")
    parser.add_argument("--quality", default="standard")
    parser.add_argument(
        "--delivery-root",
        help=(
            "Final-video root. Defaults to OPENMONTAGE_DELIVERY_DIR or "
            "<repo>/final-videos."
        ),
    )
    parser.add_argument(
        "--provider-config",
        help="JSON/YAML model and voice settings only; keep MODELSLAB_API_KEY in the environment",
    )
    parser.add_argument("--audio-model-id")
    parser.add_argument("--voice-id")
    parser.add_argument("--audio-language")
    parser.add_argument("--audio-speed", type=float)
    parser.add_argument("--video-model-id")
    parser.add_argument("--image-video-model-id")
    parser.add_argument("--reference-video-model-id")
    parser.add_argument("--reference-image-model-id")
    parser.add_argument("--fallback-video-model-id")
    parser.add_argument("--max-generation-attempts", type=int)
    parser.add_argument("--semantic-qa-model")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--full-run-preauthorized",
        action="store_true",
        help=(
            "Run through proposal, asset, and final QA gates without stopping. "
            "Use only after budget and creative direction are already approved."
        ),
    )
    args = vars(parser.parse_args())
    args["input_path"] = args.pop("source")
    try:
        print(json.dumps(run_pdf_to_video(args), indent=2))
    except Exception as exc:
        print(f"Document-to-video failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
