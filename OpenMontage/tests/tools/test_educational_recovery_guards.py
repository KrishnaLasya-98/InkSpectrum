from pathlib import Path

from tools.base_tool import ToolResult, ToolStatus
from tools.structure.educational_generator import _motion_narration_chunks
from tools.video.render_mode_router import RenderModeRouter, _render_video_gen
from tools.analysis.educational_clip_qa import semantic_frame_audit


def test_text_chunks_preserve_decimals_and_complete_sentences():
    text = "Dr. Rao explains the Tropic of Capricorn (23.5 degrees south). Asia has many different cultures and languages."
    chunks = _motion_narration_chunks(text, max_words=3)
    assert chunks == [
        "Dr. Rao explains the Tropic of Capricorn (23.5 degrees south).",
        "Asia has many different cultures and languages.",
    ]
    assert " ".join(chunks) == text


def test_evaluator_error_is_pending_not_rejected(monkeypatch):
    monkeypatch.setattr("tools.analysis.video_understand.VideoUnderstand.get_status", lambda self: ToolStatus.AVAILABLE)
    monkeypatch.setattr("tools.analysis.video_understand.VideoUnderstand.execute", lambda self, data: ToolResult(success=False, error="Invalid argument"))
    result = semantic_frame_audit("unused.mp4", {"description": "A globe rotates"})
    assert result["status"] == "pending"
    assert result["match_ratio"] is None


def test_evaluator_outage_preserves_clip_and_stops_regeneration(monkeypatch, tmp_path):
    calls = []
    def generate(self, request):
        calls.append(request)
        Path(request["output_path"]).write_bytes(b"generated")
        return ToolResult(success=True)
    monkeypatch.setattr("tools.video.modelslab_video.ModelsLabVideo.execute", generate)
    monkeypatch.setattr("tools.analysis.educational_clip_qa.audit_generated_clip", lambda *args, **kwargs: {"status": "pending", "issues": ["evaluator unavailable"]})
    monkeypatch.setattr("tools.video.render_mode_router._probe_duration", lambda path: 5.0)
    result = _render_video_gen({"section_id": "one", "description": "A globe rotates", "duration_seconds": 5}, "social", tmp_path, False, {"max_generation_attempts": 3})
    assert not result.success
    assert result.production_state == "semantic_pending"
    assert Path(result.video_path).read_bytes() == b"generated"
    assert len(calls) == 1


def test_account_block_stops_queue_without_fallback(monkeypatch, tmp_path):
    calls = []
    def generate(self, request):
        calls.append(request)
        return ToolResult(success=False, error="You have exhausted your third party access; fund your wallet")
    monkeypatch.setattr("tools.video.modelslab_video.ModelsLabVideo.execute", generate)
    sections = [{"section_id": str(i), "render_mode": "video_gen", "description": "A globe rotates", "duration_seconds": 5} for i in range(3)]
    result = RenderModeRouter().execute({"educational_plan": {"sections": sections}, "output_dir": str(tmp_path), "video_provider": {"model_id": "wan2.2", "fallback_model_id": "another-model", "max_generation_attempts": 3}})
    assert not result.success
    assert len(calls) == 1
    assert result.data["clip_manifest"][0]["production_state"] == "provider_blocked"
    assert result.data["clip_manifest"][1]["production_state"] == "deferred"


def test_dry_run_does_not_overwrite_existing_media(tmp_path):
    path = tmp_path / "one.mp4"
    path.write_bytes(b"approved-media")
    _render_video_gen({"section_id": "one", "duration_seconds": 5}, "social", tmp_path, True)
    assert path.read_bytes() == b"approved-media"
