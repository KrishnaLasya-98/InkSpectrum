"""Scene planner: converts ScriptScene list into a deterministic ScenePlan.

The scene plan is the bridge between script (what to say) and assets (what to show).
It produces a renderer-ready layout for each scene.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from tools.base_tool import BaseTool, ToolMetadata, ToolTier, ToolRuntime, ToolStability
from lib.tool_registry import register_tool

logger = logging.getLogger(__name__)


class ScenePlannerTool(BaseTool):
    metadata = ToolMetadata(
        name="scene_planner",
        version="1.0.0",
        tier=ToolTier.CORE,
        capability="scene_planning",
        provider="inkspectrum",
        runtime=ToolRuntime.LOCAL,
        stability=ToolStability.BETA,
        estimated_cost_usd=0.0,
        description="Convert ScriptScene list into a deterministic ScenePlan with layouts and asset lists",
        dependencies=[],
    )

    def run(self, input: dict[str, Any]) -> dict[str, Any]:
        scenes_json = input.get("scenes_json")
        if scenes_json:
            scenes = json.loads(scenes_json)
        else:
            path = Path(input["scenes_path"])
            scenes = json.loads(path.read_text(encoding="utf-8"))

        plan = []
        for scene in scenes:
            scene_plan = {
                "scene_id": scene.get("id"),
                "title": scene.get("title"),
                "duration_seconds": scene.get("duration_seconds"),
                "layout": "title_top" if scene.get("scene_steps") and scene.get("scene_steps")[0].get("type") == "title" else "centered",
                "assets_required": self._extract_assets(scene),
                "voiceover_lines": len(scene.get("voiceover_lines", [])),
                "scene_steps": len(scene.get("scene_steps", [])),
            }
            plan.append(scene_plan)

        output = {"scene_count": len(plan), "scenes": plan}
        out_path = input.get("output_json")
        if out_path:
            p = Path(out_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(output, indent=2), encoding="utf-8")

        return output

    def _extract_assets(self, scene: dict) -> list[str]:
        assets = []
        for step in scene.get("scene_steps", []):
            stype = step.get("type", "")
            if stype in ("vocabulary_card", "pronunciation_guide"):
                assets.append("image:vocabulary_card")
            elif stype in ("map_marker", "geographic_map"):
                assets.append("image:map")
            elif stype in ("latex_inline", "latex_block"):
                assets.append("render:latex")
            elif stype in ("word_highlight", "sentence_token"):
                assets.append("text:highlight")
        return assets


register_tool(ScenePlannerTool())
