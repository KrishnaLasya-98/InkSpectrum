"""Offline failure injection: no models, paid jobs, or chapter renders."""
import json
import hashlib
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from lib.production_runtime import run_logged
from tools.structure import educational_job_worker as worker
from tools.video.hyperframes_compose import HyperFramesCompose


def test_logs_are_bounded_and_rotated(tmp_path):
    result = run_logged([sys.executable, "-c", "import sys; print('x'*200000); print('y'*200000,file=sys.stderr)"],
                        log_dir=tmp_path, tail_bytes=1024, max_log_bytes=16384)
    assert result.returncode == 0
    assert len(result.stdout.encode()) <= 1024
    assert len(result.stderr.encode()) <= 1024
    assert all(p.stat().st_size <= 16384 for p in tmp_path.iterdir())


def test_timeout_is_normal_failed_result(tmp_path):
    result = run_logged([sys.executable, "-c", "import time; print('start',flush=True); time.sleep(30)"],
                        log_dir=tmp_path, timeout=.5)
    assert result.returncode == 124
    assert "timeout" in result.stderr


def test_timeout_stops_child_descendant(tmp_path):
    import time
    marker = tmp_path / "survived.txt"
    child = f"import time; from pathlib import Path; time.sleep(2); Path({str(marker)!r}).touch()"
    parent = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child!r}]); time.sleep(30)"
    result = run_logged([sys.executable, "-c", parent], log_dir=tmp_path / "logs", timeout=.5)
    assert result.returncode == 124
    time.sleep(2.1)
    assert not marker.exists()


def test_nonrender_timeout_decodes_bytes(monkeypatch):
    def expired(*args, **kwargs):
        raise subprocess.TimeoutExpired("node", 1, output=b"progress", stderr=b"warning")
    monkeypatch.setattr(subprocess, "run", expired)
    result = HyperFramesCompose()._run_hf(["check"], cwd=None, timeout=1, check=False)
    assert result.returncode == 124 and "warning" in result.stderr
    assert result.stdout == "progress"


def queued(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "input_root", lambda: tmp_path / "inbox")
    root = worker.ensure_queue(tmp_path / "jobs")
    source = tmp_path / "inbox" / "chapter.pdf"
    source.write_bytes(b"pdf")
    job = {"id": "chapter", "approved": True, "source": str(source)}
    (root / "pending" / "chapter.json").write_text(json.dumps(job))
    return root


@pytest.mark.parametrize("payload,destination", [(None, "failed"), ({"status": "awaiting_human"}, "attention"),
    ({"status": "completed", "final_video": "missing.mp4"}, "failed")])
def test_worker_requires_explicit_result(tmp_path, monkeypatch, payload, destination):
    root = queued(tmp_path, monkeypatch)
    def run(command, **kwargs):
        if payload is not None:
            Path(kwargs["env"]["OPENMONTAGE_RESULT_PATH"]).parent.mkdir(parents=True, exist_ok=True)
            Path(kwargs["env"]["OPENMONTAGE_RESULT_PATH"]).write_text(json.dumps(payload))
        return subprocess.CompletedProcess(command, 0, 'progress\n{"status":"completed"}', '')
    monkeypatch.setattr(worker, "run_logged", run)
    assert worker.run_once(root)
    assert (root / destination / "chapter.json").exists()


def test_recovery_does_not_resubmit(tmp_path, monkeypatch):
    root = queued(tmp_path, monkeypatch)
    (root / "pending" / "chapter.json").replace(root / "running" / "chapter.json")
    monkeypatch.setattr(worker, "run_logged", Mock(side_effect=AssertionError("must not launch")))
    assert not worker.run_once(root)
    assert (root / "attention" / "chapter.json").exists()


@pytest.mark.parametrize("dry_run", [False, True])
def test_worker_accepts_verified_result(tmp_path, monkeypatch, dry_run):
    root = queued(tmp_path, monkeypatch)
    path = root / "pending" / "chapter.json"
    job = json.loads(path.read_text())
    job["dry_run"] = dry_run
    path.write_text(json.dumps(job))
    video = tmp_path / "final.mp4"
    video.write_bytes(b"fixture")
    project = tmp_path / "chapter"
    project.mkdir()
    sheet = project / "encoded-sheet.jpg"
    sheet.write_bytes(b"reviewed fixture")
    comparison = project / "comparison.json"
    comparison.write_text(json.dumps({"automated_status": "pass", "gates": {"fixture_gate": True},
        "candidate": str(video), "candidate_sha256": hashlib.sha256(video.read_bytes()).hexdigest()}))
    (project / "final-review.json").write_text(json.dumps({"status": "pass", "output_path": str(video),
        "metadata": {"encoded_comparison_ref": str(comparison), "contact_sheets_reviewed": [str(sheet)]}}))
    (project / "checkpoint_quality_assurance.json").write_text(json.dumps({"status": "completed",
        "metadata": {"evidence_dir": str(project)}}))
    def run(command, **kwargs):
        target = Path(kwargs["env"]["OPENMONTAGE_RESULT_PATH"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"status": "dry_run_complete" if dry_run else "completed",
            "final_video": str(video), "chapter_config": str(project / "chapter_config.json")}))
        return subprocess.CompletedProcess(command, 0, 'progress', '')
    monkeypatch.setattr(worker, "run_logged", run)
    assert worker.run_once(root)
    assert (root / "completed" / "chapter.json").exists()


def test_download_failure_preserves_previous_file(tmp_path, monkeypatch):
    from lib.media_download import download_atomic
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.headers = {"Content-Length": "12"}
    response.iter_content.return_value = [b"short"]
    monkeypatch.setattr("requests.get", lambda *a, **kw: response)
    target = tmp_path / "clip.mp4"
    target.write_bytes(b"original")
    with pytest.raises(IOError):
        download_atomic("https://example.invalid/clip", target)
    assert target.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [target]
    response.__exit__.assert_called_once()


def test_ambiguous_tts_submission_is_not_retried(tmp_path, monkeypatch):
    import requests
    from tools.voice.voice_synthesis_pipeline import VoiceSynthesisPipeline
    post = Mock(side_effect=requests.Timeout())
    monkeypatch.setattr(requests, "post", post)
    tool = VoiceSynthesisPipeline()
    kwargs = dict(text="Hello.", section_id="s1", source_block_type="concept", output_dir=tmp_path,
                  api_key="test", dry_run=False)
    assert tool._generate_segment(**kwargs)[0] is None
    assert tool._generate_segment(**kwargs)[0] is None
    assert post.call_count == 1
    assert "unknown" in tool._last_generation_error


def test_stt_failure_is_not_perfect_score(tmp_path, monkeypatch):
    from tools.voice.voice_synthesis_pipeline import VoiceSynthesisPipeline
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.json.return_value = {"status": "success", "output": ["https://example.invalid/audio"]}
    monkeypatch.setattr("requests.post", lambda *a, **kw: response)
    monkeypatch.setattr("tools.voice.voice_synthesis_pipeline._download", lambda url, dest: dest)
    monkeypatch.setattr("tools.voice.voice_synthesis_pipeline._call_stt", Mock(side_effect=RuntimeError("offline")))
    result = VoiceSynthesisPipeline()._generate_segment(text="Hello.", section_id="s1", source_block_type="concept",
                         output_dir=tmp_path, api_key="test", dry_run=False)
    assert result[0] is None and result[3] != 0


def test_disk_budget_blocks_before_render(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text('<div data-duration="900" data-width="1920" data-height="1080">')
    monkeypatch.setattr("shutil.disk_usage", lambda p: Mock(free=1))
    assert "disk" in HyperFramesCompose._render_budget(tmp_path, tmp_path / "final.mp4", {}, 30)


def test_render_timeout_configurable(monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_RENDER_TIMEOUT_SECONDS", "7200")
    assert HyperFramesCompose._render_timeout({}) == 7200
    assert HyperFramesCompose._render_timeout({"render_timeout_seconds": 9000}) == 9000


def test_kokoro_lazy_reuse_and_partial_checkpoint(tmp_path, monkeypatch):
    import numpy as np
    import soundfile as sf
    from tools.voice.voice_synthesis_pipeline import VoiceSynthesisPipeline
    load = Mock(return_value=object())
    monkeypatch.setattr("tools.voice.voice_synthesis_pipeline._load_kokoro_model", load)
    calls = []
    def generate(model, **kwargs):
        calls.append(kwargs["text"])
        if kwargs["text"] == "Fail.":
            raise RuntimeError("injected")
        sf.write(str(kwargs["destination"]), np.zeros(2400), 24000)
        return .1
    monkeypatch.setattr("tools.voice.voice_synthesis_pipeline._generate_kokoro_audio", generate)
    tool = VoiceSynthesisPipeline()
    inputs = {"provider": "kokoro", "output_dir": str(tmp_path), "narration_segments": [
        {"section_id": "s1", "text": "Hello."}, {"section_id": "s2", "text": "Fail."}]}
    assert not tool.execute(inputs).success
    assert "s1" in json.loads((tmp_path / ".tts-cache.json").read_text())["segments"]
    inputs["narration_segments"] = [{"section_id": "s1", "text": "Hello."}]
    result = VoiceSynthesisPipeline().execute(inputs)
    assert result.success and load.call_count == 1 and calls.count("Hello.") == 1
    assert result.data["qa_report"]["status"] == "unverified"
    assert result.data["qa_report"]["qa_passed"] == 0


def test_cli_result_sidecar(tmp_path, monkeypatch, capsys):
    from tools.structure.educational_agent_cli import _print
    target = tmp_path / "result.json"
    monkeypatch.setenv("OPENMONTAGE_RESULT_PATH", str(target))
    _print({"status": "awaiting_human"})
    assert json.loads(target.read_text()) == {"status": "awaiting_human"}


def test_reviewed_narration_progress_is_schema_valid():
    from schemas.artifacts import validate_artifact
    validate_artifact("narration_manifest", {"version": "1.0", "engine_used": "kokoro", "voice_name": "test",
        "segments": [{"section_id": "s1", "text": "Hello.", "audio_path": "s1.wav", "duration_seconds": 1}],
        "total_duration_seconds": 1, "generation_complete": True,
        "pronunciation_qa_status": "pending", "word_alignment_status": "pending"})


def test_live_queue_lock_prevents_recovery(tmp_path, monkeypatch):
    root = queued(tmp_path, monkeypatch)
    with worker.queue_lock(root) as acquired:
        assert acquired
        # Use a separate process so OS lock ownership semantics are exercised.
        code = "from pathlib import Path; from tools.structure.educational_job_worker import queue_lock; "
        code += f"\nwith queue_lock(Path({str(root)!r})) as ok: print(ok)"
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0 and result.stdout.strip() == "False"
