"""InkSpectrum core runtime: config, checkpoint, pipeline loader, registry, cost tracking.

This package is the OpenMontage-style runtime shell. Python here provides
**tools and persistence only**; all creative decisions and orchestration live
in pipeline manifests (YAML) and skill files (Markdown).
"""

from __future__ import annotations

__version__ = "0.1.0"
