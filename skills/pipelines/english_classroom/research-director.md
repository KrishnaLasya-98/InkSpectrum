---
mode: research-director
skill: pipelines/english_classroom/research-director
produces: [chapter_node]
tools_available: [opendataloader_extract, pymupdf_extract, docling_extract]
checkpoint_required: true
human_approval_default: false
success_criteria:
  - chapter_node JSON is written
  - section_count >= 3
review_focus:
  - heading hierarchy preserved
  - all images extracted
---

# English Classroom — Research Director

## Goal

Extract a complete ChapterNode from the input PDF.

## Tool selection

1. Try `opendataloader_extract` first (best for structured textbooks).
2. If OpenDataLoader JSON is missing, fall back to `pymupdf_extract`.
3. If the PDF has complex tables, use `docling_extract`.

## Input

- `pdf_path`: path to the PDF file
- `subject`: `english`
- `grade`: integer (1-10)
- `textbook_id`: string identifier

## Output

- `chapter_node` JSON written to `.kilo/artifacts/<run_id>/chapter_node.json`

## Quality checks

- Verify `section_count >= 3` before proceeding.
- Verify every section has non-empty `content_text`.
- Verify `page_range` is valid (`start <= end`).