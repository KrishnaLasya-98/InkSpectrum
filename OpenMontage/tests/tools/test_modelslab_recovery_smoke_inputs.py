import sys
from pathlib import Path

import pytest

from tools.base_tool import ToolResult
from tools.analysis import modelslab_recovery_smoke as smoke


@pytest.mark.parametrize("operation,field", [
    ("image_to_video", "image_url"),
    ("reference_to_video", "reference_image_urls"),
])
def test_smoke_routes_reference_to_the_selected_operation(monkeypatch, tmp_path, operation, field):
    image = tmp_path / "reference.png"
    image.write_bytes(b"reference")
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Animate the globe on its axle.", encoding="utf-8")
    output = tmp_path / "clip.mp4"
    calls = []

    def execute(self, request):
        calls.append(request)
        if not request.get("submit_only"):
            output.write_bytes(b"video")
        return ToolResult(success=True, data={"request_id": "test-job", "resumed": not request.get("submit_only", False)})

    monkeypatch.setenv("MODELSLAB_API_KEY", "test-only-placeholder")
    monkeypatch.setattr(smoke, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(smoke, "upload_modelslab_media", lambda *args: "https://example.test/reference.png")
    monkeypatch.setattr(smoke.ModelsLabVideo, "execute", execute)
    monkeypatch.setattr(sys, "argv", ["smoke", "--output", str(output), "--operation", operation,
        "--reference-image", str(image), "--prompt-file", str(prompt), "--fps", "18", "--num-frames", "90"])
    assert smoke.main() == 0
    assert len(calls) == 2
    assert field in calls[0]
    assert calls[0]["prompt"] == "Animate the globe on its axle."
    assert calls[0]["fps"] == 18
    assert calls[0]["num_frames"] == 90
    assert calls[0].get("image_url") != calls[0].get("reference_image_urls")
