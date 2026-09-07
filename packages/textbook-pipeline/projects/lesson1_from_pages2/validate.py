import json
from pathlib import Path

bp = Path("packages/textbook-pipeline/projects/lesson1_from_pages2/blueprint.json")
data = json.loads(bp.read_text())

print("=== EXTRACTION VALIDATION REPORT ===")
print(f"Title: {data['title']}")
print(f"Subject: {data['subject']}, Grade: {data['grade']}")
print(f"Total pages: {data['page_range'][1] - data['page_range'][0] + 1}")
print(f"Sections: {len(data['sections'])}")

issues = []
for i, sec in enumerate(data["sections"], 1):
    title = sec["title"]
    content = sec["content_text"]
    start, end = sec["page_range"]

    if title.endswith("-") or len(title) < 4:
        issues.append(f"sec_{i:03d}: truncated title: {title!r}")

    words = content.split()[:5]
    if all(w.isdigit() for w in words) and len(content.split()) < 20:
        issues.append(f"sec_{i:03d}: TOC-like content")

    if not content.strip():
        issues.append(f"sec_{i:03d}: empty content")

    print(f"\nSection {i}: {title}")
    print(f"  Pages: {start}-{end}")
    print(f"  Type: {sec['type']}")
    print(f"  Content length: {len(content)} chars")
    print(f"  Figures: {len(sec['figures'])}")
    print(f"  Exercises: {len(sec['exercises'])}")

print(f"\n=== ISSUES FOUND: {len(issues)} ===")
for issue in issues:
    print(f"  - {issue}")

if not issues:
    print("  None! Extraction looks clean.")
