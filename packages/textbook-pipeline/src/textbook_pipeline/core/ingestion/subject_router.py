"""Subject Router for Textbook Pipeline.

Analyzes the content of a PDF to automatically detect:
1. The Subject (ENGLISH, MATH, SCIENCE, SOCIAL)
2. The Grade (1-10)
3. The Textbook ID (extracted from title/cover)

This uses a light-weight LLM call via LangChain on the first few pages of the document.
"""

from __future__ import annotations

import os
import logging
import json
from pathlib import Path
from typing import Tuple, Optional, Any, Dict

from dotenv import load_dotenv
from textbook_pipeline.models.chapter import Subject

# Load env for API keys
load_dotenv()

logger = logging.getLogger(__name__)


def _lazy_import_langchain():
    """Import langchain only when needed to avoid hard dependency."""
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage
        return ChatOpenAI, HumanMessage, SystemMessage
    except ImportError as exc:
        raise ImportError(
            "langchain-openai is required for SubjectRouter. "
            "Install it with: pip install langchain-openai"
        ) from exc

class SubjectRouter:
    """Detects subject and grade from a document's initial content."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        # Use provided key or fallback to .env
        key = api_key or os.getenv("ANYAPI_API_KEY")
        if not key:
            raise ValueError("No API key provided and ANYAPI_API_KEY not found in environment")

        # Use provided model or fallback to MODEL_ROUTER in .env
        self.model = model or os.getenv("MODEL_ROUTER", "deepseek/deepseek-chat")

        ChatOpenAI, HumanMessage, SystemMessage = _lazy_import_langchain()
        self.client = ChatOpenAI(
            api_key=key,
            base_url="https://api.anyapi.ai/v1",
            model=self.model,
            temperature=0,
        )
        self._HumanMessage = HumanMessage
        self._SystemMessage = SystemMessage

    def route_subject(self, raw_doc: Any) -> Dict[str, Any]:
        """Analyzes content and returns a dict with Subject, Grade, and TextbookID.
        
        Args:
            raw_doc: The Docling document object.
        """
        # Extract first few pages of text for analysis
        content_parts = []
        for item in raw_doc.iterate_items():
            if hasattr(item, 'text'):
                content_parts.append(item.text)
            if sum(len(p) for p in content_parts) > 5000:
                break
        content = "\n".join(content_parts).strip()
        return self._route_with_content(content)

    def route_subject_text(self, content: str, source_pdf_path: Optional[Path] = None) -> Dict[str, Any]:
        """Analyzes raw text content and returns a dict with Subject, Grade, and TextbookID.
        
        Args:
            content: Raw text content from PDF.
            source_pdf_path: Optional path to the source PDF for filename-based detection.
        """
        return self._route_with_content(content, source_pdf_path)

    def _route_with_content(self, content: str, source_pdf_path: Optional[Path] = None) -> Dict[str, Any]:
        """Internal method to route subject from text content and optionally PDF path."""
        # FIRST: Try to extract from filename (most reliable)
        if source_pdf_path:
            filename = source_pdf_path.stem.upper()
            logger.info(f"Routing subject from filename: {filename}")
            
            # Pattern: "RPS - ENGLISH - CLASS 1 - ..."
            # Extract subject
            subject = None
            for subj in Subject:
                if f" {subj.value.upper()} " in f" {filename} " or filename.startswith(f"{subj.value.upper()} "):
                    subject = subj
                    break
            
            # Extract grade
            grade = None
            import re
            grade_match = re.search(r'CLASS\s*(\d+)', filename)
            if grade_match:
                grade = int(grade_match.group(1))
            else:
                grade_match = re.search(r'GRADE\s*(\d+)', filename)
                if grade_match:
                    grade = int(grade_match.group(1))
            
            if subject and grade:
                logger.info(f"Subject/Grade detected from filename: {subject.value}, Class {grade}")
                return {
                    "subject": subject,
                    "grade": grade,
                    "textbook_id": "extracted_from_filename"
                }
        
        # FALLBACK 1: Keyword-based detection from content
        content_lower = content.lower()
        # ... rest of keyword detection
        
        # English indicators
        english_keywords = ['phonics', 'vowel', 'consonant', 'rhyming', 'alphabet', 'says /', 'worksheet', 
                           'comprehension', 'glossary', 'speaking', 'reading', 'writing', 'story', 'poem',
                           'tick the correct', 'true or false', 'think and answer', 'let\'s discuss']
        
        # Math indicators
        math_keywords = ['addition', 'subtraction', 'multiplication', 'division', 'fraction', 'decimal',
                        'geometry', 'algebra', 'number', 'count', 'sum', 'difference', 'product',
                        'multiply', 'divide', 'equation', 'solve', 'calculate']
        
        # Science indicators
        science_keywords = ['photosynthesis', 'cell', 'organism', 'ecosystem', 'gravity', 'force', 'energy',
                           'matter', 'atom', 'molecule', 'planet', 'orbit', 'experiment', 'hypothesis',
                           'observation', 'conclusion', 'scientific method']
        
        # Social studies indicators
        social_keywords = ['history', 'geography', 'civics', 'government', 'constitution', 'democracy',
                          'civilization', 'ancient', 'medieval', 'modern', 'map', 'continent', 'country',
                          'citizen', 'rights', 'duties', 'community', 'society', 'culture']
        
        english_score = sum(1 for kw in english_keywords if kw in content_lower)
        math_score = sum(1 for kw in math_keywords if kw in content_lower)
        science_score = sum(1 for kw in science_keywords if kw in content_lower)
        social_score = sum(1 for kw in social_keywords if kw in content_lower)
        
        # If we have a clear winner from keywords, use it
        scores = {
            Subject.ENGLISH: english_score,
            Subject.MATH: math_score,
            Subject.SCIENCE: science_score,
            Subject.SOCIAL: social_score
        }
        
        max_subject = max(scores, key=scores.get)
        if scores[max_subject] > 0:
            logger.info(f"Subject detected via keywords: {max_subject.value} (score: {scores[max_subject]})")
            return {
                "subject": max_subject,
                "grade": 1,  # Default, will be refined by LLM if available
                "textbook_id": "detected_via_keywords"
            }
        
        # Fallback to LLM if no clear keyword match
        prompt = (
            "Analyze the following textbook snippet and determine the subject, grade, and textbook ID.\n\n"
            "SUBJECTS: [english, math, science, social]\n"
            "GRADES: 1 to 10\n\n"
            "TEXTBOOK SNIPPET:\n"
            f"\"\"\"\n{content[:5000]}\n\"\"\"\n\n"
            "Respond ONLY as a JSON object:\n"
            "{\n"
            "    \"subject\": \"one of the 4 subjects\",\n"
            "    \"grade\": integer,\n"
            "    \"textbook_id\": \"a short slug for the book title\"\n"
            "}"
        )
        
        try:
            response = self.client.invoke([
                self._SystemMessage(content="You are a precise classifier. Output only valid JSON."),
                self._HumanMessage(content=prompt)
            ])
            
            # Handle empty response
            if not response.content or not response.content.strip():
                logger.warning("LLM returned empty response, using keyword fallback")
                return {
                    "subject": max_subject if scores[max_subject] > 0 else Subject.SCIENCE,
                    "grade": 1,
                    "textbook_id": "llm_empty_fallback"
                }
            
            data = json.loads(response.content)
            
            # Validate subject
            subject_str = data.get("subject", "science")
            if subject_str is None:
                subject_str = "science"
            subject_str = subject_str.lower()
            try:
                subject = Subject(subject_str)
            except ValueError:
                subject = Subject.SCIENCE
                
            grade = int(data.get("grade", 1))
            textbook_id = data.get("textbook_id", "unknown_book")
            
            return {
                "subject": subject,
                "grade": grade,
                "textbook_id": textbook_id
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Subject routing failed - invalid JSON from LLM: {e}")
            return {
                "subject": max_subject if scores[max_subject] > 0 else Subject.SCIENCE,
                "grade": 1,
                "textbook_id": "llm_json_error_fallback"
            }
        except Exception as e:
            logger.error(f"Subject routing failed: {e}")
            return {
                "subject": max_subject if scores[max_subject] > 0 else Subject.SCIENCE,
                "grade": 1,
                "textbook_id": "llm_error_fallback"
            }
