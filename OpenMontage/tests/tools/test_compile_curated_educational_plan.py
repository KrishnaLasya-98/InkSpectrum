from tools.structure.compile_curated_educational_plan import compile_plan


def test_compile_plan_expands_ranges_and_requires_complete_coverage() -> None:
    document = {
        "blocks": [
            {
                "block_id": "p0001-b0001",
                "page_number": 1,
                "block_type": "chapter_title",
                "semantic_role": "lesson_content",
                "source_text": "Chapter 7",
                "required_for_coverage": True,
            },
            {
                "block_id": "p0001-b0002",
                "page_number": 1,
                "block_type": "paragraph",
                "semantic_role": "lesson_content",
                "source_text": "A point has a fixed position.",
                "required_for_coverage": True,
            },
        ]
    }
    spec = {
        "title": "Basic Shapes",
        "sections": [
            {
                "section_id": "opening",
                "title": "Chapter 7: Basic Shapes",
                "narration_script": "Welcome to basic shapes.",
                "duration_seconds": 5,
                "render_mode": "manim",
                "source_block_type": "intro",
                "source_selectors": [{"page": 1, "start": 1, "end": 2}],
            }
        ],
    }
    plan = compile_plan(document, spec)
    assert plan["sections"][0]["source_block_ids"] == [
        "p0001-b0001",
        "p0001-b0002",
    ]
    assert plan["metadata"]["mapped_required_source_block_count"] == 2


def test_source_delivery_introduces_bullet_objectives_with_colon() -> None:
    document = {"blocks": [
        {"block_id": "p0001-b0001", "page_number": 1, "block_type": "paragraph",
         "semantic_role": "lesson_content", "source_text": "Learners will be able to",
         "required_for_coverage": True},
        {"block_id": "p0001-b0002", "page_number": 1, "block_type": "bullet",
         "semantic_role": "lesson_content", "source_text": "Describe rotation.",
         "required_for_coverage": True},
    ]}
    spec = {"metadata": {"delivery_policy": {}}, "sections": [{
        "section_id": "objectives", "title": "Learning Objectives",
        "description": "Show source objectives.", "animation_action": "Reveal each line.",
        "source_delivery": True, "render_mode": "hyperframes",
        "source_selectors": [{"page": 1, "start": 1, "end": 2}],
    }]}
    section = compile_plan(document, spec)["sections"][0]
    assert "Learners will be able to: Describe rotation." in section["narration_script"]
    assert section["teaching_contract"]["source_excerpts"][0]["verbatim_text"] == "Learners will be able to"


def test_source_delivery_keeps_period_before_closing_curly_quote() -> None:
    document = {"blocks": [
        {"block_id": "p0001-b0001", "page_number": 1, "block_type": "section_heading",
         "semantic_role": "lesson_content", "source_text": "Let's Learn More!",
         "required_for_coverage": True},
        {"block_id": "p0001-b0002", "page_number": 1, "block_type": "paragraph",
         "semantic_role": "lesson_content", "source_text": "It is called the “lungs of the Earth.”",
         "required_for_coverage": True},
    ]}
    spec = {"metadata": {"delivery_policy": {}}, "sections": [{
        "section_id": "fact", "title": "Let's Learn More!",
        "description": "Show the source fact.", "animation_action": "Reveal the fact.",
        "source_delivery": True, "render_mode": "hyperframes",
        "source_selectors": [{"page": 1, "start": 1, "end": 2}],
    }]}
    section = compile_plan(document, spec)["sections"][0]
    assert section["narration_script"] == (
        "Let's Learn More! It is called the “lungs of the Earth.”"
    )
