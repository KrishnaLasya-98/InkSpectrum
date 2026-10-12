import hashlib
from pathlib import Path
import pytest
from tools.video.exercise_visuals import prepare_visual, visual_html


def matching():
    return {"qa_format": "matching", "exercise_visual": {"kind": "matching",
        "left": [{"id": "l1", "text": "Cat"}, {"id": "l2", "text": "Dog"}],
        "right": [{"id": "r1", "text": "Barks"}, {"id": "r2", "text": "Meows"}],
        "matches": [{"left_id": "l1", "right_id": "r2", "cue_text": "Cat meows."},
                    {"left_id": "l2", "right_id": "r1", "cue_text": "Dog barks."}]}}


def words():
    return [{"word": w, "start_ms": 3000+i*300, "end_ms": 3200+i*300}
            for i, w in enumerate("Cat meows. Dog barks.".split())]


def prepare(question, speech=None, tmp_path=Path(".")):
    return prepare_visual(question, speech or words(), 0, 2, 6, tmp_path, tmp_path / "assets")


def test_matching_preserves_option_order_and_times_connections():
    result = prepare(matching())
    assert [m["reveal_seconds"] for m in result["reveals"]] == [3, 3.6]
    rendered = visual_html(result, "card")
    assert 'id="card-visual-0"' in rendered
    assert result["right"][0]["text"] == "Barks"


def test_invalid_matching_and_missing_cues_block():
    question = matching()
    question["exercise_visual"]["matches"][0]["right_id"] = "unknown"
    with pytest.raises(ValueError, match="references"): prepare(question)
    question = matching()
    question["exercise_visual"]["matches"][0]["cue_text"] = "Never spoken"
    with pytest.raises(ValueError, match="cue missing"): prepare(question)


def test_diagram_crop_hash_coordinates_and_label_timing(tmp_path):
    from PIL import Image
    path = tmp_path / "source.png"
    Image.new("RGB", (400, 200), "white").save(path)
    question = {"visual_source_block_ids": ["figure-1"], "exercise_visual": {
        "kind": "diagram_label", "source_block_id": "figure-1", "image_path": str(path),
        "image_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "labels": [{"text": "Cat", "x": .5, "y": .2, "target_x": .5, "target_y": .6, "cue_text": "Cat meows."}]}}
    result = prepare(question, tmp_path=tmp_path)
    assert result["width"] == 400 and result["height"] == 200
    assert 'viewBox="0 0 400 200"' in visual_html(result, "card")
    assert (tmp_path / "assets" / Path(result["image_path"]).name).exists()
    question["exercise_visual"]["image_sha256"] = "changed"
    with pytest.raises(ValueError, match="hash"): prepare(question, tmp_path=tmp_path)
    question["exercise_visual"]["labels"][0]["x"] = float("nan")
    with pytest.raises(ValueError, match="coordinates"): prepare(question, tmp_path=tmp_path)


def test_specialized_format_cannot_silently_fall_back():
    with pytest.raises(ValueError, match="requires"):
        prepare({"qa_format": "diagram_label"})


def test_text_is_escaped_not_html():
    question = matching()
    question["exercise_visual"]["left"][0]["text"] = "<script>"
    assert "&lt;script&gt;" in visual_html(prepare(question), "card")


def test_grammar_sentence_uses_spoken_cues_and_escaped_corrections():
    speech = [{"word": word, "start_ms": 2000 + index * 300,
               "end_ms": 2200 + index * 300}
              for index, word in enumerate("Use She instead. Use runs now.".split())]
    question = {"qa_format": "grammar_sentence", "exercise_visual": {
        "kind": "grammar_sentence", "sentence": "Her run fast.",
        "corrections": [
            {"token_index": 0, "text": "She", "cue_text": "Use She instead."},
            {"token_index": 1, "text": "runs", "cue_text": "Use runs now."},
        ]}}
    result = prepare(question, speech)
    assert [item["reveal_seconds"] for item in result["reveals"]] == [2, 2.9]
    rendered = visual_html(result, "grammar")
    assert 'id="grammar-visual-0"' in rendered
    assert "Her" in rendered and "She" in rendered


def test_source_linked_table_fill_renders_timed_answers():
    speech = [{"word": word, "start_ms": 2100 + index * 300,
               "end_ms": 2300 + index * 300}
              for index, word in enumerate("The answer is twelve.".split())]
    question = {"qa_format": "table_fill", "visual_source_block_ids": ["table-1"],
        "exercise_visual": {"kind": "table_fill", "source_block_id": "table-1",
            "headers": ["Tens", "Ones"], "rows": [["1", ""]],
            "answers": [{"row": 0, "column": 1, "text": "2",
                         "cue_text": "answer is twelve."}]}}
    result = prepare(question, speech)
    rendered = visual_html(result, "table")
    assert result["reveals"][0]["reveal_seconds"] == pytest.approx(2.4)
    assert '<table aria-label="Table exercise">' in rendered
    assert 'id="table-visual-0"' in rendered


def test_worked_math_renders_steps_on_narration_timeline():
    speech = [{"word": word, "start_ms": 2200 + index * 300,
               "end_ms": 2400 + index * 300}
              for index, word in enumerate("First add tens. Then add ones.".split())]
    question = {"qa_format": "math_worked", "exercise_visual": {
        "kind": "math_worked", "expression": "23 + 14",
        "steps": [
            {"text": "20 + 10 = 30", "cue_text": "First add tens."},
            {"text": "3 + 4 = 7", "cue_text": "Then add ones."},
        ]}}
    result = prepare(question, speech)
    rendered = visual_html(result, "math")
    assert [item["reveal_seconds"] for item in result["reveals"]] == [2.2, 3.1]
    assert "23 + 14" in rendered and 'id="math-visual-1"' in rendered


def test_new_layouts_reject_dense_or_unreviewed_content():
    grammar = {"qa_format": "grammar_sentence", "exercise_visual": {
        "kind": "grammar_sentence", "sentence": " ".join(["word"] * 19),
        "corrections": [{"token_index": 0, "text": "Word", "cue_text": "Cat meows."}]}}
    with pytest.raises(ValueError, match="eighteen"): prepare(grammar)
    table = {"qa_format": "table_fill", "visual_source_block_ids": [],
        "exercise_visual": {"kind": "table_fill", "source_block_id": "missing",
            "headers": ["A"], "rows": [[""]],
            "answers": [{"row": 0, "column": 0, "text": "B", "cue_text": "Cat meows."}]}}
    with pytest.raises(ValueError, match="reviewed"): prepare(table)
