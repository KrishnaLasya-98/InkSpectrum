"""Continuity constraints must never disappear before a paid request."""
import pytest

from tools.video.modelslab_video import ModelsLabVideo


@pytest.mark.parametrize("model", ["wan-2.2-i2v", "h3-minimax-start-end-frame"])
def test_unverified_end_frame_fails_before_upload_or_submit(monkeypatch, model):
    monkeypatch.setenv("MODELSLAB_API_KEY", "test-key")

    def forbidden(*args, **kwargs):
        raise AssertionError("Blocked continuity request must not upload or submit")

    monkeypatch.setattr("tools.video.modelslab_video.upload_modelslab_media", forbidden)
    monkeypatch.setattr("tools.video.modelslab_video.submit_modelslab", forbidden)
    result = ModelsLabVideo().execute({
        "model_id": model, "operation": "image_to_video",
        "prompt": "Keep exact endpoint frames.", "image_path": "start.png",
        "end_image_url": "https://example.test/end.png",
    })
    assert not result.success
    assert result.data["job_created"] is False
    assert result.data["production_state"] == "contract_blocked"
    assert "refusing to discard" in result.error


def test_h3_start_image_remains_available_for_access_test(monkeypatch, tmp_path):
    monkeypatch.setenv("MODELSLAB_API_KEY", "test-key")
    captured = {}

    def submit(url, key, payload, timeout):
        captured.update(url=url, payload=payload)
        return {"id": "h3-pilot"}

    monkeypatch.setattr("tools.video.modelslab_video.submit_modelslab", submit)
    result = ModelsLabVideo().execute({
        "model_id": "h3-minimax-start-end-frame", "operation": "image_to_video",
        "prompt": "The globe rotates on its stand.",
        "image_url": "https://example.test/start.png",
        "duration": 5, "resolution": "768", "submit_only": True,
        "output_path": str(tmp_path / "clip.mp4"),
    })
    assert result.success
    assert captured["url"].endswith("/api/v6/video/img2video")
    assert captured["payload"]["init_image"] == ["https://example.test/start.png"]
    assert captured["payload"]["resolution"] == 768
