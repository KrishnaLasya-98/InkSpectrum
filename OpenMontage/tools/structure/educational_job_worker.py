"""Persistent file-queue worker for Railway educational-video jobs.

The worker deliberately invokes the existing agent-neutral CLI. It does not
reimplement pipeline stages or bypass approval/checkpoint policy. Jobs are
ordinary JSON files on the persistent Railway volume, so a restart never loses
the queue or its logs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from lib.paths import PROJECTS_DIR
from lib.production_runtime import atomic_json, run_logged


QUEUE_STATES = ("pending", "running", "completed", "attention", "failed")
ATTENTION_STATUSES = {"awaiting_human", "blocked", "needs_approval", "needs_input"}
SAFE_JOB_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")


@contextmanager
def queue_lock(root: Path):
    """Kernel lock is released on crashes; one active worker per queue volume."""
    with (root / ".worker.lock").open("a+b") as handle:
        if os.fstat(handle.fileno()).st_size == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        try:
            yield True
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def recover_interrupted(root: Path) -> None:
    """Caller owns queue lock. Never resubmit uncertain external work."""
    for running in (root / "running").glob("*.json"):
        atomic_json(root / "attention" / f"{running.stem}.result.json", {
            "returncode": 1, "result": {"status": "recovery_required"},
            "stderr": "Worker interrupted. Reconcile provider job IDs and child processes before resuming; not resubmitted.",
            "finished_at": time.time(),
        })
        running.replace(root / "attention" / running.name)


def queue_root() -> Path:
    default = PROJECTS_DIR.parent / "jobs"
    return Path(os.environ.get("OPENMONTAGE_JOB_QUEUE_DIR") or default)


def input_root() -> Path:
    default = PROJECTS_DIR.parent / "inbox"
    return Path(os.environ.get("OPENMONTAGE_JOB_INPUT_DIR") or default)


def ensure_queue(root: Path | None = None) -> Path:
    root = root or queue_root()
    for state in QUEUE_STATES:
        (root / state).mkdir(parents=True, exist_ok=True)
    input_root().mkdir(parents=True, exist_ok=True)
    return root


def _safe_source(source: str, allowed_root: Path | None = None) -> Path:
    root = (allowed_root or input_root()).resolve()
    candidate = Path(source)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"source must be inside {root}") from exc
    if not resolved.is_file():
        raise ValueError(f"source does not exist: {resolved}")
    return resolved


def build_command(job: dict[str, Any], allowed_root: Path | None = None) -> list[str]:
    """Validate a queue job and build the canonical educational CLI command."""

    if job.get("approved") is not True:
        raise ValueError("job must contain approved=true")
    if job.get("command", "run") != "run":
        raise ValueError("only the educational CLI 'run' command is supported")
    source = _safe_source(str(job.get("source", "")), allowed_root)
    command = [
        sys.executable,
        "-m",
        "tools.structure.educational_agent_cli",
        "run",
        str(source),
    ]
    string_flags = {
        "project_id": "--project-id",
        "subject": "--subject",
        "title": "--title",
        "quality": "--quality",
        "delivery_root": "--delivery-root",
        "provider_config": "--provider-config",
    }
    integer_flags = {
        "grade": "--grade",
        "chapter": "--chapter",
        "book_part": "--book-part",
    }
    for key, flag in string_flags.items():
        value = job.get(key)
        if value is not None:
            command.extend((flag, str(value)))
    for key, flag in integer_flags.items():
        value = job.get(key)
        if value is not None:
            command.extend((flag, str(int(value))))
    if job.get("dry_run") is True:
        command.append("--dry-run")
    if job.get("full_run_preauthorized") is True:
        command.append("--full-run-preauthorized")
    return command


def enqueue(job: dict[str, Any], root: Path | None = None) -> Path:
    root = ensure_queue(root)
    job_id = str(job.get("id") or uuid.uuid4())
    if not SAFE_JOB_ID.fullmatch(job_id):
        raise ValueError("job id contains unsupported characters")
    payload = dict(job)
    payload["id"] = job_id
    # Validate before the atomic publish into pending/.
    build_command(payload)
    target = root / "pending" / f"{job_id}.json"
    if any((root / state / f"{job_id}.json").exists() for state in QUEUE_STATES):
        raise ValueError(f"job already exists: {job_id}")
    # Reserve identity independently of the long-held execution lock so API
    # clients can enqueue while rendering, but cannot publish duplicate IDs.
    identities = root / "identities"
    identities.mkdir(exist_ok=True)
    reservation = identities / job_id
    try:
        reservation.mkdir()
    except FileExistsError as exc:
        raise ValueError(f"job already exists: {job_id}") from exc
    try:
        atomic_json(target, payload)
    except BaseException:
        reservation.rmdir()
        raise
    return target


def _result_payload(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    parsed: Any = None
    try:
        parsed = json.loads(completed.stdout) if completed.stdout.strip() else None
    except json.JSONDecodeError:
        parsed = None
    return {
        "returncode": completed.returncode,
        "result": parsed,
        "stdout": completed.stdout[-100_000:],
        "stderr": completed.stderr[-100_000:],
        "finished_at": time.time(),
    }


def verify_encoded_completion(result: dict, job: dict) -> None:
    """A nonempty MP4 alone is not permission to advance to the next chapter."""
    video = Path(str(result.get("final_video") or ""))
    if not video.is_file() or video.stat().st_size == 0:
        raise ValueError("Final encoded video is missing")
    config = result.get("chapter_config")
    project = (Path(config).resolve().parent if config
               else PROJECTS_DIR / str(job.get("project_id") or ""))
    checkpoint = json.loads((project / "checkpoint_quality_assurance.json").read_text(encoding="utf-8"))
    if checkpoint.get("status") != "completed":
        raise ValueError("Encoded QA checkpoint is not complete")
    evidence = Path(checkpoint["metadata"]["evidence_dir"])
    review = json.loads((evidence / "final-review.json").read_text(encoding="utf-8"))
    if review.get("status") != "pass" or Path(review["output_path"]).resolve() != video.resolve():
        raise ValueError("Final review did not pass for this encoded video")
    metadata = review.get("metadata", {})
    sheets = metadata.get("contact_sheets_reviewed") or []
    if not sheets or any(not Path(path).is_file() for path in sheets):
        raise ValueError("Encoded visual review evidence is missing")
    comparison = json.loads(Path(metadata["encoded_comparison_ref"]).read_text(encoding="utf-8"))
    gates = comparison.get("gates") or {}
    if (comparison.get("automated_status") != "pass" or not gates
            or not all(value is True for value in gates.values())
            or Path(comparison["candidate"]).resolve() != video.resolve()):
        raise ValueError("Encoded textbook/reference comparison did not pass")
    digest = hashlib.sha256()
    with video.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != comparison["candidate_sha256"]:
        raise ValueError("Encoded video changed after QA")


def run_once(root: Path | None = None) -> bool:
    root = ensure_queue(root)
    with queue_lock(root) as acquired:
        if not acquired:
            return False
        recover_interrupted(root)
        # Sequential textbook production must not skip a failed or uncertain
        # earlier chapter just because another JSON file is pending.
        blockers = [p for state in ("attention", "failed")
                    for p in (root / state).glob("*.json")
                    if not p.name.endswith(".result.json")]
        if blockers:
            atomic_json(root / "worker_status.json", {
                "status": "attention", "reason": "Earlier job requires reconciliation",
                "blocking_jobs": [str(p) for p in blockers], "updated_at": time.time(),
            })
            return False
        return _run_claimed(root)


def _run_claimed(root: Path) -> bool:
    pending = next(iter(sorted((root / "pending").glob("*.json"))), None)
    if pending is None:
        return False
    running = root / "running" / pending.name
    try:
        pending.replace(running)
    except FileNotFoundError:
        return False

    try:
        job = json.loads(running.read_text(encoding="utf-8"))
        command = build_command(job)
        timeout = int(os.environ.get("OPENMONTAGE_JOB_TIMEOUT_SECONDS", "43200"))
        log_dir = root / "logs" / running.stem
        result_path = log_dir / f"result-{uuid.uuid4().hex}.json"
        environment = dict(os.environ, OPENMONTAGE_RESULT_PATH=str(result_path.resolve()))
        def heartbeat(pid):
            atomic_json(log_dir / "heartbeat.json", {
                "worker_pid": os.getpid(), "child_pid": pid, "updated_at": time.time(),
            })
        completed = run_logged(
            command,
            cwd=Path(__file__).resolve().parents[2],
            timeout=timeout,
            log_dir=log_dir, env=environment, heartbeat=heartbeat,
        )
        result = _result_payload(completed)
        # stdout is only a bounded diagnostic tail, never the result protocol.
        result["result"] = json.loads(result_path.read_text(encoding="utf-8")) if result_path.is_file() else None
        if not isinstance(result["result"], dict):
            result["result"] = None
        status = (result.get("result") or {}).get("status")
        if completed.returncode != 0:
            destination = "failed"
        elif status in ATTENTION_STATUSES:
            destination = "attention"
        elif status == "dry_run_complete" and job.get("dry_run") is True:
            destination = "completed"
        elif status == "completed" and not job.get("dry_run"):
            verify_encoded_completion(result["result"], job)
            destination = "completed"
        else:
            destination = "failed"
            result["stderr"] += "\nMissing or invalid explicit completion result"
    except Exception as exc:
        result = {
            "returncode": 1,
            "result": None,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
            "finished_at": time.time(),
        }
        destination = "failed"

    atomic_json(root / destination / f"{running.stem}.result.json", result)
    running.replace(root / destination / running.name)
    return True


def work_forever(poll_seconds: float = 5.0) -> None:
    ensure_queue()
    while True:
        if not run_once():
            time.sleep(max(0.2, poll_seconds))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="process at most one job")
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    args = parser.parse_args(argv)
    if args.once:
        run_once()
        return 0
    work_forever(args.poll_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
