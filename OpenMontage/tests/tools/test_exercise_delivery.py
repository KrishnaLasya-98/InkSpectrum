import pytest
from tools.structure.exercise_delivery import build_exercise_delivery


def test_delivery_preserves_script_and_inserts_requested_pauses():
    text = "Let us try. How many? Count two. Two. What colour? Blue."
    parts = build_exercise_delivery(text, [
        {"question": "How many?", "thinking_pause_seconds": 4},
        {"question": "What colour?", "thinking_pause_seconds": 3}])
    assert " ".join(p["text"] for p in parts) == text
    assert [p["pause_after_seconds"] for p in parts] == [4, 3, 0]


def test_delivery_does_not_guess_missing_question():
    with pytest.raises(ValueError):
        build_exercise_delivery("Different text.", [{"question": "How many?"}])


@pytest.mark.parametrize("pause", [-1, float("nan"), 61])
def test_invalid_pause_blocks_delivery(pause):
    with pytest.raises(ValueError):
        build_exercise_delivery("How many?", [{"question": "How many?", "thinking_pause_seconds": pause}])
