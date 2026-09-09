---
mode: scene-plan-director
skill: pipelines/english_classroom/scene-plan-director
produces: [scene_plan]
tools_available: [scene_planner]
checkpoint_required: true
human_approval_default: false
success_criteria:
  - each scene has a layout
  - each scene has an asset list
review_focus:
  - asset list is complete
  - layout is renderer-compatible
---

# English Classroom — Scene Plan Director

## Goal

Convert ScriptScene[] into a deterministic ScenePlan.

## Tool

Use `scene_planner`. It takes:
- `scenes_json` or `scenes_path`
- `output_json` (optional)

## Output

- `scene_plan` JSON written to `.kilo/artifacts/<run_id>/scene_plan.json`

## Quality checks

- Every scene has `layout` (one of: title_top, centered, split, fullscreen).
- Every scene has `assets_required` list (may be empty for text-only scenes).
- `scene_count` matches `script_scenes` input count.