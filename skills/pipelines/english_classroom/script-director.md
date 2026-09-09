---
mode: script-director
skill: pipelines/english_classroom/script-director
produces: [script_scenes]
tools_available: [groq_llm_script_writer]
checkpoint_required: true
human_approval_default: false
success_criteria:
  - one ScriptScene per section
  - all SceneStep.type values are in vocabulary
  - voiceover_lines have duration_seconds
review_focus:
  - vocabulary is grade-appropriate
  - exercises are walkable
---

# English Classroom — Script Director

## Goal

Convert the ChapterNode into a list of ScriptScene objects.

## Tool

Use `groq_llm_script_writer`. It takes:
- `chapter_json` or `chapter_path`
- `output_json` (optional)

## Fallback

If the LLM returns 401/403:
1. Log the failure.
2. The tool automatically generates placeholder scenes.
3. Do NOT retry more than 2 times per section.

## Output

- `script_scenes` JSON written to `.kilo/artifacts/<run_id>/script_scenes.json`

## Quality checks

- Every scene has `id`, `title`, `voiceover_lines`, `scene_steps`.
- Every `SceneStep.type` is a valid `SceneStepType` enum value.
- Every `VoiceoverLine` has `duration_seconds > 0`.
- Total scenes == chapter.sections.length.