import pytest
from tools.analysis.narration_text_syncer import _build_qa_card_props


def aligned(text, gap_after=None):
    words = []
    cursor = 1000
    for index, word in enumerate(text.split()):
        words.append({"word": word, "start_ms": cursor, "end_ms": cursor + 200})
        cursor += 200 + (4000 if index == gap_after else 0)
    return [{"words": words}]


def test_answer_word_in_question_does_not_reveal_early():
    cards = _build_qa_card_props(aligned("Is red correct? red", 2),
        [{"question": "Is red correct?", "answer": "red", "thinking_pause_seconds": 4}], 1000)
    assert cards[0]["reveal_delay_seconds"] == 4.6
    assert cards[0]["thinking_start_seconds"] == .6
    assert cards[0]["thinking_end_seconds"] == 4.6


def test_missing_answer_has_no_arbitrary_fallback():
    with pytest.raises(ValueError, match="absent"):
        _build_qa_card_props(aligned("What colour? blue"),
                            [{"question": "What colour?", "answer": "red"}], 1000)


def test_missing_silence_rejected():
    with pytest.raises(ValueError, match="thinking pause"):
        _build_qa_card_props(aligned("What colour? red"),
                            [{"question": "What colour?", "answer": "red", "thinking_pause_seconds": 4}], 1000)


def test_multiple_questions_match_in_sequence():
    cards = _build_qa_card_props(aligned("First colour? red Next colour? red"),
        [{"question": "First colour?", "answer": "red"},
         {"question": "Next colour?", "answer": "red"}], 1000)
    assert [c["reveal_delay_seconds"] for c in cards] == [.4, 1.0]


def test_solution_steps_follow_spoken_cues():
    cards = _build_qa_card_props(aligned("How many? Count two. Add three. Five."),
        [{"question": "How many?", "answer": "Five.",
          "solution_steps": ["Count two.", "Add three."]}], 1000)
    assert cards[0]["solution_beats"] == [
        {"text": "Count two.", "start_seconds": .4},
        {"text": "Add three.", "start_seconds": .8}]
    assert cards[0]["reveal_delay_seconds"] == 1.2
