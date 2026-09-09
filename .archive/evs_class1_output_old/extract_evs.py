import json
import os
import re
import pymupdf

PDF_PATH = r"C:\Users\user\Downloads\RPS - EVS - CLASS 1 - INDIVIDUAL - B (2026) PRINTFILE-pages-2.pdf"
OUTPUT_DIR = r"D:\new_video_pip\packages\textbook-pipeline\projects\evs_class1_output"

# Read the opendataloader markdown for structured content
MD_PATH = os.path.join(
    OUTPUT_DIR,
    "odl_output",
    "RPS - EVS - CLASS 1 - INDIVIDUAL - B (2026) PRINTFILE-pages-2.md",
)
JSON_PATH = os.path.join(
    OUTPUT_DIR,
    "odl_output",
    "RPS - EVS - CLASS 1 - INDIVIDUAL - B (2026) PRINTFILE-pages-2.json",
)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def extract_images(doc):
    """Extract all images from the PDF with page mapping."""
    image_map = {}
    for page_idx in range(doc.page_count):
        page = doc[page_idx]
        img_list = page.get_images(full=True)
        page_imgs = []
        for img in img_list:
            xref = img[0]
            try:
                pix = pymupdf.Pixmap(doc, xref)
                if pix.n < 5:  # GRAY or RGB
                    pix1 = pix
                else:  # CMYK
                    pix1 = pymupdf.Pixmap(pymupdf.csRGB, pix)
                # Ensure RGB for PNG compatibility
                if pix1.colorspace and pix1.colorspace.name not in ("RGB", "Gray"):
                    pix1 = pymupdf.Pixmap(pymupdf.csRGB, pix1)
                img_name = f"page_{page_idx + 1}_img_{xref}.png"
                out_path = os.path.join(OUTPUT_DIR, "images", img_name)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                pix1.save(out_path)
                page_imgs.append({"xref": xref, "filename": img_name, "path": f"images/{img_name}"})
                pix1 = None
                pix = None
            except Exception:
                page_imgs.append({"xref": xref, "filename": f"page_{page_idx + 1}_img_{xref}.png", "path": None})
        image_map[page_idx + 1] = page_imgs
    return image_map


doc = pymupdf.open(PDF_PATH)
total_pages = doc.page_count

# Extract images
image_map = extract_images(doc)

# Read opendataloader markdown
with open(MD_PATH, encoding="utf-8") as md_file:
    odl_md = md_file.read()

# Build structured markdown output
lines = []
lines.append("# EVS Class 1 - Lesson 8: Animal Life")
lines.append("")
lines.append(f"**Source PDF:** `{os.path.basename(PDF_PATH)}`")
lines.append(f"**Total Pages:** {total_pages}")
lines.append(f"**Extraction Method:** OpenDataLoader (Markdown+JSON) + PyMuPDF (page-by-page)")
lines.append(f"**Extracted Images:** {sum(len(v) for v in image_map.values())}")
lines.append("")
lines.append("---")
lines.append("")

# Document structure / sections
lines.append("## Document Structure")
lines.append("")
lines.append("### Sections / Headings")
lines.append("")
headings = []
for line in odl_md.split("\n"):
    if re.match(r"^#{1,6}\s", line):
        headings.append(line)
lines.append("| # | Heading |")
lines.append("|---|---------|")
for i, h in enumerate(headings, 1):
    lines.append(f"| {i} | {h} |")
lines.append("")

# Key sections
key_sections = []
for h in headings:
    text = h.lstrip("# ").strip()
    key_sections.append(text)
lines.append("### Key Sections Identified")
lines.append("")
for s in key_sections:
    lines.append(f"- **{s}**")
lines.append("")
lines.append("---")
lines.append("")

# Page-by-page extraction
lines.append("## Page-by-Page Content")
lines.append("")
for page_num in range(1, total_pages + 1):
    page = doc[page_num - 1]
    text = page.get_text()
    imgs = image_map.get(page_num, [])
    words = page.get_text("words")
    blocks = page.get_text("blocks")

    lines.append(f"### Page {page_num}")
    lines.append("")
    lines.append(f"- **Text length:** {len(text)} characters")
    lines.append(f"- **Word count:** {len(words)}")
    lines.append(f"- **Text blocks:** {len(blocks)}")
    lines.append(f"- **Images:** {len(imgs)}")
    if imgs:
        lines.append("  - Image files:")
        for img in imgs:
            lines.append(f"    - `{img['filename']}` (xref: {img['xref']})")
    lines.append("")
    if text.strip():
        lines.append("**Text content:**")
        lines.append("```")
        lines.append(text.strip())
        lines.append("```")
    else:
        lines.append("*(No extractable text on this page)*")
    lines.append("")

    # Image descriptions from blocks
    if imgs:
        lines.append("**Image locations (from text blocks):**")
        for img in imgs:
            lines.append(f"- `{img['filename']}`")
        lines.append("")

lines.append("---")
lines.append("")

# Full structured content from OpenDataLoader
lines.append("## Full Structured Content (OpenDataLoader Markdown)")
lines.append("")
lines.append("The following is the full markdown output from OpenDataLoader, which")
lines.append("preserves headings, paragraphs, lists, and image references:")
lines.append("")
lines.append(odl_md)
lines.append("")

lines.append("---")
lines.append("")

# Section content with previews
lines.append("## Section Content Previews")
lines.append("")

# Parse sections from markdown
sections = []
current_title = None
current_content = []

for line in odl_md.split("\n"):
    heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
    if heading_match:
        if current_title is not None:
            sections.append({"title": current_title, "content": " ".join(current_content).strip()})
        current_title = heading_match.group(2).strip()
        current_content = []
    elif line.startswith("!["):
        current_content.append(f"[IMAGE: {line.strip()}]")
    elif line.strip():
        current_content.append(line.strip())

if current_title is not None:
    sections.append({"title": current_title, "content": " ".join(current_content).strip()})

if not sections:
    sections.append({"title": "(intro/no heading)", "content": odl_md.strip()[:500]})

lines.append("| # | Section Title | Content Preview (first 200 chars) |")
lines.append("|---|---|---|")
for i, sec in enumerate(sections, 1):
    preview = sec["content"][:200] if sec["content"] else "(empty)"
    preview_clean = preview.replace("|", "\\|").replace("\n", " ")
    lines.append(f"| {i} | {sec['title']} | {preview_clean} |")

lines.append("")

final_md = "\n".join(lines)

# Write the markdown file
md_out_path = os.path.join(OUTPUT_DIR, "evs_extracted.md")
with open(md_out_path, "w", encoding="utf-8") as f:
    f.write(final_md)
print(f"Written: {md_out_path}")

# Build summary JSON
summary = {
    "source_pdf": os.path.basename(PDF_PATH),
    "source_pdf_path": PDF_PATH,
    "total_pages": total_pages,
    "total_images": sum(len(v) for v in image_map.values()),
    "extraction_methods": {
        "structured_markdown": "OpenDataLoader (markdown + JSON + external PNG images)",
        "page_by_page": "PyMuPDF (pymupdf) - text, words, blocks, images",
    },
    "page_summary": [],
    "section_titles": [s["title"] for s in sections],
    "sections": [],
    "images": [],
    "document_structure": {
        "headings": headings,
        "key_sections": key_sections,
    },
    "odl_output": {
        "markdown_file": os.path.basename(MD_PATH),
        "json_file": os.path.basename(JSON_PATH),
        "images_dir": "odl_output/RPS - EVS - CLASS 1 - INDIVIDUAL - B (2026) PRINTFILE-pages-2_images",
    },
}

for page_num in range(1, total_pages + 1):
    page = doc[page_num - 1]
    text = page.get_text()
    words = page.get_text("words")
    imgs = image_map.get(page_num, [])
    summary["page_summary"].append({
        "page": page_num,
        "text_chars": len(text),
        "word_count": len(words),
        "image_count": len(imgs),
        "image_files": [img["filename"] for img in imgs],
    })

for sec in sections:
    preview = sec["content"][:200] if sec["content"] else "(empty)"
    summary["sections"].append({
        "title": sec["title"],
        "content_preview": preview,
        "content_length": len(sec["content"]),
    })

all_imgs = []
for page_num, imgs in image_map.items():
    for img in imgs:
        all_imgs.append({
            "page": page_num,
            "filename": img["filename"],
            "path": img["path"],
        })
summary["images"] = all_imgs

# Write summary JSON
json_out_path = os.path.join(OUTPUT_DIR, "evs_summary.json")
with open(json_out_path, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)
print(f"Written: {json_out_path}")

doc.close()
print("Done!")
