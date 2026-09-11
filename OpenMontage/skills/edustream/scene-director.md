# Stage Director: scene_plan

## Overview
Execute the scene planning stage for EduStream Pilot content.

## Method
- Code2Video-inspired storyboard generation

## Grid System
- 6x6 grid system (rows A-F, cols 1-6)
- Grid coordinates: A1=(0.5, 2.2), A6=(5.5, 2.2), F1=(0.5, -3.8), F6=(5.5, -3.8)

## Planner
- Claude-4-Opus as planner LLM

## Assets
- SmartSVGDownloader for real-world object assets (IconFinder + Iconify)
- Constraints: only first/last sections, max 4 assets, only real-world objects

## Scene Types
- talking_head, broll, animation, diagram, text_card, transition

## Math Animation
- Math animation requirements tagged for Stage 4

## Output
- `scene_plan.json` + `asset_manifest.json`
