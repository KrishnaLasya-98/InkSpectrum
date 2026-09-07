import fitz
from pathlib import Path
from textbook_pipeline.core.ingestion.pymupdf_extractor import PyMuPDFExtractor

pdf = Path(r"C:\Users\user\Downloads\RPS - ENGLISH - CLASS 1 - INDIVIDUAL - A (2026) PRINTFILE (2)-pages-2.pdf")
doc = fitz.open(pdf)
page = doc[2]
blocks = page.get_text("dict")["blocks"]

extractor = PyMuPDFExtractor()
for i, b in enumerate(blocks):
    if b.get("type") == 1:
        print(f"Block {i}: type={b.get('type')}, bbox={b.get('bbox')}")
        try:
            imgs = extractor._extract_images(page, [b], 3)
            print(f"  Extracted {len(imgs)} images")
            for img in imgs:
                print(f"    - {img.file_path}")
        except Exception as e:
            print(f"  Error: {e}")

doc.close()
