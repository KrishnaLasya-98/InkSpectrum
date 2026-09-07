# InkSpectrum — Architectural Review

## 1. Executive Summary

InkSpectrum is a monorepo attempting to build an AI-powered pipeline that transforms K-10 textbook PDFs into chapter-by-chapter video lectures. After deep analysis of the codebase, I've identified a **critical structural divergence**: the repository contains **two parallel implementations** of the `textbook_pipeline` package, with the "canonical" `src/` layout at the repo root being **non-functional stubs** while the actual working code lives in `packages/textbook-pipeline/src/`. This dual-implementation problem, combined with Pydantic v2 import errors, schema mismatches, and broken build tooling, represents a **P0 architectural blocker** that must be resolved before any meaningful progress on the pipeline can occur.

---

## 2. Comprehensive Project Synthesis

### 2.1 Repository Topology

```
D:\new_video_pip/
├── apps/
│   └── vidya-ai/                    # SEPARATE PRODUCT: Next.js educational platform (deployed on Vercel)
├── packages/
│   ├── video-explainer/             # MATURE: 1192-test explainer video system (prajwal-y upstream)
│   ├── textbook-pipeline/           # PRIMARY TARGET: K-10 textbook → video (ACTIVE DEVELOPMENT)
│   │   └── src/textbook_pipeline/   # REAL implementation lives HERE
│   ├── model_evaluator/             # Phase 0: LLM testing harness
│   ├── model_testing/               # Phase 0: Model evaluation tasks
│   ├── edugen/                      # UPSTREAM: Manim-based science video generator
│   ├── agnes-video-generator/       # UPSTREAM: Multi-scene pipeline
│   └── code2video/                  # UPSTREAM: Code-to-video
├── vendor/
│   └── docling/                     # VENDORED: PDF parsing library
├── src/
│   └── textbook_pipeline/           # FAILED REFACTOR: Empty stubs, broken imports
├── tools/                           # seed_assets.py, validate_schemas.py
├── scripts/                         # ingest_chapter.py, render_chapter.py, audit_fidelity.py
├── pyproject.toml                   # ROOT config
└── requirements.txt                 # Workspace-level deps
```

### 2.2 The Dual-Implementation Problem

**Location A (BROKEN):** `src/textbook_pipeline/`
- `models/__init__.py` imports from 8 modules that **do not exist** in this directory (`chapter.py`, `script.py`, `storyboard.py`, `assets.py`, `config.py`, `fidelity.py`)
- `cli.py` is a Typer stub with TODO comments
- All core logic is missing
- Root `pyproject.toml` pytest config points to `tests/` but doesn't include `packages/textbook-pipeline/src` in `pythonpath`

**Location B (WORKING):** `packages/textbook-pipeline/src/textbook_pipeline/`
- 50+ Python modules with real implementation
- Full model layer (chapter, script, storyboard, assets, config, fidelity)
- Core ingestion (docling, pymupdf, pdfmux extractors)
- Core script generation (LLM-based writer, planner, vocabulary)
- Subject routing (english, math, science, social)
- Wrappers for external tools (agnes, docling)
- Fidelity auditing system

**PyProject Alignment:**
- `packages/textbook-pipeline/pyproject.toml` correctly declares `packages = ["src/textbook_pipeline"]`
- But `pip install -e packages/textbook-pipeline/` fails due to **Pydantic v2 bug** in `models/fidelity.py:51` — `ConfigDict` is used without being imported

### 2.3 Current Technical State

| Component | Status | Location |
|-----------|--------|----------|
| PDF Ingestion | Partially implemented | `packages/textbook-pipeline/src/.../core/ingestion/` |
| Chapter Grouping | Implemented | `chapter_grouper.py`, `chapter_builder.py` |
| Subject Routing | Implemented | `subject_router.py` |
| Script Generation | Implemented (stub-level) | `generator.py`, `planner.py`, `writer.py` |
| LLM Integration | Uses Groq/LangChain | `generator.py` imports `langchain_openai` |
| TTS | Not implemented | — |
| Rendering | Not implemented | — |
| Compositor | Stub only | `src/textbook_pipeline/core/compose/assembler.py` |
| QA System | Stub only | `src/textbook_pipeline/core/qa/` |
| Manim Renderer | Stub only | `src/textbook_pipeline/core/render/manim/` |
| Remotion Renderer | Package exists but empty | `packages/textbook-pipeline/remotion_renderer/` |
| Fidelity Auditing | Models exist, implementation unclear | `core/fidelity/` |

---

## 3. Goal Inference & Definition

### 3.1 Product Vision

**InkSpectrum** is an automated educational video factory that takes K-10 textbook PDFs as input and produces **pedagogically sound, 100% content-faithful video lectures** as output. The end-user experience is:

1. A teacher or content creator drops a textbook PDF into the system
2. The system automatically:
   - Parses the PDF into chapter/section/exercise trees
   - Routes to subject-specific pedagogical logic
   - Generates narration scripts that preserve verbatim textbook content
   - Creates visual scene plans with AI-generated assets
   - Produces voiceover audio in appropriate TTS voices
   - Renders final MP4 videos chapter-by-chapter
3. Output is a library of ready-to-publish educational videos

### 3.2 Technical Capability (Ultimate Pipeline)

```
PDF (textbook)
  ↓ Docling / PyMuPDF extraction
Chapter Tree (sections + exercises + learning objectives)
  ↓ Subject-specific pedagogical routing
Scripted Scenes (narration + visual plan + timing)
  ↓ TTS + Asset Generation
Rendered Video Segments
  ↓ FFmpeg/MoviePy assembly
Final Chapter Video (.mp4) + Subtitles (.srt) + QA Manifest
```

### 3.3 Architectural Standard

- **Autonomy:** Near-zero human intervention after PDF upload (Phase 2+)
- **Modularity:** Each pipeline stage independently testable and replaceable
- **Fidelity:** 100% content preservation (verbatim text, exact definitions, no hallucinations)
- **Scalability:** Multi-subject support (English, Math, Science, Social → GK, Humanities)
- **Observability:** Fidelity manifests track every content element through the pipeline

---

## 4. Alignment Audit

### 4.1 Structural Alignment

**Monorepo + `src` Layout:** The decision to use a monorepo with `packages/` isolation is **sound** for long-term scalability. The `src/` layout inside each package follows Python packaging best practices. However, the **execution is broken**:

- The root-level `src/textbook_pipeline/` was created as part of a refactor but was **never populated** with actual code
- The `packages/textbook-pipeline/src/textbook_pipeline/` contains the real implementation but is **orphaned** from the root workspace
- `src/run.py` tries to import from `packages/model_testing` (which exists) but also references non-standard paths

**Verdict:** The structural intent is correct, but the refactor created a **split-brain architecture** where two copies of the same package exist, one functional and one not.

### 4.2 Technical Debt vs. Progress

The "P0/P1 issues" are **not** expected growing pains — they are **critical blockers** that deviate from the goal:

| Issue | Severity | Impact |
|-------|----------|--------|
| `src/textbook_pipeline/models/__init__.py` imports non-existent modules | P0 | Root package is completely non-functional |
| `fidelity.py` uses `ConfigDict` without import | P0 | `pip install -e packages/textbook-pipeline/` fails |
| Schema mismatch between two implementations | P0 | Any cross-package integration is impossible |
| Makefile references wrong paths (`EduGen/`, `video_explainer/`) | P1 | Build tooling is broken |
| Root `pyproject.toml` missing `packages/textbook-pipeline/src` in pythonpath | P1 | Tests cannot import the package from root |
| Hardcoded Windows paths in runner scripts | P1 | WSL/Windows hybrid environment breaks |

These are **not** growing pains. They indicate that the refactor was **incomplete** — the decision was made to move to `src/` layout, but the migration was only half-executed, leaving the repo in an inconsistent state.

### 4.3 Feature Alignment

**Current focus on `model-evaluator` and `textbook-pipeline`:** This **correctly prioritizes** the foundation needed for the "Research Agent" and "Orchestrator":

- `model_evaluator` (Phase 0) validates LLM providers before building the pipeline — **correct sequencing**
- `textbook-pipeline` contains the core domain logic (chapter models, subject routing, fidelity tracking) — **correct prioritization**

**However:** The `video-explainer` package, while mature (1192 tests), is **architecturally divergent** from the textbook pipeline:
- Different schema (Storyboard vs StoryboardScene, Beat vs no Beat)
- Different CLI design (Typer vs argparse)
- Different project organization
- Different asset management

This means **code cannot be shared** between the two packages despite similar goals. The `video-explainer` package serves as a reference architecture but cannot be directly integrated.

---

## 5. Strategic Gap Analysis

### 5.1 Blind Spots & Missing Components

| Gap | Description | Risk |
|-----|-------------|------|
| **No Unified Source of Truth** | Two implementations of the same package with different schemas | Critical — blocks all integration work |
| **No Working Pipeline** | All CLI commands are stubs; no end-to-end flow exists | Critical — nothing can be demonstrated |
| **No TTS Integration** | No Edge TTS or ElevenLabs implementation | High — audio layer missing |
| **No Rendering Implementation** | Remotion renderer is empty; Manim renderer is stubbed | High — no video output possible |
| **No Research Agent** | No autonomous content analysis or knowledge extraction | High — manual script generation only |
| **No Orchestrator** | No pipeline orchestration or state management | High — stages cannot be chained |
| **Broken Build Tooling** | Makefile, pytest config, and imports all misaligned | High — CI/CD impossible |
| **Vendored Docling Duplication** | `vendor/docling/` duplicates installed package | Medium — maintenance burden |
| **Vidya-AI Isolation** | Separate Next.js app with no shared Python backend | Medium — potential for feature duplication |
| **No Content Fidelity Implementation** | Fidelity models exist but no auditor implementation | Medium — core value prop unvalidated |

### 5.2 Environment Considerations

The WSL/Windows hybrid environment creates specific constraints:
- **PowerShell vs Bash:** Makefile uses Unix commands (`del /s /q`) that won't work in WSL
- **Path separators:** Hardcoded paths in runner scripts were partially cleaned up but may persist
- **Node.js toolchain:** Remotion requires Node.js 20+, adding complexity to a Python-centric pipeline
- **GPU dependencies:** Manim, MusicGen, and video rendering require GPU acceleration

---

## 6. Recommendations

### Immediate (P0 — Blockers)

1. **Consolidate to a single `textbook_pipeline` implementation**
   - Delete `src/textbook_pipeline/` at the repo root
   - Make `packages/textbook-pipeline/src/textbook_pipeline/` the canonical source
   - Update root `pyproject.toml` to include `packages/textbook-pipeline/src` in `pythonpath`
   - Fix `fidelity.py` to import `ConfigDict` from pydantic

2. **Fix schema consistency**
   - Audit the two implementations' schemas and unify
   - Ensure `models/__init__.py` exports match across all entry points

3. **Repair build tooling**
   - Fix Makefile paths to use `packages/` prefix
   - Ensure `make test` and `make lint` work from both Windows PowerShell and WSL

### Short-term (P1 — Foundation)

4. **Implement the TTS layer** — Edge TTS wrapper with word-level timestamps
5. **Implement the Rendering layer** — At minimum, a functional Remotion renderer scaffold
6. **Build a minimal Orchestrator** — Chain ingest → script → render with proper error handling
7. **Add integration tests** — Test at least one end-to-end flow (PDF → chapter JSON)

### Medium-term (P2 — Intelligence)

8. **Research Agent** — Autonomous content analysis, key concept extraction, prerequisite mapping
9. **Fidelity Auditor** — Implement the `ContentManifest` tracking system
10. **Subject-specific renderers** — Math (Manim), English (Remotion + assets), Science (animation), Social (slides + voiceover)

### Long-term (P3 — Scale)

11. **Batch processing** — Process entire textbooks, not single chapters
12. **Quality automation** — Self-evaluation, fact-checking, visual QA
13. **Multi-language support** — Extend beyond English to Indian languages (align with Vidya-AI)

---

## 7. Conclusion

InkSpectrum has a **strong architectural vision** and **valuable reference implementations** in `video-explainer` and the upstream repos. However, the current state is **blocked by a failed refactor** that created a dual-implementation problem. The working code in `packages/textbook-pipeline/src/` is solid, but it cannot be used until the root-level stubs are removed and the build tooling is repaired.

**The priority is not adding new features — it's cleaning up the existing mess so that progress can be measured.** Once the package structure is unified and the Pydantic bug is fixed, the team can meaningfully advance toward the Final Goal of automated, fidelity-preserving educational video generation.
