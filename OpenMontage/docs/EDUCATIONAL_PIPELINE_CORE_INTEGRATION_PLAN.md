# Educational Pipeline → OpenMontage Core Integration Plan

## Decision

Integrate incrementally. Keep the educational planning, media research, asset
routing, and synchronization components modular and registry-discovered. Do not
couple subject policy to renderers or provider adapters. Promote the pipeline to
core production only after checkpoint enforcement, observability, and a real
chapter soak run pass.

The user-selected composition runtime is **HyperFrames**. Remotion remains an
available alternative and compatibility renderer, but it is not the default for
this educational-video program. FFmpeg remains the media preparation, muxing,
and encoding layer beneath or around HyperFrames.

## Current architecture

| Component | Responsibility | Core coupling | State |
| --- | --- | --- | --- |
| `HybridPDFExtractor` | PDF → canonical Markdown/JSON | `BaseTool`, artifact schema | Ready for beta |
| `EducationalMediaResearchPlanner` | Subject-aware search plan | `BaseTool`, media-plan schema | Isolated and tested |
| `DirectClipSearch` | Multi-source candidate acquisition | Existing stock adapters, requests, FFmpeg | Existing beta tool |
| `HybridAssetRouter` | Existing/stock/generated/diagram decision | `BaseTool`, downstream selectors | Isolated and tested |
| `NarrationTextSyncer` | Word/subtitle alignment | Existing STT tools | Existing production path |
| `MultimediaSyncPlanner` | Authoritative post-render timeline | `BaseTool` | Isolated and tested |
| Pipeline manifests | Ordered stages and approval gates | Loader and checkpoint layer | Valid; needs staged rollout |

## Dependency analysis

The three new deterministic planners use only Python's standard library and
existing OpenMontage abstractions. They introduce no package-version conflict.

Installed runtime observed during audit:

- Python 3.14.7
- requests 2.34.2
- jsonschema 4.26.0
- pydantic 2.13.5
- FFmpeg 9.0.1
- Node 24.19.0 / npm 11.17.0
- Remotion 4.0.484

Manim is declared in `requirements.txt` but is not installed. It must remain an
optional renderer with a Remotion/HyperFrames/diagram fallback until its Python
3.14 compatibility is verified in a clean environment. Stock acquisition uses
existing `requests`; thumbnails use existing FFmpeg. Pexels/Pixabay/Unsplash
may require credentials, while Archive.org, Wikimedia, NASA, NARA, Library of
Congress, Coverr, and Pond5 public-domain adapters are currently discoverable
without mandatory keys.

## Compatibility findings

1. Registry discovery succeeds for `educational_media_research_planner`,
   `hybrid_asset_router`, `multimedia_sync_planner`, and `direct_clip_search`.
2. Artifact schemas cover PDF extraction, media research, narration timing,
   proposals, plans, assets, rendering, and final review.
3. Manifest loading and runtime-selection governance tests pass.
4. Manifest stage order is dynamic and checkpoint prerequisites use it when
   `pipeline_type="educational-video"` is supplied.
5. Risk: `CANONICAL_STAGE_ARTIFACTS` still maps legacy generic stage names.
   A specialized completed stage can therefore omit its declared primary
   artifact unless the caller explicitly supplies and validates it.
6. Risk: `direct_clip_search` is beta, networked, downloads up to its configured
   disk budget, and has no native resume support. Its partial-result behavior
   must be surfaced in checkpoints.
7. Risk: the legacy subject runner is one-process compatibility code, not the
   canonical resumable agent path.
8. Risk: the legacy `RenderModeRouter` implements HyperFrames only as a chapter
   title renderer; Q&A remains Remotion-specific. Full HyperFrames production
   must use the authored workspace / `hyperframes_compose` path rather than
   relabeling legacy per-section modes.

## Required core changes before production promotion

### Checkpoint enforcement

Teach the checkpoint layer to obtain required `produces` artifacts from the
selected manifest rather than relying only on `CANONICAL_STAGE_ARTIFACTS`.
Maintain the static map as backward compatibility for projects without a
pipeline type. Add contract tests for missing `media_research_plan`,
`asset_manifest`, and `multimedia_sync_plan` at completed checkpoints.

### Execution boundary

Add or standardize a manifest stage executor that:

1. writes an `in_progress` checkpoint;
2. validates tool input and output;
3. persists artifacts atomically;
4. records duration, cost, provider/model, retries, and failure class;
5. writes `awaiting_human` or `completed` according to the manifest gate;
6. resumes only idempotent or explicitly resumable work.

Do not embed subject decisions in this executor. Subject behavior belongs in
the media research plan and asset strategy artifacts.

### Observability

Use existing checkpoint `metadata` and `cost_snapshot` fields initially. Add a
read-only project metrics aggregator rather than telemetry or a background
service. It should report:

- stage wall time and wait time;
- tool/provider success and retry counts;
- cost estimate versus actual cost;
- media-search hit rate and candidate rejection reasons;
- stock/generated/diagram mix;
- render failures and revisions per scene;
- peak temporary disk estimate;
- audio/clip drift before correction;
- subtitle coverage and boundary violations;
- final QA result and total time to approved output.

No external telemetry should be added without a separate privacy review.

## Test strategy

### Unit

- Subject classification and search-policy routing.
- Stock/generated/diagram decisions and budget gates.
- PDF canonical artifact persistence.
- Narration and clip duration reconciliation.
- Schema validation for every new artifact.

### Contract

- Tool registry discovery and resolvable skill pointers.
- Pipeline manifest ordering and runtime-choice governance.
- Manifest-derived required artifacts at checkpoint completion.
- Human gates fail closed.
- Old projects without the new stages continue to load.

### Integration

- Fixture PDF → extraction → proposal → plans, with providers mocked.
- Scene plan → search plan → candidate metadata → asset manifest.
- Synthetic audio and clips → subtitles → sync plan → short composition.
- Resume after a failed stock search and after an interrupted render.

### End-to-end acceptance

Run one representative chapter each for:

- science/social studies: attributable documentary media;
- mathematics: diagram-first rendering with a real-world hook;
- English story: character continuity and limited stock establishing shots;
- English grammar/phonics: typography-first composition;
- unknown subject: routing from scene semantics, not hardcoded names.

Each final video must be fully decoded, inspected at scene boundaries, checked
for audio/subtitle drift, and approved through the final human gate.

## Phased rollout

### Phase 0 — Freeze and baseline

- Preserve the current working video path and benchmark duration, cost, disk,
  subtitle coverage, and QA failures.
- Separate unrelated working-tree changes before review.
- No production-default change.

### Phase 1 — Beta pipeline

- Publish the new manifest under a beta identity or feature flag.
- Enable local deterministic planners and mocked provider integration.
- Acceptance gate: unit/contract suite green and old pipeline regression green.

### Phase 2 — Checkpoint and metrics integration

- Implement manifest-derived artifact enforcement.
- Add the read-only metrics aggregator and resume tests.
- Acceptance gate: forced interruption resumes without duplicated paid work.

### Phase 3 — Controlled chapter pilots

- Run the five subject profiles above with strict cost/disk limits.
- Compare output quality and performance with the baseline.
- Acceptance gate: no severity-1 QA failures and no gate bypasses.

### Phase 4 — Production promotion

- Promote the beta manifest version only after pilot approval.
- Retain the previous version for rollback and existing projects.
- Document migration rules; never reinterpret old checkpoints in place.

## Version-control practice

- Use a dedicated integration branch.
- Keep commits reviewable: schemas/contracts, planners, manifest/skills,
  checkpoint enforcement, metrics, then pilot fixtures.
- Do not mix generated video assets or unrelated UI edits into core commits.
- Tag the pre-integration baseline and the first production release.
- Use additive schema changes during beta; require a migration note for
  removals, renamed fields, or changed stage semantics.

## Rollback

Rollback is manifest-version selection, not destructive file replacement.
Existing projects retain their recorded `pipeline_type` and manifest version.
New components write additive artifacts, so disabling the beta pipeline leaves
legacy projects and renderers intact.

## Production readiness gate

The integration is production-ready only when all of the following are true:

- manifest-derived artifact enforcement is merged;
- checkpoint interruption/resume tests pass;
- dependency installation is reproducible on a supported Python version;
- the five subject-profile pilots pass encoded-output QA;
- metrics show acceptable duration, cost, and disk use;
- documentation and rollback steps have been exercised by a second operator.
