"""Chapter grouper for Textbook Pipeline.

This module transforms a flat list of Docling document items into a
hierarchical ChapterNode structure. It handles the logic of detecting
chapter boundaries and classifying sections as theoretical or exercises.
"""

from __future__ import annotations

import logging
import re
import os
from pathlib import Path
from typing import List, Optional, Any

from textbook_pipeline.models.chapter import (
    ChapterNode,
    DoclingRef,
    ExerciseNode,
    ExerciseType,
    SectionNode,
    SectionType,
    Subject,
    ImageAsset,
    LaTeXEquation,
    TableData,
)

logger = logging.getLogger(__name__)

class ChapterGrouper:
    """Groups Docling items into a pedagogical chapter hierarchy."""

    def __init__(self, subject: Subject, grade: int):
        self.subject = subject
        self.grade = grade

    def group_into_chapter(self, raw_doc: Any, subject_info: dict, textbook_id: str = "unknown", source_pdf: Path = Path("placeholder.pdf")) -> ChapterNode:
        """Convenience wrapper to group items into a ChapterNode using a subject_info dict."""
        # Extract items as a list
        doc_items = list(raw_doc.iterate_items())
        return self.group_items(doc_items, textbook_id, source_pdf)

    def group_items(self, doc_items: List[Any], textbook_id: str, source_pdf: Path) -> ChapterNode:
        """Groups a sequence of document items into a single ChapterNode."""
        sections = []
        current_section = None
        
        # Heuristic: patterns that indicate an exercise section
        exercise_markers = [
            r"exercise", r"practice", r"questions", r"try this", 
            r"solve the following", r"answer the following"
        ]
        exercise_regex = re.compile("|".join(exercise_markers), re.IGNORECASE)

        for i, item in enumerate(doc_items):
            # 1. Detect Section Boundaries (Headers)
            if hasattr(item, 'label') and item.label == 'section_header':
                # Close previous section
                if current_section:
                    sections.append(current_section)
                
                # Determine if this is an exercise or theoretical section
                section_type = SectionType.THEORETICAL
                if hasattr(item, 'text') and exercise_regex.search(item.text):
                    section_type = SectionType.EXERCISE

                current_section = SectionNode(
                    id=f"sec_{i}",
                    type=section_type,
                    title=getattr(item, 'text', f"Section {i}"),
                    content_text="",
                    page_range=(item.prov[0].page_no, item.prov[0].page_no) if hasattr(item, 'prov') else (1, 1),
                    docling_refs=[DoclingRef(item_id=str(i), page_number=item.prov[0].page_no if hasattr(item, 'prov') else 1, label="SECTION_HEADER")]
                )
            
            elif current_section:
                # 2. Distribute content into the current section
                if hasattr(item, 'text'):
                    current_section.content_text += f" {item.text}"
                
                # Map items to specialized assets
                if hasattr(item, 'label'):
                    if item.label == 'formula':
                        current_section.equations.append(LaTeXEquation(
                            latex=getattr(item, 'text', ""), 
                            plain_text=getattr(item, 'text', ""), 
                            page_number=item.prov[0].page_no if hasattr(item, 'prov') else 1
                        ))
                    elif item.label == 'picture':
                        current_section.figures.append(ImageAsset(
                            page_number=item.prov[0].page_no if hasattr(item, 'prov') else 1,
                            file_path=Path(f"assets/images/page_{item.prov[0].page_no if hasattr(item, 'prov') else 1}_{i}.png"),
                            caption=getattr(item, 'caption', None)
                        ))
                    elif item.label == 'table':
                        current_section.tables.append(TableData(
                            page_number=item.prov[0].page_no if hasattr(item, 'prov') else 1,
                            headers=[], 
                            rows=[[getattr(item, 'text', "")]]
                        ))

                # 3. Specialized Exercise Extraction
                if current_section.type == SectionType.EXERCISE:
                    item_text = getattr(item, 'text', "")
                    if re.match(r"^(Q\d+|\d+[\.\)])", item_text):
                        current_section.exercises.append(ExerciseNode(
                            id=f"ex_{i}",
                            question_text=item_text,
                            exercise_type=ExerciseType.SHORT_ANSWER,
                            difficulty=3,
                            page_number=item.prov[0].page_no if hasattr(item, 'prov') else 1,
                            docling_refs=[DoclingRef(item_id=str(i), page_number=item.prov[0].page_no if hasattr(item, 'prov') else 1, label="EXERCISE")]
                        ))

        # Add final section
        if current_section:
            sections.append(current_section)

        return ChapterNode(
            id=f"{textbook_id}_ch1",
            number=1,
            title="Extracted Chapter",
            subject=self.subject,
            grade=self.grade,
            textbook_id=textbook_id,
            sections=sections,
            page_range=(1, 1), 
            source_pdf=source_pdf,
        )
