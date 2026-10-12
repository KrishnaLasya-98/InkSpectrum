from tools.analysis.narration_text_syncer import rebase_alignment_to_timeline


def test_rebase_alignment_uses_measured_global_timeline_once():
    result = rebase_alignment_to_timeline(
        [
            {
                "section_id": "s1",
                "text": "Hello children.",
                "start_ms": 500,
                "end_ms": 1500,
                "words": [
                    {"word": "Hello", "start_ms": 500, "end_ms": 900},
                    {"word": "children.", "start_ms": 950, "end_ms": 1500},
                ],
            }
        ],
        [
            {
                "section_id": "s1",
                "start_seconds": 2.0,
                "end_seconds": 3.0,
            }
        ],
    )

    segment = result["narration_aligned"][0]
    assert segment["start_ms"] == 2000
    assert segment["end_ms"] == 3000
    assert segment["words"][0]["start_ms"] == 2000
    assert segment["words"][1]["end_ms"] == 3000
    assert result["word_captions"][0]["startMs"] == 2000
    assert "00:00:02" in result["formatted_srt"]


def test_rebase_alignment_rejects_missing_section():
    try:
        rebase_alignment_to_timeline(
            [{"section_id": "missing", "start_ms": 0, "end_ms": 1, "words": []}],
            [],
        )
    except ValueError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("missing measured timing must fail closed")
