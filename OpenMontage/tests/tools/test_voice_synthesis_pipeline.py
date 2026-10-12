from __future__ import annotations

from pathlib import Path

from tools.voice.voice_synthesis_pipeline import VoiceSynthesisPipeline


def test_dry_run_locks_one_voice_across_chapter_sections(tmp_path: Path):
    result = VoiceSynthesisPipeline().execute(
        {
            "narration_segments": [
                {"section_id": "intro", "text": "Welcome.", "source_block_type": "concept"},
                {"section_id": "recall", "text": "Let us recall.", "source_block_type": "recall"},
                {"section_id": "glossary", "text": "Here is the glossary.", "source_block_type": "glossary"},
            ],
            "output_dir": str(tmp_path),
            "voice_profile": {
                "voice_id": "teacher-voice-1",
                "model_id": "text-to-speech",
                "language": "neutral english",
                "speed": 0.82,
            },
            "dry_run": True,
        }
    )

    assert result.success
    manifest = result.data["narration_manifest"]
    assert manifest["voice_name"] == "teacher-voice-1"
    assert manifest["metadata"]["voice_locked_for_chapter"] is True
    assert {segment["voice_used"] for segment in manifest["segments"]} == {
        "teacher-voice-1-dryrun"
    }
    assert {
        segment["delivery_cues_applied"]["speed"]
        for segment in manifest["segments"]
    } == {"0.82"}


def test_kokoro_provider_uses_one_locked_voice_without_modelslab_key(
    tmp_path: Path, monkeypatch
):
    monkeypatch.delenv("MODELSLAB_API_KEY", raising=False)
    monkeypatch.setattr(
        "tools.voice.voice_synthesis_pipeline._load_kokoro_model",
        lambda: object(),
    )

    def fake_generate(_model, **kwargs):
        kwargs["destination"].write_bytes(b"RIFF" + b"0" * 64)
        return 1.25

    monkeypatch.setattr(
        "tools.voice.voice_synthesis_pipeline._generate_kokoro_audio",
        fake_generate,
    )
    result = VoiceSynthesisPipeline().execute(
        {
            "provider": "huggingface-kokoro",
            "narration_segments": [
                {"section_id": "s1", "text": "A point marks an exact position."},
                {"section_id": "s2", "text": "A line continues in both directions."},
            ],
            "output_dir": str(tmp_path),
            "voice_profile": {
                "voice_id": "af_heart",
                "model_id": "hexgrad/Kokoro-82M",
                "language": "en-us",
                "speed": 0.82,
            },
        }
    )

    assert result.success
    manifest = result.data["narration_manifest"]
    assert manifest["engine_used"] == "huggingface-kokoro-82m"
    assert manifest["voice_name"] == "af_heart"
    assert {item["voice_used"] for item in manifest["segments"]} == {"af_heart"}


def test_kokoro_provider_dry_run_does_not_require_model_loading(tmp_path: Path):
    result = VoiceSynthesisPipeline().execute(
        {
            "provider": "huggingface-kokoro",
            "narration_segments": [
                {
                    "section_id": "s1",
                    "text": "A point marks a position.",
                    "spoken_heading": "Points.",
                    "title_card_hold_seconds": 4,
                },
            ],
            "output_dir": str(tmp_path),
            "voice_profile": {
                "voice_id": "af_heart",
                "model_id": "hexgrad/Kokoro-82M",
                "language": "en-us",
                "speed": 0.82,
            },
            "dry_run": True,
        }
    )

    assert result.success
    manifest = result.data["narration_manifest"]
    assert manifest["engine_used"] == "huggingface-kokoro-82m"
    assert manifest["segments"][0]["title_card_hold_seconds"] == 4
    assert manifest["segments"][0]["duration_seconds"] >= 5


def test_multiple_headings_have_individual_pauses_and_topic_tail(tmp_path, monkeypatch):
    import numpy as np
    import soundfile as sf
    monkeypatch.setattr("tools.voice.voice_synthesis_pipeline._load_kokoro_model", lambda: object())
    def generate(_model, **kwargs):
        sf.write(str(kwargs["destination"]), np.full(24000, 0.25), 24000)
        assert kwargs["speed"] == 0.85
        return 1.0
    monkeypatch.setattr("tools.voice.voice_synthesis_pipeline._generate_kokoro_audio", generate)
    inputs = {"provider": "kokoro", "output_dir": str(tmp_path), "speed": 0.85,
              "narration_segments": [{"section_id": "s1", "text": "Body.",
                 "spoken_headings": ["Title", "Subtitle"], "title_card_hold_seconds": 4,
                 "topic_end_pause_seconds": 2}]}
    result = VoiceSynthesisPipeline().execute(inputs)
    assert result.success, result.error
    segment = result.data["narration_manifest"]["segments"][0]
    assert segment["duration_seconds"] == 13
    assert segment["body_start_seconds"] == 10
    assert [(x["start_seconds"], x["end_seconds"]) for x in segment["heading_holds"]] == [(1, 5), (6, 10)]
    samples, rate = sf.read(segment["audio_path"])
    for start, end in [(1, 5), (6, 10), (11, 13)]:
        assert np.max(np.abs(samples[start*rate:end*rate])) == 0
    again = VoiceSynthesisPipeline().execute(inputs)
    assert again.data["narration_manifest"]["segments"][0]["duration_seconds"] == 13


def test_exercise_pause_is_real_audio_silence_and_survives_cache(tmp_path, monkeypatch):
    import numpy as np
    import soundfile as sf
    monkeypatch.setattr("tools.voice.voice_synthesis_pipeline._load_kokoro_model", lambda: object())
    calls = []
    def generate(_model, **kwargs):
        calls.append(kwargs["text"])
        sf.write(str(kwargs["destination"]), np.full(24000, .25), 24000)
        return 1.0
    monkeypatch.setattr("tools.voice.voice_synthesis_pipeline._generate_kokoro_audio", generate)
    inputs = {"provider": "kokoro", "output_dir": str(tmp_path), "speed": .85,
        "narration_segments": [{"section_id": "s1", "text": "How many? Two.",
            "spoken_headings": ["Try it"], "title_card_hold_seconds": 4,
            "topic_end_pause_seconds": 2,
            "exercise_questions": [{"question": "How many?", "thinking_pause_seconds": 3}]}]}
    result = VoiceSynthesisPipeline().execute(inputs)
    assert result.success, result.error
    segment = result.data["narration_manifest"]["segments"][0]
    assert segment["duration_seconds"] == 12
    assert segment["body_start_seconds"] == 5
    samples, rate = sf.read(segment["audio_path"])
    for start, end in [(1, 5), (6, 9), (10, 12)]:
        assert np.max(np.abs(samples[start*rate:end*rate])) == 0
    count = len(calls)
    again = VoiceSynthesisPipeline().execute(inputs)
    assert again.success and len(calls) == count
