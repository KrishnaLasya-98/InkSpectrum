"""Hybrid PDF extractor routing between OpenDataLoader and Marker."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    DependencyError,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStatus,
    ToolStability,
    ToolTier,
)

# ── Tunable thresholds (extracted from inline magic numbers) ──────────────────
# Raw LaTeX equation count above which Marker is preferred for math-heavy docs.
MATH_EQ_THRESHOLD = 5
# Layout complexity above which a hybrid (ODL + Marker) pass is used.
LAYOUT_COMPLEXITY_THRESHOLD = 0.7
# Below this measured confidence, retry with the alternate engine.
CONFIDENCE_FALLBACK = 0.85
# Baseline words/page used to estimate expected extraction volume.
WORDS_PER_PAGE_BASELINE = 120
# OpenDataLoader subprocess timeout (seconds); scales loosely with page count.
ODL_TIMEOUT_PER_PAGE = 6
ODL_TIMEOUT_MIN = 60
ODL_TIMEOUT_MAX = 600
# Preview length stored per section in the structured artifact.
SECTION_PREVIEW_CHARS = 500


class HybridPDFExtractor(BaseTool):
    name = "hybrid_pdf_extractor"
    version = "1.1.0"
    tier = ToolTier.SOURCE
    capability = "pdf_extraction"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.HYBRID

    dependencies = ["binary:java", "binary:python3"]
    install_instructions = (
        "Install OpenDataLoader (Java 11+): https://github.com/OpenDataLoader/OpenDataLoader\n"
        "Install Marker: pip install marker-pdf\n"
        "For GPU acceleration with Marker: pip install marker-pdf[gpu]"
    )
    agent_skills = ["pdf-extraction", "latex-rendering"]

    capabilities = ["pdf_extraction", "math_extraction", "table_extraction"]

    input_schema = {
        "type": "object",
        "required": ["pdf_path"],
        "properties": {
            "pdf_path": {"type": "string"},
            "subject_type": {
                "type": "string",
                "enum": ["theory", "mathematics", "mixed"],
                "default": "mixed",
            },
            "layout_complexity": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
            "force_engine": {
                "type": "string",
                "enum": ["opendataloader", "marker", "hybrid"],
            },
            "page_range": {"type": "array", "items": {"type": "integer"}},
            "output_dir": {"type": "string"},
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "markdown": {"type": "string"},
            "structured_json": {"type": "object"},
            "extraction_tool_used": {"type": "string"},
            "confidence_score": {"type": "number"},
            "markdown_path": {"type": "string"},
            "artifact_path": {"type": "string"},
        },
    }

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        pdf_path = inputs.get("pdf_path", "")
        page_count = self._get_page_count(pdf_path)
        return max(page_count * 0.015, 1.0)

    def _get_page_count(self, pdf_path: str) -> int:
        try:
            import fitz
            doc = fitz.open(pdf_path)
            return len(doc)
        except Exception:
            return 1

    def _count_latex_equations(self, markdown: str) -> tuple[int, float]:
        """Return (raw equation count, density as % of words)."""
        inline = len(re.findall(r"\$[^$]*\$", markdown))
        block = len(re.findall(r"\$\$[^$]*\$\$", markdown))
        total = inline + block
        word_count = len(markdown.split())
        density = total / max(word_count, 1) * 100
        return total, density

    def _compute_confidence(
        self, markdown: str, page_count: int, extracted_pages: int | None = None
    ) -> float:
        """Measured confidence from content volume vs. expected volume.

        Low only when extraction actually produced little content for the page
        count (e.g. image-only scans), so the fallback at CONFIDENCE_FALLBACK
        reflects real quality rather than a hardcoded branch label.
        """
        if not markdown or not markdown.strip():
            return 0.0
        words = len(markdown.split())
        expected = max(page_count, 1) * WORDS_PER_PAGE_BASELINE
        coverage = min(words / expected, 1.0)
        if extracted_pages:
            page_cov = min(extracted_pages / max(page_count, 1), 1.0)
            coverage = min(coverage, page_cov)
        return round(min(0.55 + 0.45 * coverage, 0.99), 2)

    def _split_sections(self, markdown: str, content_type: str) -> list[dict[str, Any]]:
        """Split markdown into real sections by heading (mirrors SectionParser)."""
        parts = re.split(r"^(#{1,6}\s+.+)$", markdown, flags=re.M)
        sections: list[dict[str, Any]] = []
        idx = 0

        def add(title: str, body: str) -> None:
            nonlocal idx
            body = body.strip()
            if body or title:
                sections.append({
                    "section_id": f"s{idx + 1}",
                    "title": title or f"Section {idx + 1}",
                    "content": body,
                    "content_preview": body[:SECTION_PREVIEW_CHARS],
                    "content_type": content_type,
                })
                idx += 1

        if parts and parts[0].strip() and not parts[0].lstrip().startswith("#"):
            add("Introduction", parts[0])
        i = 1
        while i < len(parts):
            title = re.sub(r"^#+\s*", "", parts[i].strip())
            body = parts[i + 1] if i + 1 < len(parts) else ""
            add(title, body)
            i += 2

        if not sections:
            add("Full Document", markdown)
        return sections

    def _run_opendataloader(self, pdf_path: str, page_count: int) -> tuple[str, dict, float]:
        timeout = max(
            ODL_TIMEOUT_MIN,
            min(ODL_TIMEOUT_MAX, page_count * ODL_TIMEOUT_PER_PAGE),
        )
        start = time.monotonic()
        try:
            result = subprocess.run(
                ["java", "-jar", "opendataloader.jar", "--local", pdf_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=True,
            )
            markdown = result.stdout
            structured_json = {"source": "opendataloader", "raw_output": markdown}
            return markdown, structured_json, time.monotonic() - start
        except Exception as exc:
            raise RuntimeError(f"OpenDataLoader failed: {exc}") from exc

    def _run_marker(
        self, pdf_path: str, page_count: int, page_range: list[int] | None = None
    ) -> tuple[str, dict, int | None, float]:
        # Extract the entire document (no silent 50-page truncation). A caller
        # may narrow scope via page_range; otherwise we honour the real length.
        max_pages = page_count
        if page_range:
            if len(page_range) >= 2:
                max_pages = max(1, page_range[1] - page_range[0] + 1)
            elif page_range:
                max_pages = max(1, page_range[0])
        start = time.monotonic()
        try:
            from marker.convert import convert_single_pdf
            markdown, images, metadata = convert_single_pdf(
                pdf_path, max_pages=max_pages
            )
            extracted_pages = (metadata or {}).get("pages")
            if isinstance(extracted_pages, list):
                extracted_pages = len(extracted_pages)
            structured_json = {"source": "marker", "metadata": metadata}
            return markdown, structured_json, extracted_pages, time.monotonic() - start
        except Exception as exc:
            raise RuntimeError(f"Marker failed: {exc}") from exc

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        pdf_path = inputs.get("pdf_path", "")
        subject_type = inputs.get("subject_type", "mixed")
        layout_complexity = float(inputs.get("layout_complexity", 0.5))
        force_engine = inputs.get("force_engine")
        page_range = inputs.get("page_range")

        if not pdf_path or not Path(pdf_path).exists():
            return ToolResult(success=False, error=f"PDF not found: {pdf_path}")

        page_count = self._get_page_count(pdf_path)
        odl_markdown = ""
        odl_json: dict[str, Any] = {}
        odl_time = 0.0
        final_markdown = ""
        final_json: dict[str, Any] = {}
        marker_pages: int | None = None
        tool_used = "opendataloader_local"
        confidence = 0.0

        try:
            odl_markdown, odl_json, odl_time = self._run_opendataloader(pdf_path, page_count)
        except Exception:
            odl_markdown = ""

        if odl_markdown:
            eq_count, _density = self._count_latex_equations(odl_markdown)
            needs_marker = (
                force_engine == "marker"
                or eq_count > MATH_EQ_THRESHOLD
                or subject_type == "mathematics"
                or (eq_count > 0 and layout_complexity > LAYOUT_COMPLEXITY_THRESHOLD)
            )

            if needs_marker and force_engine != "opendataloader":
                try:
                    marker_md, marker_json, marker_pages, _mt = self._run_marker(
                        pdf_path, page_count, page_range
                    )
                    if subject_type == "mathematics" or eq_count > MATH_EQ_THRESHOLD:
                        final_markdown = marker_md
                        final_json = marker_json
                        tool_used = "marker_balanced"
                    else:
                        final_markdown = odl_markdown
                        final_json = odl_json
                        tool_used = "opendataloader_hybrid"
                except Exception:
                    final_markdown = odl_markdown
                    final_json = odl_json
                    tool_used = "opendataloader_local"
            else:
                final_markdown = odl_markdown
                final_json = odl_json
                tool_used = "opendataloader_local"
        else:
            try:
                final_markdown, final_json, marker_pages, _mt = self._run_marker(
                    pdf_path, page_count, page_range
                )
                tool_used = "marker_balanced"
            except Exception as exc:
                return ToolResult(success=False, error=f"Both engines failed: {exc}")

        # Real, measured confidence (replaces the old hardcoded branch labels).
        confidence = self._compute_confidence(final_markdown, page_count, marker_pages)

        # Self-healing: retry with the alternate engine on genuinely low output.
        if confidence < CONFIDENCE_FALLBACK:
            try:
                alt_md, alt_json, alt_pages, _at = self._run_marker(
                    pdf_path, page_count, page_range
                )
                alt_conf = self._compute_confidence(alt_md, page_count, alt_pages)
                if alt_conf > confidence:
                    final_markdown = alt_md
                    final_json = alt_json
                    marker_pages = alt_pages
                    tool_used = "marker_balanced"
                    confidence = alt_conf
            except Exception:
                pass

        structured_output = {
            "version": "1.1",
            "title": Path(pdf_path).stem,
            "source_pdf": pdf_path,
            "extraction_tool_used": tool_used,
            "confidence_score": confidence,
            "total_pages": page_count,
            "pages_extracted": marker_pages if marker_pages is not None else page_count,
            "sections": self._split_sections(final_markdown, subject_type),
            "metadata": {
                "odl_runtime_s": round(odl_time, 2),
                "math_equation_count": self._count_latex_equations(final_markdown)[0],
            },
        }
        final_json.setdefault("version", "1.1")
        final_json.update(structured_output)

        markdown_path = ""
        artifact_path = ""
        if inputs.get("output_dir"):
            out_dir = Path(inputs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            markdown_file = out_dir / "extracted_content.md"
            artifact_file = out_dir / "extracted_content.json"
            markdown_file.write_text(final_markdown, encoding="utf-8")
            artifact_file.write_text(
                json.dumps(final_json, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            markdown_path = str(markdown_file)
            artifact_path = str(artifact_file)

        return ToolResult(
            success=True,
            data={
                "markdown": final_markdown,
                "structured_json": final_json,
                "extraction_tool_used": tool_used,
                "confidence_score": confidence,
                "markdown_path": markdown_path,
                "artifact_path": artifact_path,
            },
            artifacts=["extracted_content"],
            cost_usd=0.0,
            duration_seconds=odl_time,
        )

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {
            "tool": self.name,
            "estimated_cost_usd": 0.0,
            "estimated_runtime_seconds": self.estimate_runtime(inputs),
            "status": self.get_status().value,
            "would_execute": True,
        }

    def get_status(self) -> ToolStatus:
        java_ok = shutil.which("java") is not None
        python_ok = shutil.which("python3") is not None or shutil.which("python") is not None
        if java_ok and python_ok:
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE
