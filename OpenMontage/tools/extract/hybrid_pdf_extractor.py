"""Hybrid PDF extractor routing between OpenDataLoader and Marker."""

from __future__ import annotations

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


class HybridPDFExtractor(BaseTool):
    name = "hybrid_pdf_extractor"
    version = "1.0.0"
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
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "markdown": {"type": "string"},
            "structured_json": {"type": "object"},
            "extraction_tool_used": {"type": "string"},
            "confidence_score": {"type": "number"},
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
        inline = len(re.findall(r"\$[^$]*\$", markdown))
        block = len(re.findall(r"\$\$[^$]*\$\$", markdown))
        total = inline + block
        word_count = len(markdown.split())
        density = total / max(word_count, 1) * 100
        return total, density

    def _run_opendataloader(self, pdf_path: str) -> tuple[str, dict, float]:
        start = time.monotonic()
        try:
            result = subprocess.run(
                ["java", "-jar", "opendataloader.jar", "--local", pdf_path],
                capture_output=True,
                text=True,
                timeout=300,
                check=True,
            )
            markdown = result.stdout
            structured_json = {"source": "opendataloader", "raw_output": markdown}
            return markdown, structured_json, time.monotonic() - start
        except Exception as exc:
            raise RuntimeError(f"OpenDataLoader failed: {exc}") from exc

    def _run_marker(self, pdf_path: str) -> tuple[str, dict, float]:
        start = time.monotonic()
        try:
            from marker.convert import convert_single_pdf
            markdown, images, metadata = convert_single_pdf(pdf_path, max_pages=50)
            structured_json = {"source": "marker", "metadata": metadata}
            return markdown, structured_json, time.monotonic() - start
        except Exception as exc:
            raise RuntimeError(f"Marker failed: {exc}") from exc

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        pdf_path = inputs.get("pdf_path", "")
        subject_type = inputs.get("subject_type", "mixed")
        layout_complexity = float(inputs.get("layout_complexity", 0.5))
        force_engine = inputs.get("force_engine")

        if not pdf_path or not Path(pdf_path).exists():
            return ToolResult(success=False, error=f"PDF not found: {pdf_path}")

        page_count = self._get_page_count(pdf_path)
        odl_markdown = ""
        odl_json = {}
        odl_time = 0.0
        final_markdown = ""
        final_json = {}
        tool_used = "opendataloader_local"
        confidence = 0.9

        try:
            odl_markdown, odl_json, odl_time = self._run_opendataloader(pdf_path)
        except Exception:
            odl_markdown = ""

        if odl_markdown:
            eq_count, math_density = self._count_latex_equations(odl_markdown)
            needs_marker = (
                force_engine == "marker"
                or math_density > 5
                or subject_type == "mathematics"
                or (math_density > 0 and layout_complexity > 0.7)
            )

            if needs_marker and force_engine != "opendataloader":
                try:
                    marker_md, marker_json, marker_time = self._run_marker(pdf_path)
                    if subject_type == "mathematics" or math_density > 5:
                        final_markdown = marker_md
                        final_json = marker_json
                        tool_used = "marker_balanced"
                    else:
                        final_markdown = odl_markdown
                        final_json = odl_json
                        tool_used = "opendataloader_hybrid"
                    confidence = 0.95
                except Exception:
                    final_markdown = odl_markdown
                    final_json = odl_json
                    tool_used = "opendataloader_local"
                    confidence = 0.85
            else:
                final_markdown = odl_markdown
                final_json = odl_json
                tool_used = "opendataloader_local"
                confidence = 0.9
        else:
            try:
                final_markdown, final_json, _ = self._run_marker(pdf_path)
                tool_used = "marker_balanced"
                confidence = 0.88
            except Exception as exc:
                return ToolResult(success=False, error=f"Both engines failed: {exc}")

        if confidence < 0.85:
            try:
                alt_md, alt_json, _ = self._run_marker(pdf_path)
                final_markdown = alt_md
                tool_used = "marker_balanced"
                confidence = 0.87
            except Exception:
                pass

        structured_output = {
            "version": "1.0",
            "title": Path(pdf_path).stem,
            "source_pdf": pdf_path,
            "extraction_tool_used": tool_used,
            "confidence_score": confidence,
            "total_pages": page_count,
            "sections": [
                {
                    "section_id": "s1",
                    "title": "Full Document",
                    "content": final_markdown[:5000],
                    "content_type": subject_type,
                }
            ],
            "metadata": {"odl_runtime_s": round(odl_time, 2)},
        }
        final_json.setdefault("version", "1.0")
        final_json.update(structured_output)

        return ToolResult(
            success=True,
            data={
                "markdown": final_markdown,
                "structured_json": final_json,
                "extraction_tool_used": tool_used,
                "confidence_score": confidence,
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
