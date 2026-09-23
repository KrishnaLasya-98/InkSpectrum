# Agent-Compatible Educational Video Pipeline

## Scope

This document defines the safe, auditable path from a textbook PDF to a final educational video. “AGI-compatible” means that a capable coding agent can discover capabilities, make bounded decisions, resume work, explain every choice, and verify the output. It does not mean unrestricted authority.

## Canonical inputs

- Source PDF and optional teacher notes.
- Project ID, chapter title/number, subject type, audience/grade, language, duration target.
- Style playbook and approved composition runtime/mode.
- Budget, provider restrictions, licensing constraints, and checkpoint policy.

## Canonical outputs

- `extracted_content.json` and `extracted_content.md`.
- `proposal_packet.json` with the approved runtime, budget, and constraints.
- `educational_plan.json`, `scene_plan.json`, and cumulative `decision_log.json`.
- `asset_manifest.json` with source/license/provider/prompt/seed provenance.
- `narration_manifest.json`, word captions, SRT, QA-card timing, and `multimedia_sync_plan.json`.
- Rendered clips, final MP4, `render_report.json`, `final_review.json`, snapshots, and export bundle.

## Execution graph

```text
preflight
   ↓
PDF extraction → source fidelity review → production proposal ── HUMAN GATE
   ↓
educational plan ── HUMAN GATE
   ↓
scene plan → subject-aware media research → hybrid asset strategy → asset acquisition ── HUMAN GATE
   ↓
narration → word alignment
   ↓
clip rendering → authoritative multimedia sync plan
   ↓
composition → full encoded-output QA ── HUMAN GATE
```

PDF extraction and source review are sequential. Independent scene assets may run in parallel after the asset gate. Narration synthesis may be parallelized by segment. Final synchronization requires measured narration and rendered-clip durations, so it remains a join point before composition.

## Hybrid asset policy

`educational_media_research_planner` first classifies the subject and creates
provider-neutral search tasks. Science/EVS and social studies favor attributable
real-world sources; maths favors deterministic diagrams; English separates
story continuity from grammar, phonics, and concrete vocabulary.

`hybrid_asset_router` then makes a reviewable decision for each scene:

1. Reuse a reviewed project asset when it matches.
2. Prefer licensed stock for factual real-world subjects.
3. Prefer authored diagrams/animation for mathematics and abstract processes.
4. Use generated video for continuity or specificity gaps that stock cannot satisfy.
5. Block the scene when motion is required and no permitted route exists.

The router plans; selectors execute. This separation prevents hidden provider changes and makes provenance auditable.

## Synchronization protocol

`multimedia_sync_planner` treats measured narration durations as authoritative. For each section it records:

- global start/end;
- audio and clip duration;
- drift;
- visual policy (`as_is`, `trim_to_audio`, `loop_or_hold_last_frame`);
- subtitle offset;
- missing-clip blockers.

Title offsets are applied once. Subtitle and answer-reveal timing comes from word alignment, not fixed delays.

## Authority boundaries

The production agent may create reversible artifacts, call approved local tools, and resume checkpoints. It may not bypass human gates, spend above policy, switch providers/runtimes, publish externally, or perform destructive operations without explicit approval.

## Starting a new chapter

1. Place the PDF somewhere readable inside the workspace or provide its absolute path.
2. Supply project ID, audience/grade, subject type, language, and target duration if known.
3. Run registry preflight.
4. Initialize the project:

   ```powershell
   python -c "from lib.checkpoint import init_project; init_project('<project-id>', title='<Chapter title>', pipeline_type='educational-video')"
   ```

5. Have the educational-video orchestrator execute each manifest stage and stop at declared approval gates.

The project-specific agent configuration is `.cursor/agents/educational-video-orchestrator.md`; persistent operating constraints are `.cursor/rules/agi-educational-video-pipeline.mdc`.
