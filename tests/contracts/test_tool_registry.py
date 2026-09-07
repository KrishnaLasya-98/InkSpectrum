"""Contract tests for lib.tool_registry and BaseTool."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.base_tool import BaseTool, ToolMetadata, ToolTier, ToolRuntime, ToolStability
from lib.tool_registry import register_tool, get_tool, all_tools, list_capabilities, by_capability


class DummyTool(BaseTool):
    metadata = ToolMetadata(
        name="dummy_test_tool",
        version="1.0.0",
        tier=ToolTier.CORE,
        capability="testing",
        provider="dummy",
        runtime=ToolRuntime.LOCAL,
        stability=ToolStability.PRODUCTION,
        description="A dummy tool for contract tests",
    )

    def run(self, input: dict) -> dict:
        return {"echo": input.get("value", "")}


class TestBaseToolContract:
    def test_describe_shape(self):
        d = DummyTool().describe()
        assert d["name"] == "dummy_test_tool"
        assert d["tier"] == "core"
        assert d["runtime"] == "local"
        assert d["stability"] == "production"
        assert d["available"] is True
        assert d["missing_dependencies"] == []

    def test_run_returns_dict(self):
        result = DummyTool().run({"value": "hi"})
        assert result == {"echo": "hi"}


class TestToolRegistry:
    def test_register_and_get(self):
        register_tool(DummyTool())
        tool = get_tool("dummy_test_tool")
        assert tool.metadata.name == "dummy_test_tool"

    def test_by_capability(self):
        register_tool(DummyTool())
        tools = by_capability("testing")
        assert any(t.metadata.name == "dummy_test_tool" for t in tools)

    def test_list_capabilities(self):
        register_tool(DummyTool())
        caps = list_capabilities()
        assert "testing" in caps

    def test_unknown_tool_raises(self):
        with pytest.raises(KeyError):
            get_tool("definitely_not_a_real_tool_xyz")


class TestExtractionToolsRegistered:
    """Verify the Phase-1 extraction tools auto-register on import."""

    def test_opendataloader_registered(self):
        # Importing the module triggers registration
        import tools.extraction.opendataloader  # noqa: F401
        tool = get_tool("opendataloader_extract")
        assert tool.metadata.capability == "pdf_extraction"
        assert tool.metadata.runtime == ToolRuntime.LOCAL
        assert tool.metadata.stability == ToolStability.PRODUCTION

    def test_pymupdf_registered(self):
        import tools.extraction.pymupdf  # noqa: F401
        tool = get_tool("pymupdf_extract")
        assert tool.metadata.capability == "pdf_extraction"

    def test_docling_registered(self):
        import tools.extraction.docling  # noqa: F401
        tool = get_tool("docling_extract")
        assert tool.metadata.capability == "pdf_extraction"

    def test_all_extraction_tools_have_correct_metadata(self):
        import tools.extraction.opendataloader  # noqa: F401
        import tools.extraction.pymupdf  # noqa: F401
        import tools.extraction.docling  # noqa: F401
        for tool in all_tools():
            if tool.metadata.capability == "pdf_extraction":
                assert tool.metadata.tier == ToolTier.SOURCE
                assert tool.metadata.runtime in (ToolRuntime.LOCAL, ToolRuntime.HYBRID)
