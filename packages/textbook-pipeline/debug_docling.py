import fitz
from docling.document_converter import DocumentConverter
from pathlib import Path

PDF_PATH = Path(r"C:\Users\user\Downloads\RPS - ENGLISH - CLASS 1 - INDIVIDUAL - A (2026) PRINTFILE (2).pdf")

# Extract pages 6-20 (content pages)
doc = fitz.open(PDF_PATH)
content_doc = fitz.open()
content_doc.insert_pdf(doc, from_page=5, to_page=19)
chunk_path = Path("D:/new_video_pip/textbook-pipeline/debug_content.pdf")
content_doc.save(chunk_path)
content_doc.close()
doc.close()

print("Running Docling on content pages...")
converter = DocumentConverter()
result = converter.convert(chunk_path)
raw_doc = result.document

print(f"\n=== DOCLING EXTRACTION DEBUG ===")
print(f"Document name: {raw_doc.name}")
print(f"Total pages: {len(raw_doc.pages)}")

# Check all items and their labels
items_by_label = {}
for i, item in enumerate(raw_doc.iterate_items()):
    label = getattr(item, 'label', 'NO_LABEL')
    text = getattr(item, 'text', '')[:100]
    if label not in items_by_label:
        items_by_label[label] = []
    items_by_label[label].append((i, text))

print(f"\n=== ITEM LABELS FOUND ===")
for label, items in items_by_label.items():
    print(f"\n{label} ({len(items)} items):")
    for idx, text in items[:5]:  # Show first 5
        print(f"  [{idx}] {text}")

# Also check raw text from PyMuPDF for comparison
print(f"\n=== PYMUPDF RAW TEXT (first 3 pages) ===")
pdf_doc = fitz.open(chunk_path)
for p in range(min(3, len(pdf_doc))):
    page = pdf_doc[p]
    text = page.get_text()
    print(f"\n--- Page {p+1} ---")
    print(text[:500])
pdf_doc.close()