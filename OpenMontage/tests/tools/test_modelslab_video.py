from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from tools.video.modelslab_video import ModelsLabVideo, _strip_audio_track


def test_modelslab_video_uses_v7_model_id_and_video_array(monkeypatch, tmp_path: Path):
    captured: dict[str, object] = {}

    def submit(url, api_key, payload, *, timeout):
        captured["url"] = url
        captured["payload"] = payload
        return {"id": "request-1"}

    monkeypatch.setenv("MODELSLAB_API_KEY", "test-key")
    monkeypatch.setattr("tools.video.modelslab_video.submit_modelslab", submit)
    monkeypatch.setattr(
        "tools.video.modelslab_video.poll_modelslab",
        lambda request_id, api_key, endpoint: {"output": ["https://example.test/video.mp4"]},
    )
    monkeypatch.setattr(
        "tools.video.modelslab_video.download_modelslab_output",
        lambda result, output_path: output_path,
    )
    monkeypatch.setattr(
        "tools.video._shared.probe_output",
        lambda output_path: {"duration": 5.0},
    )

    result = ModelsLabVideo().execute(
        {
            "prompt": "A quiet city street at dawn",
            "operation": "video_to_video",
            "video_url": "https://example.test/source.mp4",
            "output_path": str(tmp_path / "output.mp4"),
        }
    )

    assert result.success
    assert captured["url"].endswith("/video-fusion/video-to-video")
    assert captured["payload"]["model_id"] == "wan2.1"
    assert captured["payload"]["init_video"] == ["https://example.test/source.mp4"]


def test_modelslab_h3_t2v_uses_v6_endpoint(monkeypatch, tmp_path: Path):
    captured: dict[str, object] = {}

    def submit(url, api_key, payload, *, timeout):
        captured["url"] = url
        captured["payload"] = payload
        return {"id": "request-1"}

    monkeypatch.setenv("MODELSLAB_API_KEY", "test-key")
    monkeypatch.setattr("tools.video.modelslab_video.submit_modelslab", submit)
    monkeypatch.setattr(
        "tools.video.modelslab_video.poll_modelslab",
        lambda request_id, api_key, endpoint: {"output": ["https://example.test/video.mp4"]},
    )
    monkeypatch.setattr(
        "tools.video.modelslab_video.download_modelslab_output",
        lambda result, output_path: output_path,
    )
    monkeypatch.setattr(
        "tools.video._shared.probe_output",
        lambda output_path: {"duration": 5.0},
    )

    result = ModelsLabVideo().execute(
        {
            "prompt": "A fish swims through a clear pond",
            "negative_prompt": "text, watermark, extra fins, distorted anatomy",
            "operation": "text_to_video",
            "model_id": "h3-minimax-t2v",
            "duration": "5",
            "resolution": "768",
            "output_path": str(tmp_path / "output.mp4"),
        }
    )

    assert result.success
    assert captured["url"] == "https://modelslab.com/api/v6/video/text2video"
    assert captured["payload"]["model_id"] == "h3-minimax-t2v"
    assert captured["payload"]["duration"] == "5"
    assert captured["payload"]["resolution"] == 768
    assert captured["payload"]["negative_prompt"] == (
        "text, watermark, extra fins, distorted anatomy"
    )


def test_modelslab_h3_r2v_uses_reference_inputs(monkeypatch, tmp_path: Path):
    captured: dict[str, object] = {}

    def submit(url, api_key, payload, *, timeout):
        captured["url"] = url
        captured["payload"] = payload
        return {"id": "request-1"}

    monkeypatch.setenv("MODELSLAB_API_KEY", "test-key")
    monkeypatch.setattr("tools.video.modelslab_video.submit_modelslab", submit)
    monkeypatch.setattr(
        "tools.video.modelslab_video.poll_modelslab",
        lambda request_id, api_key, endpoint: {"output": ["https://example.test/video.mp4"]},
    )
    monkeypatch.setattr(
        "tools.video.modelslab_video.download_modelslab_output",
        lambda result, output_path: output_path,
    )
    monkeypatch.setattr(
        "tools.video._shared.probe_output",
        lambda output_path: {"duration": 5.0},
    )

    result = ModelsLabVideo().execute(
        {
            "prompt": "Animate Image 1 and Video 1 as one continuous habitat lesson",
            "operation": "reference_to_video",
            "model_id": "h3-minimax-r2v",
            "duration": "5",
            "reference_image_urls": ["https://example.test/reference.png"],
            "reference_video_urls": ["https://example.test/reference.mp4"],
            "reference_audio_urls": ["https://example.test/reference.wav"],
            "output_path": str(tmp_path / "output.mp4"),
        }
    )

    assert result.success
    assert captured["url"] == "https://modelslab.com/api/v6/video/img2video"
    assert captured["payload"]["model_id"] == "h3-minimax-r2v"
    assert captured["payload"]["init_image"] == ["https://example.test/reference.png"]
    assert captured["payload"]["init_video"] == ["https://example.test/reference.mp4"]
    assert captured["payload"]["init_audio"] == ["https://example.test/reference.wav"]


def test_modelslab_h3_fast_reference_uses_v6_reference_contract(
    monkeypatch, tmp_path: Path
):
    captured: dict[str, object] = {}

    def submit(url, api_key, payload, *, timeout):
        captured["url"] = url
        captured["payload"] = payload
        return {"id": "request-fast-1"}

    monkeypatch.setenv("MODELSLAB_API_KEY", "test-key")
    monkeypatch.setattr("tools.video.modelslab_video.submit_modelslab", submit)
    monkeypatch.setattr(
        "tools.video.modelslab_video.poll_modelslab",
        lambda request_id, api_key, endpoint: {
            "output": ["https://example.test/video.mp4"]
        },
    )
    monkeypatch.setattr(
        "tools.video.modelslab_video.download_modelslab_output",
        lambda result, output_path: output_path,
    )
    monkeypatch.setattr(
        "tools.video._shared.probe_output",
        lambda output_path: {"duration": 5.0},
    )

    result = ModelsLabVideo().execute(
        {
            "prompt": "Animate Image 1 as a friendly garden lesson.",
            "operation": "reference_to_video",
            "model_id": "h3-minimax-ref-to-video-fast",
            "duration": "5",
            "resolution": "768",
            "reference_image_urls": ["https://example.test/reference.png"],
            "output_path": str(tmp_path / "output.mp4"),
        }
    )

    assert result.success
    assert captured["url"] == "https://modelslab.com/api/v6/video/img2video"
    assert captured["payload"]["model_id"] == "h3-minimax-ref-to-video-fast"
    assert captured["payload"]["init_image"] == [
        "https://example.test/reference.png"
    ]
    assert captured["payload"]["init_video"] == []
    assert captured["payload"]["init_audio"] == []


def test_modelslab_wan22_i2v_uses_ultra_endpoint(monkeypatch, tmp_path: Path):
    captured: dict[str, object] = {}

    def submit(url, api_key, payload, *, timeout):
        captured["url"] = url
        captured["payload"] = payload
        return {"id": "request-1"}

    monkeypatch.setenv("MODELSLAB_API_KEY", "test-key")
    monkeypatch.setattr("tools.video.modelslab_video.submit_modelslab", submit)
    monkeypatch.setattr(
        "tools.video.modelslab_video.poll_modelslab",
        lambda request_id, api_key, endpoint: {"output": ["https://example.test/video.mp4"]},
    )
    monkeypatch.setattr(
        "tools.video.modelslab_video.download_modelslab_output",
        lambda result, output_path: output_path,
    )
    monkeypatch.setattr(
        "tools.video.modelslab_video.upload_modelslab_media",
        lambda image_path, api_key: "https://example.test/keyframe.png",
    )
    monkeypatch.setattr(
        "tools.video._shared.probe_output",
        lambda output_path: {"duration": 5.0},
    )

    result = ModelsLabVideo().execute(
        {
            "prompt": "The children walk naturally while the sea moves gently",
            "negative_prompt": "text, watermark, identity drift",
            "operation": "image_to_video",
            "model_id": "wan-2.2-i2v",
            "image_path": str(tmp_path / "keyframe.png"),
            "fps": 18,
            "num_frames": 90,
            "output_path": str(tmp_path / "output.mp4"),
        }
    )

    assert result.success
    assert captured["url"] == "https://modelslab.com/api/v6/video/img2video_ultra"
    assert captured["payload"]["model_id"] == "wan-2.2-i2v"
    assert captured["payload"]["init_image"] == "https://example.test/keyframe.png"
    assert captured["payload"]["resolution"] == "480"
    assert captured["payload"]["fps"] == 18
    assert captured["payload"]["num_frames"] == 90


def test_modelslab_h3_r2v_strips_data_uri_prefix(monkeypatch, tmp_path: Path):
    captured: dict[str, object] = {}

    def submit(url, api_key, payload, *, timeout):
        captured["payload"] = payload
        return {"id": "request-1"}

    monkeypatch.setenv("MODELSLAB_API_KEY", "test-key")
    monkeypatch.setattr("tools.video.modelslab_video.submit_modelslab", submit)
    monkeypatch.setattr(
        "tools.video.modelslab_video.upload_modelslab_media",
        lambda image_path, api_key: "data:image/png;base64,YWJj",
    )
    monkeypatch.setattr(
        "tools.video.modelslab_video.poll_modelslab",
        lambda request_id, api_key, endpoint: {"output": ["https://example.test/video.mp4"]},
    )
    monkeypatch.setattr(
        "tools.video.modelslab_video.download_modelslab_output",
        lambda result, output_path: output_path,
    )
    monkeypatch.setattr(
        "tools.video._shared.probe_output", lambda output_path: {"duration": 5.0}
    )

    result = ModelsLabVideo().execute(
        {
            "prompt": "Animate Image 1",
            "operation": "reference_to_video",
            "model_id": "h3-minimax-r2v",
            "reference_image_paths": [str(tmp_path / "reference.png")],
            "output_path": str(tmp_path / "output.mp4"),
        }
    )

    assert result.success
    assert captured["payload"]["init_image"] == ["YWJj"]
    assert captured["payload"]["base64"] is True


def test_modelslab_wan22_i2v_marks_base64_inputs(monkeypatch, tmp_path: Path):
    captured: dict[str, object] = {}

    monkeypatch.setenv("MODELSLAB_API_KEY", "test-key")
    monkeypatch.setattr(
        "tools.video.modelslab_video.submit_modelslab",
        lambda url, api_key, payload, timeout: captured.update(payload=payload) or {"id": "request-1"},
    )
    monkeypatch.setattr(
        "tools.video.modelslab_video.poll_modelslab",
        lambda request_id, api_key, endpoint: {"output": ["https://example.test/video.mp4"]},
    )
    monkeypatch.setattr(
        "tools.video.modelslab_video.download_modelslab_output",
        lambda result, output_path: output_path,
    )
    monkeypatch.setattr(
        "tools.video.modelslab_video.upload_modelslab_media",
        lambda image_path, api_key: "data:image/png;base64,ZmFrZQ==",
    )
    monkeypatch.setattr(
        "tools.video._shared.probe_output",
        lambda output_path: {"duration": 5.0},
    )

    result = ModelsLabVideo().execute(
        {
            "prompt": "Gentle beach motion",
            "operation": "image_to_video",
            "model_id": "wan-2.2-i2v",
            "image_path": str(tmp_path / "keyframe.png"),
            "output_path": str(tmp_path / "output.mp4"),
        }
    )

    assert result.success
    assert captured["payload"]["base64"] is True


def test_educational_mode_forces_silent_provider_payload(monkeypatch, tmp_path: Path):
    captured: dict[str, object] = {}

    monkeypatch.setenv("MODELSLAB_API_KEY", "test-key")
    monkeypatch.setattr(
        "tools.video.modelslab_video.submit_modelslab",
        lambda url, api_key, payload, timeout: captured.update(payload=payload) or {"id": "request-1"},
    )
    monkeypatch.setattr(
        "tools.video.modelslab_video.poll_modelslab",
        lambda request_id, api_key, endpoint: {"output": ["https://example.test/video.mp4"]},
    )
    monkeypatch.setattr(
        "tools.video.modelslab_video.download_modelslab_output",
        lambda result, output_path: output_path,
    )
    monkeypatch.setattr(
        "tools.video._shared.probe_output", lambda output_path: {"duration": 5.0}
    )

    result = ModelsLabVideo().execute(
        {
            "prompt": "A child-friendly animated habitat lesson",
            "model_id": "seedance-t2v",
            "generate_audio": True,
            "educational_mode": True,
            "output_path": str(tmp_path / "output.mp4"),
        }
    )

    assert result.success
    assert captured["payload"]["generate_audio"] is False
    assert result.data["generate_audio"] is False
    assert result.data["audio_policy"] == "silent"
    assert result.data["provider_contract"] == "video-fusion-v7"


def test_capability_contract_rejects_wrong_wan_operation(monkeypatch):
    monkeypatch.setenv("MODELSLAB_API_KEY", "test-key")

    result = ModelsLabVideo().execute(
        {
            "prompt": "Animate this frame",
            "model_id": "wan-2.2-i2v",
            "operation": "text_to_video",
        }
    )

    assert not result.success
    assert "does not support operation" in (result.error or "")


def test_silent_postprocess_remuxes_without_audio(monkeypatch, tmp_path: Path):
    output = tmp_path / "clip.mp4"
    output.write_bytes(b"provider-output-with-audio")
    captured: dict[str, object] = {}

    monkeypatch.setattr("tools.video.modelslab_video.shutil.which", lambda name: "ffmpeg")

    def run(args, **kwargs):
        captured["args"] = args
        Path(args[-1]).write_bytes(b"silent-video")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("tools.video.modelslab_video.subprocess.run", run)

    _strip_audio_track(output)

    assert "-an" in captured["args"]
    assert output.read_bytes() == b"silent-video"


def test_timeout_persists_job_and_next_call_resumes_without_resubmit(monkeypatch, tmp_path):
    calls = {"submit": 0, "poll": 0}
    monkeypatch.setenv("MODELSLAB_API_KEY", "test-key")
    def submit(*args, **kwargs):
        calls["submit"] += 1
        return {"id": "paid-job-1"}
    def poll(*args, **kwargs):
        calls["poll"] += 1
        if calls["poll"] == 1:
            raise TimeoutError("still processing")
        return {"output": ["https://example.test/video.mp4"]}
    monkeypatch.setattr("tools.video.modelslab_video.submit_modelslab", submit)
    monkeypatch.setattr("tools.video.modelslab_video.poll_modelslab", poll)
    monkeypatch.setattr("tools.video.modelslab_video.download_modelslab_output",
                        lambda result, output: output)
    monkeypatch.setattr("tools.video._shared.probe_output", lambda output: {"duration": 5.0})
    request = {"prompt": "A moving triangle", "model_id": "wan2.2",
               "duration": "5", "output_path": str(tmp_path / "clip.mp4")}
    first = ModelsLabVideo().execute(request)
    assert not first.success and first.data["recoverable"]
    job = Path(first.data["job_state_path"])
    assert json.loads(job.read_text())["request_id"] == "paid-job-1"
    second = ModelsLabVideo().execute(request)
    assert second.success and second.data["resumed"]
    assert second.cost_usd == 0
    assert calls == {"submit": 1, "poll": 2}


def test_pending_job_with_changed_content_blocks_duplicate_submission(monkeypatch, tmp_path):
    calls = {"submit": 0}
    monkeypatch.setenv("MODELSLAB_API_KEY", "test-key")
    monkeypatch.setattr("tools.video.modelslab_video.submit_modelslab",
                        lambda *a, **k: calls.update(submit=calls["submit"] + 1) or {"id": "job"})
    monkeypatch.setattr("tools.video.modelslab_video.poll_modelslab",
                        lambda *a, **k: (_ for _ in ()).throw(TimeoutError("pending")))
    base = {"prompt": "A moving square", "model_id": "wan2.2", "duration": "5",
            "output_path": str(tmp_path / "clip.mp4")}
    assert not ModelsLabVideo().execute(base).success
    changed = {**base, "prompt": "A moving circle"}
    result = ModelsLabVideo().execute(changed)
    assert not result.success and "different content" in result.error
    assert calls["submit"] == 1


def test_explicit_resume_id_never_submits(monkeypatch, tmp_path):
    monkeypatch.setenv("MODELSLAB_API_KEY", "test-key")
    monkeypatch.setattr("tools.video.modelslab_video.submit_modelslab",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not submit")))
    monkeypatch.setattr("tools.video.modelslab_video.poll_modelslab",
                        lambda request_id, api_key, endpoint: {"output": ["https://example.test/video.mp4"]})
    monkeypatch.setattr("tools.video.modelslab_video.download_modelslab_output",
                        lambda result, output: output)
    monkeypatch.setattr("tools.video._shared.probe_output", lambda output: {"duration": 5.0})
    result = ModelsLabVideo().execute({"resume_request_id": "existing-job",
        "model_id": "wan2.2", "output_path": str(tmp_path / "clip.mp4")})
    assert result.success and result.data["request_id"] == "existing-job"
    assert result.cost_usd == 0
