---
title: InkSpectrum Roadmap to OpenMontage Alignment
status: roadmap
target: production-ready textbook-to-video pipeline
reference: calesthio/OpenMontage (12 pipelines, 52 tools, 500+ skills)
---

# InkSpectrum Roadmap — Aligned with OpenMontage Patterns

## 0. Reference Patterns Extracted from OpenMontage

After reviewing the upstream `calesthio/OpenMontage` repository and its `docs/ARCHITECTURE.md`, I extracted the following canonical patterns. InkSpectrum will adopt each.

### 0.1 Core Principles (from upstream)

| # | Principle | OpenMontage expression |
|---|-----------|-----------------------|
| P1 | **Agent-first orchestration** — no Python orchestrator; the LLM agent reads YAML + Markdown and drives everything | `lib/` is tools/persistence only; no `main.py` that runs the pipeline |
| P2 | **No LLM API key in runtime** — the agent running in the user's IDE *is* the LLM | Tools call domain APIs directly, not general-purpose LLM endpoints |
| P3 | **Dual-provider support** — every capability must support API + local/open-source | Selector pattern ranks tools across 7 dimensions |
| P4 | **Checkpoint-based resumption** — any stage fails, pipeline resumes from last checkpoint | JSON checkpoint per stage with artifact references |
| P5 | **Schema-validated artifacts** — every stage output validated against JSON Schema before checkpoint write | Pydantic models + JSON Schema |
| P6 | **Budget as first-class concept** — cost estimation, reservation, reconciliation | `config.yaml` declares `budget_default_usd` per pipeline |
| P7 | **Selector pattern over hard-coded providers** — capabilities degrade gracefully | `selector` runtime, scored across 7 dimensions |
| P8 | **3-layer skills hierarchy** — external tech skills → project skills → stage director skills | `.agents/skills/` (external) → `skills/core/` (project) → `skills/pipelines/<pipeline>/` (stage director) |

### 0.2 Repository Layout (from upstream)

```
OpenMontage/
├── lib/                    # Core runtime (config, checkpoint, pipeline_loader, media_profiles, env_loader)
├── tools/                  # 52 Python tools, grouped by capability
│   ├── base_tool.py        # Abstract base class — the tool contract
│   ├── tool_registry.py    # Auto-discovery singleton registry
│   ├── video/              # 13 video gen + compose/stitch/trim
│   ├── audio/              # 4 TTS + music + mixing
│   ├── graphics/           # 9 image/graphics
│   ├── enhancement/        # Upscale, bg remove, color grade
│   ├── analysis/           # Transcription, scene detect
│   ├── avatar/             # Talking head, lip sync
│   └── subtitle/           # SRT/VTT
├── pipeline_defs/          # 12 YAML pipeline manifests
├── skills/                 # 124+ Markdown skill files
│   ├── core/               # FFmpeg, Remotion, WhisperX skills
│   ├── creative/           # Editing, data viz, prompt engineering
│   ├── meta/               # reviewer, checkpoint-protocol, skill-creator
│   └── pipelines/          # Per-pipeline stage director skills
├── .agents/skills/         # External technology skills (47)
├── styles/                 # Visual style playbooks (YAML)
├── remotion-composer/      # Node.js/React renderer
├── schemas/                # JSON Schemas (artifacts, pipelines, styles, tools)
├── tests/                  # contracts/, qa/, eval/, pipelines/, tools/
└── docs/                   # ARCHITECTURE.md, handoffs, audits
```

### 0.3 BaseTool Contract (from upstream)

Every tool declares identity, tier, capability, provider, runtime, stability, and dependencies. This is the foundation InkSpectrum must adopt.

### 0.4 8-Stage Canonical Pipeline

```
research → proposal → script → scene_plan → assets → edit → compose → publish
```

InkSpectrum currently stops at `script` and only partially does `scene_plan`. The remaining 5 stages are missing.

---

## 1. InkSpectrum Current State — Audit

### 1.1 What exists today

| Component | Location | Status |
|-----------|----------|--------|
| Pydantic models | `packages/textbook-pipeline/src/textbook_pipeline/models/` | ✅ Working — `ChapterNode`, `SectionNode`, `ExerciseNode`, `ScriptScene`, `SceneStep`, `VoiceoverLine`, `StoryboardScene`, `AudioManifest` |
| Ingestion (PDF extract) | `packages/textbook-pipeline/src/textbook_pipeline/core/ingestion/` | ⚠️ Partial — `PyMuPDFExtractor`, `DoclingExtractor`, `OpenDataLoaderExtractor` (just added), `ChapterBuilder` |
| Script writer (LLM) | `packages/textbook-pipeline/src/textbook_pipeline/core/script/writer.py` | ⚠️ Partial — schema mismatches just fixed, Groq API key invalid |
| TTS / Image / Video clients | `packages/textbook-pipeline/src/textbook_pipeline/core/clients/` (ModelsLab) | ⚠️ Partial — clients exist, not yet wired into a stage |
| Skills | `.kilo/skills/inkspectrum-*/SKILL.md` (7 skills) | ✅ Present — orchestrator, extraction, script-generation, TTS, image-asset, video-asset, manim-renderer, remotion-renderer |
| Tests | `packages/textbook-pipeline/tests/` | ✅ 23/23 passing |
| Agent defs | `.kilo/agents/` (9 agents including new repo-optimizer) | ✅ Defined |
| Schemas directory | `schemas/` | ❌ **Missing** — must be created |
| Pipeline defs | `pipeline_defs/` | ❌ **Missing** — must be created |
| Tools directory | `tools/` (top-level) | ❌ **Missing** — must be created |
| Lib (runtime) | `lib/` | ❌ **Missing** — must be created |
| Checkpoint system | `lib/checkpoint.py` | ❌ **Missing** — must be created |
| Pipeline loader | `lib/pipeline_loader.py` | ❌ **Missing** — must be created |
| Style playbooks | `styles/` | ❌ **Missing** — must be created |
| Renderer | `remotion-composer/` | ❌ **Missing** — must be created |
| `config.yaml` | repo root | ❌ **Missing** — must be created |
| `AGENT_GUIDE.md` / `PROJECT_CONTEXT.md` | repo root | ❌ **Missing** — must be created |

### 1.2 Gaps vs OpenMontage

1. **No top-level `lib/`, `tools/`, `pipeline_defs/`, `styles/`, `schemas/`** — InkSpectrum lives inside `packages/textbook-pipeline/` and follows a layered architecture, but does not match the OpenMontage flat top-level layout.
2. **No BaseTool contract** — current ingestion/script/clients are classes, not tools with declared `tier/capability/provider/runtime/stability/dependencies`.
3. **No checkpoint system** — pipeline state is in-memory only; failures cannot be resumed.
4. **No YAML pipeline manifests** — the canonical 8-stage flow is not declarative.
5. **No style playbooks** — visual consistency is implicit.
6. **No JSON Schemas** — Pydantic models exist but no exported `.schema.json` for cross-language consumers.
7. **No `AGENT_GUIDE.md` / `PROJECT_CONTEXT.md`** — agents and skills are defined but no top-level guide ties them together.
8. **No Remotion composer** — render layer is missing entirely.
9. **No cost tracking** — ModelsLab calls are made without budget governance.
10. **No dual-provider fallback** — ModelsLab is hard-coded; no local/open-source fallback (Manim is the only offline exception).

---

## 2. Target Repository Layout (InkSpectrum after alignment)

```
D:\new_video_pip\
├── AGENTS.md                       # NEW — top-level agent contract
├── AGENT_GUIDE.md                  # NEW — operating guide and agent contract
├── PROJECT_CONTEXT.md              # NEW — architecture reference
├── config.yaml                     # NEW — global runtime config (budget, paths, defaults)
├── Makefile                        # EXTEND — add `make pipeline`, `make test`, `make render`
├── .env.example                    # EXISTS — extend with budget knobs
│
├── lib/                            # NEW — core runtime
│   ├── __init__.py
│   ├── config_model.py             # Pydantic config (LLM, budget, checkpoint, output, paths)
│   ├── checkpoint.py               # Pipeline state persistence + stage transitions
│   ├── pipeline_loader.py          # YAML manifest loading + validation
│   ├── media_profiles.py           # Platform render profiles (YouTube, TikTok, classroom)
│   ├── env_loader.py               # .env variable management
│   ├── cost_tracker.py             # NEW — budget estimation, reservation, reconciliation
│   └── tool_registry.py            # NEW — auto-discovery singleton
│
├── tools/                          # NEW — flat tools directory (or keep under packages/)
│   ├── base_tool.py                # BaseTool ABC + contract
│   ├── video/
│   │   ├── modelslab_video.py      # EXTRACT from packages/textbook-pipeline/core/clients/
│   │   ├── compose.py              # NEW — stitch scenes into timeline
│   │   ├── trim.py                 # NEW — cut scenes by timing
│   │   └── manim_render.py         # EXTRACT — math subject renderer
│   ├── audio/
│   │   ├── modelslab_tts.py        # EXTRACT
│   │   ├── audio_mix.py            # NEW — combine narration + music + sfx
│   │   └── word_timestamps.py      # NEW — for subtitle alignment
│   ├── graphics/
│   │   ├── modelslab_image.py      # EXTRACT
│   │   └── latex_render.py         # NEW — for math equations
│   ├── extraction/
│   │   ├── pymupdf_extractor.py    # EXTRACT
│   │   ├── opendataloader_extractor.py  # EXTRACT (already done)
│   │   └── docling_extractor.py    # EXTRACT
│   ├── script/
│   │   └── llm_script_writer.py    # EXTRACT
│   └── subtitle/
│       └── burn_subtitles.py       # NEW
│
├── pipeline_defs/                  # NEW — YAML pipeline manifests
│   ├── english_classroom.yaml      # NEW — primary school English lesson
│   ├── math_classroom.yaml         # NEW — math lesson with Manim
│   ├── evs_classroom.yaml          # NEW — EVS/social studies
│   ├── exercise_walkthrough.yaml   # NEW — Q&A explanation
│   └── framework_smoke.yaml        # NEW — minimal validation
│
├── skills/                         # RENAME from .kilo/skills/inkspectrum-* and add structure
│   ├── core/                       # Stage-agnostic skills
│   │   ├── ffmpeg.md
│   │   ├── remotion.md
│   │   ├── manimce.md
│   │   ├── modelslab-tts.md
│   │   ├── modelslab-image.md
│   │   ├── modelslab-video.md
│   │   ├── opendataloader.md
│   │   ├── pymupdf.md
│   │   ├── langchain-groq.md
│   │   └── cost-tracking.md        # NEW
│   ├── creative/                   # Quality/craft skills
│   │   ├── prompt-engineering.md
│   │   ├── pedagogy.md
│   │   └── pacing.md
│   ├── meta/                       # Pipeline-protocol skills
│   │   ├── checkpoint-protocol.md  # NEW
│   │   ├── reviewer.md             # NEW
│   │   ├── skill-creator.md        # NEW
│   │   └── orchestrator.md         # NEW — playbook for the LLM agent
│   └── pipelines/                  # Stage-director skills
│       ├── english_classroom/
│       │   ├── research-director.md
│       │   ├── script-director.md
│       │   ├── scene-plan-director.md
│       │   ├── asset-director.md
│       │   ├── edit-director.md
│       │   ├── compose-director.md
│       │   └── publish-director.md
│       ├── math_classroom/
│       │   └── ... (same 7)
│       ├── evs_classroom/
│       │   └── ... (same 7)
│       └── exercise_walkthrough/
│           └── ... (same 7)
│
├── styles/                         # NEW — visual playbooks
│   ├── playbooks/
│   │   ├── clean-classroom.yaml
│   │   ├── warm-primary.yaml
│   │   ├── minimal-math.yaml
│   │   └── vivid-evs.yaml
│   └── playbook_loader.py
│
├── schemas/                        # NEW — JSON Schemas
│   ├── artifacts/
│   │   ├── chapter_node.schema.json
│   │   ├── script_scene.schema.json
│   │   ├── storyboard_scene.schema.json
│   │   ├── audio_manifest.schema.json
│   │   └── final_video.schema.json
│   ├── pipelines/
│   │   └── pipeline.schema.json
│   ├── styles/
│   │   └── playbook.schema.json
│   └── tools/
│       └── base_tool.schema.json
│
├── remotion-composer/              # NEW — Node.js/React renderer
│   ├── package.json
│   ├── src/
│   │   ├── compositions/
│   │   │   ├── EnglishClassroom.tsx
│   │   │   ├── MathClassroom.tsx
│   │   │   └── EVSClassroom.tsx
│   │   └── render.ts
│   └── README.md
│
├── tests/                          # RENAME packages/textbook-pipeline/tests → add contracts/, qa/, eval/
│   ├── contracts/                  # NEW — BaseTool contract validation
│   ├── qa/                         # NEW — integration with real APIs
│   ├── eval/                       # NEW — golden scenario replay
│   ├── pipelines/                  # NEW — pipeline-level tests
│   ├── tools/                      # NEW — per-tool tests
│   └── existing 23 tests           # KEEP
│
├── docs/                           # NEW
│   ├── ARCHITECTURE.md
│   ├── PIPELINE_GUIDE.md
│   ├── STYLE_GUIDE.md
│   ├── COST_GUIDE.md
│   └── handoffs/
│
└── packages/                       # KEEP — internal package layout
    ├── textbook-pipeline/          # RENAME → keep but make it a thin client of /lib + /tools
    ├── model-evaluator/            # KEEP
    └── video-explainer/            # KEEP
```

---

## 3. Incremental Development Steps

Each step is independently shippable. Total: **6 phases over 12 weeks**.

### Phase 1 — Foundation (Weeks 1–2)

**Goal:** Establish the OpenMontage-style runtime shell around the existing textbook-pipeline package.

| Step | Deliverable | OpenMontage pattern |
|------|-------------|---------------------|
| 1.1 | `lib/config_model.py` (Pydantic) | P1, P6 |
| 1.2 | `lib/env_loader.py` | P1 |
| 1.3 | `lib/checkpoint.py` (JSON state per stage) | P4 |
| 1.4 | `lib/pipeline_loader.py` (YAML + Pydantic) | P1 |
| 1.5 | `lib/cost_tracker.py` (USD per tool call) | P6 |
| 1.6 | `lib/tool_registry.py` (auto-discovery) | P1 |
| 1.7 | `tools/base_tool.py` (ABC with contract) | P1 |
| 1.8 | `tools/extraction/` — move 3 extractors from `packages/textbook-pipeline/core/ingestion/` | P1 |
| 1.9 | `config.yaml` — global config | P1 |
| 1.10 | `AGENT_GUIDE.md` + `PROJECT_CONTEXT.md` | P1 |
| 1.11 | Tests: `tests/contracts/test_base_tool.py`, `tests/contracts/test_registry.py` | P1, P5 |
| 1.12 | Tests: `tests/eval/replay_harness/` skeleton | P5 |

**Acceptance:** `make pipeline PIPELINE=framework_smoke` runs the empty 8-stage manifest end-to-end with checkpoints written.

### Phase 2 — Script + Scene-Plan (Weeks 3–4)

**Goal:** Promote the existing script writer and schema to tools, and add scene planning as a first-class stage.

| Step | Deliverable |
|------|-------------|
| 2.1 | `tools/script/llm_script_writer.py` — move from `packages/.../core/script/writer.py`, adopt BaseTool contract |
| 2.2 | `schemas/artifacts/script_scene.schema.json` — export from Pydantic |
| 2.3 | `schemas/artifacts/scene_plan.schema.json` — NEW (between script and assets) |
| 2.4 | `tools/script/scene_planner.py` — NEW: takes ScriptScene list, returns per-scene visual plan (assets needed, timing, layout) |
| 2.5 | `pipeline_defs/english_classroom.yaml` — 8 stages with tool bindings |
| 2.6 | `skills/pipelines/english_classroom/{research,script,scene_plan}-director.md` |
| 2.7 | `skills/core/langchain-groq.md` — exact prompting patterns |
| 2.8 | `styles/playbooks/clean-classroom.yaml` — first style |
| 2.9 | Tests: `tests/qa/test_script_generation.py` (run real Groq call, assert schema) |
| 2.10 | Tests: `tests/eval/scenarios/english_lesson_grade1.json` — golden scenario |

**Acceptance:** `make pipeline PIPELINE=english_classroom` runs PDF → script + scene-plan on `RPS - ENGLISH - CLASS 1 - INDIVIDUAL - A (2026) PRINTFILE (2)-pages-2.pdf` with 100% schema validation.

### Phase 3 — Asset Generation (Weeks 5–6)

**Goal:** Wire ModelsLab TTS, image, and video tools into the `assets` stage with cost governance.

| Step | Deliverable |
|------|-------------|
| 3.1 | `tools/audio/modelslab_tts.py` — adopt BaseTool contract, add cost = $0.0001/char |
| 3.2 | `tools/audio/audio_mix.py` — combine narration + music, normalize LUFS |
| 3.3 | `tools/audio/word_timestamps.py` — WhisperX or forced alignment |
| 3.4 | `tools/graphics/modelslab_image.py` — adopt BaseTool contract, add cost = $0.002/image |
| 3.5 | `tools/graphics/latex_render.py` — Manim for math equations |
| 3.6 | `tools/video/modelslab_video.py` — adopt BaseTool contract, add cost = $0.05/second |
| 3.7 | `tools/video/manim_render.py` — move from `.kilo/skills/inkspectrum-manim-renderer/` |
| 3.8 | `lib/cost_tracker.py` — reserve budget before tool call, reconcile after |
| 3.9 | `skills/core/{modelslab-tts,modelslab-image,modelslab-video,manimce}.md` |
| 3.10 | `pipeline_defs/math_classroom.yaml` — Manim-first |
| 3.11 | `pipeline_defs/evs_classroom.yaml` |
| 3.12 | Tests: `tests/qa/test_tts.py`, `test_image_gen.py`, `test_video_gen.py` (with real APIs, cost-capped) |

**Acceptance:** A 60-second English lesson runs end-to-end through `assets` stage with total cost < $1.00, all artifacts validated.

### Phase 4 — Edit, Compose, Publish (Weeks 7–9)

**Goal:** Implement the remaining 3 stages: edit decisions, final composition, publish.

| Step | Deliverable |
|------|-------------|
| 4.1 | `tools/video/compose.py` — stitch scenes per scene-plan, dispatch to Remotion or FFmpeg |
| 4.2 | `tools/video/trim.py` — cut by timing |
| 4.3 | `tools/subtitle/burn_subtitles.py` — render + burn SRT/VTT |
| 4.4 | `remotion-composer/` — Node.js/React renderer with 3 compositions (English, Math, EVS) |
| 4.5 | `lib/media_profiles.py` — `youtube_landscape`, `youtube_shorts`, `classroom_720p` |
| 4.6 | `pipeline_defs/exercise_walkthrough.yaml` |
| 4.7 | `pipeline_defs/framework_smoke.yaml` — minimal validation pipeline |
| 4.8 | `skills/core/{remotion,ffmpeg}.md` |
| 4.9 | `skills/pipelines/<pipeline>/{edit,compose,publish}-director.md` |
| 4.10 | `lib/checkpoint.py` — finalize resume protocol |
| 4.11 | Tests: `tests/qa/test_compose.py`, `test_burn_subtitles.py` |
| 4.12 | Tests: `tests/pipelines/test_english_classroom_e2e.py` |

**Acceptance:** End-to-end pipeline produces a 60-second MP4 from a PDF. Cost < $2.00. Schema validation passes on all artifacts.

### Phase 5 — Quality, Cost, Observability (Weeks 10–11)

**Goal:** Add the OpenMontage meta layer: reviewer, budget governance, observability.

| Step | Deliverable |
|------|-------------|
| 5.1 | `skills/meta/reviewer.md` — self-review checklist (frame integrity, audio levels, schema, length, style compliance) |
| 5.2 | `skills/meta/checkpoint-protocol.md` — exact JSON shape and resume rules |
| 5.3 | `skills/meta/skill-creator.md` — how to add a new tool/skill |
| 5.4 | `lib/cost_tracker.py` — spend dashboard per pipeline run |
| 5.5 | `lib/tool_registry.py` — selector pattern with 7-dimension scoring |
| 5.6 | `tests/eval/replay_harness/` — golden scenario replay with tolerance |
| 5.7 | `docs/COST_GUIDE.md` — cost expectations per pipeline |
| 5.8 | `docs/ARCHITECTURE.md` — port OpenMontage ARCHITECTURE.md structure |
| 5.9 | Provider fallback: if ModelsLab fails 3x, fall back to local (Wan2.5 / CogVideo / Piper TTS) |
| 5.10 | `docs/handoffs/2026-09-07-*` — initial session handoff docs |

**Acceptance:** Pipeline reports cost per stage, reviewer catches 100% of schema violations before publish, 1 documented fallback path.

### Phase 6 — Production Hardening (Week 12)

| Step | Deliverable |
|------|-------------|
| 6.1 | GitHub Actions CI: `make contracts` + `make test` on every PR |
| 6.2 | `Makefile` targets: `pipeline`, `test`, `contracts`, `eval`, `cost-report`, `render-demo` |
| 6.3 | `render-demo.sh` — public demo script |
| 6.4 | README rewrite: 5-minute quickstart, cost table, pipeline comparison |
| 6.5 | License: AGPL-3.0 (matching OpenMontage) |
| 6.6 | `requirements.txt` / `requirements-dev.txt` / `requirements-gpu.txt` |
| 6.7 | 3 working demo PDFs → 3 finished MP4s |
| 6.8 | Cost report on the 3 demos: < $5.00 per video |

**Acceptance:** Repository is cloneable, `make setup && make render-demo` produces a finished video on a fresh machine with valid API keys.

---

## 4. Coding Standards (extracted from OpenMontage)

InkSpectrum will adopt these standards:

### 4.1 Python
- **Pydantic v2** for all data models and config
- **Type hints** required on all public functions
- **`from __future__ import annotations`** in every file
- **Logging** via `logging.getLogger(__name__)`, never `print`
- **Tool contract** via `BaseTool` ABC (name, version, tier, capability, provider, runtime, stability, dependencies)
- **Schema export** — every Pydantic model must export `model.schema_json()` to `schemas/artifacts/*.schema.json`
- **Tests** — `pytest` with `tests/contracts/`, `tests/qa/`, `tests/eval/` subdirs
- **Async** — all I/O tools are `async def`; sync wrappers allowed for CLI ergonomics

### 4.2 YAML
- **Pipeline manifests** in `pipeline_defs/` declare: name, mode, skill, budget_default_usd, max_revisions_per_stage, compatible_playbooks, stages[]
- Each stage declares: name, skill, produces[], tools_available[], checkpoint_required, human_approval_default, review_focus[], success_criteria[]

### 4.3 Markdown (Skills)
- **Skill files** follow OpenMontage pattern: purpose, when to load, exact prompts/snippets, common pitfalls
- **Stage director skills** are written as instructions *to the agent*, not docs *about the agent*
- **Meta skills** (reviewer, checkpoint-protocol) are mandatory reading before any stage

### 4.4 Git / Branching
- **One PR per phase** (Phases 1–6 → 6 PRs)
- **Each PR includes**: `tests/` updates + `schemas/` regen + `CHANGELOG.md` entry
- **Commit format**: `<scope>: <verb> <object>` (e.g. `tools: add BaseTool ABC`)

### 4.5 Documentation
- `docs/ARCHITECTURE.md` is the single source of truth for system design
- `AGENT_GUIDE.md` is the contract between the human and the AI agents
- `PROJECT_CONTEXT.md` is the running glossary + decisions log
- `docs/handoffs/YYYY-MM-DD-<topic>.md` for every session that changes state

---

## 5. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| ModelsLab pricing changes | Cost projections break | Cost tracker reads current rates from `config.yaml`; budget reserve caps each call |
| Groq API key invalidation | Script generation halts | Dual-provider: also support `openai/gpt-4o-mini` via OpenAI, fall back automatically |
| Remotion composer complexity | Blocks Phase 4 | Keep Remotion minimal; allow FFmpeg-only path for Math/English as fallback |
| Skill bloat (500+ files) | Hard to maintain | Cap per-skill length at 200 lines; reference external tech skills by name, do not duplicate |
| Pydantic v2 vs v1 drift | Models fail validation | Pin `pydantic>=2.5,<3` in `pyproject.toml`; CI runs `make contracts` |
| WSL/Windows path differences | Hard failures on cross-platform | All paths via `pathlib.Path`; never use `os.path.join` |

---

## 6. Immediate Next Steps (this week)

1. **Save this roadmap** as `.kilo/plans/2026-09-07-inkspectrum-roadmap.md` — DONE
2. **Create `lib/` skeleton** with `__init__.py`, `config_model.py`, `env_loader.py` (Phase 1.1–1.2)
3. **Create `tools/base_tool.py`** with the full contract (Phase 1.7)
4. **Move `OpenDataLoaderExtractor` and `ChapterBuilder`** from `packages/textbook-pipeline/core/ingestion/` into `tools/extraction/` (Phase 1.8)
5. **Generate first JSON Schema** from Pydantic: `chapter_node.schema.json` (Phase 2.2 dry-run)
6. **Write `AGENT_GUIDE.md`** (Phase 1.10)
7. **Set up the 23 existing tests under `tests/contracts/`** instead of `packages/textbook-pipeline/tests/`

---

## 7. Open Questions for the User

1. **License** — should InkSpectrum stay proprietary, or move to AGPL-3.0 like OpenMontage?
2. **Renderer strategy** — commit to Remotion (Node.js + React), or go FFmpeg-only with MoviePy for the first version?
3. **Provider strategy** — ModelsLab-only, or build dual-provider (ModelsLab + local Wan2.5 / CogVideo) from day one?
4. **Storage** — where do generated videos go? Local disk, S3, or both?
5. **Classroom deployment** — does the final video need to be offline-playable, or is cloud streaming acceptable?
6. **Cost target** — what is the maximum acceptable cost per minute of finished video? ($1/min? $5/min?)
