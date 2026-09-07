#!/usr/bin/env python3
"""Cross-verify PDF extraction using vision-capable LLMs via AnyAPI."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
from pathlib import Path
from typing import Optional

import httpx
import pymupdf as fitz

# Configuration
ANYAPI_KEY = os.getenv("ANYAPI_API_KEY", "")
VISION_MODELS = [
    "google/gemma-4-26b-a4b-it:free",
    "qwen/qwen3.8-27b",
]
PDF_DIR = Path("/mnt/c/Users/user/Downloads")
EXTRACTED_DIR = Path("/mnt/c/Users/user/Downloads/opendataloader_output")
OUTPUT_DIR = Path("packages/textbook-pipeline/projects/vision_verification")

PDFS = [
    "RPS - MATHS - CLASS 1 - INDIVIDUAL - B (2026) PRINTFILE-pages-2.pdf",
    "RPS - EVS - CLASS 1 - INDIVIDUAL - B (2026) PRINTFILE-pages-2.pdf",
    "RPS - ENGLISH - CLASS 1 - INDIVIDUAL - A (2026) PRINTFILE (2)-pages-2.pdf",
]


def pdf_page_to_image(pdf_path: Path, page_number: int, dpi: int = 150) -> Optional[str]:
    """Convert PDF page to base64-encoded PNG."""
    try:
        doc = fitz.open(pdf_path)
        if page_number < 1 or page_number > len(doc):
            doc.close()
            return None
        
        page = doc[page_number - 1]
        pix = page.get_pixmap(dpi=dpi)
        img_bytes = pix.tobytes("png")
        doc.close()
        
        return base64.b64encode(img_bytes).decode("utf-8")
    except Exception as exc:
        print(f"Error converting page {page_number} of {pdf_path.name}: {exc}")
        return None


def load_extracted_content(pdf_path: Path) -> dict:
    """Load extracted content from OpenDataLoader JSON if available."""
    opendataloader_dir = Path("/mnt/c/Users/user/Downloads/opendataloader_output")
    json_file = opendataloader_dir / (pdf_path.stem + ".json")
    
    if json_file.exists():
        return json.loads(json_file.read_text(encoding="utf-8"))
    return {}


def build_verification_prompt(extracted_content: dict, page_number: int) -> str:
    """Build prompt for vision model to verify extraction."""
    prompt = f"""You are a PDF extraction verification assistant. Your task is to compare the extracted content below against the actual PDF page image.

EXTRACTED CONTENT FROM PAGE {page_number}:
"""
    
    if extracted_content:
        kids = extracted_content.get("kids", [])
        page_items = [k for k in kids if k.get("page number") == page_number]
        
        for item in page_items[:20]:  # Limit to first 20 items
            item_type = item.get("type", "unknown")
            content = item.get("content", "")
            bbox = item.get("bounding box", [])
            
            if content:
                prompt += f"\n[{item_type}] {content[:200]}"
                if bbox:
                    prompt += f" (bbox: {bbox})"
    
    prompt += """

INSTRUCTIONS:
1. Compare the extracted text above with what you see in the PDF page image
2. Identify any of these issues:
   - MISSING TEXT: Content in the PDF that wasn't extracted
   - WRONG TEXT: Extracted text that differs from the PDF
   - HALLUCINATION: Extracted text that doesn't exist in the PDF
   - WRONG ORDER: Text extracted in wrong reading order
   - MISSING IMAGES: Images in PDF that weren't extracted
   - WRONG LABELS: Wrong heading levels or classifications

3. Be specific: quote exact text and describe the location (top/middle/bottom, left/center/right)

4. If everything looks correct, say "NO ISSUES FOUND"

5. Format your response as JSON:
{
  "page": <page_number>,
  "status": "PASS" or "FAIL",
  "issues": [
    {
      "type": "missing_text|wrong_text|hallucination|wrong_order|missing_image|wrong_label",
      "severity": "high|medium|low",
      "description": "...",
      "pdf_text": "...",
      "extracted_text": "..."
    }
  ],
  "summary": "Brief summary of findings"
}
"""
    
    return prompt


async def verify_page_with_vision_model(
    client: httpx.AsyncClient,
    pdf_path: Path,
    page_number: int,
    extracted_content: dict,
    model: str,
    max_retries: int = 3,
) -> dict:
    """Verify a single PDF page using a vision model."""
    
    # Convert page to image
    image_b64 = pdf_page_to_image(pdf_path, page_number)
    if not image_b64:
        return {"page": page_number, "error": "Failed to convert page to image"}
    
    # Build prompt
    prompt = build_verification_prompt(extracted_content, page_number)
    
    # Prepare messages with image
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_b64}"
                    }
                }
            ]
        }
    ]
    
    for attempt in range(max_retries):
        try:
            response = await client.post(
                "https://api.anyapi.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {ANYAPI_KEY}"},
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.1,
                    "max_tokens": 2000,
                },
                timeout=120.0,
            )
            
            if response.status_code == 429:
                wait_time = (2 ** attempt) + 1  # Exponential backoff: 2s, 4s, 8s
                print(f"    Rate limited, waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)
                continue
            
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            # Try to parse JSON response
            try:
                # Extract JSON from response (handle markdown wrapping)
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    json_str = content.split("```")[1].split("```")[0]
                else:
                    json_str = content
                
                result = json.loads(json_str)
                result["model"] = model
                result["page"] = page_number
                return result
            except json.JSONDecodeError:
                return {
                    "page": page_number,
                    "model": model,
                    "status": "PARSE_ERROR",
                    "raw_response": content,
                }
        
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429 and attempt < max_retries - 1:
                continue
            return {"page": page_number, "model": model, "error": str(exc)}
        except Exception as exc:
            return {"page": page_number, "model": model, "error": str(exc)}
    
    return {"page": page_number, "model": model, "error": "Max retries exceeded for rate limit"}


async def verify_pdf(pdf_path: Path, model: str, max_pages: int = 3) -> dict:
    """Verify extraction for a PDF using vision model."""
    
    extracted_content = load_extracted_content(pdf_path)
    
    # Get total pages
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    doc.close()
    
    # Verify first few pages
    pages_to_verify = min(max_pages, total_pages)
    
    async with httpx.AsyncClient() as client:
        results = []
        for page_num in range(1, pages_to_verify + 1):
            print(f"  Verifying page {page_num}/{pages_to_verify}...")
            result = await verify_page_with_vision_model(
                client, pdf_path, page_num, extracted_content, model
            )
            results.append(result)
    
    return {
        "pdf": pdf_path.name,
        "model": model,
        "pages_verified": pages_to_verify,
        "total_pages": total_pages,
        "results": results,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python verify_extraction_vision.py <pdf_index>")
        print(f"Available PDFs:")
        for i, pdf_name in enumerate(PDFS):
            print(f"  {i+1}. {pdf_name}")
        sys.exit(1)
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Get PDF index from command line
    pdf_index = int(sys.argv[1]) - 1
    if pdf_index < 0 or pdf_index >= len(PDFS):
        print(f"Invalid PDF index. Choose 1-{len(PDFS)}")
        sys.exit(1)
    
    pdf = PDF_DIR / PDFS[pdf_index]
    model = VISION_MODELS[0]
    
    print(f"Vision Verification")
    print(f"PDF: {pdf}")
    print(f"Model: {model}")
    print(f"=" * 60)
    
    result = asyncio.run(verify_pdf(pdf, model, max_pages=2))
    
    # Save results
    output_file = OUTPUT_DIR / f"verification_{pdf.stem}_{model.replace('/', '_').replace(':', '_')}.json"
    output_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    
    print(f"\n✅ Results saved to: {output_file}")
    
    # Print summary
    print(f"\n=== VERIFICATION SUMMARY ===")
    for page_result in result.get("results", []):
        page = page_result.get("page", "?")
        status = page_result.get("status", "unknown")
        if status == "PASS":
            print(f"  Page {page}: ✅ PASS")
        elif status == "FAIL":
            issues = page_result.get("issues", [])
            print(f"  Page {page}: ❌ FAIL ({len(issues)} issues)")
            for issue in issues[:3]:
                print(f"    - [{issue.get('type', '?')}] {issue.get('description', '?')[:100]}")
        else:
            print(f"  Page {page}: ⚠️ {status}")
            if "error" in page_result:
                print(f"    Error: {page_result['error']}")
    
    return 0


if __name__ == "__main__":
    import os
    sys.exit(main())
