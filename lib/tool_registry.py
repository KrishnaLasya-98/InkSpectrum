"""Auto-discovery tool registry. Tools register themselves on import.

Pattern mirrors OpenMontage `tools/tool_registry.py`:
- A tool module imports and decorates a class with `@register_tool`.
- `get_tool(name)` returns the instance by capability name.
- `list_capabilities()` enumerates what the system can do.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from tools.base_tool import BaseTool, ToolMetadata

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._by_capability: dict[str, list[BaseTool]] = {}
        self._lock = threading.Lock()

    def register(self, tool: BaseTool) -> None:
        with self._lock:
            self._tools[tool.metadata.name] = tool
            self._by_capability.setdefault(tool.metadata.capability, []).append(tool)
            logger.info("Registered tool: %s (capability=%s)", tool.metadata.name, tool.metadata.capability)

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise KeyError(f"Tool not registered: {name}. Known: {list(self._tools)}")
        return self._tools[name]

    def by_capability(self, capability: str) -> list[BaseTool]:
        return list(self._by_capability.get(capability, []))

    def list_capabilities(self) -> list[str]:
        return sorted(self._by_capability.keys())

    def all(self) -> list[BaseTool]:
        return list(self._tools.values())


_REGISTRY = ToolRegistry()


def register_tool(tool: BaseTool) -> BaseTool:
    """Decorator / helper. Registers a tool instance into the singleton registry."""
    _REGISTRY.register(tool)
    return tool


def get_tool(name: str) -> BaseTool:
    return _REGISTRY.get(name)


def by_capability(capability: str) -> list[BaseTool]:
    return _REGISTRY.by_capability(capability)


def list_capabilities() -> list[str]:
    return _REGISTRY.list_capabilities()


def all_tools() -> list[BaseTool]:
    return _REGISTRY.all()


def registry() -> ToolRegistry:
    return _REGISTRY
