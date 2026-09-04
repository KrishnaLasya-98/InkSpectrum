"""PDF Splitter for Textbook Pipeline.

This module provides functionality to split large textbook PDFs into smaller chunks.
This is critical for CPU-based environments to prevent timeouts during 
the Docling parsing process.
"""

from __future__ import annotations

import os
import logging
from pathlib import Path
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

class PDFSplitter:
    """Splits a PDF into smaller, manageable chunks."""

    def __init__(self, chunk_size: int = 10):
        """
        Args:
            chunk_size: Number of pages per chunk.
        """
        self.chunk_size = chunk_size

    def split_pdf(self, pdf_path: Path, output_dir: Path) -> list[Path]:
        """
        Splits the provided PDF into chunks of self.chunk_size pages.
        
        Args:
            pdf_path: Path to the source PDF.
            output_dir: Directory to save the chunks.
            
        Returns:
            A list of paths to the created chunk files.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        chunk_files = []
        
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            logger.info(f"Splitting {pdf_path.name} ({total_pages} pages) into chunks of {self.chunk_size}...")
            
            for i in range(0, total_pages, self.chunk_size):
                start_page = i
                end_page = min(i + self.chunk_size - 1, total_pages - 1)
                
                # Create a new PDF for the chunk
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=start_page, to_page=end_page)
                
                chunk_filename = f"chunk_{start_page+1}_{end_page+1}.pdf"
                chunk_path = output_dir / chunk_filename
                new_doc.save(chunk_path)
                new_doc.close()
                
                chunk_files.append(chunk_path)
                logger.debug(f"Saved chunk: {chunk_filename}")
                
            doc.close()
            logger.info(f"Successfully split into {len(chunk_files)} chunks.")
            return chunk_files
            
        except Exception as e:
            logger.error(f"PDF splitting failed: {e}")
            raise
