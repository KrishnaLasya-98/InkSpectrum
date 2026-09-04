"""PyMuPDF-based Smart Extractor for Textbook Pipeline.

This module replaces Docling for textbooks where Docling fails to detect structure.
It uses font size, position, and keyword heuristics to extract pedagogical structure.
"""

from __future__ import annotations

import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

import pymupdf as fitz

from textbook_pipeline.models.chapter import (
    ChapterNode,
    SectionNode,
    ExerciseNode,
    DoclingRef,
    SectionType,
    ExerciseType,
    Subject,
    LaTeXEquation,
    ImageAsset,
    TableData,
)

logger = logging.getLogger(__name__)

@dataclass
class TextBlock:
    """A text block with position and font info."""
    text: str
    page: int
    bbox: fitz.Rect
    font_size: float
    font_name: str
    is_bold: bool
    is_centered: bool

class PyMuPDFExtractor:
    """Extracts pedagogical structure from textbooks using PyMuPDF."""
    
    # Patterns for section detection
    LESSON_PATTERN = re.compile(r'(Lesson|Chapter|Unit)\s*\d+', re.IGNORECASE)
    PHONICS_PATTERN = re.compile(r'Phonics', re.IGNORECASE)
    WORKSHEET_PATTERN = re.compile(r'Worksheet', re.IGNORECASE)
    EXERCISE_PATTERN = re.compile(r'(Exercise|Practice|Activity|Questions?|Try\s+This)', re.IGNORECASE)
    POEM_PATTERN = re.compile(r'Poem', re.IGNORECASE)
    
    # Patterns for exercise questions
    QUESTION_PATTERN = re.compile(r'^(Q\d+|\d+[\.\)])\s*', re.IGNORECASE)
    
    def __init__(self, heading_font_threshold: float = 12.0):
        self.heading_font_threshold = heading_font_threshold
    
    def extract_text_blocks(self, pdf_path: Path) -> List[TextBlock]:
        """Extract all text blocks with font/position metadata."""
        blocks = []
        doc = fitz.open(pdf_path)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks_data = page.get_text("dict")["blocks"]
            
            for block in blocks_data:
                if "lines" not in block:
                    continue
                    
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"].strip()
                        if not text:
                            continue
                            
                        bbox = fitz.Rect(span["bbox"])
                        font_size = span["size"]
                        font_name = span["font"]
                        is_bold = "bold" in font_name.lower() or span["flags"] & 16
                        
                        # Check if centered (rough heuristic)
                        page_width = page.rect.width
                        is_centered = abs((bbox.x0 + bbox.x1) / 2 - page_width / 2) < page_width * 0.15
                        
                        blocks.append(TextBlock(
                            text=text,
                            page=page_num + 1,
                            bbox=bbox,
                            font_size=font_size,
                            font_name=font_name,
                            is_bold=is_bold,
                            is_centered=is_centered
                        ))
        
        doc.close()
        return blocks
    
    def classify_block(self, block: TextBlock) -> str:
        """Classify a text block into a section type."""
        text = block.text
        
        # Check for lesson/chapter headers
        if self.LESSON_PATTERN.search(text):
            if self.PHONICS_PATTERN.search(text):
                return "phonics"
            if self.POEM_PATTERN.search(text):
                return "poem"
            return "lesson"
        
        # Check for worksheet
        if self.WORKSHEET_PATTERN.search(text):
            return "worksheet"
        
        # Check for exercise sections
        if self.EXERCISE_PATTERN.search(text):
            return "exercise"
        
        # Check for question patterns
        if self.QUESTION_PATTERN.search(text):
            return "question"
        
        # Large centered text = likely heading
        if block.font_size >= self.heading_font_threshold and block.is_centered and block.is_bold:
            return "heading"
        
        return "content"
    
    def classify_section_type(self, title: str, content: str) -> SectionType:
        """Classify a section as THEORETICAL or EXERCISE based on title and content."""
        text = (title + " " + content).lower()
        
        # Strong exercise indicators
        exercise_indicators = [
            r'\btick\b', r'\btrue\s*or\s*false\b', r'\bthink\s+and\s+answer\b',
            r'\bcomprehending\s+ability\b', r'\blet.?s\s+discuss\b',
            r'\bspeaking\s+ability\b', r'\bexercise\b', r'\bactivity\b',
            r'\bquestion\b', r'\banswer\b', r'\bfill\s+in\b',
            r'\bmatch\b', r'\bcircle\b', r'\bchoose\b', r'\bselect\b',
            r'\btrue\b.*\bfalse\b', r'\bfalse\b.*\btrue\b'
        ]
        
        for pattern in exercise_indicators:
            if re.search(pattern, text):
                return SectionType.EXERCISE
        
        # Phonics worksheets and reading practice are exercises too
        if 'worksheet' in title.lower() or 'phonics' in title.lower():
            return SectionType.EXERCISE
        
        # Comprehension, glossary, speaking, discussion = exercises
        if any(kw in title.lower() for kw in ['comprehending', 'glossary', 'speaking', 'discuss', 'think', 'answer']):
            return SectionType.EXERCISE
        
        return SectionType.THEORETICAL
    
    def extract_chapters(self, pdf_path: Path, subject: Subject, grade: int, textbook_id: str) -> ChapterNode:
            """Extract full chapter structure from PDF."""
            blocks = self.extract_text_blocks(pdf_path)
        
            # Group blocks by page for context
            sections = []
            current_section = None
            section_counter = 0
        
            for block in blocks:
                classification = self.classify_block(block)
            
                # Start new section on lesson/phonics/worksheet/heading
                if classification in ("lesson", "phonics", "worksheet", "poem", "heading"):
                    if current_section:
                        sections.append(current_section)
                
                    section_counter += 1
                
                    # Use the new classification method
                    sec_type = self.classify_section_type(block.text, "")
                
                    current_section = SectionNode(
                        id=f"sec_{section_counter}",
                        type=sec_type,
                        title=block.text,
                        content_text="",
                        page_range=(block.page, block.page),
                        docling_refs=[DoclingRef(
                            item_id=f"pymupdf_{block.page}_{section_counter}",
                            page_number=block.page,
                            label=classification.upper()
                        )]
                    )
            
                elif current_section:
                    # Add content to current section
                    current_section.content_text += f" {block.text}"
                
                    # Re-classify section type based on accumulated content
                    current_section.type = self.classify_section_type(
                        current_section.title, current_section.content_text
                    )
                
                    # Extract exercises within exercise sections
                    if current_section.type == SectionType.EXERCISE and classification == "question":
                        current_section.exercises.append(ExerciseNode(
                            id=f"ex_{section_counter}_{len(current_section.exercises)+1}",
                            question_text=block.text,
                            exercise_type=ExerciseType.SHORT_ANSWER,
                            difficulty=2,
                            page_number=block.page,
                            docling_refs=[DoclingRef(
                                item_id=f"pymupdf_q_{block.page}_{len(current_section.exercises)}",
                                page_number=block.page,
                                label="QUESTION"
                            )]
                        ))
        
            # Don't forget the last section
            if current_section:
                sections.append(current_section)
        
            # If no sections found, create one from all content
            if not sections:
                all_text = " ".join(b.text for b in blocks)
                sections.append(SectionNode(
                    id="sec_1",
                    type=SectionType.THEORETICAL,
                    title="Extracted Content",
                    content_text=all_text,
                    page_range=(1, max(b.page for b in blocks) if blocks else 1),
                    docling_refs=[DoclingRef(item_id="pymupdf_all", page_number=1, label="CONTENT")]
                ))
        
            return ChapterNode(
                id=f"{textbook_id}_ch1",
                number=1,
                title=sections[0].title if sections else "Extracted Chapter",
                subject=subject,
                grade=grade,
                textbook_id=textbook_id,
                sections=sections,
                page_range=(1, max(b.page for b in blocks) if blocks else 1),
                source_pdf=Path(pdf_path),
            )

def extract_with_pymupdf(pdf_path: Path, subject: Subject, grade: int, textbook_id: str) -> ChapterNode:
    """Convenience function for the pipeline."""
    extractor = PyMuPDFExtractor()
    return extractor.extract_chapters(pdf_path, subject, grade, textbook_id)
