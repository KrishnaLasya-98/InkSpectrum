# Educational Video Pipeline Runner

## Purpose

This skill covers the compatibility runner behind the manifest-driven
`educational-video` pipeline. It supports PDF, Markdown, text, and DOCX chapter
inputs, records Backlot state, composes with the locked HyperFrames educational
template, and performs encoded-output QA.

The canonical cross-agent instructions are in
`.agents/skills/openmontage-educational-video/SKILL.md`.

## Entry points

Preferred, agent-neutral controller:

```powershell
python -m tools.structure.educational_agent_cli run "C:\path\chapter.pdf" `
  --project-id class1-chapter --subject evs --grade 1 --dry-run
```

Lower-level runners:

```powershell
python -m tools.structure.pdf_to_video_pipeline "C:\path\chapter.pdf" --dry-run
python -m tools.structure.subject_pipeline_runner --chapter-config projects\class1-chapter\chapter_config.json --dry-run
```

## Checkpoint behavior

The one-process compatibility runner emits the same manifest-ordered
checkpoints and Backlot events as an agent-managed run. It does not skip work
solely because a checkpoint is complete, but the media renderer can reuse a
previous clip only when its content fingerprint and semantic QA are valid.

Guided production stops at `proposal`, `content_structuring`, `assets`, and
`quality_assurance`. Approve and inspect them with:

```powershell
python -m tools.structure.educational_agent_cli status projects\class1-chapter --write
python -m tools.structure.educational_agent_cli approve projects\class1-chapter proposal
```

Use `--full-run-preauthorized` only when the user has already approved creative
direction, paid generation, and final delivery. Dry-run mode uses this flow
internally because it makes no provider calls or renders.

## Dependencies

1. `MODELSLAB_API_KEY` for production narration and generated motion assets.
2. FFmpeg and ffprobe on `PATH`.
3. HyperFrames/Node.js for composition and rendering.
4. Manim for deterministic mathematics/science teaching animations when the
   selected scene strategy calls for it.

ModelsLab is not assumed to be free or unlimited. Cost and quota are
account/model dependent; preflight and the proposal gate must run before paid
generation.

## Stage contract

1. Input ingestion and source/coverage artifacts.
2. Proposal and decision log.
3. Educational content structure and chapter-faithful narration.
4. Scene plan and subject-aware media research.
5. Asset strategy/approval and fresh media acquisition.
6. One locked narrator voice, punctuation-aware delivery, and STT QA.
7. Speech-derived word alignment and subtitle generation.
8. Clip rendering with animation-first policy.
9. Measured-audio authoritative multimedia synchronization.
10. HyperFrames composition with the locked educational UI package.
11. Encoded-output visual/audio/subtitle/source-fidelity QA and local export.

## Outputs

The chapter project contains:

- `project.json`, `events.jsonl`, and `checkpoint_*.json` for Backlot.
- `decision_log.json` and `artifacts/agent_status.json` for any agent.
- Extracted source, chapter document, coverage contract, educational plan,
  scene plan, media research plan, and asset manifest.
- Narration manifest, word captions, SRT, and multimedia sync plan.
- Clip manifest, HyperFrames workspace, render report, final review, and
  publish log.

Never present a dry-run placeholder or a render with `final_review.status`
other than `pass` as the completed final video.
