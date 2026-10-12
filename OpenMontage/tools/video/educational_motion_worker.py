"""Recover then fill up to 15 cloud slots for approved chapter motion batches.

This is a MEDIA worker, not an agent or a final-video/QA completion substitute.
It never starts another chapter or launches a local renderer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from lib.production_runtime import atomic_json
from tools.structure.educational_job_worker import queue_lock
from tools.video.modelslab_motion_budget import MotionBudget
from tools.video.recover_educational_motion_batch import recover
from tools.video.submit_educational_motion_batch import submit_batch


def recovery_retry_delay(base_seconds: float, consecutive_errors: int) -> float:
    """Bound transport-only recovery retries without changing provider state."""
    if base_seconds < 30 or consecutive_errors < 1:
        raise ValueError("Recovery retry inputs are out of bounds")
    return min(base_seconds * (2 ** (consecutive_errors - 1)), 300.0)


def _queue_payload(project: Path, queue_file: Path) -> dict:
    """Load the durable rolling queue and fail closed on ambiguous paths/state."""
    project = project.resolve()
    queue_path = queue_file.resolve()
    if not queue_path.is_relative_to(project):
        raise ValueError(f"Approved queue is outside project: {queue_path}")
    payload = json.loads(queue_path.read_text(encoding="utf-8"))
    if payload.get("version") != "1.1":
        raise ValueError("Approved batch queue must use schema version 1.1")
    declared_project = Path(str(payload.get("project_path") or ""))
    if not declared_project.is_absolute() or declared_project.resolve() != project:
        raise ValueError("Approved batch queue project_path must be this absolute project path")
    if payload.get("admission") not in {"enabled", "paused"}:
        raise ValueError("Approved batch queue admission must be enabled or paused")
    entries = payload.get("batches")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Approved batch queue must contain a non-empty batches list")
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("state") != "approved":
            raise ValueError("Every queue batch must be an approved object")
        value = entry.get("path")
        path = Path(str(value or ""))
        if not path.is_absolute():
            raise ValueError("Every durable queue batch path must be absolute")
        resolved = path.resolve()
        if not resolved.is_relative_to(project) or not resolved.is_file():
            raise ValueError(f"Invalid approved queue batch path: {resolved}")
    return payload


def approved_batches(project: Path, command_batches: list[Path], queue_file: Path | None) -> list[Path]:
    """Resolve an explicit durable queue without ever globbing old chapter batches."""
    project = project.resolve()
    candidates = list(command_batches)
    if queue_file is not None:
        payload = _queue_payload(project, queue_file)
        candidates.extend(Path(entry["path"]) for entry in payload["batches"])
    resolved = []
    seen = set()
    for candidate in candidates:
        path = candidate if candidate.is_absolute() else project / candidate
        path = path.resolve()
        if not path.is_relative_to(project):
            raise ValueError(f"Approved batch is outside project: {path}")
        if not path.is_file():
            raise FileNotFoundError(path)
        if path not in seen:
            seen.add(path)
            resolved.append(path)
    return resolved


def tick(project: Path, batches: list[Path], *, budget=None, allow_submissions: bool = True):
    project = project.resolve()
    admission = budget if budget is not None else MotionBudget()
    reports = []
    # Resolve/recover every existing job in this chapter before new submissions.
    for batch in batches:
        report = recover(project, batch)
        reports.append(report)
        if any(row["status"] == "check_error" for row in report["jobs"]):
            # A read-only poll can fail during a brief network interruption.
            # Never submit while any known job could not be checked; the watch
            # loop may retry this recovery-only state a bounded number of times.
            return {"status": "recovery_check_deferred",
                    "reason": "Transient provider recovery check failed",
                    "recovery": reports, "new_submissions": 0}
        if any(row["status"] not in {"downloaded", "recovered", "not_submitted",
                                     "processing", "queued", "pending", "suspect_terminal"}
               for row in report["jobs"]):
            return {"status": "attention", "reason": "Provider recovery needs reconciliation",
                    "recovery": reports, "new_submissions": 0}
    if all(r["downloaded"] == r["total"] for r in reports):
        return {"status": "media_downloaded_qa_pending", "recovery": reports,
                "new_submissions": 0}
    if not allow_submissions:
        return {"status": "recovery_only", "recovery": reports,
                "new_submissions": 0, "budget": admission.snapshot()}
    submissions = []
    for batch in batches:
        result = submit_batch(project, batch, max_new=15, budget=admission)
        submissions.append(result)
        if result.get("status", "").startswith("waiting_"):
            break
    return {"status": "media_generation_in_progress", "recovery": reports,
            "submissions": submissions,
            "new_submissions": sum(r["new_submissions"] for r in submissions),
            "budget": admission.snapshot()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True, action="append")
    parser.add_argument("--queue-file", type=Path,
                        help="Durable JSON list of additional explicitly approved batches, re-read each tick")
    parser.add_argument("--recover-only", action="store_true",
                        help="Poll/download existing durable IDs but never submit a new paid request")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=60)
    args = parser.parse_args()
    if not args.batch or args.poll_seconds < 30:
        parser.error("At least one batch and a polling interval >=30 seconds are required")
    state = args.project / "artifacts" / "cloud-motion-worker"
    state.mkdir(parents=True, exist_ok=True)
    with queue_lock(state) as acquired:
        if not acquired:
            raise SystemExit("A cloud motion worker already owns this chapter")
        consecutive_check_errors = 0
        while True:
            batches = []
            allow_submissions = False
            try:
                batches = approved_batches(args.project, args.batch, args.queue_file)
                queue_admission = "paused" if args.recover_only else "enabled"
                if args.queue_file is not None:
                    queue_admission = _queue_payload(args.project.resolve(), args.queue_file)["admission"]
                allow_submissions = not args.recover_only and queue_admission == "enabled"
                report = tick(args.project, batches, allow_submissions=allow_submissions)
            except Exception as exc:
                # Do not automatically repeat unknown HTTP outcomes.
                report = {"status": "attention", "error_type": type(exc).__name__,
                          "reason": "Worker stopped; reconcile saved jobs/reservations before resuming"}
                if isinstance(exc, (ValueError, FileNotFoundError)):
                    # Local queue/config validation messages contain no provider
                    # payload and make a fail-closed stop directly actionable.
                    report["validation_detail"] = str(exc)
            report["updated_at_unix"] = time.time()
            if batches:
                content_hashes = {
                    str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in batches
                }
                queue_hash = None
                if args.queue_file is not None and args.queue_file.resolve().is_file():
                    queue_hash = hashlib.sha256(args.queue_file.resolve().read_bytes()).hexdigest()
                report["checkpoint"] = {
                    "project_path": str(args.project.resolve()),
                    "batch_paths": [str(path) for path in batches],
                    "batch_content_sha256": content_hashes,
                    "queue_file_sha256": queue_hash,
                    "admission": "enabled" if allow_submissions else "paused",
                    "continuation": "recover_saved_ids_before_any_new_submission",
                }
            if report["status"] == "recovery_check_deferred":
                consecutive_check_errors += 1
                report["consecutive_check_errors"] = consecutive_check_errors
                report["next_retry_seconds"] = recovery_retry_delay(
                    args.poll_seconds, consecutive_check_errors
                )
                if consecutive_check_errors >= 5:
                    report["status"] = "attention"
                    report["reason"] = (
                        "Five consecutive recovery checks failed; provider/network "
                        "access requires reconciliation"
                    )
            else:
                consecutive_check_errors = 0
            atomic_json(state / "status.json", report)
            print(json.dumps({k: v for k, v in report.items() if k != "recovery"}), flush=True)
            if report["status"] == "attention":
                raise SystemExit(1)
            if not args.watch or report["status"] == "media_downloaded_qa_pending":
                return
            time.sleep(float(report.get("next_retry_seconds") or args.poll_seconds))


if __name__ == "__main__":
    main()
