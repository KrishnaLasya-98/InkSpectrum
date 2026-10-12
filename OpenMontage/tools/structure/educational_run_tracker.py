"""Backlot/checkpoint integration for educational-video productions.

The educational pipeline can be driven by a coding agent or by the compatibility
runner.  This module gives both paths the same durable state contract: project
markers, manifest-ordered checkpoints, approval gates, cost snapshots, and an
append-only Backlot event stream.
"""
from __future__ import annotations

import json
import hashlib
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

from lib.checkpoint import init_project, read_checkpoint, write_checkpoint
from lib.events import emit_event
from lib.pipeline_loader import (
    get_stage_human_approval_default,
    load_pipeline_readonly,
)


PIPELINE_TYPE = "educational-video"
DEFAULT_STAGE_ESTIMATES_SECONDS = {
    "input_ingestion": 90.0, "proposal": 20.0, "content_structuring": 180.0,
    "scene_plan": 45.0, "media_research": 90.0, "assets": 30.0,
    "voice_synthesis": 300.0, "text_audio_alignment": 180.0,
    "render_clips": 900.0, "multimedia_synchronization": 60.0,
    "composition": 900.0, "quality_assurance": 300.0,
}


def artifact_fingerprint(artifacts: dict[str, Any]) -> str:
    """Bind approval to the exact JSON artifact payload, not a stage name."""
    payload = json.dumps(artifacts, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class EducationalRunTracker:
    """Persist educational run state in the canonical Backlot format."""

    def __init__(
        self,
        project_dir: str | Path,
        *,
        title: str,
        approval_policy: str = "guided",
        style_playbook: str = "clean-professional",
    ) -> None:
        self.project_dir = Path(project_dir).resolve()
        self.pipeline_dir = self.project_dir.parent
        self.project_id = self.project_dir.name
        self.title = title
        self.approval_policy = approval_policy
        self.preauthorized = approval_policy == "full-run-preauthorized"
        self._approved_stages: dict[str, str] = {}
        self.checkpoint_policy = (
            "auto_noncreative" if self.preauthorized else "guided"
        )
        self.manifest = load_pipeline_readonly(PIPELINE_TYPE)
        init_project(
            self.project_id,
            title=title,
            pipeline_type=PIPELINE_TYPE,
            pipeline_dir=self.pipeline_dir,
            style_playbook=style_playbook,
        )

    def _gate_required(self, stage: str) -> bool:
        return bool(get_stage_human_approval_default(self.manifest, stage))

    def _approved_fingerprint(self, stage: str) -> str | None:
        if stage in self._approved_stages:
            return self._approved_stages[stage]
        try:
            checkpoint = read_checkpoint(self.pipeline_dir, self.project_id, stage)
        except Exception:
            return None
        if not checkpoint or not (checkpoint.get("human_approved") or
                                  checkpoint.get("status") == "in_progress"):
            return None
        fingerprint = (checkpoint.get("metadata") or {}).get("approved_artifact_sha256")
        if fingerprint != artifact_fingerprint(checkpoint.get("artifacts") or {}):
            return None
        return fingerprint

    def _invalidate_downstream(self, stage: str) -> None:
        """Conservatively invalidate dependent checkpoints, preserving their output."""
        names = [s["name"] for s in self.manifest["stages"]]
        for name in names[names.index(stage) + 1:]:
            self._approved_stages.pop(name, None)
            previous = read_checkpoint(self.pipeline_dir, self.project_id, name)
            if not previous:
                continue
            write_checkpoint(
                self.pipeline_dir, self.project_id, name, "failed",
                previous.get("artifacts") or {}, pipeline_type=PIPELINE_TYPE,
                checkpoint_policy=self.checkpoint_policy,
                error=f"Upstream stage {stage} restarted; outputs require rebuilding or revalidation.",
                metadata={"invalidated_by": stage, "previous_status": previous["status"]},
            )
            emit_event(self.project_dir, {"type": "pipeline_stage", "stage": name,
                       "status": "failed", "pipeline_type": PIPELINE_TYPE,
                       "invalidated_by": stage})

    def was_approved(self, stage: str, artifacts: dict[str, Any]) -> bool:
        """Only identical reviewed payloads may reuse a prior approval."""

        return self._approved_fingerprint(stage) == artifact_fingerprint(artifacts)

    def begin(
        self, stage: str, *, metadata: dict[str, Any] | None = None
    ) -> Path:
        # Preserve a prior explicit approval when a guided agent resumes and
        # re-enters the stage. The in-progress heartbeat intentionally
        # replaces the current checkpoint, so the approval must be captured
        # before that write occurs.
        fingerprint = self._approved_fingerprint(stage)
        if fingerprint:
            self._approved_stages[stage] = fingerprint
        previous = read_checkpoint(self.pipeline_dir, self.project_id, stage)
        stage_metadata = {**((previous or {}).get("metadata") or {}), **(metadata or {})}
        stage_metadata.pop("approved_artifact_sha256", None)
        if fingerprint:
            stage_metadata["approved_artifact_sha256"] = fingerprint
        stage_metadata["recovery_policy"] = "inspect-before-retry"
        stage_metadata["stage_started_at_unix"] = time.time()
        stage_metadata["estimated_duration_seconds"] = float(
            stage_metadata.get("estimated_duration_seconds")
            or DEFAULT_STAGE_ESTIMATES_SECONDS.get(stage, 60.0)
        )
        stage_metadata["attempt"] = int(((previous or {}).get("metadata") or {}).get("attempt", 0)) + 1
        emit_event(
            self.project_dir,
            {
                "type": "pipeline_stage",
                "stage": stage,
                "status": "in_progress",
                "pipeline_type": PIPELINE_TYPE,
            },
        )
        path = write_checkpoint(
            self.pipeline_dir,
            self.project_id,
            stage,
            "in_progress",
            (previous or {}).get("artifacts") or {},
            pipeline_type=PIPELINE_TYPE,
            checkpoint_policy=self.checkpoint_policy,
            metadata=stage_metadata,
        )
        write_status_json(self.project_dir)
        return path

    def progress(self, stage: str, *, partial_progress: dict[str, Any]) -> Path:
        """Persist resumable item IDs/job handles without approving partial output.

        Store provider job identifiers, never credentials. The caller must query
        existing jobs before submitting replacements after an interruption.
        """
        previous = read_checkpoint(self.pipeline_dir, self.project_id, stage)
        if not previous or previous.get("status") != "in_progress":
            raise ValueError("Partial progress requires an in-progress stage")
        path = write_checkpoint(
            self.pipeline_dir, self.project_id, stage, "in_progress",
            previous.get("artifacts") or {}, pipeline_type=PIPELINE_TYPE,
            checkpoint_policy=self.checkpoint_policy,
            metadata={**(previous.get("metadata") or {}),
                      "partial_progress": partial_progress},
        )
        write_status_json(self.project_dir)
        return path

    def finish(
        self,
        stage: str,
        artifacts: dict[str, Any],
        *,
        metadata: dict[str, Any] | None = None,
        review: dict[str, Any] | None = None,
        total_spent_usd: float = 0.0,
    ) -> str:
        gate_required = self._gate_required(stage)
        artifacts = deepcopy(artifacts)
        # Match checkpoint writer normalization before binding approval hashes.
        if isinstance(artifacts.get("decision_log"), dict):
            ref = str(self.project_dir / "decision_log.json")
            proposal = artifacts.get("proposal_packet", {})
            if isinstance(proposal.get("production_plan"), dict):
                proposal["production_plan"]["decision_log_ref"] = ref
            if isinstance(artifacts.get("render_report"), dict):
                artifacts["render_report"]["decision_log_ref"] = ref
        fingerprint = artifact_fingerprint(artifacts)
        previous = read_checkpoint(self.pipeline_dir, self.project_id, stage)
        if previous and artifact_fingerprint(previous.get("artifacts") or {}) != fingerprint:
            self._invalidate_downstream(stage)
        approved = self.preauthorized or self.was_approved(stage, artifacts)
        status = "completed" if not gate_required or approved else "awaiting_human"
        human_approved = approved if gate_required else False
        stage_metadata = dict(metadata or {})
        started = float(((previous or {}).get("metadata") or {}).get("stage_started_at_unix") or time.time())
        estimated = float(((previous or {}).get("metadata") or {}).get("estimated_duration_seconds")
                          or DEFAULT_STAGE_ESTIMATES_SECONDS.get(stage, 60.0))
        elapsed = max(0.0, time.time() - started)
        stage_metadata["stage_started_at_unix"] = started
        stage_metadata["stage_duration_seconds"] = round(elapsed, 3)
        stage_metadata["estimated_duration_seconds"] = estimated
        stage_metadata["eta_accuracy_ratio"] = round(elapsed / estimated, 3) if estimated else None
        stage_metadata.pop("approved_artifact_sha256", None)
        stage_metadata["artifact_sha256"] = fingerprint
        if gate_required and approved:
            stage_metadata["approved_artifact_sha256"] = fingerprint
        if not approved:
            self._approved_stages.pop(stage, None)
        if gate_required:
            stage_metadata["approval_evidence"] = (
                "full-run-preauthorized"
                if self.preauthorized
                else "previous-approved-checkpoint"
                if approved
                else "awaiting-explicit-user-approval"
            )
        write_checkpoint(
            self.pipeline_dir,
            self.project_id,
            stage,
            status,
            artifacts,
            pipeline_type=PIPELINE_TYPE,
            checkpoint_policy=self.checkpoint_policy,
            human_approval_required=gate_required,
            human_approved=human_approved,
            review=review,
            cost_snapshot={
                "total_spent_usd": round(float(total_spent_usd), 4),
                "total_reserved_usd": 0.0,
                "budget_remaining_usd": round(max(0.0, float(
                    (self.manifest.get("orchestration") or {}).get("budget_default_usd", 0.0)
                ) - float(total_spent_usd)), 4),
            },
            metadata=stage_metadata,
        )
        emit_event(
            self.project_dir,
            {
                "type": "pipeline_stage",
                "stage": stage,
                "status": status,
                "pipeline_type": PIPELINE_TYPE,
                "human_approval_required": gate_required,
            },
        )
        write_status_json(self.project_dir)
        return status

    def fail(
        self,
        stage: str,
        error: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        self._approved_stages.pop(stage, None)
        previous = read_checkpoint(self.pipeline_dir, self.project_id, stage)
        self._invalidate_downstream(stage)
        emit_event(
            self.project_dir,
            {
                "type": "pipeline_stage",
                "stage": stage,
                "status": "failed",
                "pipeline_type": PIPELINE_TYPE,
                "error": error,
            },
        )
        path = write_checkpoint(
            self.pipeline_dir,
            self.project_id,
            stage,
            "failed",
            (previous or {}).get("artifacts") or {},
            pipeline_type=PIPELINE_TYPE,
            checkpoint_policy=self.checkpoint_policy,
            error=error,
            metadata={**{k: v for k, v in ((previous or {}).get("metadata") or {}).items()
                         if k != "approved_artifact_sha256"}, **(metadata or {})},
        )
        write_status_json(self.project_dir)
        return path


def approve_educational_stage(project_dir: str | Path, stage: str) -> Path:
    """Approve an awaiting educational stage without mutating its artifacts."""

    project = Path(project_dir).resolve()
    checkpoint = read_checkpoint(project.parent, project.name, stage)
    if not checkpoint:
        raise ValueError(f"No checkpoint exists for stage {stage!r}")
    if checkpoint.get("status") != "awaiting_human":
        raise ValueError(
            f"Stage {stage!r} is {checkpoint.get('status')!r}, not awaiting_human"
        )
    expected = (checkpoint.get("metadata") or {}).get("artifact_sha256")
    if expected and expected != artifact_fingerprint(checkpoint.get("artifacts") or {}):
        raise ValueError("Artifact payload changed after review was requested; rerun the stage before approval")
    path = write_checkpoint(
        project.parent,
        project.name,
        stage,
        "completed",
        dict(checkpoint.get("artifacts") or {}),
        pipeline_type=PIPELINE_TYPE,
        style_playbook=checkpoint.get("style_playbook"),
        checkpoint_policy=str(checkpoint.get("checkpoint_policy") or "guided"),
        human_approval_required=True,
        human_approved=True,
        review=checkpoint.get("review"),
        cost_snapshot=checkpoint.get("cost_snapshot"),
        metadata={
            **dict(checkpoint.get("metadata") or {}),
            "approval_evidence": "explicit-stage-approval",
            "approved_artifact_sha256": artifact_fingerprint(checkpoint.get("artifacts") or {}),
        },
    )
    emit_event(
        project,
        {
            "type": "pipeline_stage",
            "stage": stage,
            "status": "completed",
            "pipeline_type": PIPELINE_TYPE,
            "human_approved": True,
        },
    )
    write_status_json(project)
    return path


def migrate_legacy_educational_project(
    project_dir: str | Path,
    *,
    title: str | None = None,
) -> Path:
    """Add the canonical marker/layout to an existing educational workspace."""

    project = Path(project_dir).resolve()
    if not project.is_dir():
        raise ValueError(f"Project directory does not exist: {project}")
    marker_dir = init_project(
        project.name,
        title=title or project.name.replace("-", " ").title(),
        pipeline_type=PIPELINE_TYPE,
        pipeline_dir=project.parent,
        style_playbook="clean-professional",
    )
    emit_event(
        marker_dir,
        {
            "type": "project_migration",
            "pipeline_type": PIPELINE_TYPE,
            "status": "completed",
        },
    )
    return marker_dir / "project.json"


def checkpoint_summary(project_dir: str | Path) -> dict[str, Any]:
    """Return an agent-neutral status payload for CLI and external agents."""

    project = Path(project_dir).resolve()
    stages: list[dict[str, Any]] = []
    manifest = load_pipeline_readonly(PIPELINE_TYPE)
    blocked_by = None
    for stage in manifest.get("stages", []):
        name = str(stage["name"])
        try:
            checkpoint = read_checkpoint(project.parent, project.name, name)
        except Exception as exc:
            checkpoint = {"status": "invalid", "error": str(exc)}
        expected = ((checkpoint or {}).get("metadata") or {}).get("artifact_sha256")
        if expected and expected != artifact_fingerprint(checkpoint.get("artifacts") or {}):
            checkpoint = {**checkpoint, "status": "invalid", "human_approved": False,
                          "error": "Artifact content does not match its recorded fingerprint."}
        if checkpoint and checkpoint.get("human_approved"):
            approved_hash = (checkpoint.get("metadata") or {}).get("approved_artifact_sha256")
            if approved_hash != artifact_fingerprint(checkpoint.get("artifacts") or {}):
                checkpoint = {**checkpoint, "status": "invalid", "human_approved": False,
                              "error": "Approval is missing or does not match artifact content; rerun and review this stage."}
        if blocked_by and checkpoint and checkpoint.get("status") in {"completed", "awaiting_human"}:
            checkpoint = {**checkpoint, "status": "blocked", "human_approved": False,
                          "error": f"Waiting for upstream stage {blocked_by}; output is not currently usable."}
        if blocked_by is None and (not checkpoint or checkpoint.get("status") != "completed"):
            blocked_by = name
        stages.append(
            {
                "name": name,
                "status": checkpoint.get("status", "pending") if checkpoint else "pending",
                "human_approval_required": bool(
                    stage.get("human_approval_default", False)
                ),
                "human_approved": bool(
                    checkpoint and checkpoint.get("human_approved", False)
                ),
                "error": checkpoint.get("error") if checkpoint else None,
            }
        )
    return {
        "project_id": project.name,
        "pipeline_type": PIPELINE_TYPE,
        "project_dir": str(project),
        "stages": stages,
    }


def write_status_json(project_dir: str | Path) -> Path:
    project = Path(project_dir).resolve()
    path = project / "artifacts" / "agent_status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(checkpoint_summary(project), indent=2), encoding="utf-8"
    )
    return path
