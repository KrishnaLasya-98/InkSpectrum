from tools.analysis.encoded_educational_comparison import (
    caption_audit, production_evidence, topic_coverage,
)


def test_topic_coverage_uses_captions_and_display_text():
    data = {"sections": [{"heading": "Ferns", "display": ["beautiful leaves"]}],
            "captions": [{"words": [{"word": word} for word in
                         "Ferns do not produce flowers or seeds.".split()]}]}
    results = topic_coverage(
        ["Ferns do not produce flowers or seeds and have beautiful leaves"],
        production_evidence(data),
    )
    assert results[0]["status"] == "pass"


def test_caption_audit_accepts_punctuated_monotonic_words():
    data = {"captions": [{"id": "c1", "start": 0.0, "end": 1.0, "words": [
        {"word": "Hello,", "start": 0.0, "end": .4},
        {"word": "children!", "start": .4, "end": 1.0},
    ]}]}
    assert caption_audit(data, 2.0)["status"] == "pass"


def test_caption_audit_reports_punctuation_and_overlap():
    data = {"captions": [
        {"id": "c1", "start": 0.0, "end": 1.0,
         "words": [{"word": "First.", "start": 0.0, "end": 1.0}]},
        {"id": "c2", "start": .5, "end": 1.5,
         "words": [{"word": "Second", "start": .5, "end": 1.5}]},
    ]}
    result = caption_audit(data, 2.0)
    assert result["status"] == "review"
    assert any("punctuation" in issue for issue in result["issues"])
    assert any("overlapping" in issue for issue in result["issues"])


def test_caption_audit_accepts_readable_chunks_split_mid_sentence():
    data = {"captions": [
        {"id": "c1", "start": 0.0, "end": 1.0, "words": [
            {"word": "Weather", "start": 0.0, "end": .4},
            {"word": "and", "start": .5, "end": .9},
        ]},
        {"id": "c2", "start": 1.0, "end": 2.0, "words": [
            {"word": "climate.", "start": 1.0, "end": 1.8},
        ]},
    ]}
    result = caption_audit(data, 2.0)
    assert result["status"] == "pass"
    assert result["terminal_punctuation_count"] == 1
