import fitz
pdf_path = r"C:\Users\user\Downloads\RPS - ENGLISH - CLASS 1 - INDIVIDUAL - A (2026) PRINTFILE (2)-pages-2.pdf"
doc = fitz.open(pdf_path)
page = doc[2]  # page 3 (0-indexed)
blocks = page.get_text("dict")["blocks"]
for i, b in enumerate(blocks):
    btype = b.get("type")
    print(f"Block {i}: type={btype}, keys={list(b.keys())}")
    if btype == 1:
        print(f"  Image block: {b.get('bbox')}")
doc.close()
