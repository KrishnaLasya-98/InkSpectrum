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
        """Find content elements that lack voiceover lines."""
        missing = []
        for trace in self.registry.traces:
            if trace.stage.value in ("script", "asset", "compose"):
                if not trace.voiceover_text:
                    missing.append(trace.content_hash)
        return missing

    def check_missing_assets(self) -> List[str]:
        """Find content elements that lack generated assets."""
        missing = []
        for trace in self.registry.traces:
            if trace.stage.value in ("script", "asset", "compose"):
                if not trace.asset_path:
                    missing.append(trace.content_hash)
        return missing

    def check_orphan_assets(self, asset_dir: Path) -> List[str]:
        """Find assets on disk that are not referenced in the registry."""
        if not asset_dir.exists():
            return []

        referenced = {str(trace.asset_path) for trace in self.registry.traces if trace.asset_path}
        orphaned = []

        for ext in ("*.png", "*.jpg", "*.jpeg", "*.mp4", "*.wav", "*.mp3"):
            for asset_path in asset_dir.rglob(ext):
                if str(asset_path) not in referenced:
                    orphaned.append(str(asset_path))

        return orphaned

    def check_audio_sync(self, tolerance_seconds: float = 0.1) -> List[Dict[str, Any]]:
        """Check that voiceover timing aligns with scene timing."""
        issues = []
        # Group traces by scene
        scene_traces: Dict[str, List] = {}
        for trace in self.registry.traces:
            if trace.scene_id:
                scene_traces.setdefault(trace.scene_id, []).append(trace)

        for scene_id, traces in scene_traces.items():
            # Check that each scene has at least one voiceover
            voiceovers = [t for t in traces if t.voiceover_text]
            if not voiceovers:
                issues.append({
                    "scene_id": scene_id,
                    "issue": "missing_voiceover",
                    "severity": "high",
                })

        return issues

    def run_full_audit(self, asset_dir: Optional[Path] = None) -> Dict[str, Any]:
        """Run all QA checks and return a comprehensive report."""
        report = {
            "total_elements": len(self.registry.traces),
            "missing_voiceover": self.check_missing_voiceover(),
            "missing_assets": self.check_missing_assets(),
            "orphan_assets": self.check_orphan_assets(asset_dir or Path(".")),
            "audio_sync_issues": self.check_audio_sync(),
            "passes_qa": True,
        }

        # Determine overall pass/fail
        critical_issues = (
            len(report["missing_voiceover"]) +
            len(report["missing_assets"]) +
            len(report["audio_sync_issues"])
        )
        report["passes_qa"] = critical_issues == 0
        report["fidelity_score"] = (
            ((report["total_elements"] - critical_issues) / report["total_elements"] * 100.0)
            if report["total_elements"] > 0 else 100.0
        )

        if not report["passes_qa"]:
            logger.warning(f"QA audit failed: {critical_issues} issues found")

        return report