"""Secure path resolution and containment checks."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Union


class PathSecurityError(ValueError):
    """Raised when a path fails security containment checks."""


def secure_resolve(path: Union[str, Path], base_dir: Path) -> Path:
    """Resolve path and verify it's within base_dir.

    Uses os.path.realpath() to resolve symlinks before containment check.
    This prevents symlink-based path traversal attacks.

    Args:
        path: User-provided path
        base_dir: Trusted base directory for containment

    Returns:
        Resolved absolute path

    Raises:
        PathSecurityError: If path is outside base_dir
    """
    resolved = Path(os.path.realpath(path))
    base = Path(os.path.realpath(base_dir))

    try:
        resolved.relative_to(base)
    except ValueError:
        raise PathSecurityError(
            f"Path {path} resolves to {resolved}, which is outside "
            f"allowed directory {base}"
        )

    return resolved


def validate_pdf_path(path: Path) -> Path:
    """Validate that a path is a readable PDF file."""
    resolved = path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    if not resolved.is_file():
        raise ValueError(f"Not a file: {path}")
    if resolved.suffix.lower() != ".pdf":
        raise ValueError(f"Not a PDF file: {path}")
    return resolved


def ensure_absolute(path: Union[str, Path]) -> Path:
    """Ensure path is absolute, resolving relative to cwd."""
    return Path(path).resolve()
