from tools.structure.source_contract import normalize_markdown_document


def test_running_book_footer_is_decorative_and_does_not_replace_heading(tmp_path):
    source = tmp_path / "chapter.md"
    source.write_text(
        "# Read and Enjoy\n\n"
        "Kind words help us make friends.\n\n"
        "## 8 Rockland- Class 4 - English (Volume - 1)\n\n"
        "<!-- page: 2 -->\n\n"
        "Polite behaviour begins at home.\n",
        encoding="utf-8",
    )

    document = normalize_markdown_document(source)
    footer = next(
        block for block in document["blocks"]
        if "Rockland" in block["source_text"]
    )
    following = document["blocks"][-1]

    assert footer["block_type"] == "decorative"
    assert footer["required_for_coverage"] is False
    assert following["heading"] == "Read and Enjoy"
