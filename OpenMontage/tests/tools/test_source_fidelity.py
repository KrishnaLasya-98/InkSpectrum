from pathlib import Path

from tools.structure.source_fidelity import parse_source_markdown


def test_source_manifest_preserves_text_and_punctuation(tmp_path: Path):
    source = tmp_path / "source.md"
    source.write_text(
        "# Lesson : 8 Animal Life\n\n"
        "Animals live both on land and in water.\n\n"
        "## Water animals.\n\n"
        "Animals that live in water are called \u201cWater Animals or Aquatic Animals\u201d.\n\n"
        "- Birds build their own nest.\n",
        encoding="utf-8",
    )

    manifest = parse_source_markdown(source)
    source_texts = [item["source_text"] for item in manifest["items"]]

    assert source_texts == [
        "Lesson : 8 Animal Life",
        "Animals live both on land and in water.",
        "Water animals.",
        "Animals that live in water are called \u201cWater Animals or Aquatic Animals\u201d.",
        "Birds build their own nest.",
    ]
    assert manifest["validation"]["max_content_lines"] <= 3
    assert manifest["text_policy"]["case_format"] == "Tt"
    assert manifest["text_policy"]["punctuation"] == "preserve_source"


def test_title_cards_are_graphics_only_and_content_cards_have_three_lines_max(tmp_path: Path):
    source = tmp_path / "source.md"
    source.write_text("# Title\n\nA.\nB.\nC.\nD.\n", encoding="utf-8")

    manifest = parse_source_markdown(source)
    title_cards = [card for card in manifest["cards"] if card["card_type"] == "title"]
    content_cards = [card for card in manifest["cards"] if card["card_type"] == "content"]

    assert title_cards[0]["media_policy"] == "graphics_only"
    assert all(card["line_count"] <= 3 for card in content_cards)
