import json
from pathlib import Path
import subprocess
import sys

import pytest
from tools.structure import educational_startup as startup
from tools.structure.educational_startup import fingerprint, verify_references, resume_project


def test_reference_identity_and_drift(tmp_path):
    media = tmp_path / "reference.mp4"
    media.write_bytes(b"approved")
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps({"references": [{"id": "test", "path": media.name,
                          "sha256": fingerprint(media)}], "presentation_contract": {}}))
    assert verify_references(tmp_path, lock)["status"] == "pass"
    media.write_bytes(b"changed")
    assert verify_references(tmp_path, lock)["checks"][0]["status"] == "changed"
    media.unlink()
    assert verify_references(tmp_path, lock)["checks"][0]["status"] == "missing"


def test_resume_rejects_unregistered_project(tmp_path):
    with pytest.raises(ValueError, match="missing project.json"):
        resume_project(tmp_path)


def test_start_without_input_is_dependency_light():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, "-S", "-m", "tools.structure.educational_agent_cli", "start"],
                            cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "needs_input"


def test_setup_needs_no_external_python_packages():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, "-S", "-m", "tools.structure.educational_agent_cli", "setup"],
                            cwd=root, capture_output=True, text=True)
    assert result.returncode == 2, result.stderr
    assert json.loads(result.stdout)["status"] == "needs_setup"


@pytest.mark.parametrize("status,approved,expected", [
    ("awaiting_human", False, "awaiting_human"),
    ("in_progress", False, "resume_ready"),
    ("completed", True, "completed"),
])
def test_resume_preserves_gates(tmp_path, monkeypatch, status, approved, expected):
    from tools.structure import educational_run_tracker as tracker
    from lib import pipeline_loader
    (tmp_path / "project.json").write_text("{}")
    monkeypatch.setattr(tracker, "checkpoint_summary", lambda p: {"stages": [{
        "name": "proposal", "status": status, "human_approval_required": True,
        "human_approved": approved}]})
    monkeypatch.setattr(pipeline_loader, "load_pipeline_readonly", lambda p: {
        "stages": [{"name": "proposal", "skill": "edustream/proposal-director"}]})
    result = resume_project(tmp_path)
    assert result["status"] == expected
    assert result["paid_generation_started"] is False


def test_conda_first_and_explicit_venv(monkeypatch):
    monkeypatch.setattr(startup, "find_conda", lambda: "conda")
    assert startup.setup_environment()["environment_manager"] == "conda"
    assert startup.setup_environment(manager="venv")["environment_manager"] == "venv"


def test_missing_explicit_conda_fails_without_install(monkeypatch):
    monkeypatch.setattr(startup, "find_conda", lambda: None)
    with pytest.raises(ValueError, match="Conda not found"):
        startup.setup_environment(install_python=True, manager="conda")


def test_existing_conda_only_inspected(tmp_path, monkeypatch):
    monkeypatch.setattr(startup, "ROOT", tmp_path)
    (tmp_path / ".conda-educational" / "conda-meta").mkdir(parents=True)
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 2, '{"status":"needs_setup"}', '')
    monkeypatch.setattr(startup.subprocess, "run", run)
    assert startup.setup_conda("conda")["environment_created"] is False
    assert len(calls) == 1 and calls[0][1] == "run"


def test_conda_create_uses_repository_spec(tmp_path, monkeypatch):
    monkeypatch.setattr(startup, "ROOT", tmp_path)
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, '{"status":"ready"}', '')
    monkeypatch.setattr(startup.subprocess, "run", run)
    assert startup.setup_conda("conda")["environment_created"] is True
    assert calls[0][1:3] == ["env", "create"]
    assert str(tmp_path / "environment.yml") in calls[0]


def test_setup_detects_pinned_hyperframes_and_repository_secret(tmp_path, monkeypatch):
    monkeypatch.setattr(startup, "ROOT", tmp_path)
    cli = tmp_path / ".runtime/hyperframes/node_modules/hyperframes/bin/hyperframes.mjs"
    cli.parent.mkdir(parents=True)
    cli.write_text("// cli", encoding="utf-8")
    (tmp_path / ".env").write_text("MODELSLAB_API_KEY=secret-not-returned\n", encoding="utf-8")
    monkeypatch.setattr(startup.shutil, "which", lambda name: "node" if name in {
        "node", "npm", "ffmpeg", "ffprobe"} else None)
    monkeypatch.setattr(startup.importlib.util, "find_spec", lambda name: object())
    result = startup.setup_environment(manager="venv")
    assert result["commands"]["hyperframes"] is True
    assert result["credentials"]["MODELSLAB_API_KEY"] == "configured"
    assert "secret-not-returned" not in json.dumps(result)


def test_conda_refuses_unrelated_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(startup, "ROOT", tmp_path)
    (tmp_path / ".conda-educational").mkdir()
    with pytest.raises(ValueError, match="Refusing"):
        startup.setup_conda("conda")


def test_vm_baselines_work_without_video(tmp_path):
    image = tmp_path / "baseline.jpg"
    image.write_bytes(b"baseline")
    package = tmp_path / "package.json"
    package.write_text(json.dumps({"files": [{"id": "frame", "path": image.name,
                                             "sha256": fingerprint(image)}]}))
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps({"portable_package": package.name,
        "references": [{"id": "video", "path": "absent.mp4", "sha256": "not-present"}],
        "presentation_contract": {}}))
    assert verify_references(tmp_path, lock)["status"] == "pass"
    assert verify_references(tmp_path, lock, require_full_video=True)["status"] == "fail"
    image.write_bytes(b"drift")
    assert verify_references(tmp_path, lock)["status"] == "fail"
    image.unlink()
    assert verify_references(tmp_path, lock)["status"] == "fail"
