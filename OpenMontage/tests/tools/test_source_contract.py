import json
from pathlib import Path

import pytest

from schemas.artifacts import validate_artifact
from tools.extract.section_parser import SectionParser
from tools.structure.source_contract import (
    build_coverage_contract,
    normalize_markdown_document,
    validate_coverage_contract,
    validate_final_source_coverage,
    write_source_contracts,
)


def _chapter_markdown() -> str:
    return (
        "<!-- page: 1 -->\n"
        "# Chapter 8: Plants\n\n"
        "## Recall\n"
        "- Plants need sunlight, air, and water.\n\n"
        "## Plant uses\n"
        "| Plant | Use |\n"
        "| --- | --- |\n"
        "| Tulsi | Medicine |\n"
        "| Cotton | Clothes |\n\n"
        "<!-- page: 2 -->\n"
        "## Fill in the blanks\n"
        "1. A tree has a strong _____.\n"
        "![Parts of a plant](images/plant.png)\n"
    )


def test_normalized_document_preserves_tables_boxes_exercises_and_reading_order(tmp_path: Path):
    source = tmp_path / "chapter.md"
    source.write_text(_chapter_markdown(), encoding="utf-8")

    document = normalize_markdown_document(source, source_pdf="chapter.pdf")
    validate_artifact("chapter_document", document)

    assert [block["reading_order"] for block in document["blocks"]] == list(
        range(1, len(document["blocks"]) + 1)
    )
    assert [page["page_number"] for page in document["pages"]] == [1, 2]

    recall = next(block for block in document["blocks"] if block["block_type"] == "recall")
    assert recall["source_text"] == "Plants need sunlight, air, and water."
    assert recall["semantic_role"] == "recall"
    assert recall["heading"] == "Recall"

    table = next(block for block in document["blocks"] if block["block_type"] == "table")
    assert table["table"]["row_count"] == 3
    assert table["table"]["column_count"] == 2
    assert table["table"]["cells"][0] == {
        "row": 0,
        "column": 0,
        "text": "Plant",
        "row_span": 1,
        "column_span": 1,
        "is_header": True,
    }

    assessment = next(
        block for block in document["blocks"] if block["block_type"] == "assessment"
    )
    assert assessment["source_text"] == "A tree has a strong _____."
    assert assessment["list_ordinal"] == "1"

    figure = next(block for block in document["blocks"] if block["block_type"] == "figure")
    assert figure["media"]["source"] == "images/plant.png"
    assert document["layout_fidelity"]["requires_visual_pdf_audit"] is True


def test_word_bank_and_remember_are_not_lost_or_misclassified(tmp_path: Path):
    source = tmp_path / "chapter.md"
    source.write_text(
        "<!-- page: 4 -->\n## Let's Remember\nEarth rotates.\n"
        "<!-- page: 5 -->\n## Word Bank\nOrbit – The path of Earth around the Sun.\n",
        encoding="utf-8",
    )
    document = normalize_markdown_document(source)
    headings = {block.get("heading") or block.get("source_text"): block for block in document["blocks"]}
    assert headings["Let's Remember"]["semantic_role"] == "recall"
    assert headings["Word Bank"]["semantic_role"] == "glossary"
    assert [page["page_number"] for page in document["pages"]] == [4, 5]

    parsed = SectionParser().parse_text(source.read_text(encoding="utf-8"), "social_studies")
    assert [(block.heading, block.block_type.value) for block in parsed] == [
        ("Let's Remember", "recall"), ("Word Bank", "glossary"),
    ]


def test_coverage_contract_fails_closed_until_every_required_block_is_mapped(tmp_path: Path):
    source = tmp_path / "chapter.md"
    source.write_text("# Animals\nAnimals move and grow.\n", encoding="utf-8")
    document = normalize_markdown_document(source)
    contract = build_coverage_contract(document)
    validate_artifact("coverage_contract", contract)

    assert contract["summary"]["coverage_ratio"] == 0
    assert contract["summary"]["render_ready"] is False
    with pytest.raises(ValueError, match="Source coverage is incomplete"):
        validate_coverage_contract(contract)

    for index, entry in enumerate(contract["entries"]):
        entry["status"] = "mapped"
        entry["mappings"]["screen_ids"] = [f"screen-{index}"]
    summary = validate_coverage_contract(contract)
    assert summary["coverage_ratio"] == 1
    assert summary["render_ready"] is True


def test_mapped_coverage_entry_requires_real_timeline_mapping(tmp_path: Path):
    source = tmp_path / "chapter.md"
    source.write_text("# Animals\n", encoding="utf-8")
    contract = build_coverage_contract(normalize_markdown_document(source))
    contract["entries"][0]["status"] = "mapped"

    with pytest.raises(ValueError, match="has no narration or screen mapping"):
        validate_coverage_contract(contract)


def test_write_source_contracts_persists_schema_valid_artifacts(tmp_path: Path):
    source = tmp_path / "chapter.md"
    source.write_text(_chapter_markdown(), encoding="utf-8")
    document_path = tmp_path / "artifacts" / "chapter_document.json"
    coverage_path = tmp_path / "artifacts" / "coverage_contract.json"

    document, coverage = write_source_contracts(source, document_path, coverage_path)

    assert json.loads(document_path.read_text(encoding="utf-8")) == document
    assert json.loads(coverage_path.read_text(encoding="utf-8")) == coverage
    validate_artifact("chapter_document", document)
    validate_artifact("coverage_contract", coverage)


def test_pdf_layout_geometry_is_attached_when_extractor_supplies_it(tmp_path: Path):
    source = tmp_path / "chapter.md"
    source.write_text("# Plants\nPlants need water.\n", encoding="utf-8")
    extraction = tmp_path / "extracted_content.json"
    extraction.write_text(
        json.dumps({
            "layout_pages": [{
                "page_number": 3,
                "width": 612,
                "height": 792,
                "unit": "points",
                "blocks": [
                    {
                        "kind": "text",
                        "reading_order": 1,
                        "bbox": [40, 50, 200, 80],
                        "text": "Plants",
                    },
                    {
                        "kind": "text",
                        "reading_order": 2,
                        "bbox": [40, 90, 400, 130],
                        "text": "Plants need water.",
                        "text_styles": [{
                            "text": "Plants need water.",
                            "font": "Bookman",
                            "size": 14.0,
                            "color": 0,
                            "bold": False,
                            "italic": True,
                        }],
                    },
                ],
                "tables": [],
            }],
        }),
        encoding="utf-8",
    )

    document = normalize_markdown_document(
        source,
        source_pdf="chapter.pdf",
        extraction_artifact_path=extraction,
    )

    validate_artifact("chapter_document", document)
    assert [block["page_number"] for block in document["blocks"]] == [3, 3]
    assert document["blocks"][1]["bbox"] == [40.0, 90.0, 400.0, 130.0]
    assert document["pages"][0]["width"] == 612.0
    assert document["layout_fidelity"]["geometry"] == "pdf_bounding_boxes_complete"
    assert document["layout_fidelity"]["text_boxes"] == "positions_and_text_style_preserved"
    assert document["blocks"][1]["source_layout"]["normalized_bbox"] == [
        round(40 / 612, 6), round(90 / 792, 6),
        round(400 / 612, 6), round(130 / 792, 6),
    ]
    assert document["blocks"][1]["source_layout"]["text_styles"][0]["italic"] is True
    assert document["layout_fidelity"]["requires_visual_pdf_audit"] is False


def test_pdf_layout_recovers_table_and_box_missing_from_markdown(tmp_path: Path):
    source = tmp_path / "chapter.md"
    source.write_text("# Plants\nPlants need water.\n", encoding="utf-8")
    extraction = tmp_path / "extracted_content.json"
    extraction.write_text(
        json.dumps({
            "layout_pages": [{
                "page_number": 1,
                "width": 600,
                "height": 800,
                "unit": "points",
                "blocks": [
                    {"kind": "text", "reading_order": 1, "bbox": [30, 40, 220, 70], "text": "Plants"},
                    {"kind": "text", "reading_order": 2, "bbox": [30, 80, 400, 115], "text": "Plants need water."},
                    {
                        "kind": "text",
                        "reading_order": 3,
                        "bbox": [320, 130, 560, 220],
                        "text": "We Learn\nWhy do plants need sunlight?",
                        "text_styles": [{
                            "text": "We Learn",
                            "font": "Bookman-Bold",
                            "size": 15.0,
                            "color": 1122867,
                            "bold": True,
                            "italic": False,
                        }],
                    },
                ],
                "tables": [{
                    "table_index": 1,
                    "bbox": [30, 250, 560, 360],
                    "rows": [["Plant", "Use"], ["Cotton", "Clothes"]],
                }],
            }],
        }),
        encoding="utf-8",
    )

    document = normalize_markdown_document(
        source,
        source_pdf="chapter.pdf",
        extraction_artifact_path=extraction,
    )
    validate_artifact("chapter_document", document)

    recovered = [
        block for block in document["blocks"]
        if block["provenance"]["extraction_mode"] == "pdf-layout-recovery"
        and block["source_text"].startswith(("We Learn", "Plant | Use"))
    ]
    assert len(recovered) == 2
    callout = next(block for block in recovered if block["block_type"] == "callout")
    table = next(block for block in recovered if block["block_type"] == "table")
    assert callout["semantic_role"] == "we_learn"
    assert callout["source_layout"]["text_styles"][0]["bold"] is True
    assert table["table"]["cells"][3]["text"] == "Clothes"
    assert document["validation"]["recovered_layout_blocks"] == 2


def test_symbolic_math_rows_are_not_misclassified_as_markdown_bullets(
    tmp_path: Path,
):
    source = tmp_path / "chapter.md"
    source.write_text("# Addition\n\n+ =\n", encoding="utf-8")
    document = normalize_markdown_document(source)

    symbolic = next(
        block for block in document["blocks"] if block["source_text"] == "+ ="
    )
    assert symbolic["block_type"] == "equation"
    assert symbolic["required_for_coverage"] is True


def test_recovered_textbook_footer_is_decorative_and_not_required(tmp_path: Path):
    source = tmp_path / "chapter.md"
    source.write_text("# At the Beach\n\nChildren play near the sea.\n", encoding="utf-8")
    extraction = tmp_path / "extracted_content.json"
    extraction.write_text(
        json.dumps({
            "layout_pages": [{
                "page_number": 1,
                "width": 600,
                "height": 800,
                "unit": "points",
                "blocks": [
                    {"kind": "text", "reading_order": 1, "bbox": [30, 40, 250, 70], "text": "At the Beach"},
                    {"kind": "text", "reading_order": 2, "bbox": [30, 90, 450, 120], "text": "Children play near the sea."},
                    {"kind": "text", "reading_order": 3, "bbox": [30, 760, 300, 780], "text": "17 Rockland English - Class 1"},
                ],
                "tables": [],
            }],
        }),
        encoding="utf-8",
    )

    document = normalize_markdown_document(
        source,
        source_pdf="chapter.pdf",
        extraction_artifact_path=extraction,
    )

    footer = next(block for block in document["blocks"] if "Rockland" in block["source_text"])
    assert footer["block_type"] == "decorative"
    assert footer["required_for_coverage"] is False


def test_final_source_coverage_proves_blocks_survive_composition(tmp_path: Path):
    source = tmp_path / "chapter.md"
    source.write_text("# Plants\nPlants need water.\n", encoding="utf-8")
    contract = build_coverage_contract(normalize_markdown_document(source))
    section_ids = ["section-0001", "section-0002"]
    for entry, section_id in zip(contract["entries"], section_ids):
        entry["status"] = "mapped"
        entry["mappings"] = {
            "narration_segment_ids": [section_id],
            "screen_ids": [section_id],
            "visual_cue_ids": [f"{section_id}:visual"],
        }
    contract["summary"] = validate_coverage_contract(contract)
    plan = {
        "sections": [
            {"section_id": section_id, "source_block_ids": [entry["source_block_id"]]}
            for entry, section_id in zip(contract["entries"], section_ids)
        ]
    }
    narration = {
        "segments": [
            {"section_id": section_id, "text": "Narrated source text."}
            for section_id in section_ids
        ]
    }
    clips = [{"section_id": section_id, "success": True} for section_id in section_ids]
    timeline = {"sections": plan["sections"]}

    report = validate_final_source_coverage(
        contract,
        educational_plan=plan,
        narration_manifest=narration,
        clip_manifest=clips,
        composition_timeline=timeline,
    )
    assert report["status"] == "pass"
    assert report["coverage_ratio"] == 1.0

    timeline["sections"] = timeline["sections"][:-1]
    with pytest.raises(ValueError, match="missing_composition_section"):
        validate_final_source_coverage(
            contract,
            educational_plan=plan,
            narration_manifest=narration,
            clip_manifest=clips,
            composition_timeline=timeline,
        )
