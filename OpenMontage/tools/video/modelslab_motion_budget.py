"""Conservative shared-account admission for durable video submissions.

Reservations precede HTTP calls: an interrupted/unknown submission is never
silently repeated. Use the same state directory and projects root for every
worker sharing an API account. Provider caps/other clients remain authoritative.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
from contextlib import contextmanager
from pathlib import Path

from lib.paths import PROJECTS_DIR, REPO_ROOT
from lib.production_runtime import atomic_json


class MotionBudget:
    def __init__(self, state_dir=None, projects_dir=None, clock=time.time):
        self.root = Path(state_dir or os.environ.get("OPENMONTAGE_MODELSLAB_STATE_DIR")
                         or REPO_ROOT / "work" / "modelslab-motion-budget")
        self.projects = Path(projects_dir or PROJECTS_DIR)
        self.clock = clock
        self.root.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def locked(self):
        with (self.root / ".admission.lock").open("a+b") as handle:
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

    def _entries(self):
        entries = {}
        # Sidecar updates may race polling, but these are atomic writes.
        for path in self.projects.rglob("*.modelslab-job.json"):
            state = json.loads(path.read_text(encoding="utf-8"))
            if state.get("provider") != "modelslab":
                continue
            output = str(Path(state.get("output_path") or str(path)[:-len(".modelslab-job.json")]).resolve())
            state["submitted_at_unix"] = state.get("submitted_at_unix", path.stat().st_mtime)
            entries[output] = state
        for path in (self.root / "reservations").glob("*.json"):
            state = json.loads(path.read_text(encoding="utf-8"))
            output = state["output_path"]
            # A recovered provider handle replaces the uncertain reservation.
            if output not in entries:
                entries[output] = state
        return entries

    def snapshot(self):
        now = self.clock()
        entries = self._entries()
        active = sum(row.get("status") not in {"success", "terminal_failed"}
                     for row in entries.values())
        ages = [now - float(row["submitted_at_unix"]) for row in entries.values()]
        half = sum(age < 1800 for age in ages)
        hour = sum(age < 3600 for age in ages)
        waits = []
        if half >= 18:
            waits.append(sorted(1800 - age for age in ages if age < 1800)[half - 18])
        if hour >= 35:
            waits.append(sorted(3600 - age for age in ages if age < 3600)[hour - 35])
        provider_wait = 0
        throttle = self.root / "provider-throttle.json"
        if throttle.is_file():
            provider_state = json.loads(throttle.read_text(encoding="utf-8"))
            provider_wait = max(0, math.ceil(float(provider_state.get("not_before_unix", 0)) - now))
            if provider_wait:
                waits.append(provider_wait)
        available = max(0, min(15 - active, 18 - half, 35 - hour))
        if provider_wait:
            available = 0
        return {"active": active, "started_last_30_minutes": half,
                "started_last_hour": hour,
                "available": available,
                "retry_after_seconds": max(1, math.ceil(max(waits, default=30))),
                "provider_retry_after_seconds": provider_wait,
                "limits": {"active": 15, "per_30_minutes": 18, "per_hour": 35}}

    def reserve(self, output: Path):
        """Caller holds account lock. Returns None when work must wait."""
        output = output.resolve()
        identity = hashlib.sha256(str(output).encode()).hexdigest()
        path = self.root / "reservations" / f"{identity}.json"
        if path.exists():
            raise RuntimeError("Submission reservation already exists; recover/reconcile it, do not resubmit")
        if self.snapshot()["available"] == 0:
            return None
        atomic_json(path, {"provider": "modelslab", "status": "submission_unknown",
                           "output_path": str(output), "submitted_at_unix": self.clock()})
        return path

    def acknowledge(self, reservation: Path, request_id):
        state = json.loads(reservation.read_text(encoding="utf-8"))
        state.update(status="submitted", request_id=request_id)
        atomic_json(reservation, state)
