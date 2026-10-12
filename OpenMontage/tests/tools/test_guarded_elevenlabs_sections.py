import json
from pathlib import Path

import pytest
import requests

from tools.voice import guarded_elevenlabs_sections as voice


def _fixture(tmp_path: Path) -> Path:
    project = tmp_path / "chapter"
    (project / "artifacts").mkdir(parents=True)
    (project / "chapter_config.json").write_text(json.dumps({
        "subject": "social-studies", "approval_policy": "full-run-preauthorized",
        "providers": {"audio": {"provider": "elevenlabs", "model_id": voice.MODEL,
                                "voice_id": voice.VOICE, "speed": 0.85}},
    }), encoding="utf-8")
    (project / "artifacts" / "educational_plan.json").write_text(json.dumps({
        "sections": [{"section_id": "s01-title", "title": "Lesson 8", "narration_script": "Lesson 8."}],
    }), encoding="utf-8")
    (project / "artifacts" / "chapter_document.json").write_text(json.dumps({"blocks": []}), encoding="utf-8")
    (project / "artifacts" / "elevenlabs-access-preflight.json").write_text(json.dumps({
        "status": "pass", "voice_id": voice.VOICE, "voice_available": True,
        "model_id": voice.MODEL, "model_available": True,
        "character_count": 0, "character_limit": 1000,
    }), encoding="utf-8")
    return project


def test_dry_run_makes_no_charged_request(tmp_path, monkeypatch):
    project = _fixture(tmp_path)
    monkeypatch.setattr(voice, "validate_teaching_contract", lambda *a, **kw: {"status": "pass"})
    monkeypatch.setattr(voice.requests, "post", lambda *a, **kw: pytest.fail("POST during dry run"))
    result = voice.run(project, dry_run=True)
    assert result["status"] == "dry_run_pass"
    assert result["new_requests_sent"] == 0
    assert not (project / "assets").exists()


def test_uncertain_submission_is_never_retried(tmp_path, monkeypatch):
    project = _fixture(tmp_path)
    monkeypatch.setattr(voice, "validate_teaching_contract", lambda *a, **kw: {"status": "pass"})
    monkeypatch.setattr(voice, "load_dotenv", lambda *a, **kw: None)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-only")
    calls = []

    def timeout(*args, **kwargs):
        calls.append(1)
        raise requests.Timeout("unknown outcome")

    monkeypatch.setattr(voice.requests, "post", timeout)
    with pytest.raises(RuntimeError, match="Uncertain ElevenLabs submission"):
        voice.run(project, max_new=1)
    sidecar = project / "assets" / "audio" / "narration-elevenlabs-v1" / "s01-title.request.json"
    assert json.loads(sidecar.read_text(encoding="utf-8"))["status"] == "submission_unknown"
    with pytest.raises(RuntimeError, match="requires reconciliation"):
        voice.run(project, max_new=1)
    assert len(calls) == 1
