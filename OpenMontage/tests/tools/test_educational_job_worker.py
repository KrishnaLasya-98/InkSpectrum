from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tools.structure.educational_job_worker import build_command, run_once


def _job(source: Path, **overrides):
    payload = {
        "id": "lesson-1",
        "approved": True,
        "command": "run",
        "source": source.name,
        "project_id": "lesson-1",
        "grade": 1,
        "subject": "english",
        "dry_run": True,
    }
    payload.update(overrides)
    return payload


def test_build_command_uses_only_supported_cli_flags(tmp_path):
    source = tmp_path / "chapter.pdf"
    source.write_bytes(b"pdf")
    command = build_command(_job(source), tmp_path)

    assert command[:5] == [
        sys.executable,
        "-m",
        "tools.structure.educational_agent_cli",
        "run",
        str(source.resolve()),
    ]
    assert "--project-id" in command
    assert "--dry-run" in command


def test_build_command_rejects_unapproved_or_external_sources(tmp_path):
    source = tmp_path / "chapter.pdf"
    source.write_bytes(b"pdf")
    with pytest.raises(ValueError, match="approved=true"):
        build_command(_job(source, approved=False), tmp_path)

    outside = tmp_path.parent / "outside.pdf"
    outside.write_bytes(b"pdf")
    try:
        outside_job = _job(outside)
        outside_job["source"] = str(outside)
        with pytest.raises(ValueError, match="source must be inside"):
            build_command(outside_job, tmp_path)
    finally:
        outside.unlink(missing_ok=True)


def test_run_once_moves_bad_job_to_failed(tmp_path, monkeypatch):
    queue = tmp_path / "jobs"
    pending = queue / "pending"
    pending.mkdir(parents=True)
    (pending / "bad.json").write_text(
        json.dumps({"id": "bad", "approved": False, "source": "missing.pdf"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "tools.structure.educational_job_worker.input_root", lambda: tmp_path / "inbox"
    )

    assert run_once(queue) is True
    assert (queue / "failed" / "bad.json").is_file()
    result = json.loads((queue / "failed" / "bad.result.json").read_text())
    assert result["returncode"] == 1
    assert "approved=true" in result["stderr"]
