"""Content fidelity and audit models."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ContentStage(str, Enum):
    """Pipeline stages for content tracking."""
    INGEST = "ingest"
    SCRIPT = "script"
    ASSET = "asset"
    COMPOSE = "compose"
    DELIVER = "deliver"


@dataclass
class ContentTrace:
    """Trace a single content element through the pipeline."""
    docling_ref: Dict[str, Any]
    section_id: str
    scene_id: str
    step_id: str
    stage: ContentStage
    content_hash: str
    voiceover_text: Optional[str] = None
    asset_path: Optional[Path] = None
    final_frame: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["stage"] = self.stage.value
        if self.asset_path:
            data["asset_path"] = str(self.asset_path)
        return data


class ContentManifest(BaseModel):
    """Complete content fidelity manifest for a chapter."""
    model_config = ConfigDict(extra="forbid")

    chapter_id: str
    total_elements: int = Field(ge=0)
    stages: Dict[str, int] = Field(default_factory=dict)
    missing_voiceover: List[str] = Field(default_factory=list)
    missing_assets: List[str] = Field(default_factory=list)
    orphan_assets: List[str] = Field(default_factory=list)
    fidelity_score: float = Field(ge=0.0, le=100.0, description="Percentage of content preserved")
    audit_timestamp: str = Field(default_factory=lambda: __import__("datetime").datetime.utcnow().isoformat())
    passes_qa: bool = Field(default=False, description="True if fidelity_score >= 99.0 and no gaps")


class ContentRegistry:
    """Tracks all content from PDF ingestion to final video delivery."""

    def __init__(self, chapter_id: str, output_dir: Path):
        self.chapter_id = chapter_id
        self.output_dir = output_dir
        self.traces: List[ContentTrace] = []
        self._content_hash_index: Dict[str, ContentTrace] = {}

    def register_ingest(
        self,
        docling_ref: Dict[str, Any],
        section_id: str,
        content_text: str,
    ) -> str:
        """Register a PDF content element."""
        content_hash = hashlib.sha256(content_text.encode()).hexdigest()[:16]
        trace = ContentTrace(
            docling_ref=docling_ref,
            section_id=section_id,
            scene_id="",
            step_id="",
            stage=ContentStage.INGEST,
            content_hash=content_hash,
        )
        self.traces.append(trace)
        self._content_hash_index[content_hash] = trace
        return content_hash

    def register_script(
        self,
        content_hash: str,
        scene_id: str,
        step_id: str,
        voiceover_text: str,
    ) -> None:
        """Link content to script scene and voiceover."""
        trace = self._content_hash_index.get(content_hash)
        if not trace:
            logger.warning(f"Content hash {content_hash} not found in registry")
            return
        trace.scene_id = scene_id
        trace.step_id = step_id
        trace.voiceover_text = voiceover_text
        trace.stage = ContentStage.SCRIPT

    def register_asset(self, content_hash: str, asset_path: Path) -> None:
        """Link content to generated asset."""
        trace = self._content_hash_index.get(content_hash)
        if not trace:
            logger.warning(f"Content hash {content_hash} not found in registry")
            return
        trace.asset_path = asset_path
        trace.stage = ContentStage.ASSET

    def audit_fidelity(self) -> ContentManifest:
        """Run QA audit: check for missing content at each stage."""
        report = {
            "total_elements": len(self.traces),
            "stages": {},
            "missing_voiceover": [],
            "missing_assets": [],
            "orphan_assets": [],
        }

        for stage in ContentStage:
            stage_traces = [t for t in self.traces if t.stage == stage]
            report["stages"][stage.value] = len(stage_traces)

        for trace in self.traces:
            if trace.stage in (ContentStage.SCRIPT, ContentStage.ASSET, ContentStage.COMPOSE):
                if not trace.voiceover_text:
                    report["missing_voiceover"].append(trace.content_hash)
                if not trace.asset_path:
                    report["missing_assets"].append(trace.content_hash)

        total = len(self.traces)
        missing = len(report["missing_voiceover"]) + len(report["missing_assets"])
        fidelity_score = ((total - missing) / total * 100.0) if total > 0 else 100.0

        return ContentManifest(
            chapter_id=self.chapter_id,
            total_elements=total,
            stages=report["stages"],
            missing_voiceover=report["missing_voiceover"],
            missing_assets=report["missing_assets"],
            orphan_assets=report["orphan_assets"],
            fidelity_score=fidelity_score,
            passes_qa=fidelity_score >= 99.0 and not report["missing_voiceover"] and not report["missing_assets"],
        )

    def save(self) -> Path:
        """Persist registry to JSON."""
        output_path = self.output_dir / f"{self.chapter_id}_content_registry.json"
        manifest = self.audit_fidelity()
        data = {
            "chapter_id": self.chapter_id,
            "traces": [t.to_dict() for t in self.traces],
            "audit": manifest.model_dump(mode="json"),
        }
        output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        return output_path
