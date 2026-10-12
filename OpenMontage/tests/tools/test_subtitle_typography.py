from tools.analysis import narration_text_syncer as sync


def test_script_punctuation_preserves_speech_timestamps():
    words = [
        {"word": "hello", "start_ms": 100, "end_ms": 300},
        {"word": "children", "start_ms": 320, "end_ms": 700},
    ]
    restored = sync._restore_script_typography(words, "Hello, children!")
    assert [w["word"] for w in restored] == ["Hello,", "children!"]
    assert [(w["start_ms"], w["end_ms"]) for w in restored] == [(100, 300), (320, 700)]
    assert words[0]["word"] == "hello"


def test_typography_does_not_conceal_spoken_word_mismatch():
    assert sync._restore_script_typography([{"word": "35"}], "3.5.") is None
    assert sync._restore_script_typography([{"word": "diameter"}], "Radius.") is None
    assert sync._restore_script_typography([{"word": "Hello"}], "Hello children.") is None


def test_quotes_apostrophes_and_decimal_values():
    restored = sync._restore_script_typography(
        [{"word": "lets"}, {"word": "measure"}, {"word": "3.5"}],
        "Let’s measure 3.5.",
    )
    assert [w["word"] for w in restored] == ["Let’s", "measure", "3.5."]
    words = [{"word": '“Ready?”'}, {"word": "Yes."}]
    assert len(sync._chunk_into_phrases(words)) == 2


def test_whisperx_path_uses_approved_punctuation(monkeypatch):
    from unittest.mock import Mock
    audio = Mock()
    audio.exists.return_value = True
    audio.stat.return_value.st_size = 1
    monkeypatch.setattr(sync, "_align_with_whisperx", lambda _: [
        {"word": "ready", "start_ms": 20, "end_ms": 400}])
    words, method = sync._get_word_timestamps(audio, "Ready?", 500, 1000)
    assert method == "whisperx"
    assert words == [{"word": "Ready?", "start_ms": 1020, "end_ms": 1400}]
