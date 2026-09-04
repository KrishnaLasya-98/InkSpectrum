import os
import sys
from pathlib import Path
import json

# 3. Import our connectors and logic
try:
    from textbook_pipeline.wrappers.docling_client import DoclingClient
    from textbook_pipeline.core.ingestion.subject_router import SubjectRouter
    from textbook_pipeline.core.ingestion.chapter_grouper import ChapterGrouper
    from textbook_pipeline.core.ingestion.pdf_splitter import PDFSplitter
except ImportError as e:
    print(f"Critical Import Error: {e}")
    exit(1)

# File Path - targeting the content pages (6-20)
PDF_PATH = Path(r"C:\Users\user\Downloads\RPS - ENGLISH - CLASS 1 - INDIVIDUAL - A (2026) PRINTFILE (2).pdf")
PROJECT_DIR = Path("D:/new_video_pip/textbook-pipeline/projects/english_class1_content")
PROJECT_DIR.mkdir(parents=True, exist_ok=True)

def run_content_extraction():
    print(f"\n--- STARTING CONTENT EXTRACTION for {PDF_PATH.name} ---")
    
    # Step 0: Extract only the content pages (6-20) to avoid front matter
    print("\n[Step 0/4] Extracting content pages (6-20)...")
    import fitz
    doc = fitz.open(PDF_PATH)
    content_doc = fitz.open()
    content_doc.insert_pdf(doc, from_page=5, to_page=19)  # 0-indexed: pages 6-20
    chunk_path = PROJECT_DIR / "content_pages_6_20.pdf"
    content_doc.save(chunk_path)
    content_doc.close()
    doc.close()
    print(f"Saved content chunk to: {chunk_path}")

    # Step A: Ingest via Docling
    print("\n[Step 1/4] Parsing Content Chunk via Docling...")
    from docling.document_converter import DocumentConverter
    converter = DocumentConverter()
    result = converter.convert(chunk_path) 
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
        source_pdf=chunk_path
    )
    
    # Save Result
    output_file = PROJECT_DIR / "content_blueprint.json"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(chapter_node.model_dump_json(indent=2))
    
    print(f"\n✅ SUCCESS! Content Blueprint saved to: {output_file}")
    return chapter_node

if __name__ == "__main__":
    try:
        result = run_content_extraction()
        if result:
            print("\n=== CONTENT EXTRACTION SUMMARY ===")
            print(f"Chapter Title: {result.title}")
            print(f"Subject: {result.subject}")
            print(f"Grade: {result.grade}")
            print(f"Total Sections: {len(result.sections)}")
            print(f"Theoretical Sections: {len([s for s in result.sections if s.type == 'THEORY'])}")
            print(f"Exercises Detected: {sum(len(s.exercises) if s.type == 'EXERCISE' else 0 for s in result.sections)}")
            print("-" * 30)
    except Exception as e:
        print(f"\n❌ ERROR during extraction: {e}")
        import traceback
        traceback.print_exc()