from tools.structure.textbook_video_pipeline import detect_chapters_from_page_texts


def test_detects_toc_and_resolves_front_matter_offset_from_titles():
    pages = [
        "Cover",
        "CONTENT Lesson 1 - Being Polite 7 - 10 Lesson 2 - Lovely Rose 11 - 14",
        "Preface",
        "More front matter",
        "Lesson 1 Being Polite Warm Up",
        "lesson content",
        "lesson content",
        "Lesson 2 Lovely Rose The Poem",
        "poem content",
    ]

    chapters = detect_chapters_from_page_texts(pages)

    assert [(item["chapter"], item["title"]) for item in chapters] == [
        (1, "Being Polite"),
        (2, "Lovely Rose"),
    ]
    assert chapters[0]["start_pdf_page"] == 5
    assert chapters[0]["end_pdf_page"] == 7
    assert chapters[1]["start_pdf_page"] == 8
    assert chapters[1]["end_pdf_page"] == 9


def test_refuses_to_guess_when_no_multi_chapter_toc_exists():
    assert detect_chapters_from_page_texts(["One lesson only"]) == []


def test_detects_volume_toc_without_separator_after_chapter_number():
    pages = [
        "Cover",
        (
            "CONTENT Page Chapter 7 Basic Shapes 7 - 23 "
            "Chapter 8 Patterns and Symmetry 24 - 38 "
            "Chapter 9 Metric Measures 39 - 54"
        ),
        "Preface",
        "More front matter",
        "Another front matter page",
        "Chapter structure",
        "Spiral Learning Chapter - 7 : Basic Shapes Knowing about polygons",
        "Basic Shapes continued",
        "Patterns are found all around us. Chapter - 8 : Patterns and Symmetry",
        "Metric Measures Chapter 9",
    ]

    chapters = detect_chapters_from_page_texts(pages)

    assert [chapter["chapter"] for chapter in chapters] == [7, 8, 9]
    assert chapters[0]["title"] == "Basic Shapes"
    assert chapters[0]["start_pdf_page"] == 7
