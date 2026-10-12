"""Check one approved ModelsLab batch once and recover completed clips.

Never submits new video jobs. Preserve uncertain provider outcomes for the next
scheduled check rather than retrying generation. Credentials stay in .env.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

from lib.production_runtime import atomic_json
from tools.video.modelslab_video import ModelsLabVideo


def terminal_disposition(state: dict, payload: dict, *, now: float | None = None) -> tuple[str, dict]:
    """Require repeated confirmation for a previously tracked 'not found' job."""
    observed = str(payload.get("status") or "unknown").lower()
    message = str(payload.get("message") or payload.get("error") or "")
    timestamp = float(now if now is not None else time.time())
    if observed not in {"failed", "error", "cancelled", "canceled"}:
        return observed, state
    not_found = "not found" in message.casefold() or "does not exist" in message.casefold()
    if not not_found:
        return "terminal_failed", {
            **state, "status": "terminal_failed", "provider_status": observed,
            "failed_at_unix": timestamp,
        }
    suspect = dict(state.get("suspect_terminal") or {})
    first = float(suspect.get("first_seen_unix") or timestamp)
    count = int(suspect.get("confirmation_count") or 0) + 1
    updated = {
        **state, "status": "suspect_terminal",
        "suspect_terminal": {
            "reason": "provider_request_not_found", "first_seen_unix": first,
            "last_seen_unix": timestamp, "confirmation_count": count,
        },
    }
    # A missing-history response is not terminal on first sight. Preserve its
    # active reservation through three confirmations spanning at least 10 min.
    if count >= 3 and timestamp - first >= 600:
        updated.update(status="terminal_failed", provider_status=observed,
                       failed_at_unix=timestamp, terminal_confirmation_count=count)
        return "terminal_failed", updated
    return "suspect_terminal", updated


def recover(project: Path, batch_path: Path) -> dict:
    project = project.resolve()
    batch_path = batch_path.resolve()
    if not batch_path.is_relative_to(project):
        raise ValueError("Batch must be inside the chapter project")
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    key = os.environ.get("MODELSLAB_API_KEY")
    if not key:
        raise RuntimeError("MODELSLAB_API_KEY must be set locally")
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    output_dir = project / "assets" / "video" / batch_path.stem
    rows = []
    for shot in batch["shots"]:
        output = output_dir / f"{shot['shot_id']}.mp4"
        sidecar = Path(str(output) + ".modelslab-job.json")
        row = {"shot_id": shot["shot_id"], "output_path": str(output),
               "new_submission": False}
        if output.is_file() and output.stat().st_size > 0:
            row["status"] = "downloaded"
        elif not sidecar.is_file():
            row["status"] = "not_submitted"
        else:
            state = json.loads(sidecar.read_text(encoding="utf-8"))
            request_id = str(state.get("request_id") or "")
            endpoint = state.get("poll_endpoint")
            if (state.get("provider") != "modelslab" or not request_id.isdigit()
                    or endpoint not in {"video", "video-fusion"}):
                row["status"] = "invalid_sidecar"
            elif state.get("status") == "terminal_failed":
                row["status"] = "terminal_failed"
            else:
                row["request_id"] = request_id
                version = "v6" if endpoint == "video" else "v7"
                try:
                    response = requests.post(
                        f"https://modelslab.com/api/{version}/{endpoint}/fetch/{request_id}",
                        json={"key": key}, timeout=(10, 30),
                    )
                    row["http_status"] = response.status_code
                    response.raise_for_status()
                    payload = response.json()
                    row["status"] = str(payload.get("status") or "unknown")
                    if row["status"] in {"failed", "error", "cancelled", "canceled"}:
                        row["status"], durable = terminal_disposition(state, payload)
                        atomic_json(sidecar, durable)
                    if row["status"] == "success":
                        result = ModelsLabVideo().execute({
                            "resume_request_id": request_id,
                            "model_id": state["model_id"],
                            "operation": state["operation"],
                            "poll_endpoint": endpoint,
                            "generate_audio": False, "educational_mode": True,
                            "output_path": str(output), "job_state_path": str(sidecar),
                        })
                        row["status"] = "recovered" if result.success and output.is_file() else "recovery_error"
                        row["output_bytes"] = output.stat().st_size if output.is_file() else 0
                        if not result.success:
                            row["error"] = result.error
                except (requests.RequestException, ValueError, KeyError) as exc:
                    row["status"] = "check_error"
                    row["error_type"] = type(exc).__name__
        rows.append(row)
    report = {
        "version": "1.0", "checked_at": datetime.now(timezone.utc).isoformat(),
        "batch": str(batch_path), "new_submissions": 0, "jobs": rows,
        "downloaded": sum(r["status"] in {"downloaded", "recovered"} for r in rows),
        "total": len(rows),
    }
    atomic_json(batch_path.with_name(batch_path.stem + "-recovery.json"), report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--batch", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(recover(args.project, args.batch), indent=2))


if __name__ == "__main__":
    main()
