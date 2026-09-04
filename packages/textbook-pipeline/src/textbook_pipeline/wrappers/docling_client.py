"""Connector for the Docling Standard Library.

This wrapper provides a simplified interface to the IBM Docling project's
document parsing capabilities, translating their complex internal
DoclingDocument format into our pedagogical ChapterNode schema.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

# Use the dynamic environment bridge to ensure docling is in sys.path
from docling.document_converter import DocumentConverter

from textbook_pipeline.models.chapter import (
    ChapterNode,
    SectionNode,
    SectionType,
    DoclingRef,
    ImageAsset,
    LaTeXEquation,
    TableData,
    Subject,
)

logger = logging.getLogger(__name__)

class DoclingClient:
    """A thin wrapper around the Docling DocumentConverter.
    
    Acts as a 'Connector' that maps the standard Docling library
    to the textbook-pipeline's internal data models.
    """

    def __init__(self, options: Optional[dict] = None):
        """Initialize the Docling converter.
        
        Args:
            options: Optional configuration for the converter
        """
        try:
            self.converter = DocumentConverter()
            logger.info("Docling converter initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Docling converter: {e}")
            raise

    def convert_pdf(self, pdf_path: Path) -> ChapterNode:
        """Converts a PDF file into a ChapterNode.
        
        This is the bridge between raw PDF layout and our pedagogical structure.
        
        Args:
            pdf_path: Absolute path to the textbook PDF
            
        Returns:
            A ChapterNode containing extracted sections, equations, and images.
        """
        logger.info(f"Converting PDF: {pdf_path}")
        
        # 1. Call the Standard Library (Docling)
        # This is the 'muscle' part - Docling does the heavy lifting
        result = self.converter.convert(pdf_path)
        doc = result.document
        
        # 2. Translation Layer (The 'Connector' logic)
        # Here we map Docling's DocItemLabel to our SectionNode and ExerciseNode
        
        sections = []
        current_section = None
        
        # Docling's document is an iterable of items (headers, text, tables, formulas)
        # We iterate through them to group them into our pedagogical sections
        for i, item in enumerate(doc.iterate_items()):
            # Check if the item is a section header (Level 1, 2, etc.)
            # Docling labels these as 'section_header'
            if hasattr(item, 'label') and item.label == 'section_header':
                # Save previous section and start a new one
                if current_section:
                    sections.append(current_section)
                
                current_section = SectionNode(
                    id=f"sec_{i}",
                    type=SectionType.THEORETICAL, # Default, determined by subject_router later
                    title=item.text,
                    content_text="",
                    page_range=(item.prov[0].page_no, item.prov[0].page_no),
                    docling_refs=[DoclingRef(item_id=str(i), page_number=item.prov[0].page_no, label="SECTION_HEADER")]
                )
            
            elif current_section:
                # Append content to the current section
                if hasattr(item, 'text'):
                    current_section.content_text += f" {item.text}"
                
                # Map Docling items to our asset types
                if hasattr(item, 'label'):
                    if item.label == 'formula':
                        current_section.equations.append(LaTeXEquation(
                            latex=item.text, 
                            plain_text=item.text, 
                            page_number=item.prov[0].page_no
                        ))
                    elif item.label == 'picture':
                        current_section.figures.append(ImageAsset(
                            page_number=item.prov[0].page_no,
                            file_path=Path(f"assets/images/page_{item.prov[0].page_no}_{i}.png"),
                            caption=getattr(item, 'caption', None)
                        ))
                    elif item.label == 'table':
                        # Extract table data (simplified)
                        current_section.tables.append(TableData(
                            page_number=item.prov[0].page_no,
                            headers=[], 
                            rows=[[item.text]]
                        ))
        
        # Add the final section
        if current_section:
            sections.append(current_section)

        # 3. Build the final ChapterNode
        return ChapterNode(
            id="docling_gen_chapter",
            number=1, # To be filled by chapter_detector
            title=doc.name or "Extracted Chapter",
            subject=Subject.SCIENCE, # To be filled by subject_router
            grade=4,
            textbook_id="extracted_pdf",
            sections=sections,
            page_range=(1, len(doc.pages)),
            source_pdf=pdf_path,
        )

