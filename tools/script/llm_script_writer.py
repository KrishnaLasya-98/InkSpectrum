"""LLM script writer tool wrapper.

Wraps textbook_pipeline.core.script.writer.ScriptWriter in the BaseTool contract.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from tools.base_tool import BaseTool, ToolMetadata, ToolTier, ToolRuntime, ToolStability
from lib.tool_registry import register_tool
from textbook_pipeline.core.script.writer import ScriptWriter
from textbook_pipeline.models.chapter import ChapterNode

logger = logging.getLogger(__name__)


class LLMScriptWriterTool(BaseTool):
    metadata = ToolMetadata(
        name="groq_llm_script_writer",
        version="1.0.0",
        tier=ToolTier.CORE,
        capability="script_generation",
        provider="groq",
        runtime=ToolRuntime.API,
        stability=ToolStability.BETA,
        estimated_cost_usd=0.01,
        description="Generate pedagogical video scripts from ChapterNode using Groq LLM",
        dependencies=["env:GROQ_API_KEY"],
    )

    def __init__(self):
        self._writer = ScriptWriter()

    def run(self, input: dict[str, Any]) -> dict[str, Any]:
        chapter_json = input.get("chapter_json")
        output_json = input.get("output_json")
        chunk_size = input.get("chunk_size", 999)
        delay_seconds = input.get("delay_seconds", 0.0)
        checkpoint_path = input.get("checkpoint_path")

        if chapter_json:
            chapter = ChapterNode.model_validate_json(chapter_json)
        else:
            chapter_path = Path(input["chapter_path"])
            chapter = ChapterNode.model_validate_json(chapter_path.read_text(encoding="utf-8"))

        # Use chunked mode if delay_seconds > 0 or checkpoint_path is set
        if delay_seconds > 0 or checkpoint_path:
            scenes = self._writer.generate_chapter_script_chunked(
                chapter,
                chunk_size=chunk_size,
                delay_seconds=delay_seconds,
                checkpoint_path=checkpoint_path,
            )
        else:
            scenes = self._writer.generate_chapter_script(chapter)

        out_path: Path | None = None
        if output_json:
            out_path = Path(output_json)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                "[\n" + ",\n".join(s.model_dump_json(indent=2) for s in scenes) + "\n]\n",
                encoding="utf-8",
            )

        return {
            "scene_count": len(scenes),
            "output_json": str(out_path) if out_path else None,
            "scenes": [s.model_dump(mode="json") for s in scenes],
        }


register_tool(LLMScriptWriterTool())
