
import pymupdf as fitz
from pathlib import Path
import os
import json

pdf_paths = [
    r"C:\Users\user\Downloads\RPS - ENGLISH - CLASS 1 - INDIVIDUAL - A (2026) PRINTFILE (2).pdf",
    r"C:\Users\user\Downloads\RPS - MATHS - CLASS 1 - INDIVIDUAL - B (2026) PRINTFILE.pdf",
    r"C:\Users\user\Downloads\RPS - ENGLISH - CLASS 5 - VOLUME - 1 (2026) PRINTFILE.pdf",
    r"C:\Users\user\Downloads\RPS - EVS - CLASS 4 - VOLUME - 1 (2026) PRINTFILE.pdf"
]

print("=== STARTING PDF STRUCTURAL INSPECTION ===")
for p_str in pdf_paths:
    path = Path(p_str)
    print(f"File: {path.name}")
    print(f"Path: {p_str}")
    if not path.exists():
        print("ERROR: File does not exist!")
        print("-" * 50)
        continue
    
    file_size_mb = path.stat().st_size / (1024 * 1024)
    print(f"Size: {file_size_mb:.2f} MB")
    
    try:
        doc = fitz.open(path)
        print(f"Total Pages: {len(doc)}")
        
        # Check Table of Contents
        toc = doc.get_toc()
        print(f"TOC Entries count: {len(toc)}")
        if toc:
            print("Sample TOC (up to 10 entries):")
            for entry in toc[:10]:
                print(f"  {entry}")
        else:
            print("No programmatic TOC found in PDF metadata.")
            
        # Inspect page-by-page structure for first 10 pages to detect chapters
        print("First 10 pages inspection (identifying chapter markers):")
        for p_idx in range(min(15, len(doc))):
            page = doc[p_idx]
            text = page.get_text()
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            
            # Print page number and first 3 non-empty lines
            print(f"  Page {p_idx+1}: {lines[:4]} (Total lines: {len(lines)})")
            
        print("-" * 50)
    except Exception as e:
        print(f"Exception while parsing {path.name}: {e}")
        print("-" * 50)

print("=== INSPECTION COMPLETE ===")
