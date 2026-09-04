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
        from lib.textbook_ingest.subject_router import SubjectRouter
        from lib.textbook_ingest.pymupdf_extractor import extract_with_pymupdf
        from schemas import Subject, SectionType
except ImportError as e:
    print(f"Critical Import Error: {e}")
    exit(1)

# File Path - targeting the content pages (6-20)
PDF_PATH = Path(r"C:\Users\user\Downloads\RPS - ENGLISH - CLASS 1 - INDIVIDUAL - A (2026) PRINTFILE (2).pdf")
PROJECT_DIR = Path("D:/new_video_pip/textbook-pipeline/projects/english_class1_pymupdf")
PROJECT_DIR.mkdir(parents=True, exist_ok=True)

def run_pymupdf_extraction():
    print(f"\n--- STARTING PYMUPDF EXTRACTION for {PDF_PATH.name} ---")
    
    # Step 0: Extract content pages (6-20)
    print("\n[Step 0/3] Extracting content pages (6-20)...")
    import fitz
    doc = fitz.open(PDF_PATH)
    content_doc = fitz.open()
    content_doc.insert_pdf(doc, from_page=5, to_page=19)  # 0-indexed: pages 6-20
    chunk_path = PROJECT_DIR / "content_pages_6_20.pdf"
    content_doc.save(chunk_path)
    content_doc.close()
    doc.close()
    print(f"Saved content chunk to: {chunk_path}")

    # Step A: Route Subject & Grade using PyMuPDF text directly
    print("\n[Step 1/3] Routing Subject & Grade via LLM...")
    router = SubjectRouter()
    
    # Extract text from first few pages for routing
    doc = fitz.open(chunk_path)
    routing_text = ""
    for p in range(min(5, len(doc))):
        routing_text += doc[p].get_text()
    doc.close()
    
    # Use the router with extracted text AND the PDF path for filename-based detection
    subject_info = router.route_subject_text(routing_text, source_pdf_path=chunk_path)
    print(f"Detected: Subject={subject_info['subject']}, Grade={subject_info['grade']}")
    
    # Step B: Extract with PyMuPDF (bypassing Docling entirely)
    print("\n[Step 2/3] Extracting pedagogical structure with PyMuPDF...")
    chapter_node = extract_with_pymupdf(
        pdf_path=chunk_path,
        subject=subject_info['subject'],
        grade=subject_info['grade'],
        textbook_id=subject_info.get('textbook_id', 'class1_english')
    )
    
    # Save Result
    output_file = PROJECT_DIR / "pymupdf_blueprint.json"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(chapter_node.model_dump_json(indent=2))
    
    print(f"\n✅ SUCCESS! PyMuPDF Blueprint saved to: {output_file}")
    return chapter_node

if __name__ == "__main__":
    try:
        result = run_pymupdf_extraction()
        if result:
            print("\n=== PYMUPDF EXTRACTION SUMMARY ===")
            print(f"Chapter Title: {result.title}")
            print(f"Subject: {result.subject}")
            print(f"Grade: {result.grade}")
            print(f"Total Sections: {len(result.sections)}")
            print(f"Theoretical Sections: {len([s for s in result.sections if s.type == SectionType.THEORETICAL])}")
            print(f"Exercise Sections: {len([s for s in result.sections if s.type == SectionType.EXERCISE])}")
            total_exercises = sum(len(s.exercises) for s in result.sections)
            print(f"Individual Exercises: {total_exercises}")
            print("-" * 30)
            
            # Print first few sections for verification
            for i, sec in enumerate(result.sections[:5]):
                print(f"\n  Section {i+1}: {sec.title[:60]}... (Type: {sec.type})")
                print(f"  Content preview: {sec.content_text[:100]}...")
    except Exception as e:
        print(f"\n❌ ERROR during extraction: {e}")
        import traceback
        traceback.print_exc()