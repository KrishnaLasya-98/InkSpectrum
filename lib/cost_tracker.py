"""Budget tracker. Reserves cost before a tool call, reconciles after.

Prevents surprise API bills. The agent cannot silently overspend.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class BudgetLedger:
    """Per-pipeline-run cost ledger."""

    pipeline_id: str
    run_id: str
    cap_usd: float
    per_stage_caps: dict[str, float] = field(default_factory=dict)
    reserved: float = 0.0
    spent: float = 0.0
    by_stage: dict[str, float] = field(default_factory=dict)
    by_tool: dict[str, float] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def reserve(self, amount_usd: float, tool: str, stage: str) -> bool:
        """Try to reserve a budget for a tool call. Returns False if it would exceed cap."""
        with self._lock:
            stage_cap = self.per_stage_caps.get(stage, self.cap_usd)
            projected_stage = self.by_stage.get(stage, 0.0) + amount_usd
            projected_total = self.spent + self.reserved + amount_usd
            if projected_stage > stage_cap:
                logger.warning(
                    "Budget denied (stage %s cap %.4f < %.4f)",
                    stage, stage_cap, projected_stage,
                )
                return False
            if projected_total > self.cap_usd:
                logger.warning(
                    "Budget denied (pipeline cap %.4f < %.4f)",
                    self.cap_usd, projected_total,
                )
                return False
            self.reserved += amount_usd
            return True

    def commit(self, estimated_usd: float, actual_usd: float, tool: str, stage: str) -> None:
        """Reconcile estimated vs actual cost after a tool call returns."""
        with self._lock:
            self.reserved = max(0.0, self.reserved - estimated_usd)
            self.spent += actual_usd
            self.by_stage[stage] = self.by_stage.get(stage, 0.0) + actual_usd
            self.by_tool[tool] = self.by_tool.get(tool, 0.0) + actual_usd

    def release(self, estimated_usd: float) -> None:
        """Release a reservation when a call fails before charging."""
        with self._lock:
            self.reserved = max(0.0, self.reserved - estimated_usd)

    def snapshot(self) -> dict:
        return {
            "pipeline_id": self.pipeline_id,
            "run_id": self.run_id,
            "cap_usd": self.cap_usd,
            "reserved_usd": round(self.reserved, 6),
            "spent_usd": round(self.spent, 6),
            "remaining_usd": round(self.cap_usd - self.spent - self.reserved, 6),
            "by_stage": {k: round(v, 6) for k, v in self.by_stage.items()},
            "by_tool": {k: round(v, 6) for k, v in self.by_tool.items()},
        }


# Module-level registry: pipeline_id+run_id -> BudgetLedger
_LEDGERS: dict[str, BudgetLedger] = {}
_LEDGER_LOCK = threading.Lock()


def get_ledger(pipeline_id: str, run_id: str, cap_usd: float) -> BudgetLedger:
    key = f"{pipeline_id}:{run_id}"
    with _LEDGER_LOCK:
        if key not in _LEDGERS:
            _LEDGERS[key] = BudgetLedger(pipeline_id=pipeline_id, run_id=run_id, cap_usd=cap_usd)
        return _LEDGERS[key]
