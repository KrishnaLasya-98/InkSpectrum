from typing import List, Dict, Any, Optional
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "vendor", "docling"))


class ExtractionTask:
    name = "pdf_extraction"
    description = "Extract and summarize content from a PDF document"
    
    def get_messages(self, pdf_text: str, max_length: int = 2000) -> List[Dict[str, str]]:
        truncated = pdf_text[:max_length]
        return [
            {
                "role": "system",
                "content": "You are an expert at extracting and summarizing educational content from textbooks."
            },
            {
                "role": "user",
                "content": f"Extract the key concepts, definitions, and learning objectives from this textbook content. Provide a structured summary:\n\n{truncated}"
            }
        ]
    
    def score(self, output: str) -> float:
        score = 0.0
        if len(output) > 200:
            score += 2.0
        if "concept" in output.lower() or "definition" in output.lower():
            score += 1.5
        if "objective" in output.lower() or "learning" in output.lower():
            score += 1.5
        if ":" in output or "-" in output:
            score += 1.0
        return min(score, 5.0)
