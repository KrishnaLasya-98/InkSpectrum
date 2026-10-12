"""Run Backlot and the persistent educational job worker in one service.

One process owns both components because a Railway service can attach only one
volume and the Backlot board and worker must observe the same project files.
"""

from __future__ import annotations

import os
import subprocess
import sys

from backlot.__main__ import _host, _port, cmd_serve


def _enabled(name: str, default: bool = True) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def main() -> int:
    worker: subprocess.Popen | None = None
    if _enabled("OPENMONTAGE_WORKER_ENABLED"):
        worker = subprocess.Popen(
            [sys.executable, "-m", "tools.structure.educational_job_worker"],
            cwd=os.fspath(os.path.dirname(os.path.dirname(__file__))),
        )
    try:
        return cmd_serve(_port(), _host())
    finally:
        if worker is not None and worker.poll() is None:
            worker.terminate()
            try:
                worker.wait(timeout=10)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
