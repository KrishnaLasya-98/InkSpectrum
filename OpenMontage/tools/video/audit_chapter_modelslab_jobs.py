"""Audit one chapter's ModelsLab jobs for duplicates, uncertainty and review state."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from tools.video.modelslab_motion_budget import MotionBudget


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def batch_number(path: Path) -> int:
    return int(path.stem.split("-")[2])


def collect_decisions(artifacts: Path) -> dict[tuple[int, str], str]:
    decisions: dict[tuple[int, str], str] = {}
    for path in sorted(artifacts.glob("motion-batch-*-review.json")):
        number = batch_number(path)
        for row in read(path).get("clips", []):
            value = str(row.get("visual_status", "")).lower()
            if value in {"pass", "accept", "accepted"}:
                decisions[(number, row["shot_id"])] = "accepted"
            elif value in {"reject", "rejected"}:
                decisions[(number, row["shot_id"])] = "rejected"
    for path in sorted(artifacts.glob("motion-batch-*-semantic-decisions.json")):
        number = batch_number(path)
        for row in read(path).get("decisions", []):
            value = str(row.get("status", "")).lower()
            if value in {"pass", "accept", "accepted"}:
                decisions[(number, row["shot_id"])] = "accepted"
            elif value in {"reject", "rejected"}:
                decisions[(number, row["shot_id"])] = "rejected"
    return decisions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    project = args.project.resolve()
    video = project / "assets/video"
    artifacts = project / "artifacts"
    output = (args.output or artifacts / "modelslab-job-audit-v1.json").resolve()

    planned: dict[tuple[int, str], dict] = {}
    never_submitted = []
    retirement_path = artifacts / "provider-target-retirement-v1.json"
    retirement = read(retirement_path) if retirement_path.is_file() else {}
    retired_rows = list(retirement.get("targets", []))
    retired = {(int(row["batch"]), row["shot_id"]): row for row in retired_rows}
    retired_batch_rules = list(retirement.get("batches", []))

    def retired_by_rule(number: int) -> dict | None:
        for rule in retired_batch_rules:
            if "batch" in rule and int(rule["batch"]) == number:
                return rule
            if int(rule.get("batch_start", -1)) <= number <= int(rule.get("batch_end", -1)):
                return rule
        return None
    for batch in sorted(video.glob("motion-batch-*.json")):
        if batch.stem.endswith(("-status", "-recovery")):
            continue
        try:
            number = int(batch.stem.rsplit("-", 1)[-1])
        except ValueError:
            continue
        for row in read(batch).get("shots", []):
            planned[(number, row["shot_id"])] = row
            target = video / batch.stem / f"{row['shot_id']}.mp4"
            if not target.is_file() and not Path(str(target) + ".modelslab-job.json").is_file():
                rule = retired_by_rule(number)
                if (number, row["shot_id"]) not in retired and rule is None:
                    never_submitted.append({"batch": number, "shot_id": row["shot_id"],
                                            "section_id": row.get("section_id")})
                elif rule is not None:
                    retired_rows.append({"batch": number, "shot_id": row["shot_id"],
                                         "section_id": row.get("section_id"),
                                         "reason": rule.get("reason", "retired batch target")})

    decisions = collect_decisions(artifacts)
    rows = []
    suffix = ".mp4.modelslab-job.json"
    for sidecar in sorted(video.glob("motion-batch-*/*.modelslab-job.json")):
        number = int(sidecar.parent.name.rsplit("-", 1)[-1])
        sid = sidecar.name[:-len(suffix)]
        state = read(sidecar)
        spec = planned.get((number, sid), {})
        target = Path(state.get("output_path") or str(sidecar)[:-len(".modelslab-job.json")])
        provider_status = str(state.get("status") or "")
        visual = decisions.get((number, sid), "unreviewed")
        if provider_status == "terminal_failed" and not target.is_file():
            visual = "provider_terminal_failed"
        rows.append({
            "batch": number,
            "shot_id": sid,
            "section_id": spec.get("section_id"),
            "request_id": str(state.get("request_id") or ""),
            "request_fingerprint": state.get("request_fingerprint"),
            "prompt_sha256": hashlib.sha256(str(spec.get("prompt") or "").strip().encode()).hexdigest(),
            "provider_status": provider_status,
            "output_path": str(target.resolve()),
            "output_exists": target.is_file() and target.stat().st_size > 0,
            "visual_review": visual,
        })

    def duplicates(field: str, skip_empty: bool = False) -> dict[str, list[str]]:
        groups: dict[str, list[str]] = defaultdict(list)
        for row in rows:
            value = str(row.get(field) or "")
            if skip_empty and not value:
                continue
            groups[value].append(row["shot_id"])
        return {key: value for key, value in groups.items() if len(value) > 1}

    duplicate_checks = {
        "request_ids": duplicates("request_id", True),
        "output_targets": duplicates("output_path"),
        "request_fingerprints": duplicates("request_fingerprint", True),
        "exact_prompt_hashes": duplicates("prompt_sha256", True),
    }
    uncertain = [row for row in rows if row["provider_status"] not in {"success", "terminal_failed"}
                 or (not row["output_exists"] and row["provider_status"] != "terminal_failed")]
    targets = {row["output_path"] for row in rows}
    reservation_only = []
    for path in (MotionBudget().root / "reservations").glob("*.json"):
        reservation = read(path)
        raw = reservation.get("output_path")
        if not raw:
            continue
        resolved = Path(raw).resolve()
        if resolved.is_relative_to(project) and str(resolved) not in targets:
            reservation_only.append(reservation)

    counts = Counter(row["visual_review"] for row in rows)
    blocked = any(duplicate_checks.values()) or bool(uncertain) or bool(reservation_only)
    report = {
        "version": "1.0",
        "status": "blocked" if blocked else "pass_no_duplicate_or_uncertain_submissions",
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "scope": str(project),
        "counts": {
            "provider_starts": len(rows),
            "unique_provider_request_ids": len({row["request_id"] for row in rows if row["request_id"]}),
            "durable_sidecars": len(rows),
            "downloaded_outputs": sum(row["output_exists"] for row in rows),
            "accepted_after_encoded_visual_review": counts["accepted"],
            "rejected_after_encoded_visual_review": counts["rejected"],
            "provider_terminal_failed_without_output": counts["provider_terminal_failed"],
            "unreviewed": counts["unreviewed"],
            "planned_not_submitted": len(never_submitted),
            "retired_before_submission": len(retired_rows),
            "currently_processing_or_uncertain": len(uncertain),
            "reservation_without_sidecar": len(reservation_only),
        },
        "duplicate_checks": duplicate_checks,
        "budget_snapshot": MotionBudget().snapshot(),
        "planned_not_submitted": never_submitted,
        "retired_before_submission": retired_rows,
        "uncertain": uncertain,
        "reservation_only": reservation_only,
        "submitted_jobs": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "counts": report["counts"],
                      "duplicate_checks": duplicate_checks, "budget_snapshot": report["budget_snapshot"]}, indent=2))


if __name__ == "__main__":
    main()
