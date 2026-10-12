from tools.structure.exercise_inventory import propose_question_groups


def block(bid, text, top, page=1, left=10):
    return {"block_id": bid, "source_text": text, "block_type": "assessment",
            "page_number": page, "bbox": [left, top, left+150, top+10]}


def test_clear_option_wrap_retains_both_source_ids():
    blocks = [block("a", "a) Choose the shape (square/", 10), block("b", "triangle)", 22)]
    result = propose_question_groups({"blocks": blocks})
    assert result["groups"][0]["source_block_ids"] == ["a", "b"]
    assert result["groups"][0]["question"] == "a) Choose the shape (square/ triangle)"
    assert result["groups"][0]["status"] == "needs_review"
    assert blocks[0]["source_text"].endswith("/")


def test_new_question_does_not_merge_even_after_unclosed_bracket():
    result = propose_question_groups({"blocks": [block("a", "a) Choose (", 10), block("b", "b) Next question?", 22)]})
    assert len(result["groups"]) == 2


def test_page_column_and_missing_geometry_do_not_guess():
    first = block("a", "a) Complete the", 10)
    for second in (block("b", "sentence.", 22, page=2), block("b", "sentence.", 22, left=300),
                   {"block_id": "b", "source_text": "sentence.", "block_type": "assessment"}):
        assert len(propose_question_groups({"blocks": [first, second]})["groups"]) == 2


def test_heading_is_a_hard_boundary_and_no_fragments_are_dropped():
    result = propose_question_groups({"blocks": [block("a", "a) Complete the", 10),
        {**block("h", "Exercise", 22), "block_type": "section_heading", "semantic_role": "assessment"},
        block("b", "sentence.", 34)]})
    assert [g["source_block_ids"] for g in result["groups"]] == [["a"], ["b"]]


def test_english_and_science_continuations():
    for first, second in [("a) Write the plural of", "child."), ("a) Plants need water", "and sunlight.")]:
        result = propose_question_groups({"blocks": [block("a", first, 10), block("b", second, 22)]})
        assert len(result["groups"]) == 1
