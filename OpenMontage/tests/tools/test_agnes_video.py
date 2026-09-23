from __future__ import annotations

from pathlib import Path

from tools.video.agnes_video import AgnesVideo


class _Response:
    def __init__(self, payload=None, content=b"video", status_code=200):
        self._payload = payload or {}
        self.content = content
        self.status_code = status_code
        self.headers = {}

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_agnes_text_to_video_payload(monkeypatch, tmp_path: Path):
    captured = {}

    def request(method, url, **kwargs):
        if method == "POST":
            captured.update({"url": url, "payload": kwargs["json"], "headers": kwargs["headers"]})
            return _Response({"video_id": "video-1", "status": "queued"})
        if url.endswith("/agnesapi"):
            return _Response({"video_id": "video-1", "status": "completed", "url": "https://example.test/out.mp4"})
        return _Response(content=b"mp4")

    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    monkeypatch.setenv("OPENMONTAGE_ALLOW_NETWORK", "1")
    monkeypatch.setattr("requests.request", request)
    monkeypatch.setattr("tools.video._shared.probe_output", lambda path: {"duration": 5.0})

    output = tmp_path / "out.mp4"
    result = AgnesVideo().execute(
        {
            "prompt": "A friendly 3D fish swims left to right",
            "negative_prompt": "text, watermark, extra fins",
            "duration": "5",
            "seed": 42,
            "output_path": str(output),
        }
    )

    assert result.success
    assert captured["url"].endswith("/v1/videos")
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["payload"]["model"] == "agnes-video-2.5-flash"
    assert captured["payload"]["mode"] == "text"
    assert "Avoid: text, watermark, extra fins" in captured["payload"]["prompt"]
    assert output.read_bytes() == b"mp4"


def test_agnes_reference_video_requires_non_flash(monkeypatch):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    monkeypatch.setenv("OPENMONTAGE_ALLOW_NETWORK", "1")
    result = AgnesVideo().execute(
        {
            "prompt": "Preserve the same 3D animal design",
            "operation": "reference_to_video",
            "model_id": "agnes-video-2.5-flash",
            "reference_video_urls": ["https://example.test/reference.mp4"],
        }
    )
    assert not result.success
    assert "non-Flash" in result.error


def test_agnes_flash_rejects_higher_resolution(monkeypatch):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    monkeypatch.setenv("OPENMONTAGE_ALLOW_NETWORK", "1")
    result = AgnesVideo().execute(
        {
            "prompt": "A 3D rabbit",
            "model_id": "agnes-video-2.5-flash",
            "resolution": "1080P",
        }
    )
    assert not result.success
    assert "720P only" in result.error
