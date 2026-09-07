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
from tempfile import mkdtemp

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
from textbook_pipeline.core.ingestion.extractor import ExtractorProtocol

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


@dataclass
class PageBlock:
    """Structured block extracted from a single page."""
    page: int
    block_type: str  # "text", "image", "table"
    text: str = ""
    bbox: Optional[fitz.Rect] = None
    font_size: float = 0.0
    is_bold: bool = False
    is_centered: bool = False
    images: List[ImageAsset] = field(default_factory=list)


class PyMuPDFExtractor(ExtractorProtocol):
    """Extracts pedagogical structure from textbooks using PyMuPDF."""

    # Patterns for section detection
    LESSON_PATTERN = re.compile(r'(Lesson|Chapter|Unit)\s*\d+', re.IGNORECASE)
    PHONICS_PATTERN = re.compile(r'Phonics', re.IGNORECASE)
    WORKSHEET_PATTERN = re.compile(r'Worksheet', re.IGNORECASE)
    EXERCISE_PATTERN = re.compile(r'(Exercise|Practice|Activity|Questions?|Try\s+This)', re.IGNORECASE)
    POEM_PATTERN = re.compile(r'Poem', re.IGNORECASE)

    # Patterns for exercise questions
    QUESTION_PATTERN = re.compile(r'^(Q\d+|\d+[\.\)])\s*', re.IGNORECASE)

    # Noise patterns
    RUNNING_HEADER_PATTERN = re.compile(r'^(Rockland|Class\s+\d+|English\s*-\s*Class\s*\d+)$', re.IGNORECASE)
    PAGE_NUMBER_PATTERN = re.compile(r'^\d+$')
    HEADER_FOOTER_RATIO = 0.12  # top/bottom 12% of page
    MIN_HEADING_LENGTH = 4

    def __init__(
        self,
        heading_font_threshold: float = 12.0,
        min_heading_length: int = MIN_HEADING_LENGTH,
        temp_dir: Optional[Path] = None,
    ):
        self.heading_font_threshold = heading_font_threshold
        self.min_heading_length = min_heading_length
        self.temp_dir = temp_dir or Path(mkdtemp(prefix="textbook_pipeline_images_"))
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self._seen_headers: set[str] = set()

    def _is_header_footer(self, block: dict, page: fitz.Page) -> bool:
        page_height = page.rect.height
        y0 = block.get("bbox", [0, 0, 0, 0])[1]
        y1 = block.get("bbox", [0, 0, 0, 0])[3]
        in_header = y1 < page_height * self.HEADER_FOOTER_RATIO
        in_footer = y0 > page_height * (1 - self.HEADER_FOOTER_RATIO)
        return in_header or in_footer

    def _is_noise(self, text: str) -> bool:
        if not text or not text.strip():
            return True
        stripped = text.strip()
        if self.PAGE_NUMBER_PATTERN.match(stripped):
            return True
        if self.RUNNING_HEADER_PATTERN.match(stripped):
            return True
        return False

    def _extract_page_blocks(self, pdf_path: Path) -> List[PageBlock]:
        """Extract page-level blocks with images and text, sorted by position."""
        page_blocks: List[PageBlock] = []
        doc = fitz.open(pdf_path)
        self._seen_headers.clear()

        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_data = page.get_text("dict")
                page_height = page.rect.height
                page_width = page.rect.width

                # Collect candidate header texts from top of page
                header_candidates: List[str] = []
                for block in page_data.get("blocks", []):
                    if "lines" not in block:
                        continue
                    bbox = block.get("bbox", [0, 0, 0, 0])
                    if bbox[3] < page_height * self.HEADER_FOOTER_RATIO:
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                header_candidates.append(span.get("text", "").strip())

                # Detect repeating running headers
                for text in header_candidates:
                    if text and self._seen_headers.add(text) and len([h for h in self._seen_headers if h == text]) >= 3:
                        logger.debug(f"Detected repeating header: {text}")

                page_block_items: List[PageBlock] = []

                for block in page_data.get("blocks", []):
                    block_bbox = fitz.Rect(block.get("bbox", [0, 0, 0, 0]))

                    # Skip header/footer zones
                    if self._is_header_footer(block, page):
                        continue

                    # Image block
                    if block.get("type") == 1:
                        images = self._extract_images(page, [block], page_num + 1)
                        page_block_items.append(PageBlock(
                            page=page_num + 1,
                            block_type="image",
                            bbox=block_bbox,
                            images=images,
                        ))
                        continue

                    # Text block
                    if "lines" not in block:
                        continue

                    full_text_parts: List[str] = []
                    max_font_size = 0.0
                    is_bold = False
                    any_centered = False

                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            span_text = span.get("text", "")
                            if self._is_noise(span_text):
                                continue
                            full_text_parts.append(span_text)
                            max_font_size = max(max_font_size, span.get("size", 0.0))
                            if "bold" in span.get("font", "").lower() or span.get("flags", 0) & 16:
                                is_bold = True
                            span_bbox = fitz.Rect(span.get("bbox", [0, 0, 0, 0]))
                            span_center_x = (span_bbox.x0 + span_bbox.x1) / 2
                            if abs(span_center_x - page_width / 2) < page_width * 0.15:
                                any_centered = True

                    text = " ".join(full_text_parts).strip()
                    if not text:
                        continue

                    # Skip repeating headers discovered on this page
                    if any(self.RUNNING_HEADER_PATTERN.match(part.strip()) for part in header_candidates):
                        if text in header_candidates:
                            continue

                    page_block_items.append(PageBlock(
                        page=page_num + 1,
                        block_type="text",
                        text=text,
                        bbox=block_bbox,
                        font_size=max_font_size,
                        is_bold=is_bold,
                        is_centered=any_centered,
                    ))

                # Sort blocks top-to-bottom, left-to-right
                page_block_items.sort(key=lambda b: (b.bbox.y0 if b.bbox else 0, b.bbox.x0 if b.bbox else 0))
                page_blocks.extend(page_block_items)
        finally:
            doc.close()

        return page_blocks

    def _extract_images(self, page: fitz.Page, blocks: List[dict], page_num: int) -> List[ImageAsset]:
        """Extract images from page blocks and save to temp dir."""
        images: List[ImageAsset] = []
        for idx, block in enumerate(blocks):
            if block.get("type") != 1:
                continue
            bbox = fitz.Rect(block.get("bbox", [0, 0, 0, 0]))
            try:
                pix = page.get_pixmap(clip=bbox, dpi=150)
                image_path = self.temp_dir / f"page_{page_num}_img_{idx}.png"
                pix.save(str(image_path))
                images.append(ImageAsset(
                    page_number=page_num,
                    file_path=image_path,
                    bbox=bbox,
                ))
            except Exception as exc:
                logger.debug(f"Image extraction failed on page {page_num} block {idx}: {exc}")
        return images

    def _merge_heading(self, current: Optional[TextBlock], candidate: PageBlock) -> Optional[TextBlock]:
        """Merge consecutive heading-like blocks into a single title."""
        if current is None:
            if candidate.block_type == "text" and self._is_heading_candidate(candidate):
                return TextBlock(
                    text=candidate.text,
                    page=candidate.page,
                    bbox=candidate.bbox or fitz.Rect(),
                    font_size=candidate.font_size,
                    font_name="",
                    is_bold=candidate.is_bold,
                    is_centered=candidate.is_centered,
                )
            return None

        if candidate.block_type == "text" and self._is_heading_candidate(candidate):
            current.text = f"{current.text} {candidate.text}".strip()
            if candidate.bbox:
                current.bbox = fitz.Rect(
                    min(current.bbox.x0, candidate.bbox.x0),
                    min(current.bbox.y0, candidate.bbox.y0),
                    max(current.bbox.x1, candidate.bbox.x1),
                    max(current.bbox.y1, candidate.bbox.y1),
                )
            return current

        return current

    def _is_heading_candidate(self, block: PageBlock) -> bool:
        if block.block_type != "text":
            return False
        if len(block.text) < self.min_heading_length:
            return False
        if block.text.endswith(("-", ":", ".")) and len(block.text) < 30:
            return False
        return (
            block.font_size >= self.heading_font_threshold
            and block.is_bold
            and block.is_centered
        )

    def _classify_section_type(self, title: str, content: str) -> SectionType:
        """Classify a section as THEORETICAL or EXERCISE based on title and content."""
        text = (title + " " + content).lower()

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

        if 'worksheet' in title.lower() or 'phonics' in title.lower():
            return SectionType.EXERCISE

        if any(kw in title.lower() for kw in ['comprehending', 'glossary', 'speaking', 'discuss', 'think', 'answer']):
            return SectionType.EXERCISE

        return SectionType.THEORETICAL

    def _find_nearest_section(self, sections: List[SectionNode], page: int, y: float) -> Optional[SectionNode]:
        """Find the nearest section to an image by page and y-position."""
        candidates = [s for s in sections if s.page_range[0] <= page <= s.page_range[1]]
        if not candidates:
            return sections[-1] if sections else None
        return candidates[-1]

    def extract_chapters(self, pdf_path: Path, subject: Subject, grade: int, textbook_id: str) -> ChapterNode:
        """Extract full chapter structure from PDF."""
        page_blocks = self._extract_page_blocks(pdf_path)

        sections: List[SectionNode] = []
        current_section: Optional[SectionNode] = None
        section_counter = 0
        pending_images: List[ImageAsset] = []

        for block in page_blocks:
            if block.block_type == "image":
                pending_images.extend(block.images)
                continue

            text = block.text
            is_heading = self._is_heading_candidate(block)

            if is_heading:
                if current_section:
                    sections.append(current_section)

                section_counter += 1
                sec_type = self._classify_section_type(text, "")

                current_section = SectionNode(
                    id=f"sec_{section_counter:03d}",
                    type=sec_type,
                    title=text,
                    content_text="",
                    page_range=(block.page, block.page),
                    docling_refs=[DoclingRef(
                        item_id=f"pymupdf_{block.page}_{section_counter}",
                        page_number=block.page,
                        label="HEADING",
                    )],
                )

                # Associate any pending images with this new section
                if pending_images and current_section is not None:
                    current_section.figures.extend(pending_images)
                    pending_images.clear()

            elif current_section is not None:
                current_section.content_text += f" {text}"
                current_section.page_range = (
                    current_section.page_range[0],
                    max(current_section.page_range[1], block.page),
                )

                # Assign pending images to nearest section by position
                for image in pending_images:
                    target = self._find_nearest_section(
                        sections + ([current_section] if current_section else []),
                        image.page_number,
                        image.bbox.y0 if image.bbox else 0,
                    )
                    if target is not None:
                        target.figures.append(image)
                pending_images.clear()

                # Extract exercises within exercise sections
                if current_section.type == SectionType.EXERCISE and self.QUESTION_PATTERN.match(text):
                    current_section.exercises.append(ExerciseNode(
                        id=f"ex_{section_counter:03d}_{len(current_section.exercises)+1}",
                        question_text=text,
                        exercise_type=ExerciseType.SHORT_ANSWER,
                        difficulty=2,
                        page_number=block.page,
                        docling_refs=[DoclingRef(
                            item_id=f"pymupdf_q_{block.page}_{len(current_section.exercises)}",
                            page_number=block.page,
                            label="QUESTION",
                        )],
                    ))

        if current_section:
            sections.append(current_section)

        if not sections:
            all_text = " ".join(b.text for b in page_blocks if b.block_type == "text")
            sections.append(SectionNode(
                id="sec_001",
                type=SectionType.THEORETICAL,
                title="Extracted Content",
                content_text=all_text,
                page_range=(1, max((b.page for b in page_blocks), default=1)),
                docling_refs=[DoclingRef(item_id="pymupdf_all", page_number=1, label="CONTENT")],
            ))

        # Reclassify section types using full accumulated content
        for section in sections:
            section.type = self._classify_section_type(section.title, section.content_text)

        return ChapterNode(
            id=f"{textbook_id}_ch1",
            number=1,
            title=sections[0].title if sections else "Extracted Chapter",
            subject=subject,
            grade=grade,
            textbook_id=textbook_id,
            sections=sections,
            page_range=(1, max((b.page for b in page_blocks), default=1)),
            source_pdf=Path(pdf_path),
        )

    def extract(
        self,
        pdf_path: Path,
        subject: Subject,
        grade: int,
        textbook_id: str,
    ) -> ChapterNode:
        """Extract chapter structure from PDF."""
        return self.extract_chapters(pdf_path, subject, grade, textbook_id)

    def extract_text_blocks(self, pdf_path: Path) -> List[dict]:
        """Extract raw text blocks from PDF pages for backward compatibility."""
        page_blocks = self._extract_page_blocks(pdf_path)
        blocks = []
        for pb in page_blocks:
            if pb.block_type == "text":
                blocks.append({
                    "page_number": pb.page,
                    "text": pb.text,
                    "bbox": {
                        "x": pb.bbox.x0 if pb.bbox else 0,
                        "y": pb.bbox.y0 if pb.bbox else 0,
                        "w": (pb.bbox.x1 - pb.bbox.x0) if pb.bbox else 0,
                        "h": (pb.bbox.y1 - pb.bbox.y0) if pb.bbox else 0,
                    },
                    "block_type": "text",
                    "font_size": pb.font_size,
                    "is_bold": pb.is_bold,
                    "is_centered": pb.is_centered,
                })
        return blocks


def extract_with_pymupdf(pdf_path: Path, subject: Subject, grade: int, textbook_id: str) -> ChapterNode:
    """Convenience function for the pipeline."""
    extractor = PyMuPDFExtractor()
    return extractor.extract_chapters(pdf_path, subject, grade, textbook_id)
