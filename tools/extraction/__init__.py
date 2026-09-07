"""Extraction tools: PDF to ChapterNode.

These are thin tool wrappers around the existing Pydantic models in
`packages/textbook-pipeline`. The wrapper adds the OpenMontage BaseTool
contract so the registry can discover and route them.
"""

from __future__ import annotations
