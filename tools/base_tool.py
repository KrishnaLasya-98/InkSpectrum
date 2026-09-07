"""BaseTool abstract contract. Every tool in InkSpectrum inherits this.

Mirrors OpenMontage `tools/base_tool.py`. Each tool declares:
- identity (name, version)
- capability routing (tier, capability, provider, runtime, stability)
- cost model (estimated_cost_usd)
- dependencies (binaries, env vars, packages)
- availability check (is_available)
- execution (run with input dict, return output dict)
"""

from __future__ import annotations

import logging
import os
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ToolTier(str, Enum):
    CORE = "core"
    VOICE = "voice"
    ENHANCE = "enhance"
    GENERATE = "generate"
    SOURCE = "source"
    ANALYZE = "analyze"
    PUBLISH = "publish"


class ToolRuntime(str, Enum):
    LOCAL = "local"
    LOCAL_GPU = "local_gpu"
    API = "api"
    HYBRID = "hybrid"


class ToolStability(str, Enum):
    EXPERIMENTAL = "experimental"
    BETA = "beta"
    PRODUCTION = "production"


@dataclass
class ToolMetadata:
    """Identity and routing metadata for a tool."""

    name: str
    version: str
    tier: ToolTier
    capability: str
    provider: str
    runtime: ToolRuntime
    stability: ToolStability
    estimated_cost_usd: float = 0.0
    description: str = ""
    dependencies: list[str] = field(default_factory=list)


class BaseTool(ABC):
    """Abstract base for every InkSpectrum tool."""

    metadata: ToolMetadata

    @abstractmethod
    def run(self, input: dict[str, Any]) -> dict[str, Any]:
        """Execute the tool. Must return a JSON-serializable dict."""
        raise NotImplementedError

    def is_available(self) -> tuple[bool, list[str]]:
        """Check binary / env / package dependencies. Returns (ok, missing[])."""
        missing: list[str] = []
        for dep in self.metadata.dependencies:
            if dep.startswith("cmd:"):
                if shutil.which(dep[4:]) is None:
                    missing.append(dep)
            elif dep.startswith("env:"):
                if not os.environ.get(dep[4:]):
                    missing.append(dep)
            elif dep.startswith("python:"):
                try:
                    __import__(dep[7:].split("==")[0].split(">=")[0].split("<=")[0])
                except ImportError:
                    missing.append(dep)
        return (not missing, missing)

    def describe(self) -> dict[str, Any]:
        ok, missing = self.is_available()
        return {
            "name": self.metadata.name,
            "version": self.metadata.version,
            "tier": self.metadata.tier.value,
            "capability": self.metadata.capability,
            "provider": self.metadata.provider,
            "runtime": self.metadata.runtime.value,
            "stability": self.metadata.stability.value,
            "estimated_cost_usd": self.metadata.estimated_cost_usd,
            "available": ok,
            "missing_dependencies": missing,
            "description": self.metadata.description,
        }
