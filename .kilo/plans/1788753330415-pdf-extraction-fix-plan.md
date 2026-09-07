# PDF Extraction Fix Plan

## Current State Assessment

### What We Have
- 3 extractors: `DoclingExtractor`, `PdfmuxExtractor`, `PyMuPDFExtractor`
- Active runner: `run_pymupdf_extraction.py` (PyMuPDF)
- Existing output: `pymupdf_blueprint.json` (606 lines, 22 sections)
- Schema: `ChapterNode` → `SectionNode` → `ExerciseNode` with `figures`, `equations`, `tables` lists

### Critical Defects in Current Output

1. **Page range collapse**: Most sections show `page_range: [1,1]` or wrong pages even though content spans pages 12-17
2. **Content fragmentation**: `content_text` contains only table-of-contents snippets like `" 17 - 25"` instead of actual paragraph text
3. **Missing figures**: `figures: []` is empty for every section — images are never extracted or associated
4. **Heading truncation**: Titles like `"Lesson 2 -"`, `"Lesson 4 -"`, `"word."` — classifier splits lines mid-sentence
5. **Wrong section type**: `sec_19` (the story) is tagged `type: "exercise"` instead of `theoretical`
6. **Noise in content**: Footer text `"Rockland English - Class 1"` and page numbers bleed into `content_text`
7. **Reading order violation**: `sec_14` title is `"that rhymes with the word."` — clearly a continuation of `sec_13`, not a new section
8. **bbox unused for alignment**: `DoclingRef` stores bbox in some places but never used to spatially align text with images

## Root Causes

| Issue | Root Cause |
|-------|-----------|
| Wrong page ranges | `page` field in `TextBlock` comes from PyMuPDF span bbox, but `extract_chapters` passes `block.page` (1-indexed page number) correctly. The bug is that the TOC page (page 1) is parsed as content, creating phantom sections with `page_range: [1,1]`. Real content from pages 12-17 gets a separate section but some inherits wrong range. |
| Fragmented content | `extract_text_blocks` iterates `page.get_text("dict")["blocks"]` → `lines` → `spans`, creating one `TextBlock` per span. A single paragraph becomes 5-10 blocks. The section builder concatenates with `" " + block.text`, but heading detection fires on every bold/large span, splitting sections at every line. |
| Missing figures | `extract_text_blocks` only processes text spans. PyMuPDF image blocks (`block["type"] == 1`) are never extracted. No image extraction path exists. |
| Heading truncation | `classify_block` checks font size/centered/bold on individual spans. A multi-line heading like `"Lesson 2 -\n(Poem)\t1 - Love"` gets split because the second line is not bold/centered. |
| Wrong section type | `classify_section_type` uses keyword heuristics. The story section contains exercise-like words (`"tick"`, `"true or false"`) later in the same `content_text`, causing the whole section to flip to EXERCISE. |
| Noise in content | No header/footer filtering. Running headers (`"Rockland English - Class 1"`) and page numbers are included as regular text. |
| Reading order | No spatial sorting by y-coordinate within a page. Blocks from the same paragraph can appear in wrong order if the PDF stream is non-linear. |

## Plan

### Step 1: Fix PyMuPDFExtractor — single-pass, page-aware block extraction

**File**: `packages/textbook-pipeline/src/textbook_pipeline/core/ingestion/pymupdf_extractor.py`

1. Extract **page-level blocks** (not span-level) using `page.get_text("dict")`
2. For each block:
   - If `block["type"] == 0` (text): extract full text block with bbox, font size, flags
   - If `block["type"] == 1` (image): save image to temp dir, create `ImageAsset` candidate
   - Skip header/footer blocks using y-coordinate heuristics (top 10% / bottom 10% of page)
   - Skip repeating running headers by maintaining a set of seen header strings
3. Sort blocks within each page by `(bbox.y0, bbox.x0)` — top-to-bottom, left-to-right
4. Return structured blocks with: `text`, `page`, `bbox`, `font_size`, `is_bold`, `block_type`, `images` (list of image assets found on this page)

### Step 2: Fix section detection — merge fragmented headings

**File**: `packages/textbook-pipeline/src/textbook_pipeline/core/ingestion/pymupdf_extractor.py`

1. Replace per-span heading detection with **page-level heading detection**:
   - A heading is a text block where `font_size > threshold` AND `is_bold` AND `is_centered`
   - Merge consecutive heading-like blocks into a single title (concatenate with space)
   - A heading must be followed by at least one content block to be valid
2. Add **continuation guard**: if a "heading" block is < 30 chars and doesn't match lesson/unit pattern, treat it as content, not a heading
3. Section type classification must happen **per-section** after content is accumulated, not per-block. Use the full accumulated `content_text` + `title` for classification.

### Step 3: Fix page range propagation

**File**: `packages/textbook-pipeline/src/textbook_pipeline/core/ingestion/pymupdf_extractor.py`

1. When creating a `SectionNode`, set `page_start = block.page` and `page_end = block.page`
2. When appending content to a section, update: `page_end = max(page_end, block.page)`
3. Remove the TOC page from consideration OR detect TOC vs content using layout heuristics (TOC has many short lines with page numbers, low text density)

### Step 4: Associate images with nearest text section

**File**: `packages/textbook-pipeline/src/textbook_pipeline/core/ingestion/pymupdf_extractor.py`

1. Extract images with their bbox coordinates
2. For each image, find the **nearest text block on the same page** (by y-distance)
3. Assign the image to that section's `figures` list
4. If image appears between two sections, assign to the section whose content precedes it (smaller y)
5. Store image as `ImageAsset` with `file_path`, `page_number`, `bbox`, `caption=None`

### Step 5: Filter noise (headers, footers, page numbers)

**File**: `packages/textbook-pipeline/src/textbook_pipeline/core/ingestion/pymupdf_extractor.py`

1. Running header filter: collect all text blocks from top 15% of each page. If the same string appears on 3+ consecutive pages, mark it as header and drop it.
2. Footer filter: drop blocks from bottom 10% of page if they contain only page numbers or publisher marks.
3. Page number filter: drop isolated numbers that match `^\d+$` and appear near page edges.

### Step 6: Unify schema — ensure `figures`, `equations`, `tables` are populated

**File**: `packages/textbook-pipeline/src/textbook_pipeline/models/chapter.py`

1. Add `bbox` field to `ImageAsset` for spatial alignment
2. Ensure `SectionNode.figures` is typed as `list[ImageAsset]` with proper defaults
3. Add `raw_blocks: list[dict]` optional field to `SectionNode` for debugging/QA

### Step 7: Add extraction QA / validation

**File**: `packages/textbook-pipeline/src/textbook_pipeline/core/ingestion/extractor.py` (new method)

1. Add `validate_extraction(chapter: ChapterNode) -> list[str]` that checks:
   - No section has `page_range[0] > page_range[1]`
   - No section title is truncated (ends with `-`, `:`, or is < 3 chars)
   - No section has `content_text` that is only page numbers/TOC entries
   - Total sections > 0
   - No duplicate section IDs
2. Call this validation at the end of `extract_chapters` and log warnings

### Step 8: Add integration test fixture

**File**: `packages/textbook-pipeline/tests/test_extraction.py` (new)

1. Create a test that loads the known-good `pymupdf_blueprint.json` or a minimal synthetic PDF
2. Assert: sections are in page order, no empty `content_text`, `figures` populated for pages with images, page ranges are correct

## Execution Order

1. Step 1 (block extraction) — unblocks everything else
2. Step 3 (page ranges) — quick win, depends on Step 1
3. Step 5 (noise filtering) — depends on Step 1
4. Step 2 (heading detection) — depends on Step 1
5. Step 4 (image association) — depends on Step 1
6. Step 6 (schema tweaks) — can run in parallel
7. Step 7 (QA validation) — after Steps 1-5
8. Step 8 (tests) — last

## Validation Criteria

Before locking this logic for production, the extraction must pass:

- [ ] All sections have `page_range` that matches actual PDF pages
- [ ] `content_text` contains real paragraph text, not TOC snippets
- [ ] No truncated titles (`"Lesson 2 -"`, `"word."`)
- [ ] `figures` list is non-empty for pages that contain images
- [ ] Sections appear in correct reading order (by page number, then y-position)
- [ ] No footer/header noise in `content_text`
- [ ] Section types are correct: story/theory = `theoretical`, exercises = `exercise`

## Dynamic Input Handling Strategy

### Problem
Current runners use hardcoded paths like `Path(r"C:\Users\user\Downloads\RPS - ENGLISH - CLASS 1...")`. This breaks when:
- PDFs change names or locations
- Running on WSL vs Windows
- Running in CI/CD
- Processing batch inputs

### Recommendation: Configurable Runner with Three Input Layers

**Layer 1: CLI Arguments** (highest priority)
```bash
python -m textbook_pipeline ingest --pdf /path/to/file.pdf --subject english --grade 1 --output projects/lesson1
```

**Layer 2: Environment Variables** (fallback)
```bash
export TEXTBOOK_PDF_PATH=/path/to/file.pdf
export TEXTBOOK_SUBJECT=english
export TEXTBOOK_GRADE=1
python -m textbook_pipeline ingest
```

**Layer 3: Config File** (optional, for batch processing)
```yaml
# extraction_config.yaml
pdf_path: /path/to/file.pdf
subject: english
grade: 1
output_dir: projects/lesson1
```

### Implementation Rules

1. **Never hardcode absolute paths** in any module under `packages/textbook-pipeline/src/`
2. **All runner scripts** (`run_*.py`) must accept input via CLI args or env vars
3. **Default output directory**: `projects/<subject>_<grade>/` relative to package root
4. **PDF validation**: Before processing, verify file exists, is readable, and has `.pdf` extension
5. **Path normalization**: Use `Path.resolve()` and convert Windows paths to POSIX for WSL compatibility

### Example: Dynamic Ingestion Runner

```python
# packages/textbook-pipeline/src/textbook_pipeline/cli.py
@app.command()
def ingest(
    pdf: Path = typer.Argument(..., exists=True, help="Input PDF path"),
    subject: str = typer.Option("english", help="Subject: english, math, science, social"),
    grade: int = typer.Option(1, help="Grade level (1-10)"),
    output: Path = typer.Option(None, help="Output directory"),
):
    """Extract chapter structure from PDF."""
    subject_enum = Subject(subject)
    output = output or Path(f"projects/{subject}_grade{grade}")
    output.mkdir(parents=True, exist_ok=True)
    
    extractor = PyMuPDFExtractor()
    chapter = extractor.extract(pdf, subject_enum, grade, textbook_id=pdf.stem)
    
    # Save blueprint
    blueprint_path = output / "blueprint.json"
    blueprint_path.write_text(chapter.model_dump_json(indent=2))
    print(f"✅ Saved blueprint to {blueprint_path}")
```

### Testability

- Unit tests must use **fixture PDFs** in `packages/textbook-pipeline/tests/fixtures/`
- No test should reference `C:\Users\...` or `/home/user/...` paths
- Use `tmp_path` pytest fixture for output directories
- CI runs against synthetic/minimal PDFs, not real textbooks

### Validation

Before finalizing any extraction logic:
- [ ] All runners accept `--pdf` argument
- [ ] No hardcoded paths in `src/textbook_pipeline/`
- [ ] Tests pass on Windows and WSL
- [ ] `python -m textbook_pipeline ingest --pdf <any_path>` works without code changes

## Dynamic Input Handling Strategy

### Problem
Current runners use hardcoded paths like `Path(r"C:\Users\user\Downloads\RPS - ENGLISH - CLASS 1...")`. This breaks when:
- PDFs change names or locations
- Running on WSL vs Windows
- Running in CI/CD
- Processing batch inputs

### Recommendation: Configurable Runner with Three Input Layers

**Layer 1: CLI Arguments** (highest priority)
```bash
python -m textbook_pipeline ingest --pdf /path/to/file.pdf --subject english --grade 1 --output projects/lesson1
```

**Layer 2: Environment Variables** (fallback)
```bash
export TEXTBOOK_PDF_PATH=/path/to/file.pdf
export TEXTBOOK_SUBJECT=english
export TEXTBOOK_GRADE=1
python -m textbook_pipeline ingest
```

**Layer 3: Config File** (optional, for batch processing)
```yaml
# extraction_config.yaml
pdf_path: /path/to/file.pdf
subject: english
grade: 1
output_dir: projects/lesson1
```

### Implementation Rules

1. **Never hardcode absolute paths** in any module under `packages/textbook-pipeline/src/`
2. **All runner scripts** (`run_*.py`) must accept input via CLI args or env vars
3. **Default output directory**: `projects/<subject>_<grade>/` relative to package root
4. **PDF validation**: Before processing, verify file exists, is readable, and has `.pdf` extension
5. **Path normalization**: Use `Path.resolve()` and convert Windows paths to POSIX for WSL compatibility

### Example: Dynamic Ingestion Runner

```python
# packages/textbook-pipeline/src/textbook_pipeline/cli.py
@app.command()
def ingest(
    pdf: Path = typer.Argument(..., exists=True, help="Input PDF path"),
    subject: str = typer.Option("english", help="Subject: english, math, science, social"),
    grade: int = typer.Option(1, help="Grade level (1-10)"),
    output: Path = typer.Option(None, help="Output directory"),
):
    """Extract chapter structure from PDF."""
    subject_enum = Subject(subject)
    output = output or Path(f"projects/{subject}_grade{grade}")
    output.mkdir(parents=True, exist_ok=True)
    
    extractor = PyMuPDFExtractor()
    chapter = extractor.extract(pdf, subject_enum, grade, textbook_id=pdf.stem)
    
    # Save blueprint
    blueprint_path = output / "blueprint.json"
    blueprint_path.write_text(chapter.model_dump_json(indent=2))
    print(f"✅ Saved blueprint to {blueprint_path}")
```

### Testability

- Unit tests must use **fixture PDFs** in `packages/textbook-pipeline/tests/fixtures/`
- No test should reference `C:\Users\...` or `/home/user/...` paths
- Use `tmp_path` pytest fixture for output directories
- CI runs against synthetic/minimal PDFs, not real textbooks

### Validation

Before finalizing any extraction logic:
- [ ] All runners accept `--pdf` argument
- [ ] No hardcoded paths in `src/textbook_pipeline/`
- [ ] Tests pass on Windows and WSL
- [ ] `python -m textbook_pipeline ingest --pdf <any_path>` works without code changes
