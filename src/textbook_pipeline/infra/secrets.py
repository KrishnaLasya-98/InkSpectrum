"""Secrets management utilities."""

from __future__ import annotations

import os
from typing import Optional


def get_secret(name: str, required: bool = True) -> Optional[str]:
    """Retrieve a secret from environment variables.

    Args:
        name: Environment variable name
        required: If True, raise ValueError when secret is missing

    Returns:
        Secret value or None

    Raises:
        ValueError: If required and secret is missing
    """
    value = os.environ.get(name)
    if required and not value:
        raise ValueError(
            f"Required secret {name} not found in environment. "
            f"Set it in .env or export it before running."
        )
    return value


def mask_secret(value: Optional[str], visible_chars: int = 4) -> str:
    """Mask a secret for safe logging.

    Args:
        value: Secret value to mask
        visible_chars: Number of visible characters at start/end

    Returns:
        Masked string like "sk-...xyz"
    """
    if not value:
        return "(none)"
    if len(value) <= visible_chars * 2:
        return "*" * len(value)
    return f"{value[:visible_chars]}...{value[-visible_chars:]}"
