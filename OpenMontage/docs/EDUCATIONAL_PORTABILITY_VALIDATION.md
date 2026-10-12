# Educational Pipeline Portability Validation

Validated on 2026-09-28 from the Windows source checkout.

## Cross-agent package

`python -m tools.structure.educational_agent_cli doctor` passed all adapters,
the `educational-video` manifest, and all 11 manifest-referenced director/meta
skills. The supported control contract is JSON + exit codes + project files;
it does not require a Codex, Claude, Cursor, or Hermes SDK.

## Real-source multi-subject matrix

The following supplied PDFs completed the full no-cost dry-run graph, including
source coverage, scene/asset planning, narration placeholders, subtitle timing,
clip routing, authoritative synchronization, locked HyperFrames authoring, and
all 12 Backlot checkpoints.

| Subject | Source blocks | Planned sections | Coverage | Planned duration |
|---|---:|---:|---:|---:|
| EVS | 99 | 102 | 100% | 310.0 s |
| English | 110 | 155 | 100% | 362.5 s |
| Maths | 242 | 253 | 100% | 1095.0 s |
| General Knowledge | 26 | 32 | 100% | 99.0 s |

All runs selected ModelsLab contracts for narration and generated motion,
HyperFrames for composition, one worker with low-memory rendering, and the
locked educational template package.

## Validation boundary

This matrix verifies real PDF extraction, subject generalization, schemas,
orchestration, artifact generation, and Backlot integration. Dry-run narration
uses placeholder timing and therefore reports linear subtitle interpolation.
It does **not** prove ModelsLab availability/output quality, speech-derived word
timing, encoded motion quality, or final audio/video sync. Those require a paid
production run followed by the mandatory encoded-output review; a render is not
final unless `final_review.status` is `pass`.
