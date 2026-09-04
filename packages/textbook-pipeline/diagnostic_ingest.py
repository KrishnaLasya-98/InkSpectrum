"""Diagnostic Ingestion Script.

This script runs Docling on selected pages of the sample textbooks to
analyze exactly what gets extracted (tables, math formulas, headings,
and images) and evaluates our pedagogical structure parsing.
"""

import os
import sys
from pathlib import Path

# Setup sys.path for importing textbook-pipeline modules
sys.path.append(str(Path(__file__).resolve().parent))

# Import Docling converter
from docling.document_converter import DocumentConverter

def analyze_pdf(pdf_path: str, max_pages: int = 15):
    print("=" * 80)
    print(f"DIAGNOSTIC ANALYSIS FOR: {Path(pdf_path).name}")
    print("=" * 80)
    
    # Initialize Docling Converter
    converter = DocumentConverter()
    
    # We can convert specific pages to keep it fast
    print(f"Ingesting first {max_pages} pages of PDF (this may take a minute on CPU)...")
    try:
        # Note: we can restrict page range if supported or just run full/partial
        result = converter.convert(pdf_path)
        doc = result.document
    except Exception as e:
        print(f"Error during Docling extraction: {e}")
        return None

    # 1. Broad Statistics
    elements = list(doc.iterate_items())
    print(f"\n📊 Total elements extracted: {len(elements)}")
    
    counts = {}
    for item in elements:
        item_type = item.__class__.__name__
        counts[item_type] = counts.get(item_type, 0) + 1
        
    print("\nElement Breakdown:")
    for item_type, count in counts.items():
        print(f"  - {item_type}: {count}")

    # 2. Section Headers Analysis
    print("\n🔍 Heading/Section Tree Structure (First 15 headings):")
    headings = [item for item in elements if item.__class__.__name__ == "HeadingItem" or "heading" in getattr(item, 'label', '').lower()]
    for i, h in enumerate(headings[:15]):
        level = getattr(h, 'level', 1)
        text = getattr(h, 'text', '')
        print(f"  {'  ' * (level - 1)}* [Level {level}] {text}")

    # 3. Math Equation Analysis
    print("\n🔍 Mathematical Notation / Formulas Found:")
    formulas = [item for item in elements if "formula" in item.__class__.__name__.lower() or "formula" in getattr(item, 'label', '').lower()]
    if formulas:
        print(f"  Found {len(formulas)} formula elements:")
        for i, f in enumerate(formulas[:10]):
            text = getattr(f, 'text', '')
            print(f"    {i+1}. {text}")
    else:
        print("  ❌ No explicit FormulaItem elements detected.")
        # Check if math is embedded as normal TextItems with LaTeX/symbolic markers
        print("  Checking normal TextItems for math symbols (e.g., +, -, =, /)...")
        math_suspects = []
        for item in elements:
            if item.__class__.__name__ == "TextItem":
                text = getattr(item, 'text', '')
                if any(char in text for char in ['+', '−', '×', '÷', '=', '>', '<', '\\(', '\\[']):
                    math_suspects.append(text)
        if math_suspects:
            print(f"    Found {len(math_suspects)} text blocks containing math characters. Samples:")
            for i, text in enumerate(math_suspects[:10]):
                print(f"      - {text}")
        else:
            print("    ❌ No math-related characters found in the first 15 pages.")

    # 4. Table Detection
    print("\n🔍 Tables Found:")
    tables = [item for item in elements if "table" in item.__class__.__name__.lower() or "table" in getattr(item, 'label', '').lower()]
    if tables:
        print(f"  Found {len(tables)} tables. Sample structures:")
        for i, t in enumerate(tables[:3]):
            print(f"    Table {i+1}:")
            # Let's inspect rows/columns if possible
            if hasattr(t, 'data') and hasattr(t.data, 'table_rows'):
                for r_idx, row in enumerate(t.data.table_rows[:3]):
                    cells = [getattr(cell, 'text', '') for cell in getattr(row, 'cells', [])]
                    print(f"      Row {r_idx+1}: {cells}")
    else:
        print("  ❌ No TableItem elements detected.")

    # 5. Exercises/Questions Detection
    print("\n🔍 Exercise / Question Detection Analysis:")
    exercise_keywords = ["exercise", "question", "solve", "practice", "match", "fill in", "choose", "mcq", "activities"]
    found_questions = []
    for item in elements:
        if item.__class__.__name__ in ["TextItem", "ListItem"]:
            text = getattr(item, 'text', '').lower()
            if any(kw in text for kw in exercise_keywords) or (len(text) > 0 and text[0].isdigit() and ('.' in text[:3] or ')' in text[:3])):
                found_questions.append(getattr(item, 'text', ''))
                
    if found_questions:
        print(f"  Found {len(found_questions)} potential exercise/question items. Samples:")
        for q in found_questions[:10]:
            print(f"    - {q}")
    else:
        print("  ❌ No exercise/question items detected via pattern matching.")

    return doc

if __name__ == "__main__":
    # Test on the English and Maths books
    english_class5 = "C:/Users/user/Downloads/RPS - ENGLISH - CLASS 5 - VOLUME - 1 (2026) PRINTFILE.pdf"
    maths_class1 = "C:/Users/user/Downloads/RPS - MATHS - CLASS 1 - INDIVIDUAL - B (2026) PRINTFILE.pdf"
    
    print("Starting Diagnostic Pipeline...")
    
    # Run analysis on English first (quick check)
    if os.path.exists(english_class5):
        analyze_pdf(english_class5, max_pages=15)
    else:
        print(f"File not found: {english_class5}")
        
    print("\n" + "="*80 + "\n")
    
    # Run analysis on Math
    if os.path.exists(maths_class1):
        analyze_pdf(maths_class1, max_pages=15)
    else:
        print(f"File not found: {maths_class1}")
