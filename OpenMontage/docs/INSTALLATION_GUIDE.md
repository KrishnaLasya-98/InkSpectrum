# OpenMontage Installation Guide

This document is the installation source of truth for the OpenMontage
educational PDF-to-video pipeline. It covers the complete production runtime,
scanned-PDF OCR, HyperFrames rendering, optional Manim/GPU profiles, validation,
and the mandatory dependency change record.

## Installation contract

Every dependency installation, removal, or upgrade must update all applicable
items in the same change:

1. The appropriate requirements, Conda, Node, or system dependency manifest.
2. The installation ledger at the end of this document.
3. The setup/preflight check when the dependency is production-required.
4. A verification command or automated test.

Do not rely on an undocumented global package, a user-site package, a manually
downloaded JAR, or a tool that happens to be on one workstation's `PATH`.
Credentials belong only in ignored environment files or a secret manager and
must never appear in this guide or a requirements file.

## Dependency profiles

| Profile | Manifest | Purpose |
| --- | --- | --- |
| Complete educational production | `requirements-educational.txt` | Orchestration, scanned/digital PDF extraction, OCR, narration fallback, Backlot and media processing |
| Core cloud production | `requirements-educational-core.txt` | Lightweight API-driven pipeline without the local OCR/model stack |
| Conda production environment | `environment.yml` | Python 3.11, FFmpeg, Node.js, libsndfile and the complete educational pip profile |
| Development and tests | `requirements-dev.txt` | Pytest, async tests and HTTP test tooling |
| Optional GPU runtime | `requirements-gpu.txt` | Torch, TorchAudio and TorchVision |
| Optional Manim renderer | `environment-manim.yml` | Isolated deterministic Maths/Science animation environment |

`requirements-educational.txt` contains direct dependencies and intentional
version constraints. It is not a universal transitive lockfile: operating
system, CPU/GPU architecture and Python wheel availability differ. Produce a
platform-specific resolved lock only after validating that target platform.

## Required system software

| Dependency | Required constraint | Why |
| --- | --- | --- |
| Conda/Miniforge/Miniconda | Current supported release | Creates the isolated reproducible production environment |
| Python | 3.11 in `environment.yml` | Main orchestration and extraction runtime |
| Java | 11 or newer | Required by OpenDataLoader PDF's bundled Java engine |
| Node.js | 22 in `environment.yml` | HyperFrames CLI/runtime |
| FFmpeg and ffprobe | Supplied by Conda | Audio/video composition and encoded-output QA |
| HyperFrames | Validated local package 0.8.82 | HTML video composition, preview and rendering |
| Git | Current supported release | Source and dependency manifest tracking |

The workstation snapshot recorded on 2026-09-30 had Java 25.0.4.1, Node
24.19.0, FFmpeg/ffprobe 9.0.1 and HyperFrames 0.8.82. These are validation
evidence, not permission to silently upgrade the declared environment.

## Recommended installation: Conda

Run from the repository root:

```powershell
conda env create --prefix .conda-educational --file environment.yml
conda run --prefix .conda-educational python -m tools.structure.educational_agent_cli setup
conda run --prefix .conda-educational python -m tools.structure.educational_agent_cli doctor
conda run --prefix .conda-educational python -m tools.structure.educational_agent_cli references
```

The agent-managed equivalent is:

```powershell
python -m tools.structure.educational_agent_cli setup --install-python --manager conda
```

Installation is an explicit action. A greeting, PDF upload, or status request
does not authorize creating or changing environments.

## Venv fallback

Use Python 3.11 and install system dependencies separately:

```powershell
py -3.11 -m venv .venv-educational
.\.venv-educational\Scripts\python.exe -m pip install --upgrade pip
.\.venv-educational\Scripts\python.exe -m pip install -r requirements-educational.txt
.\.venv-educational\Scripts\python.exe -m tools.structure.educational_agent_cli setup
```

The venv route does not install Java, Node.js, FFmpeg, ffprobe, browser
binaries, fonts, or HyperFrames. The final setup report must find them before
production is considered ready.

## OpenDataLoader PDF and scanned-textbook OCR

The complete profile pins `opendataloader-pdf[hybrid]==2.5.7`. Use the Python
SDK or installed CLI; do not call an untracked relative `opendataloader.jar`.

For selectable-text PDFs, local conversion can produce Markdown and structured
JSON. For scanned/image-only textbooks, start the local hybrid backend with OCR:

```powershell
conda run --prefix .conda-educational opendataloader-pdf-hybrid --port 5002 --force-ocr --ocr-lang en
```

Then convert contents pages or chapter PDFs through the SDK/CLI with the hybrid
backend enabled. Batch chapter files in one conversion call when practical,
because each separate conversion starts a JVM.

Required educational outputs are:

- Markdown for headings, prose, lists, questions and narration grounding.
- JSON for page numbers, element types, tables and bounding boxes.
- Extracted figures only when the textbook image is pedagogically required.
- A source-coverage report proving every required block was handled.

If `opendataloader_pdf`, `docling`, Java, or the hybrid backend is unavailable,
the pipeline must stop with a visible preflight failure for an image-only PDF.
It must not silently claim success through an empty PyMuPDF fallback.

## HyperFrames

The repository's validated CLI is:

```text
.runtime/hyperframes/node_modules/hyperframes/bin/hyperframes.mjs
```

Verify it with the educational setup command and run project-specific
HyperFrames `info`, `lint`, `check`, snapshots and render QA. Do not substitute
Remotion for an existing HyperFrames project without an approved runtime change.

## Optional Manim environment

Keep deterministic Maths/Science rendering isolated:

```powershell
conda env create --file environment-manim.yml
```

Set `OPENMONTAGE_MANIM_PYTHON` to that environment's Python executable. Do not
install unrestricted LLM-generated Manim code into the main production runtime.

## Optional GPU and local models

Install `requirements-gpu.txt` only when the target machine and selected model
require it. WhisperX, local TTS, local music generation, browser packages,
fonts, and model weights are optional profiles until explicitly selected.
Before installing any of them:

1. Add or update a dedicated manifest.
2. Record storage, RAM/VRAM, license and platform constraints here.
3. Add a preflight status that distinguishes required from optional.
4. Record the verification result in the ledger.

## Credentials

Use ignored `.env` files or deployment secret stores. Common variables include
`MODELSLAB_API_KEY`, `OPENMONTAGE_PROJECTS_DIR`,
`OPENMONTAGE_COLLECTIONS_DIR`, `OPENMONTAGE_DELIVERY_DIR`, and
`OPENMONTAGE_MANIM_PYTHON`. Record variable names only—never their values.

## Verification checklist

```powershell
conda run --prefix .conda-educational python -m tools.structure.educational_agent_cli setup
conda run --prefix .conda-educational python -m tools.structure.educational_agent_cli doctor
conda run --prefix .conda-educational python -c "import opendataloader_pdf, docling"
java -version
node --version
ffmpeg -version
ffprobe -version
```

For scanned-PDF readiness, run a small OCR fixture and require non-empty
Markdown plus JSON elements with page numbers and bounding boxes. For final
video readiness, also run HyperFrames lint/check, a representative render, and
encoded-output QA.

## Troubleshooting

### OpenDataLoader worked before but is missing now

Check the interpreter and user-site boundary. A package installed under global
Python or a base Conda environment is not automatically available inside
`.conda-educational`. Reinstall through the recorded manifest; do not add a
global Scripts directory to `PATH` as a hidden workaround.

### Digital PDFs work but scanned PDFs are empty

Local PDF parsing cannot recover text pixels. Confirm the hybrid extra is
installed, `docling` imports, and the backend was started with `--force-ocr`.

### Setup reports HyperFrames missing

Check Node.js and the pinned local CLI path. Do not install a different version
without adding a ledger entry and rerunning template/render regression checks.

## Installation ledger

Add one row for every install, removal, or upgrade. For a completed operation,
replace `planned` with the resolved version and verification result.

| Date | Dependency/action | Target environment | Reason | Manifest or configuration | Resolved result and verification |
| --- | --- | --- | --- | --- | --- |
| 2026-09-30 | Install `opendataloader-pdf[hybrid]==2.5.7` | `.conda-educational` | Structured extraction, layout JSON, bounding boxes, extracted images, and forced OCR for scanned textbooks | `requirements-educational.txt`, `environment.yml` | Installed `opendataloader-pdf 2.5.7`, `docling 2.131.0`, `easyocr 1.7.2`, and CPU `torch 2.14.0`; import/CLI checks passed and a forced-OCR probe produced Markdown, JSON, bounding boxes, a 13-row contents table, and an extracted PNG. Package/model caches are redirected to `D:\InkSpectrum\OpenMontage\.cache`. The Windows CPU backend is restarted per chapter because the persistent process crashed after two consecutive documents. |
| 2026-09-30 | Record HyperFrames 0.8.82 | Repository-local `.runtime/hyperframes` | Canonical educational composition runtime | Existing local runtime | Existing installation verified by package metadata |
| 2026-09-30 | Record Java 25.0.4.1, Node 24.19.0 and FFmpeg 9.0.1 | Current workstation | Document validated system-tool snapshot | System tools | Existing installations verified with version commands |
| 2026-09-30 | Declare Railway Linux container runtime: Node 22, Python 3, Java 17, FFmpeg, Chromium, fonts and libsndfile | Root `Dockerfile` | Persistent Backlot and educational queue-worker deployment | `Dockerfile`, `.dockerignore`, `.railway/railway.ts` | Declared only; local unit tests validate server/worker behavior. A Railway image build and dry-run deployment are still required before portability is confirmed. |
| 2026-09-30 | Install `railway@3.12.0` | Repository root `node_modules` | Evaluate and validate Railway Infrastructure as Code | Root `package.json`, `package-lock.json` | Installed 6 packages; npm audit reported 0 vulnerabilities. `esbuild@0.28.2` postinstall remained blocked by npm allow-scripts policy; IaC plan verification is recorded separately. |

| 2026-10-06 | Download public `facebook/wav2vec2-base-960h` alignment weights; reuse installed packages | Existing Python 3.14; model cache `.cache/alignment` on D: | Replace guessed word timestamps with local CTC forced alignment after ElevenLabs alignment returned HTTP 401 | `requirements-alignment-ctc.txt` | Model downloaded; no package installation or upgrade. Chapter 2 `align_ctc_v5.py` completed all 15 audio segments, including spelled-number normalization. Three low-confidence word endings remain explicitly flagged in `artifacts/alignment-ctc-v5/audit-all.json`; successful alignment alone is not semantic or encoded-video QA. |

### Ledger entry template

```text
| YYYY-MM-DD | Install/upgrade/remove name and requested constraint | environment/path | reason | manifest/configuration | resolved version; verification command and outcome |
```
