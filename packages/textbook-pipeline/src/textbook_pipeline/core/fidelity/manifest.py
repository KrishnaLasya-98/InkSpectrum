"""Content manifest builder for export."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from textbook_pipeline.models.fidelity import ContentRegistry

logger = logging.getLogger(__name__)


class ContentManifestBuilder:
    """Builds machine-readable and human-readable content manifests."""

    def __init__(self, registry: ContentRegistry):
        self.registry = registry

    def build_json_manifest(self) -> Dict[str, Any]:
        """Build a JSON-serializable manifest."""
        return {
            "chapter_id": self.registry.chapter_id,
            "generated_at": datetime.utcnow().isoformat(),
            "total_elements": len(self.registry.traces),
            "traces": [trace.to_dict() for trace in self.registry.traces],
        }

    def build_human_readable(self) -> str:
        """Build a human-readable Markdown manifest."""
        lines = [
            f"# Content Manifest: {self.registry.chapter_id}",
            f"Generated: {datetime.utcnow().isoformat()}",
            "",
            f"**Total Elements:** {len(self.registry.traces)}",
            "",
            "## Element Traces",
            "",
        ]

        for trace in self.registry.traces:
            lines.append(f"### {trace.content_hash}")
            lines.append(f"- **Section:** {trace.section_id}")
            lines.append(f"- **Scene:** {trace.scene_id or 'pending'}")
            lines.append(f"- **Step:** {trace.step_id or 'pending'}")
            lines.append(f"- **Stage:** {trace.stage.value}")
            if trace.voiceover_text:
                lines.append(f"- **Voiceover:** {trace.voiceover_text[:80]}...")
            if trace.asset_path:
                lines.append(f"- **Asset:** {trace.asset_path}")
            lines.append("")

        return "\n".join(lines)

    def save(self, output_dir: Path, format: str = "both") -> Dict[str, Path]:
        """Save manifest in requested format(s)."""
        output_dir.mkdir(parents=True, exist_ok=True)
        saved_paths = {}

        if format in ("json", "both"):
            json_path = output_dir / f"{self.registry.chapter_id}_manifest.json"
            json_path.write_text(json.dumps(self.build_json_manifest(), indent=2, ensure_ascii=False))
            saved_paths["json"] = json_path

        if format in ("markdown", "both"):
            md_path = output_dir / f"{self.registry.chapter_id}_manifest.md"
            md_path.write_text(self.build_human_readable(), encoding="utf-8")
            saved_paths["markdown"] = md_path

        return saved_paths