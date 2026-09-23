# Educational Video Pipeline Audit — 2026-09-17

## Audit scope

Reviewed the repository operating contract, architecture, checkpoint protocol,
pipeline manifests, EduStream stage skills, artifact schemas, tool registry,
PDF ingestion, narration/alignment, render routing, composition, and QA paths.
Primary sources were `AGENTS.md`, `AGENT_GUIDE.md`, `PROJECT_CONTEXT.md`,
`docs/ARCHITECTURE.md`, `docs/PIPELINE_FIXES_AND_STATUS.md`, both educational
pipeline manifests, and their referenced skills.

## Baseline rules

- The agent is the decision-maker; Python tools execute bounded operations and
  persist artifacts.
- Every long stage is checkpointed and schema-validated.
- Human gates cannot be bypassed by an autonomous run.
- Composition runtime, paid generation, licensed stock, provider changes, and
  publishing are explicit decisions.
- The source chapter remains the factual authority and all media needs
  provenance.

## Capacity assessment

Registry preflight found usable capacity for PDF extraction, FFmpeg, Remotion,
HyperFrames, image/video generation, TTS, speech-to-text, subtitles, audio,
asset strategy, and multimedia synchronization. Local Manim was unavailable.
The configured scene-planner provider was unavailable without
`ANTHROPIC_API_KEY`; an agent-authored schema-valid scene plan remains possible.
Local ComfyUI was unavailable, while multiple cloud image/video providers were
discoverable.

The principal throughput bottleneck is rendering. The legacy subject runner is
mostly sequential, re-encodes complete outputs, and can repeat speech analysis.
Its own status report estimates that parallelizing independent title/character
work with narration could save roughly 90–120 seconds. Parallelism must remain
bounded by browser, GPU, memory, disk, and provider limits.

## Gaps found and remediation

| Gap | Impact | Remediation |
| --- | --- | --- |
| Specialized manifest used undeclared top-level keys | Manifest validation failed | Extended the manifest schema for subjects, style playbook, render modes, and provider model configuration |
| No explicit proposal/runtime-choice stage | Agents could silently choose a compositor | Added `proposal` and `proposal_packet`, with a human gate and runtime decision contract |
| Hybrid media choice existed only in prose | Stock/generated choices were not deterministic or auditable | Added `hybrid_asset_router` and an asset approval stage |
| Timing logic was distributed | Offset duplication and drift were possible | Added `multimedia_sync_planner`; measured narration is authoritative |
| Declared specialized stage order differed from runtime | QA props/subtitles could be missing when clips rendered | Reordered voice → alignment → render → sync → composition |
| Narration schema rejected runtime timing fields | Valid enriched manifests could fail schema validation | Added start/end/timeline-source fields |
| Generic subjects were rejected by parser enum | New PDF subjects required code edits | Made subject labels dynamic when an explicit source path is supplied |
| PDF extraction did not persist canonical outputs | Resume/provenance were fragile | Added optional canonical Markdown/JSON persistence |
| Live compatibility runner lacked a plan input | Non-dry runs could fail before orchestration | Added inline/path educational-plan inputs |

## Architecture decision

The canonical autonomous path is the manifest-driven `educational-video`
pipeline, not the monolithic compatibility runner. The agent executes one stage
at a time, records decisions and checkpoints, and pauses at gates. Tools remain
small, deterministic, independently testable adapters. This makes the system
agent-compatible without granting unrestricted authority.

## Verification

- Changed Python modules compile successfully.
- Both educational manifests load and return the intended ordered stage graph.
- Focused routing, synchronization, PDF persistence, subtitle, checkpoint,
  planning, and manifest suite: 111 passed, 2 skipped.
- A broader contracts/libraries run during the audit reported 1,278 passed,
  16 skipped, and 29 failed. It exposed two new-tool skill-pointer failures and
  two planning-stage failures; all four categories were corrected and pass in
  the focused follow-up. Known unrelated debt remains in legacy skill pointers,
  theme-playbook keys, a provider-set expectation, and one UTF-8 BOM.

## Remaining work for a new chapter

The new chapter cannot be ingested until its PDF path and audience metadata are
provided. After ingestion, the proposal, educational plan, and asset strategy
must pass their declared human gates before paid or licensed media acquisition.
