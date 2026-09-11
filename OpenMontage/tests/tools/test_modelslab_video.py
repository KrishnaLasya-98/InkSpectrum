from __future__ import annotations

from pathlib import Path

from tools.video.modelslab_video import ModelsLabVideo


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
    assert captured["payload"]["resolution"] == "768P"


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
