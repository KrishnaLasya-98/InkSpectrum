import os
import sys
from pathlib import Path
import json

# 1. Force project root into sys.path
PROJECT_ROOT = Path("D:/new_video_pip/textbook-pipeline").absolute()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 2. Initialize Environment
try:
    from lib.environment import initialize_environment
    initialize_environment()
    print("✅ Environment bridge active.")
except ImportError as e:
    print(f"Critical Import Error: {e}")
    exit(1)

# 3. Import our connectors and logic
try:
    from wrappers.docling_client import DoclingClient
    from lib.textbook_ingest.subject_router import SubjectRouter
    from lib.textbook_ingest.chapter_grouper import ChapterGrouper
    from lib.textbook_ingest.pdf_splitter import PDFSplitter
except ImportError as e:
    print(f"Critical Import Error: {e}")
    exit(1)

# File Path
PDF_PATH = Path(r"C:\Users\user\Downloads\RPS - ENGLISH - CLASS 1 - INDIVIDUAL - A (2026) PRINTFILE (2).pdf")
PROJECT_DIR = Path("D:/new_video_pip/textbook-pipeline/projects/english_class1_chunked")
PROJECT_DIR.mkdir(parents=True, exist_ok=True)

def run_chunked_phase1():
    print(f"\n--- STARTING CHUNKED PHASE 1: Ingestion for {PDF_PATH.name} ---")
    
    # Step 0: Chunking the PDF
    # We split the PDF into small chunks (e.g., 5 pages) to ensure the CPU doesn't timeout
    print("\n[Step 0/4] Chunking PDF into smaller segments...")
    splitter = PDFSplitter(chunk_size=5)
    chunks_dir = PROJECT_DIR / "chunks"
    chunks = splitter.split_pdf(PDF_PATH, chunks_dir)
    print(f"Created {len(chunks)} chunks in {chunks_dir}")

    # For the test, we will only process the first chunk to verify the pipeline
    test_chunk = chunks[0]
    print(f"Processing test chunk: {test_chunk.name}")

    # Step A: Ingest via Docling
    print("\n[Step 1/4] Parsing Chunk via Docling...")
    client = DoclingClient()
    from docling.document_converter import DocumentConverter
    converter = DocumentConverter()
    result = converter.convert(test_chunk) 
    raw_doc = result.document
    
    if not raw_doc:
        print("Error: Docling returned no content.")
        return None

    # Step B: Route Subject & Grade
    print("\n[Step 2/4] Routing Subject & Grade via LLM...")
    router = SubjectRouter()
    subject_info = router.route_subject(raw_doc)
    print(f"Detected: Subject={subject_info['subject']}, Grade={subject_info['grade']}")
    
    # Step C: Group into Chapter Structure
    print("\n[Step 3/4] Grouping into Pedagogical Tree...")
    grouper = ChapterGrouper(
        subject=subject_info['subject'], 
        grade=subject_info['grade']
    )
    chapter_node = grouper.group_into_chapter(
        raw_doc=raw_doc, 
        subject_info=subject_info,
        textbook_id=subject_info.get('textbook_id', 'class1_english'),
        source_pdf=test_chunk
    )
    
    # Save Result
    output_file = PROJECT_DIR / "mini_blueprint.json"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(chapter_node.model_dump_json(indent=2))
    
    print(f"\n✅ SUCCESS! Chunked Blueprint saved to: {output_file}")
    return chapter_node

if __name__ == "__main__":
    try:
        result = run_chunked_phase1()
        if result:
            print("\n=== PHASE 1 CHUNKED EXTRACTION SUMMARY ===")
            print(f"Chapter Title: {result.title}")
            print(f"Subject: {result.subject}")
            print(f"Grade: {result.grade}")
            print(f"Theoretical Sections: {len([s for s in result.sections if s.type == 'THEORY'])}")
            print(f"Exercises Detected: {sum(len(s.exercises) if s.type == 'EXERCISE' else 0 for s in result.sections)}")
            print("-" * 30)
    except Exception as e:
        print(f"\n❌ ERROR during Phase 1: {e}")
        import traceback
        traceback.print_exc()
