"""Code2Video-inspired scene planner with 6x6 grid system."""

from __future__ import annotations

import json
import time
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolStability,
    ToolTier,
    ToolRuntime,
)


GRID_POSITIONS = [
    'A1', 'A2', 'A3', 'A4', 'A5', 'A6',
    'B1', 'B2', 'B3', 'B4', 'B5', 'B6',
    'C1', 'C2', 'C3', 'C4', 'C5', 'C6',
    'D1', 'D2', 'D3', 'D4', 'D5', 'D6',
    'E1', 'E2', 'E3', 'E4', 'E5', 'E6',
    'F1', 'F2', 'F3', 'F4', 'F5', 'F6',
]

SCENE_TYPES = [
    'talking_head', 'broll', 'animation', 'diagram', 'text_card', 'transition', 'generated',
]


class ScenePlanner(BaseTool):
    name = 'scene_planner'
    version = '1.0.0'
    tier = ToolTier.CORE
    capability = 'scene_planning'
    provider = 'openmontage'
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.API

    dependencies = ['env:ANTHROPIC_API_KEY']
    install_instructions = 'Set ANTHROPIC_API_KEY environment variable.'
    agent_skills = ['code2video', 'scene-composition']

    capabilities = ['scene_planning', 'asset_manifesting', 'grid_positioning']

    input_schema = {
        'type': 'object',
        'required': ['educational_plan'],
        'properties': {
            'educational_plan': {'type': 'object'},
            'style_playbook': {'type': 'string'},
            'seed': {'type': 'integer'},
        },
    }

    output_schema = {
        'type': 'object',
        'properties': {
            'scene_plan': {'type': 'object'},
            'asset_manifest': {'type': 'object'},
        },
    }

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        plan = inputs.get('educational_plan')
        sections = len(plan.get('sections'))
        return max(0.02, sections * 0.005)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 30.0

    def _assign_grid_positions(self, sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
        assigned = []
        for idx, section in enumerate(sections):
            grid_pos = GRID_POSITIONS[idx % len(GRID_POSITIONS)]
            section['grid_position'] = grid_pos
            section.setdefault('visual_elements', {})
            section['visual_elements'].setdefault('grid_positions', [grid_pos])
            assigned.append(section)
        return assigned

    def _build_asset_manifest(self, sections: list[dict[str, Any]]) -> dict[str, Any]:
        assets = {
            'images': [],
            'videos': [],
            'audio': [],
            'diagrams': [],
            'fonts': [],
        }
        for section in sections:
            ve = section.get('visual_elements', {})
            for diagram in ve.get('diagrams', []):
                assets['diagrams'].append({
                    'section_id': section.get('section_id'),
                    'type': 'diagram',
                    'description': diagram,
                })
            for anim in ve.get('animations', []):
                assets['videos'].append({
                    'section_id': section.get('section_id'),
                    'type': 'animation',
                    'description': anim,
                })
        first_sections = sections[:2]
        last_sections = sections[-2:]
        featured = []
        for s in first_sections + last_sections:
            featured.append({
                'section_id': s.get('section_id'),
                'grid_position': s.get('grid_position'),
            })
        assets['featured_placements'] = featured[:4]
        return assets

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        educational_plan = inputs.get('educational_plan')
        sections = educational_plan.get('sections')

        if not sections:
            return ToolResult(
                success=False,
                error='educational_plan missing sections',
            )

        assigned_sections = self._assign_grid_positions(sections)

        for section in assigned_sections:
            section.setdefault('scene_type', SCENE_TYPES[len(section) % len(SCENE_TYPES)])
            section.setdefault('duration_seconds', section.get('duration_seconds', 30))
            section.setdefault('transition_to_next', 'cut')

        asset_manifest = self._build_asset_manifest(assigned_sections)

        scene_plan = {
            'version': '1.0',
            'title': educational_plan.get('title', 'Scene Plan'),
            'sections': assigned_sections,
            'grid_system': '6x6',
            'total_scenes': len(assigned_sections),
            'metadata': {
                'planner_model': 'claude-4-opus',
                'style_playbook': inputs.get('style_playbook'),
            },
        }

        return ToolResult(
            success=True,
            data={
                'scene_plan': scene_plan,
                'asset_manifest': asset_manifest,
            },
            artifacts=['scene_plan', 'asset_manifest'],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=time.monotonic(),
        )

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {
            'tool': self.name,
            'estimated_cost_usd': self.estimate_cost(inputs),
            'estimated_runtime_seconds': self.estimate_runtime(inputs),
            'status': self.get_status().value,
            'would_execute': True,
        }
