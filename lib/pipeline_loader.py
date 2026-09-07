"""YAML pipeline manifest loader with Pydantic validation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class StageSpec(BaseModel):
    name: str
    skill: str
    produces: list[str] = Field(default_factory=list)
    tools_available: list[str] = Field(default_factory=list)
    checkpoint_required: bool = True
    human_approval_default: bool = False
    review_focus: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)


class PipelineManifest(BaseModel):
    name: str
    category: str = "generated"
    description: str = ""
    mode: str = "executive-producer"
    skill: str = ""
    budget_default_usd: float = 2.00
    max_revisions_per_stage: int = 3
    compatible_playbooks: list[str] = Field(default_factory=list)
    stages: list[StageSpec]

    def stage(self, name: str) -> StageSpec:
        for s in self.stages:
            if s.name == name:
                return s
        raise KeyError(f"Stage not found: {name}")


def load_manifest(path: Path | str) -> PipelineManifest:
    """Load and validate a YAML pipeline manifest."""
    p = Path(path)
    data: dict[str, Any] = yaml.safe_load(p.read_text(encoding="utf-8"))
    return PipelineManifest.model_validate(data)
