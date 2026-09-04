"""Content auditor for pipeline QA checks."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from textbook_pipeline.models.fidelity import ContentRegistry

logger = logging.getLogger(__name__)


class ContentAuditor:
    """Runs QA checks on ContentRegistry to ensure fidelity."""

    def __init__(self, registry: ContentRegistry):
        self.registry = registry

    def check_missing_voiceover(self) -> List[str]:
        missing = []
        for trace in self.registry.traces:
            if trace.stage.value in ("script", "asset", "compose"):
                if not trace.voiceover_text:
                    missing.append(trace.content_hash)
        return missing

    def check_missing_assets(self) -> List[str]:
        missing = []
        for trace in self.registry.traces:
            if trace.stage.value in ("script", "asset", "compose"):
                if not trace.asset_path:
                    missing.append(trace.content_hash)
        return missing

    def check_orphan_assets(self, asset_dir: Path) -> List[str]:
        if not asset_dir.exists():
            return []

        referenced = {str(trace.asset_path) for trace in self.registry.traces if trace.asset_path}
        orphaned = []

        for ext in ("*.png", "*.jpg", "*.jpeg", "*.mp4", "*.wav", "*.mp3"):
            for asset_path in asset_dir.rglob(ext):
                if str(asset_path) not in referenced:
                    orphaned.append(str(asset_path))

        return orphaned

    def run_full_audit(self, asset_dir: Optional[Path] = None) -> Dict[str, Any]:
        report = {
            "total_elements": len(self.registry.traces),
            "missing_voiceover": self.check_missing_voiceover(),
            "missing_assets": self.check_missing_assets(),
            "orphan_assets": self.check_orphan_assets(asset_dir or Path(".")),
            "passes_qa": True,
        }

        critical_issues = (
            len(report["missing_voiceover"]) +
            len(report["missing_assets"])
        )
        report["passes_qa"] = critical_issues == 0

        if not report["passes_qa"]:
            logger.warning(f"QA audit failed: {critical_issues} issues found")

        return report
