from __future__ import annotations

from tools.structure.educational_preflight import run_educational_preflight


def _config() -> dict:
    return {
        "providers": {
            "audio": {"provider": "modelslab"},
            "video": {
                "provider": "modelslab",
                "model_id": "wan2.2",
                "image_model_id": "wan-2.2-i2v",
                "reference_model_id": "h3-minimax-r2v",
                "fallback_model_id": "h3-minimax-t2v",
                "semantic_qa": {"required": True},
            },
        },
        "qa_policy": {"require_semantic_av_match": True},
    }


def test_preflight_validates_model_contracts_without_credentials_in_dry_run(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        "tools.structure.educational_preflight.load_dotenv",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.delenv("MODELSLAB_API_KEY", raising=False)

    report = run_educational_preflight(_config(), workspace=tmp_path, dry_run=True)

    assert report["status"] == "pass"
    assert report["failure_count"] == 0
    names = {check["name"] for check in report["checks"]}
    assert "model_contract:text_to_video" in names
    assert "model_contract:reference_to_video" in names


def test_preflight_fails_before_generation_when_production_key_is_missing(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        "tools.structure.educational_preflight.load_dotenv",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.delenv("MODELSLAB_API_KEY", raising=False)
    monkeypatch.setattr("tools.structure.educational_preflight.shutil.which", lambda _name: "tool")
    monkeypatch.setattr(
        "tools.structure.educational_preflight.shutil.disk_usage",
        lambda _path: type("Usage", (), {"free": 20 * 1024 ** 3})(),
    )

    report = run_educational_preflight(_config(), workspace=tmp_path, dry_run=False)

    assert report["status"] == "fail"
    assert any(
        item["name"] == "modelslab_credentials" for item in report["failures"]
    )
