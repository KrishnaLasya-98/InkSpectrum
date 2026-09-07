# PROJECT_CONTEXT.md

> Architecture reference for InkSpectrum. Single source of truth for the system design.

## Purpose

Turn a K-10 textbook PDF into a finished, narrated, captioned video. OpenMontage-style agent-first architecture.

## High-level flow

```
PDF textbook
   │
   ▼
research (extraction)       → ChapterNode JSON
   │
   ▼
script (LLM)                → ScriptScene[] JSON
   │
   ▼
scene_plan (rules)          → ScenePlan JSON
   │
   ▼
assets (ModelsLab)          → audio/, images/, video/ on disk
   │
   ▼
edit (reviewer)             → EditDecisions JSON
   │
   ▼
compose (Remotion/FFmpeg)   → final.mp4
   │
   ▼
publish (metadata)          → .kilo/output/videos/<id>.mp4
```

## Repository layout

```
D:\new_video_pip\
├── lib/                    # Core runtime: config, checkpoint, pipeline_loader, registry, cost tracker
├── tools/                  # Tools (BaseTool subclasses), grouped by capability
│   ├── base_tool.py
│   └── extraction/         # PDF → ChapterNode
├── pipeline_defs/          # YAML pipeline manifests
├── skills/                 # Agent instructions (Markdown), 3-layer hierarchy
├── schemas/                # JSON Schemas (exported from Pydantic)
├── styles/                 # Visual style playbooks (YAML)
├── packages/               # Internal package layout (textbook-pipeline, model-evaluator, video-explainer)
├── tests/                  # contracts/, qa/, eval/
├── docs/                   # Architecture, pipeline guide, cost guide
├── config.yaml             # Global runtime config
├── AGENT_GUIDE.md          # Operating guide and agent contract
├── PROJECT_CONTEXT.md      # This file
├── Makefile                # Common commands
├── .env                    # Secrets (gitignored)
└── .env.example            # Template
```

## Core principles

1. **Agent-first orchestration** — the LLM agent in the IDE is the control plane; Python is tools and persistence only.
2. **No LLM API key in runtime for orchestration** — the IDE's LLM is the orchestrator. Only domain APIs (ModelsLab, TTS, image gen) are called at runtime.
3. **Dual-provider support** — every capability must support API + local. Selector pattern ranks tools across 7 dimensions.
4. **Checkpoint-based resumption** — every stage writes a JSON checkpoint. Failed runs resume from the last completed stage.
5. **Schema-validated artifacts** — every stage output is validated against a Pydantic model and (where exported) a JSON Schema.
6. **Budget as a first-class concept** — cost is reserved before a tool call and reconciled after.
7. **3-layer skills hierarchy** — external tech → project core → per-pipeline stage director.

## Data model

Pydantic v2 in `packages/textbook-pipeline/src/textbook_pipeline/models/`:

- `ChapterNode` — a complete chapter extracted from a PDF
- `SectionNode` — a section within a chapter (theoretical / exercise / activity)
- `ExerciseNode` — a single question
- `ScriptScene` — narration + visual plan for a video scene
- `SceneStep` — one visual element at one moment in time
- `VoiceoverLine` — a single narration line
- `StoryboardScene` — script + audio linked with timing
- `AudioManifest` — TTS output with word-level timestamps

## Tool contract

`BaseTool` (in `tools/base_tool.py`) declares:
- `name`, `version` — identity
- `tier` — CORE | VOICE | ENHANCE | GENERATE | SOURCE | ANALYZE | PUBLISH
- `capability` — what it does (`pdf_extraction`, `tts`, `image_generation`, etc.)
- `provider` — which service (`opendataloader`, `modelslab`, `manim`, `ffmpeg`)
- `runtime` — LOCAL | LOCAL_GPU | API | HYBRID
- `stability` — EXPERIMENTAL | BETA | PRODUCTION
- `dependencies` — `cmd:ffmpeg`, `env:MODELSLAB_API_KEY`, `python:torch`
- `is_available()` — checks dependencies
- `run(input: dict) -> dict` — execute the tool

## Status

| Component | Status |
|-----------|--------|
| `lib/` runtime shell | ✅ Phase 1 |
| `tools/base_tool.py` | ✅ Phase 1 |
| `tools/extraction/*` | ✅ Phase 1 (3 extractors wrapped) |
| `config.yaml`, `AGENT_GUIDE.md`, `PROJECT_CONTEXT.md` | ✅ Phase 1 |
| `tests/contracts/` for BaseTool + registry | 🚧 Phase 1 (next) |
| `pipeline_defs/framework_smoke.yaml` | ✅ Phase 1 |
| `pipeline_defs/english_classroom.yaml` | 🚧 Phase 2 |
| `tools/script/`, `tools/audio/`, `tools/graphics/`, `tools/video/` | ⏳ Phases 2–3 |
| `remotion-composer/` | ⏳ Phase 4 |
| `styles/`, `docs/`, CI | ⏳ Phases 5–6 |

See `.kilo/plans/2026-09-07-inkspectrum-roadmap.md` for the full 12-week plan.
