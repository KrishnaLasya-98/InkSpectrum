from tools.structure.educational_delivery_naming import (
    canonical_subject_label,
    delivery_folder_name,
    delivery_video_name,
    infer_book_part,
)


def test_class_subject_folder_name_is_canonical():
    assert delivery_folder_name(4, "english") == "Class-4-English"
    assert delivery_folder_name(1, "general knowledge") == "Class-1-GK"
    assert delivery_folder_name(1, "EVS") == "Class-1-EVS"


def test_explicit_volume_is_book_part_but_pages_suffix_is_not():
    assert infer_book_part(
        "RPS - ENGLISH - CLASS 4 - VOLUME - 1 (2026) PRINTFILE.pdf"
    ) == 1
    assert infer_book_part("chapter-export-pages-2.pdf") is None
    assert infer_book_part("English Class 4 Part 3.pdf") == 3


def test_video_name_contains_class_subject_part_chapter_and_title():
    assert delivery_video_name(
        grade=4,
        subject_label=canonical_subject_label("english"),
        book_part=1,
        chapter=2,
        chapter_title="Lovely Rose",
    ) == "Class-4-English-Part-01-Chapter-02-Lovely-Rose.mp4"
