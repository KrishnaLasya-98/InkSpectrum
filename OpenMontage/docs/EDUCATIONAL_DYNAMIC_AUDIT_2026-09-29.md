# Educational pipeline dynamic-readiness audit

Date: 2026-09-29

## Verdict

The repository has a configurable shared educational pipeline, but it is not yet a verified, fully autonomous any-PDF-to-final-video system. Existing chapter results combine shared tools with substantial chapter-specific production logic. A new chapter still needs source, narration, visual, exercise, and encoded-output review.

## Scope and evidence limits

This is a targeted architecture and implementation audit: shared planning, subject profiles, narration, composition, source coverage, stage tracking, precision rendering, validation documentation, and representative EVS, English, Maths, and GK production scripts. Project source/script paths were inventoried. It is not a claim that every historical file, binary asset, video frame, or generated artifact was read end to end. Full per-file review and live multi-subject production validation remain outstanding.

## Common requirements across subjects

1. Preserve chapter identity, grade, source order, headings, learning boxes, examples, activities, glossary, and assessments where present in the PDF.
2. Maintain source provenance and a chapter-specific workspace, asset manifest, narration manifest, and storyboard.
3. Use grade-appropriate narration, consistent narrator identity, punctuation, deliberate pauses, and measured audio timing.
4. Present source-faithful teaching panels and word-highlight subtitles in the shared HyperFrames appearance.
5. Match the visible object, diagram, or action to the current spoken concept.
6. Use subject-appropriate visuals: precise geometry/equations for Maths; character continuity and vocabulary/exercises for English; semantic object/animal/plant matching for EVS and GK.
7. Preserve textbook questions; show verified answers and explanation steps according to the lesson's answer-reveal policy. Personal-response questions need example responses, not fabricated unique answers.
8. Validate encoded output as well as source artifacts. A mapping coverage percentage alone cannot establish educational completeness.

## Implemented reusable foundations

- `tools/structure/subject_profiles.py` resolves YAML-configured subject profiles.
- `tools/structure/educational_generator.py` builds source-block-based plans and carries tables, provenance, questions, and layout metadata.
- `tools/structure/subject_pipeline_runner.py` connects narration, alignment, media routing, synchronization, HyperFrames composition, and QA.
- `tools/structure/educational_run_tracker.py` writes manifest-stage checkpoints and approval evidence for Backlot integration.
- `tools/structure/source_contract.py` verifies mapped blocks survive downstream artifact references.
- `tools/video/educational_hyperframes_composer.py` implements common teaching panels, structured tables, captions, and transitions.
- Existing portability documentation records real-source dry runs for EVS, English, Maths, and GK, explicitly excluding proof of live provider quality and final encoded sync.

## Confirmed gaps

| Priority | Finding | Evidence | Consequence |
|---|---|---|---|
| P0 | Maths templates embed textbook-specific numbers | `tools/video/manim_generator.py`: ruler/compass 5 cm, pizza 24/12 cm, compass radius 4 cm, four circles radius 3 cm | Reusing the same template for different numbers can display an incorrect explanation. |
| P0 | Coverage validates references, not semantic equivalence | `validate_final_source_coverage` checks scene IDs, provenance, clip success, and nonempty narration | 100% mapped blocks does not prove all textbook content is visible/spoken correctly. |
| P0 | Spoken headings are only partially integrated | Voice synthesis accepts `spoken_heading`; main runner supplies body text and selected hold durations but no heading | The requested spoken title followed by a four-second pause is not guaranteed. |
| P1 | Automatic plan is primarily source chunking | `educational_generator.py`, deterministic-source-contract planner | Source fidelity is useful, but engaging explanations and complete worked solutions are not guaranteed. |
| P1 | Successful chapter pipelines retain custom logic | English crop dictionary; EVS source-line map; GK section-to-media dictionaries; Class 1 Maths revision-specific builder/artifacts | New PDFs cannot simply inherit all the quality of the reference videos. |
| P1 | Generic renderer does not demonstrate arbitrary PDF figure reconstruction | Composer consumes structured tables and stores source bboxes; English exercise crops use hand-audited coordinates | Diagram-heavy and unusual exercise pages still require additional extraction/layout handling. |
| P1 | Grade is still hardcoded in export metadata | `final_stage_director.py` emits Class 1 description and Class1 tags | Higher-grade deliveries can receive wrong metadata. |
| P1 | Offline voice fallback is incomplete | `_call_piper` checks executable availability but contains no invocation body | Opt-in fallback cannot be relied upon. |
| P1 | Final-output parity remains unproven across subjects | `docs/EDUCATIONAL_PORTABILITY_VALIDATION.md` explicitly limits validation to dry runs | Agent-neutral packaging does not establish unattended production reliability. |

## Faster path to reliable dynamic production

1. Consolidate the strongest chapter builders into one scene schema: source heading, question, verified answer, worked steps, figure references, media cues, and word timing.
2. Parameterize all Maths templates and reject unsupported concepts rather than selecting an unrelated default animation.
3. Extract PDF figures using page/bbox provenance and generate reusable exercise components from structured content.
4. Derive heading speech, pauses, captions, visual reveals, and transitions from one authoritative cue timeline.
5. Cache by content fingerprint across source, script, voice, diagram parameters, provider/model, and template version; invalidate only dependent artifacts.
6. Persist provider job IDs and poll existing jobs on resume. Run independent clip jobs with bounded concurrency; keep the proven one-worker local final render configuration.
7. Use short representative preview renders before full encoding; never change the active render's inputs midway.
8. Add semantic coverage checks for exact values, units, questions, answer steps, diagram labels, and spoken/displayed headings, followed by encoded visual/audio review.
9. Validate with previously unseen PDFs across subjects and grades, including scanned pages, tables, and figure-heavy exercises. Record live results separately from dry-run results.

## Verification performed

Read-only source inspection and cross-project comparison. Attempted a focused pytest run for voice synthesis, generalization, and HyperFrames composition. The run was obstructed by Windows PermissionError during temporary-directory setup/cleanup, including a workspace-local basetemp retry; no clean test-pass claim is made. No production code was changed as part of this audit.

## Operational answer

The desired interface can remain one PDF input and one or more chapter-video outputs. Internally, automated QA must run for every chapter. Until the gaps above are closed and validated on unseen inputs, expect agent review and targeted repairs before final delivery; a promise of correct output for any arbitrary PDF would be unsupported.
