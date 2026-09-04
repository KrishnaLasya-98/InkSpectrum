"""Test if PyMuPDF properly extracts body text from pages 17-25 of the English Class 1 PDF."""

import pymupdf as fitz

PDF_PATH = r"C:\Users\user\Downloads\RPS - ENGLISH - CLASS 1 - INDIVIDUAL - A (2026) PRINTFILE (2).pdf"

doc = fitz.open(PDF_PATH)
print(f"Total pages: {len(doc)}")

# Pages 17-25 = indexes 16-24
for page_num in range(16, 26):
    if page_num >= len(doc):
        break
    page = doc[page_num]
    text = page.get_text("text")
    print(f"\n{'='*60}")
    print(f"PAGE {page_num + 1}")
    print(f"{'='*60}")
    print(text[:1500])
    print("..." if len(text) > 1500 else "")

doc.close()
