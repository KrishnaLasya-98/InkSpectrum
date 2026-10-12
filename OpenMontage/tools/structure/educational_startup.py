"""Dependency-light onboarding and read-only recovery for coding agents.

Resume deliberately returns the next stage to the agent, rather than replaying
the monolithic runner: replay is not a safe substitute for stage-level resume.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[2]
REFERENCE_LOCK = ROOT / "config/educational-reference-lock.json"


def _pinned_hyperframes() -> Path | None:
    candidate = ROOT / ".runtime" / "hyperframes" / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs"
    return candidate if candidate.is_file() and shutil.which("node") else None


def _repo_env_has(name: str) -> bool:
    """Check a repository-scoped ignored env file without loading or exposing values."""
    path = ROOT / ".env"
    if not path.is_file():
        return False
    try:
        return any(
            line.split("=", 1)[0].strip() == name and bool(line.split("=", 1)[1].strip())
            for line in path.read_text(encoding="utf-8").splitlines()
            if "=" in line and not line.lstrip().startswith("#")
        )
    except OSError:
        return False


def fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_references(root: Path = ROOT, lock_path: Path = REFERENCE_LOCK,
                      *, require_full_video: bool = False) -> dict:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    checks = []
    portable = lock.get("portable_package")
    entries = list(lock["references"])
    if portable:
        entries += json.loads((root / portable).read_text(encoding="utf-8"))["files"]
    for item in entries:
        path = root / item["path"]
        optional = bool(portable and item in lock["references"] and not require_full_video)
        state = ("optional_missing" if optional else "missing") if not path.is_file() else (
            "pass" if fingerprint(path) == item["sha256"] else "changed")
        checks.append({"id": item["id"], "status": state, "path": str(path)})
    return {"status": "pass" if all(c["status"] in {"pass", "optional_missing"} for c in checks) else "fail",
            "checks": checks, "presentation_contract": lock["presentation_contract"],
            "boundary": "Portable reference integrity only. Run template tests and encoded-output QA separately; screenshots cannot verify audio or motion."}


def find_conda() -> str | None:
    candidate = os.environ.get("CONDA_EXE")
    if candidate and Path(candidate).is_file():
        return candidate
    return shutil.which("conda")


def setup_conda(conda: str) -> dict:
    """Create our dedicated prefix or inspect it; never update another env."""
    destination = ROOT / ".conda-educational"
    if destination.exists() and not (destination / "conda-meta").is_dir():
        raise ValueError(f"Refusing to overwrite non-Conda directory: {destination}")
    created = not destination.exists()
    if created:
        subprocess.run([conda, "env", "create", "--prefix", str(destination),
                        "--file", str(ROOT / "environment.yml"), "--yes"],
                       cwd=ROOT, check=True, stdout=sys.stderr, stderr=sys.stderr)
    check = subprocess.run([conda, "run", "--prefix", str(destination), "python", "-m",
                            "tools.structure.educational_agent_cli", "setup"],
                           cwd=ROOT, capture_output=True, text=True)
    if check.returncode not in (0, 2):
        raise RuntimeError("Conda environment check failed; inspect the environment before retrying.")
    result = json.loads(check.stdout)
    result.update(environment_prefix=str(destination), environment_created=created,
                  environment_manager="conda")
    return result


def setup_environment(*, install_python: bool = False, manager: str = "auto") -> dict:
    if manager not in {"auto", "conda", "venv"}:
        raise ValueError("Unknown environment manager")
    conda = find_conda()
    selected = ("conda" if conda else "venv") if manager == "auto" else manager
    if install_python and selected == "conda":
        if not conda:
            raise ValueError("Conda not found. Install Miniforge/Miniconda or select --manager venv.")
        return setup_conda(conda)
    if install_python:
        destination = ROOT / ".venv-educational"
        venv.EnvBuilder(with_pip=True).create(destination)
        python = destination / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run([str(python), "-m", "pip", "install", "-r",
                        str(ROOT / "requirements-educational.txt")], check=True,
                       stdout=sys.stderr, stderr=sys.stderr)
        check = subprocess.run([str(python), "-m", "tools.structure.educational_agent_cli", "setup"],
                               cwd=ROOT, capture_output=True, text=True)
        result = json.loads(check.stdout)
        result["environment_python"] = str(python)
        return result
    modules = {name: importlib.util.find_spec(name) is not None for name in
               ("yaml", "pydantic", "jsonschema", "dotenv", "PIL", "numpy", "requests",
                "soundfile", "fitz", "pdfplumber", "fastapi", "watchfiles",
                "opendataloader_pdf", "docling")}
    commands = {name: shutil.which(name) is not None for name in
                ("node", "npm", "ffmpeg", "ffprobe", "java", "hyperframes")}
    commands["hyperframes"] = commands["hyperframes"] or _pinned_hyperframes() is not None
    ready = all(modules.values()) and all(commands.values())
    return {"status": "ready" if ready else "needs_setup", "python": sys.executable,
            "environment_manager": selected, "conda_available": bool(conda),
            "active_conda_prefix": os.environ.get("CONDA_PREFIX"),
            "optional_manim": {"local_module": importlib.util.find_spec("manim") is not None,
                               "configured_python_exists": bool(os.environ.get("OPENMONTAGE_MANIM_PYTHON") and Path(os.environ["OPENMONTAGE_MANIM_PYTHON"]).is_file())},
            "python_modules": modules, "commands": commands,
            "credentials": {"MODELSLAB_API_KEY": "configured" if (os.environ.get("MODELSLAB_API_KEY") or _repo_env_has("MODELSLAB_API_KEY")) else "not_configured"},
            "next_steps": ["Reuse this interpreter if checks pass. Otherwise use setup --install-python (Conda-first) only with installation approval.",
                           "Follow docs/INSTALLATION_GUIDE.md and record every install or upgrade there.",
                           "Install missing system tools separately; select the approved HyperFrames version.",
                           "Run project-specific preflight before paid production."],
            "boundary": "Availability check only; does not verify browser, model downloads or live providers."}


def resume_project(project: Path) -> dict:
    project = project.resolve()
    if not (project / "project.json").is_file():
        raise ValueError("Not a registered project: missing project.json; migrate legacy projects explicitly.")
    from tools.structure.educational_run_tracker import checkpoint_summary
    from lib.pipeline_loader import load_pipeline_readonly
    state = checkpoint_summary(project)
    for stage in state["stages"]:
        if stage["status"] == "invalid":
            raise ValueError(f"Invalid checkpoint for {stage['name']}; repair before resuming.")
        if stage["status"] == "completed" and (not stage["human_approval_required"] or stage["human_approved"]):
            continue
        definition = next(s for s in load_pipeline_readonly("educational-video")["stages"] if s["name"] == stage["name"])
        from lib.checkpoint import read_checkpoint
        checkpoint = read_checkpoint(project.parent, project.name, stage["name"]) or {}
        return {"status": "awaiting_human" if stage["status"] == "awaiting_human" else "resume_ready",
                "project_dir": str(project), "next_stage": stage,
                "skill": str(ROOT / "skills" / (definition["skill"] + ".md")),
                "artifacts_dir": str(project / "artifacts"),
                "recovery": {
                    "artifacts": checkpoint.get("artifacts") or {},
                    "partial_progress": (checkpoint.get("metadata") or {}).get("partial_progress", {}),
                    "invalidated_by": (checkpoint.get("metadata") or {}).get("invalidated_by"),
                    "provider_retry_policy": "Query recorded job IDs before retrying; never blindly resubmit paid work.",
                },
                "action": "Read the checkpoint and stage skill; validate partial artifacts and continue only unfinished work. Preserve approval gates.",
                "execution": "agent_handoff", "paid_generation_started": False}
    return {"status": "completed", "project_dir": str(project), "paid_generation_started": False}
