# Dynamic educational pipeline: implementation checkpoint

Updated 2026-09-29. Shared code takes priority over chapter-specific repairs.
This is an implementation checkpoint, not a declaration of unrestricted
autonomous production readiness.

## Implemented and checked in this work

- Shared guided approvals now bind to a SHA-256 of the complete checkpoint
  artifact JSON. Identical payloads retain approval; changed payloads stop for
  review. Failed stages discard cached approval. Status/resume flags missing or
  mismatched approval hashes instead of claiming approved completion.
  Legacy approvals without hashes require rerun/review. Explicit full-run
  preauthorization remains a separate user-selected policy.
  This binds embedded JSON, not the bytes of arbitrary files named in that JSON;
  arbitrary referenced-file integrity and live provider recovery remain
  separate validation requirements.
- Dependency invalidation: an unfinished upstream stage blocks downstream
  status. A changed artifact payload or upstream failure marks existing later
  checkpoints failed and revokes approvals, preserving artifacts and history.
  An identical upstream rerun restores availability without revoking later approvals.
- Recovery: stage entry preserves artifacts and partial-progress metadata.
  Approval fingerprints survive process restart for identical content. The
  tracker exposes `progress()` for completed item IDs and pending provider job
  handles. Resume returns this recovery data without issuing provider requests.
  This is an agent handoff, not an automatic job scheduler; provider-specific
  loops still need to record and reconcile their jobs before retrying.
- Structured answer reviews bind to question, answer, solution and source content.
  Matching and diagram-label templates use ordered word-aligned reveals and
  validated local diagram assets. Unsupported/dense layouts stop for review.
- Multi-block question provenance shared by teaching and authored coverage checks.
- Conservative exercise inventory distinguishes instructions, question candidates,
  uncertain fragments, and visual exercises. Ambiguity remains reviewable.
- Script punctuation/capitalization restoration for lexically matching WhisperX
  output, without changing timestamps; quoted sentence endings recognized.
- Ordered full-question/full-answer timing; no fixed answer-reveal fallback.
- Requested thinking silence validated from word timestamps.
- HyperFrames question/choices, thinking cue, answer reveal, and sequential
  solution text tied to the final global word timeline.
- Coverage reads exercise cards instead of replaced legacy panel text.
- Runner forwards exercise delivery requirements to voice synthesis; same-voice
  audio parts joined with actual PCM pauses. Cache fingerprints include delivery.
- New template package hash updated in pipeline and chapter-config defaults.
  Existing project locks are not silently migrated.

## Verification evidence

- Approval binding, startup and production-artifact regression suite: 22 passed.
  Includes changed-content rejection, identical-content resume, checkpoint
  alteration detection, failure revocation and explicit preauthorization.
- Shared UI, exercise, subtitle, coverage, and startup suite: 53 passed.
- Broader planning/provider-contract/tracking/preflight/source/timing/QA suite:
  60 passed, without paid media generation.
- Voice and exercise-delivery suite: 10 passed, including real PCM-silence checks
  using a mocked voice provider and cache reuse.
- Synthetic 24-second exercise MP4: H.264/AAC, 1920x1080, 30 fps.
  HyperFrames inspection at 21.2, 21.8, 22.6 seconds: no errors or warnings.
  Encoded contact sheet inspected: question, thinking, answer states visible.
  Local fixture: `tmp/exercise-smoke-20260929/workspace/exercise-ui-check.mp4`.
  This uses test patterns and tones, not educational narration. It predates the
  solution-text addition; solution text has code tests, not encoded-frame QA yet.

## Remaining work, in dependency order

1. Complete source-question boundary resolution and reviewed answer production
   across extraction layouts; heuristics are not universal PDF understanding.
2. Validate dedicated matching, diagram-label, grammar, table and mathematical
   animation templates against their source layouts. Current reusable cards
   now include matching and diagram labels; not all specialized interactions
   or dense layouts have encoded-output validation.
3. Review solution-step UI in encoded output, including dense/long content.
4. Verify proposal costs and ETA calibration against actual provider jobs;
   structural tests do not establish accurate prices or queue completion times.
5. Exercise interrupted-run recovery and Backlot progress with live jobs, then
   validate independent assistants and deployment environments.
6. Run approved source-grounded chapters through all stages and compare the
   encoded outputs to PDFs and approved appearance references.

No existing chapter was certified complete by this checkpoint. No paid API
generation or historical reference-video changes were made.
