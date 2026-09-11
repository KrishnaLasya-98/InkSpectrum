# EduStream Pro — Pipeline Runner Skill

## Overview

This skill teaches the AI agent (Claude / Kiro / Cursor / Kilo) how to invoke
the full EduStream Pro pipeline for any Class 1 subject.

**Entry point:**
```bash
python -m tools.structure.subject_pipeline_runner --subject <evs|english|maths>
python -m tools.structure.subject_pipeline_runner --subject evs --dry-run   # test run
```

The pipeline is defined in `pipeline_defs/edustream-pro.yaml`.
All stages are resumable — if a run is interrupted, re-running picks up from
the last completed checkpoint.

## Prerequisites

1. `.env` has `MODELSLAB_API_KEY` set (all TTS + video models are free/unlimited)
2. `ffmpeg` and `ffprobe` are on PATH (`winget install FFmpeg` on Windows)
3. `manim` installed: `pip install manim`
4. `hyperframes` CLI installed: `npm install -g hyperframes`
5. `npx remotion` available: `cd remotion-composer && npm install`

## Triggering from Natural Language

When the user says any of:
- "Generate an EduStream Pro video for EVS"
- "Make the Class 1 Animal Life chapter video"
- "Run the pipeline for Maths Chapter 8"
- "Build educational video for English Lesson 1"

→ Read `pipeline_defs/edustream-pro.yaml` first, then invoke the pipeline runner.

## Stage Summary

| Stage | Tool | Cost |
|---|---|---|
| 0 Input ingestion | `section_parser` | $0 |
| 1 Content structuring | `educational_content_generator` | $0 (dry_run) or ~$0.05 |
| 2 Orchestration | `edustream_orchestrator` | $0 |
| 3 Render clips | `render_mode_router` → Manim/Remotion/HyperFrames/ModelsLab | $0 |
| 4 Voice synthesis | `voice_synthesis_pipeline` (ModelsLab text-to-speech) | $0 |
| 5 Composition | `av_composer` + subtitle burn | $0 |
| 6 QA + export | `quality_assurance` + `export_bundle` | $0 |
| **Total** | | **$0** |

## Dry-Run Mode

Always run with `--dry-run` first to verify the pipeline completes without errors:
```bash
python -m tools.structure.subject_pipeline_runner --subject evs --dry-run
```

Dry-run exercises all stages, writes checkpoint files, and produces a cost
estimate — but skips all API calls and renders. Takes ~5 seconds.

## Output Files

After a successful run, the following files are written to
`projects/{subject}/`:

```
artifacts/
  section_blocks.json        ← ContentBlock[] from SectionParser
  educational_plan.json      ← EduGen 6-step plan with render_mode
  evs_script.json            ← LASEV EVS triplet (P, N, A)
  narration_manifest.json    ← TTS segments + STT QA results
  cost_log.json              ← per-stage cost breakdown

renders/
  clips/
    s00_title.mp4            ← HyperFrames chapter title card
    s01.mp4 s02.mp4 ...      ← per-section clips
    clip_manifest.json       ← router results
  audio/
    s01.wav s02.wav ...      ← narration audio per section
  {subject}_chapter.mp4      ← composed video (no subtitles)
  {subject}_chapter_final.mp4 ← final video with subtitles burned
  {subject}_chapter.srt      ← subtitle file
```

## Running All Three Subjects

```bash
# Run sequentially
python -m tools.structure.subject_pipeline_runner --subject evs
python -m tools.structure.subject_pipeline_runner --subject english
python -m tools.structure.subject_pipeline_runner --subject maths
```

## Troubleshooting

**"MODELSLAB_API_KEY not set"** → set in `.env` and reload environment

**"HyperFrames CLI not found"** → `npm install -g hyperframes`
(non-fatal: chapter title card skipped, rest of pipeline continues)

**"Manim render timed out"** → Reduce section `duration_seconds` or
lower quality with `--quality low`

**"X clips failed to render"** → Check `renders/clips/clip_manifest.json`
for error messages per section_id. Fix the section in `educational_plan.json`
and re-run (already-rendered clips are skipped automatically)

**Stage 1 produces sections without render_mode** → The LLM didn't assign
render_mode. The `_infer_render_mode()` heuristic in `educational_generator.py`
fills them automatically based on source_block_type and keywords.
