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
    print("Check if wrappers/docling_client.py and lib/textbook_ingest exist.")
    exit(1)

# File Path
PDF_PATH = r"C:\Users\user\Downloads\RPS - ENGLISH - CLASS 5 - VOLUME - 1 (2026) PRINTFILE.pdf"
OUTPUT_DIR = Path("D:/new_video_pip/textbook-pipeline/projects/english_class5_outdoor")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def run_test():
    print(f"\n--- Starting Extraction Test on: {Path(PDF_PATH).name} ---")
    
    # Step A: Ingest via Docling
    print("\n[Step 1/3] Parsing PDF via Docling (Lesson 1: Pages 7-12)...")
    client = DoclingClient()
    
    # We use the internal converter to get the raw doc for the SubjectRouter
    # The client class has the converter inside it
    raw_doc = client.converter.convert(PDF_PATH).document
    
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
    grouper = ChapterGrouper(subject=subject_info['subject'], grade=subject_info['grade'])
    # We pass the raw_doc and the subject_info
    chapter_node = grouper.group_into_chapter(raw_doc, subject_info)
    
    # Save Result
    output_file = OUTPUT_DIR / "chapter_1.json"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(chapter_node.model_dump_json(indent=2))
    
    print(f"\n✅ SUCCESS! Structured JSON saved to: {output_file}")
    return chapter_node

if __name__ == "__main__":
    try:
        result = run_test()
        if result:
            print("\n=== EXTRACTION SUMMARY ===")
            print(f"Chapter Title: {result.title}")
            print(f"Subject: {result.subject}")
            print(f"Grade: {result.grade}")
            print(f"Theoretical Sections: {len([s for s in result.sections if s.type == 'THEORY'])}")
            print(f"Glossary Items: {sum(len(s.items) if s.type == 'GLOSSARY' else 0 for s in result.sections)}")
            print(f"Exercises Detected: {sum(len(s.exercises) if s.type == 'EXERCISE' else 0 for s in result.sections)}")
            print("-" * 30)
            print("Check the JSON file for full detail.")
    except Exception as e:
        print(f"\n❌ ERROR during execution: {e}")
        import traceback
        traceback.print_exc()
