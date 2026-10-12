"""Advance a reviewed chapter through source-locked, no-cost production stages.

The input checkpoint and authored plan must already exist. This command never
extracts raw OCR again or submits a media job. Re-running it preserves completed
checkpoints and rejects changed plans instead of silently invalidating media.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

from schemas.artifacts import validate_artifact
from tools.analysis.educational_media_research_planner import EducationalMediaResearchPlanner
from tools.structure.chapter_config import load_chapter_config
from tools.structure.educational_production_artifacts import build_production_artifacts
from tools.structure.educational_run_tracker import EducationalRunTracker, artifact_fingerprint
from tools.structure.pdf_to_video_pipeline import build_config
from tools.structure.teaching_contract import validate_teaching_contract


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def _finish_once(tracker: EducationalRunTracker, project: Path, stage: str,
                 artifacts: dict, metadata: dict) -> str:
    # The checkpoint writer binds proposal approval to the normalized decision
    # log path. Compare the same payload on resume, not the pre-normalized one.
    expected = deepcopy(artifacts)
    if isinstance(expected.get("decision_log"), dict):
        proposal = expected.get("proposal_packet") or {}
        if isinstance(proposal.get("production_plan"), dict):
            proposal["production_plan"]["decision_log_ref"] = str(project / "decision_log.json")
    checkpoint_path = project / f"checkpoint_{stage}.json"
    if checkpoint_path.is_file():
        previous = _read(checkpoint_path)
        if previous.get("status") == "completed":
            if artifact_fingerprint(previous.get("artifacts") or {}) != artifact_fingerprint(expected):
                raise ValueError(f"Completed {stage} differs from current plan; explicit revision required")
            return "already_completed"
    tracker.begin(stage, metadata=metadata)
    return tracker.finish(stage, artifacts, metadata=metadata)


def prepare(project: Path, *, audio_provider: str = "huggingface-kokoro", audio_config: dict | None = None) -> dict:
    project = project.resolve()
    artifacts = project / "artifacts"
    ingestion = _read(project / "checkpoint_input_ingestion.json")
    if ingestion.get("status") != "completed" or ingestion.get("metadata", {}).get("page_audit_status") != "pass":
        raise ValueError("Reviewed source ingestion must pass before chapter preparation")
    source = ingestion["artifacts"]
    plan_path = artifacts / "educational_plan.json"
    plan = _read(plan_path)
    document = _read(Path(source["chapter_document_path"]))
    validate_artifact("educational_plan", plan)
    teaching = validate_teaching_contract(plan, document["blocks"], subject=plan.get("domain", ""))
    if teaching["status"] != "pass":
        raise ValueError(f"Teaching contract failed: {teaching['issues'][:5]}")
    scope = plan.get("metadata", {}).get("production_scope") or {}
    sections = plan["sections"]
    if (not scope.get("user_approved") or not scope.get("exclude_assessments")
            or sections[-1]["section_id"] != scope.get("end_section_id")
            or sections[-1].get("source_semantic_role") != "glossary"):
        raise ValueError("The approved through-Word-Bank scope is missing or changed")
    pdf = Path(ingestion["metadata"]["source_pdf"])
    if not pdf.is_file():
        raise ValueError(f"Missing original chapter PDF: {pdf}")
    details = plan["metadata"]
    grade = int(details["grade"])
    chapter = int(details["chapter"])
    subject = str(details["subject"])
    metadata = {
        "title": plan["title"], "grade": grade, "chapter": chapter,
        "subject": subject, "subject_label": "Social" if subject == "social-studies" else details.get("subject_label", subject.title()),
        "subject_profile": "social_science" if subject == "social-studies" else subject,
        "subject_type": plan["subject_classification"],
        "age_range": f"{grade + 4}-{grade + 6}", "book_part": None,
    }
    config = build_config(
        pdf, project, Path(source["extracted_content_path"]), metadata,
        extracted_artifact_path=artifacts / "extracted_content.json",
        chapter_document_path=Path(source["chapter_document_path"]),
        coverage_contract_path=Path(source["coverage_contract_path"]),
        provider_overrides={"audio": audio_config or {
            "provider": audio_provider, "model_id": "hexgrad/Kokoro-82M",
            "voice_id": "af_heart", "language": "en-us", "speed": 0.85,
            "lock_voice": True, "enable_stt_qa": False,
        }},
        approval_policy="full-run-preauthorized",
    )
    config["duration_seconds"] = plan["total_duration_seconds"]
    config["educational_plan_path"] = str(plan_path.resolve())
    config["content_policy"]["require_teaching_contract"] = True
    config["render_policy"]["provider_outage_fallback"] = "blocked-no-substitution"
    config_path = project / "chapter_config.json"
    if config_path.is_file():
        old = _read(config_path)
        if old != config:
            raise ValueError("Existing chapter configuration differs; explicit revision required")
    else:
        _save(config_path, config)
    load_chapter_config(config_path)
    _save(artifacts / "teaching_contract_review.json", teaching)

    built = build_production_artifacts(config, plan)
    for name, value in built.items():
        validate_artifact(name, value)
        output = artifacts / f"{name}.json"
        if output.is_file() and _read(output) != value:
            raise ValueError(f"Existing {name} differs; explicit revision required")
        if not output.is_file():
            _save(output, value)
    tracker = EducationalRunTracker(project, title=plan["title"], approval_policy="full-run-preauthorized")
    stages = {}
    stages["proposal"] = _finish_once(
        tracker, project, "proposal",
        {"proposal_packet": built["proposal_packet"], "decision_log": built["decision_log"]},
        {"proposal_path": str(artifacts / "proposal_packet.json"), "scope": "opening-through-Word-Bank"},
    )
    stages["content_structuring"] = _finish_once(
        tracker, project, "content_structuring",
        {"educational_plan_path": str(plan_path),
         "source_coverage_path": source["coverage_contract_path"]},
        {"sections": len(sections), "verified_source_blocks": teaching["verified_text_blocks"]},
    )
    stages["scene_plan"] = _finish_once(
        tracker, project, "scene_plan", {"scene_plan": built["scene_plan"]},
        {"scene_plan_path": str(artifacts / "scene_plan.json"), "scenes": len(sections)},
    )
    media_result = EducationalMediaResearchPlanner().execute({
        "subject": subject, "scenes": built["scene_plan"]["scenes"],
    })
    if not media_result.success:
        raise ValueError(f"Media-research planning failed: {media_result.error}")
    media_plan = media_result.data["media_research_plan"]
    # The user explicitly approved fresh chapter-specific 3D motion and exact
    # original figures. Stock footage is not an alternate source for this run.
    for item in media_plan["scenes"]:
        item.update(search_required=False, queries=[], preferred_sources=[],
                    selection_status="not_required",
                    rationale=item["rationale"] + " Stock search is waived for the approved fresh-3D/source-figure production mode.")
    media_plan["search_scene_count"] = 0
    media_plan["selection_policy"]["fresh_3d_and_source_figures_only"] = True
    validate_artifact("media_research_plan", media_plan)
    media_path = artifacts / "media_research_plan.json"
    if media_path.is_file() and _read(media_path) != media_plan:
        raise ValueError("Existing media-research plan differs; explicit revision required")
    if not media_path.is_file():
        _save(media_path, media_plan)
    stages["media_research"] = _finish_once(
        tracker, project, "media_research", {"media_research_plan": media_plan},
        {"path": str(media_path), "stock_searches": 0, "selection": "fresh_3d_plus_source_figures"},
    )
    if built["asset_strategy"]["blocked_scene_ids"]:
        raise ValueError("Asset strategy contains blocked scenes")
    # This checkpoint approves the asset strategy and provider, not completion
    # of the pending video jobs. render_clips and final QA remain mandatory.
    stages["assets"] = _finish_once(
        tracker, project, "assets",
        {"asset_manifest": built["asset_manifest"], "asset_strategy": built["asset_strategy"]},
        {"asset_manifest_path": str(artifacts / "asset_manifest.json"),
         "asset_strategy_path": str(artifacts / "asset_strategy.json"),
         "acquisition_status": "planned_not_generated", "planned_assets": len(built["asset_manifest"]["assets"])},
    )
    return {"project": str(project), "chapters_prepared": 1, "sections": len(sections),
            "source_blocks": teaching["verified_text_blocks"], "stages": stages,
            "next_stage": "voice_synthesis"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.project), indent=2))


if __name__ == "__main__":
    main()
