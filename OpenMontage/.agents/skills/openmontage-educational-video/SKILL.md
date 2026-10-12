---
name: openmontage-educational-video
description: Run, resume, inspect, and approve OpenMontage's source-grounded PDF-to-educational-video pipeline for any supported subject. Use for textbook ingestion, educational chapter generation, HyperFrames composition, ModelsLab narration/video, Backlot stage tracking, or educational-video QA.
---

# OpenMontage Educational Video

Use this workflow from a source checkout. It is agent-neutral: communicate
through the CLI's JSON output, project artifacts, checkpoints, and exit codes.

## Required reading

1. Read `AGENT_GUIDE.md`.
2. Read `pipeline_defs/educational-video.yaml`.
3. Read the skill named by the current manifest stage before doing that stage.
4. Treat the extracted textbook and coverage contract as the factual authority.

## Environment

- Start onboarding with `python -m tools.structure.educational_agent_cli setup`.
  Installation requires explicit approval (`setup --install-python`); a greeting
  alone is not permission. See `docs/EDUCATIONAL_STARTUP.md`.
  Setup prefers Conda when available; `--manager venv` remains supported.
  Reuse a checked active environment. Never update another environment implicitly.
  Keep Manim in the optional `environment-manim.yml` environment.
- Use `start` without arguments to discover required input. For existing projects,
  use `resume <project_dir>` and follow its returned stage skill and checkpoints;
  do not replay ingestion. Resume is an agent handoff, not an unattended scheduler.
- Approved visual references and newer timing overrides are recorded in
  `config/educational-reference-lock.json`; verify identities with `references`.
  Compare new encoded output against the presentation checklist. Hash checks
  alone are not visual QA. Never change the baseline without user approval.
  On a VM, use the Git-shippable `tests/fixtures/educational-reference` package;
  full historical MP4s are optional. Follow its README for structural tests and
  visual review. Never treat optional_missing MP4s as missing chapter assets.

- Verify the cross-agent package with
  `python -m tools.structure.educational_agent_cli doctor`.
- Set credentials only through environment variables. For the locked provider,
  use `MODELSLAB_API_KEY`; never store a key in chapter JSON or Markdown.
- Ensure Python dependencies, FFmpeg/ffprobe, Node.js, and HyperFrames are
  available. Run `python -m tools.structure.educational_preflight` when
  diagnosing a project.
- Generated story/explanation media must be moving video, not still images or
  Ken Burns substitutes. Stable textbook, glossary, recall, and exercise cards
  are allowed while they are actively narrated.

## Portable commands

No-cost structural validation:

```powershell
python -m tools.structure.educational_agent_cli run "C:\path\chapter.pdf" `
  --project-id my-chapter --subject evs --grade 1 --dry-run
```

For a complete textbook, first generate and review its chapter map:

```powershell
python -m tools.structure.educational_agent_cli book "C:\path\textbook.pdf"
```

Then run every detected chapter through the same pipeline:

```powershell
python -m tools.structure.educational_agent_cli book "C:\path\textbook.pdf" `
  --approve-chapter-map --dry-run
```

Book metadata is inferred from explicit class/subject/volume tokens in the
filename and verified against PDF contents. Collection workspaces use
`OPENMONTAGE_COLLECTIONS_DIR`; approved MP4 delivery uses
`OPENMONTAGE_DELIVERY_DIR/Class-{grade}-{subject}/`. Each chapter also owns a
dynamic HyperFrames workspace with `DESIGN.md`, `index.html`, and timeline JSON.

Guided production (stops at declared human gates):

```powershell
python -m tools.structure.educational_agent_cli run "C:\path\chapter.pdf" `
  --project-id my-chapter --subject evs --grade 1
```

Inspect or approve a gate:

```powershell
python -m tools.structure.educational_agent_cli status projects\my-chapter --write
python -m tools.structure.educational_agent_cli approve projects\my-chapter proposal
```

Continue by running the same guided command again. Previously generated clips
may be reused only when their content fingerprint and semantic QA both pass.

For an explicitly approved unattended run:

```powershell
python -m tools.structure.educational_agent_cli run "C:\path\chapter.pdf" `
  --project-id my-chapter --subject evs --grade 1 --full-run-preauthorized
```

Do not add that flag merely for convenience. It records approval evidence and
permits paid generation to pass proposal, asset, and final-QA gates.

## Required outputs

Every run must create `project.json`, manifest-ordered `checkpoint_*.json`
files, `events.jsonl`, `artifacts/agent_status.json`, a cumulative
`decision_log.json`, source/coverage artifacts, narration and alignment
artifacts, clip and synchronization manifests, `render_report.json`,
`final_review.json`, and `publish_log.json`.

Only present the video as final when encoded-output QA passes. A dry run proves
orchestration and schemas, not visual quality or provider output quality.

For a source-audited encoded chapter, run the deterministic comparison gate:

```powershell
python -m tools.analysis.encoded_educational_comparison `
  --candidate projects\<id>\renders\chapter.mp4 `
  --source-pdf projects\<id>\source\chapter.pdf `
  --source-audit projects\<id>\artifacts\source-audit.json `
  --production-data projects\<id>\hyperframes-final\production-data.json `
  --output-dir projects\<id>\artifacts\encoded-comparison
```

The generated contact sheet still requires semantic/aesthetic review. A pass
does not authorize publication by itself.
