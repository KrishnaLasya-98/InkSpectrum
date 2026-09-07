"""Load `.env` file into the process environment exactly once."""

from __future__ import annotations

import os
from pathlib import Path

_loaded = False


def load_env(path: Path | str = ".env") -> None:
    """Idempotent .env loader. Loads only on the first call."""
    global _loaded
    if _loaded:
        return
    p = Path(path)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)
    _loaded = True
