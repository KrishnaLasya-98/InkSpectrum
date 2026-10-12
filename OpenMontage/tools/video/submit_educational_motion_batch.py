"""Submit a bounded, durable chapter-specific ModelsLab motion batch.

Existing output files and provider job sidecars are never replaced. A second
invocation resumes by skipping them; recovery is a separate read/poll step.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from lib.production_runtime import atomic_json
from tools.video.modelslab_video import ModelsLabVideo
from tools.video.modelslab_motion_budget import MotionBudget


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_sealed_batch_approval(project: Path, batch_path: Path, batch: dict, plan: dict) -> dict:
    """Bind paid admission to the exact twice-reviewed batch, references and source routes."""
    match = re.search(r"motion-batch-(\d+)$", batch_path.stem)
    if not match:
        raise ValueError("Paid batch filename must end in motion-batch-N")
    approval_path = project / "artifacts" / f"motion-batch-{int(match.group(1)):02d}-pre-generation-review.json"
    if not approval_path.is_file():
        raise ValueError(f"Missing sealed pre-generation review: {approval_path.name}")
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    if approval.get("version") != "1.1" or approval.get("status") != "approved_exact_batch_not_submitted":
        raise ValueError(f"Pre-generation review is not sealed for paid admission: {approval_path.name}")
    if approval.get("batch_path") != str(batch_path) or approval.get("batch_sha256") != _sha256(batch_path):
        raise ValueError("Batch changed after pre-generation review")
    approved = approval.get("approved_shots")
    shots = batch.get("shots") or []
    if not isinstance(approved, list) or len(approved) != len(shots):
        raise ValueError("Sealed approval shot count differs from batch")
    approved_by_id = {row.get("shot_id"): row for row in approved}
    if len(approved_by_id) != len(approved):
        raise ValueError("Sealed approval contains duplicate shot IDs")
    plan_by_id = {row["section_id"]: row for row in plan.get("sections", [])}
    for shot in shots:
        sealed = approved_by_id.get(shot.get("shot_id"))
        if not sealed or sealed.get("section_id") != shot.get("section_id"):
            raise ValueError(f"Shot is not sealed to its source section: {shot.get('shot_id')}")
        source_ids = sealed.get("source_block_ids")
        expected_ids = plan_by_id.get(shot.get("section_id"), {}).get("source_block_ids")
        if not source_ids or source_ids != expected_ids:
            raise ValueError(f"Source routing is not sealed: {shot.get('shot_id')}")
        if batch.get("operation") == "image_to_video":
            reference = (project / shot["reference_image"]).resolve()
            if sealed.get("reference_sha256") != _sha256(reference):
                raise ValueError(f"Reference image changed after review: {shot.get('shot_id')}")
    checks = approval.get("checks") or {}
    required = {
        "two_visual_review_rounds", "unique_shot_ids", "unique_reference_hashes",
        "source_matched_sections", "generated_text_forbidden", "authored_labels_retained",
    }
    if any(checks.get(key) is not True for key in required):
        raise ValueError("Sealed approval is missing a required review check")
    return approval


def submit_batch(project: Path, batch_path: Path, *, max_new: int = 15, budget=None) -> dict:
    project = project.resolve()
    batch_path = batch_path.resolve()
    if max_new < 1 or max_new > 15:
        raise ValueError("max_new must be between 1 and 15")
    if not batch_path.is_relative_to(project):
        raise ValueError("Batch must be inside its chapter project")
    config = json.loads((project / "chapter_config.json").read_text(encoding="utf-8"))
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    video = config["providers"]["video"]
    operation = batch["operation"]
    expected_model = (video["model_id"] if operation == "text_to_video"
                      else video["image_model_id"] if operation == "image_to_video" else None)
    if (video["provider"] != "modelslab" or batch["provider"] != "modelslab"
            or batch["model_id"] != expected_model):
        raise ValueError("Batch differs from the approved ModelsLab Wan 2.2 provider contract")
    if not config.get("approval_policy") == "full-run-preauthorized":
        raise ValueError("Paid generation is not preauthorized for this chapter")
    plan = json.loads((project / "artifacts" / "educational_plan.json").read_text(encoding="utf-8"))
    section_ids = {section["section_id"] for section in plan["sections"]}
    shots = batch.get("shots") or []
    if not isinstance(shots, list) or not shots:
        raise ValueError("Batch has no shots")
    shot_ids = [shot["shot_id"] for shot in shots]
    if len(set(shot_ids)) != len(shot_ids):
        raise ValueError("Duplicate shot IDs")
    for shot in shots:
        frames = shot.get("num_frames", 81 if operation == "text_to_video" else 82)
        if type(frames) is not int or not 81 <= frames <= 120:
            raise ValueError("Wan shot num_frames must be an integer from 81 through 120")
        if operation != "text_to_video" and "num_frames" in shot:
            raise ValueError("Custom frame budgets are enabled only for Wan text-to-video")
        if shot["section_id"] not in section_ids or len(shot["prompt"].strip()) < 80:
            raise ValueError(f"Unreviewed shot: {shot['shot_id']}")
        if re.search(r"\bballs?\b", shot["prompt"], re.IGNORECASE):
            if not re.search(r"\bblue\s+(?:rubber\s+)?balls?\b", shot["prompt"], re.IGNORECASE):
                raise ValueError(f"Ball shot must specify a blue ball: {shot['shot_id']}")
            if re.search(r"\b(?:red|orange|yellow|green|purple|pink|brown|black|white)\s+balls?\b",
                         shot["prompt"], re.IGNORECASE):
                raise ValueError(f"Ball shot specifies a non-blue ball: {shot['shot_id']}")
        if not shot["shot_id"].replace("-", "").isalnum():
            raise ValueError("Shot ID contains unsafe filename characters")
        if operation == "image_to_video":
            reference = (project / shot["reference_image"]).resolve()
            if not reference.is_relative_to(project) or not reference.is_file():
                raise ValueError(f"Missing or out-of-project reference image: {shot['shot_id']}")
    validate_sealed_batch_approval(project, batch_path, batch, plan)
    output_dir = project / "assets" / "video" / batch_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = batch_path.with_name(batch_path.stem + "-status.json")
    previous = json.loads(status_path.read_text(encoding="utf-8")) if status_path.is_file() else {"shots": []}
    reports = {row["shot_id"]: row for row in previous["shots"]}
    submitted = 0
    tool = ModelsLabVideo()
    for shot in shots:
        if submitted >= max_new:
            break
        output = output_dir / f"{shot['shot_id']}.mp4"
        sidecar = Path(str(output) + ".modelslab-job.json")
        if output.is_file() or sidecar.is_file():
            reports.setdefault(shot["shot_id"], {
                "shot_id": shot["shot_id"], "status": "existing_file_or_job",
                "output_path": str(output),
            })
            continue
        request = {
            "prompt": shot["prompt"],
            "negative_prompt": "text, captions, labels, watermark, logos, malformed geography, still image, freeze, stutter, loop, flicker, photorealism, live action",
            "model_id": batch["model_id"], "operation": operation,
            "duration": "5", "fps": 16,
            "num_frames": shot.get("num_frames", 81 if operation == "text_to_video" else 82),
            "resolution": "480p", "aspect_ratio": "16:9",
            "generate_audio": False, "educational_mode": True,
            "submit_only": True, "output_path": str(output),
        }
        if operation == "image_to_video":
            request["image_path"] = str((project / shot["reference_image"]).resolve())
        # Submit-only releases the HTTP request quickly; the GPU work stays
        # asynchronous. Admission is shared across chapters, not per batch.
        admission = budget if budget is not None else MotionBudget()
        with admission.locked() as acquired:
            if not acquired:
                return {"status": "waiting_for_account_lock", "new_submissions": submitted,
                        "batch": str(batch_path), "retry_after_seconds": 5}
            reservation = admission.reserve(output)
            if reservation is None:
                return {"status": "waiting_for_capacity", "new_submissions": submitted,
                        "batch": str(batch_path), "budget": admission.snapshot()}
            result = tool.execute(request)
            if result.success:
                admission.acknowledge(reservation, (result.data or {}).get("request_id"))
        row = {
            "shot_id": shot["shot_id"], "section_id": shot["section_id"],
            "status": "submitted" if result.success else "submission_error",
            "request_id": (result.data or {}).get("request_id"),
            "output_path": str(output), "error": result.error,
        }
        reports[shot["shot_id"]] = row
        atomic_json(status_path, {"version": "1.0", "batch": str(batch_path),
                                  "shots": list(reports.values()), "complete": False})
        if not result.success:
            raise RuntimeError(f"ModelsLab submission failed for {shot['shot_id']}: {result.error}")
        submitted += 1
    return {"batch": str(batch_path), "new_submissions": submitted,
            "tracked_shots": len(reports), "total_shots": len(shots),
            "status_path": str(status_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--batch", required=True, type=Path)
    parser.add_argument("--max-new", type=int, default=15)
    args = parser.parse_args()
    print(json.dumps(submit_batch(args.project, args.batch, max_new=args.max_new), indent=2))


if __name__ == "__main__":
    main()
