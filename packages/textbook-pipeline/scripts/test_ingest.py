"""Test script to verify the full ingestion pipeline from PDF to ChapterNode.

This script tests the 'First Mile':
PDF -> Docling (Parsing) -> SubjectRouter (Classification) -> ChapterGrouper (Structuring) -> ChapterNode (JSON)

It verifies that we are capturing the FULL content of the chapter, not a summary,
and correctly identifies headers, theoretical sections, and exercises.
"""

import logging
import json
from pathlib import Path
from dotenv import load_dotenv

# Initialize environment bridge
from lib import environment
load_dotenv()

from textbook_pipeline.wrappers.docling_client import DoclingClient
from textbook_pipeline.core.ingestion.subject_router import SubjectRouter
from textbook_pipeline.core.ingestion.chapter_grouper import ChapterGrouper
from textbook_pipeline.models import Subject

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("test_ingest")

# Input PDFs provided by user
TEST_PDFS = [
    r"C:\Users\user\Downloads\RPS - ENGLISH - CLASS 1 - INDIVIDUAL - A (2026) PRINTFILE (2).pdf",
    r"C:\Users\user\Downloads\RPS - MATHS - CLASS 1 - INDIVIDUAL - B (2026) PRINTFILE.pdf",
    r"C:\Users\user\Downloads\RPS - ENGLISH - CLASS 5 - VOLUME - 1 (2026) PRINTFILE.pdf",
    r"C:\Users\user\Downloads\RPS - EVS - CLASS 4 - VOLUME - 1 (2026) PRINTFILE.pdf",
]

def run_test_on_pdf(pdf_path: str):
    print(f"\n{'='*80}\nTESTING PDF: {pdf_path}\n{'='*80}")
    
    try:
        # 1. Initialize clients
        docling_client = DoclingClient()
        # Use Groq API from .env
        import os
        router = SubjectRouter(api_key=os.getenv("GROQ_API_KEY"), model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"))
        
        # 2. Parsing (Docling)
        print("\n[1/3] Parsing PDF with Docling...")
        pdf_path_obj = Path(pdf_path)
        doc = docling_client.convert_pdf(pdf_path_obj)
        # To get the items for the grouper, we need to access the internal Docling document
        # Our DoclingClient.convert_pdf returns a ChapterNode, but we want the items for the grouper test
        # Let's use the converter directly for the test to see the raw items
        raw_result = docling_client.converter.convert(pdf_path_obj)
        doc_items = list(raw_result.document.iterate_items())
        print(f"  -> Extracted {len(doc_items)} items from PDF.")

        # 3. Routing (Subject/Grade detection)
        print("\n[2/3] Routing Subject & Grade...")
        # Use first 2000 chars for routing
        snippet = " ".join([item.text for item in doc_items[:50] if hasattr(item, 'text')])[:2000]
        subject, grade, textbook_id = router.route(snippet)
        print(f"  -> Detected: Subject={subject.value}, Grade={grade}, ID={textbook_id}")

        # 4. Grouping (Theoretical vs Exercise)
        print("\n[3/3] Structuring into ChapterNode...")
        grouper = ChapterGrouper(subject=subject, grade=grade)
        chapter_node = grouper.group_items(doc_items, textbook_id=textbook_id, source_pdf=pdf_path_obj)
        
        # 5. Analysis of results
        print(f"\n--- RESULTS FOR {textbook_id} ---")
        print(f"Chapter Title: {chapter_node.title}")
        print(f"Total Sections: {len(chapter_node.sections)}")
        
        theoretical = chapter_node.get_theoretical_sections()
        exercises = chapter_node.get_exercise_sections()
        
        print(f"Theoretical Sections: {len(theoretical)}")
        print(f"Exercise Sections: {len(exercises)}")
        print(f"Total Exercises found: {len(chapter_node.all_exercises())}")
        
        # Print a sample of the extracted sections to see if we missed anything
        print("\n--- Section Breakdown ---")
        for i, sec in enumerate(chapter_node.sections):
            type_str = "THEO" if sec.type == "theoretical" else "EXER"
            print(f"[{i}] {type_str} | {sec.title[:50]:<50} | Length: {len(sec.content_text)} chars")
            
        # Save result to JSON for inspection
        output_path = Path("projects/test_ingest") / f"{textbook_id}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(chapter_node.model_dump_json(indent=2))
        print(f"\nFull JSON saved to: {output_path}")

    except Exception as e:
        logger.error(f"Critical failure on {pdf_path}: {e}", exc_info=True)

if __name__ == "__main__":
    for pdf in TEST_PDFS:
        run_test_on_pdf(pdf)
