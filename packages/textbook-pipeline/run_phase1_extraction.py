import os
import sys
from pathlib import Path
import json

# 3. Import our connectors and logic
try:
    from textbook_pipeline.wrappers.docling_client import DoclingClient
    from textbook_pipeline.core.ingestion.subject_router import SubjectRouter
    from textbook_pipeline.core.ingestion.chapter_grouper import ChapterGrouper
except ImportError as e:
    print(f"Critical Import Error: {e}")
    exit(1)

# File Path
PDF_PATH = r"C:\Users\user\Downloads\RPS - ENGLISH - CLASS 1 - INDIVIDUAL - A (2026) PRINTFILE (2).pdf"
OUTPUT_DIR = Path("D:/new_video_pip/textbook-pipeline/projects/english_class1_ph1")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def run_phase1_extraction():
    print(f"\n--- STARTING PHASE 1: Ingestion for {Path(PDF_PATH).name} ---")
    
    # Step A: Ingest via Docling
    print("\n[Step 1/3] Parsing PDF via Docling (First 20 Pages)...")
    client = DoclingClient()
    from docling.document_converter import DocumentConverter
    converter = DocumentConverter()
    result = converter.convert(PDF_PATH) 
    raw_doc = result.document
    
    if not raw_doc:
        print("Error: Docling returned no content.")
        return None

    # Step B: Route Subject & Grade
    print("\n[Step 2/3] Routing Subject & Grade via LLM...")
    router = SubjectRouter()
    subject_info = router.route_subject(raw_doc)
    print(f"Detected: Subject={subject_info['subject']}, Grade={subject_info['grade']}")
    
    # Step C: Group into Chapter Structure
    print("\n[Step 3/3] Grouping into Pedagogical Tree...")
    # The Grouper needs the subject and grade to initialize
    grouper = ChapterGrouper(
        subject=subject_info['subject'], 
        grade=subject_info['grade']
    )
    chapter_node = grouper.group_into_chapter(
        raw_doc=raw_doc, 
        subject_info=subject_info,
        textbook_id=subject_info.get('textbook_id', 'class1_english'),
        source_pdf=Path(PDF_PATH)
    )
    
    # Save Result
    output_file = OUTPUT_DIR / "chapter_blueprint.json"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(chapter_node.model_dump_json(indent=2))
    
    print(f"\n✅ SUCCESS! Phase 1 Blueprint saved to: {output_file}")
    return chapter_node

if __name__ == "__main__":
    try:
        result = run_phase1_extraction()
        if result:
            print("\n=== PHASE 1 EXTRACTION SUMMARY ===")
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
