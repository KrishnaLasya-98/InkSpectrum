"""Pipeline state persistence and stage transitions.

Every stage of every pipeline writes a JSON checkpoint under
`.kilo/checkpoints/<pipeline_id>/<run_id>/<stage>.json`. The presence
of a checkpoint means the stage succeeded and is resumable.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class Checkpoint:
    """A single stage checkpoint."""

    def __init__(
        self,
        pipeline_id: str,
        run_id: str,
        stage: str,
        artifacts: list[str] | None = None,
        cost_usd: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ):
        self.pipeline_id = pipeline_id
        self.run_id = run_id
        self.stage = stage
        self.artifacts = artifacts or []
        self.cost_usd = cost_usd
        self.metadata = metadata or {}
        self.timestamp = time.time()
        self.status = "completed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "run_id": self.run_id,
            "stage": self.stage,
            "artifacts": self.artifacts,
            "cost_usd": self.cost_usd,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "status": self.status,
        }


class CheckpointStore:
    """Filesystem-backed checkpoint store with resume support."""

    def __init__(self, root: Path | str = ".kilo/checkpoints"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, pipeline_id: str, run_id: str, stage: str) -> Path:
        return self.root / pipeline_id / run_id / f"{stage}.json"

    def _run_dir(self, pipeline_id: str, run_id: str) -> Path:
        d = self.root / pipeline_id / run_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write(self, checkpoint: Checkpoint) -> Path:
        path = self._path(checkpoint.pipeline_id, checkpoint.run_id, checkpoint.stage)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(checkpoint.to_dict(), indent=2), encoding="utf-8")
        logger.info("Checkpoint written: %s", path)
        return path

    def has_stage(self, pipeline_id: str, run_id: str, stage: str) -> bool:
        return self._path(pipeline_id, run_id, stage).exists()

    def read(self, pipeline_id: str, run_id: str, stage: str) -> Checkpoint | None:
        p = self._path(pipeline_id, run_id, stage)
        if not p.exists():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        cp = Checkpoint(
            pipeline_id=data["pipeline_id"],
            run_id=data["run_id"],
            stage=data["stage"],
            artifacts=data.get("artifacts", []),
            cost_usd=data.get("cost_usd", 0.0),
            metadata=data.get("metadata", {}),
        )
        cp.timestamp = data.get("timestamp", 0.0)
        cp.status = data.get("status", "completed")
        return cp

    def completed_stages(self, pipeline_id: str, run_id: str) -> list[str]:
        d = self.root / pipeline_id / run_id
        if not d.exists():
            return []
        return sorted(p.stem for p in d.glob("*.json"))


def new_run_id() -> str:
    """Generate a short unique run id."""
    return f"{int(time.time())}-{uuid.uuid4().hex[:6]}"
