"""Textbook-to-Video Pipeline.

A multimodal system that converts educational PDFs into high-quality
video lessons with 100% content fidelity.
"""

from __future__ import annotations

__version__ = "0.1.0"

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("textbook-pipeline")
except PackageNotFoundError:
    pass


def get_version() -> str:
    """Return the package version."""
    return __version__
