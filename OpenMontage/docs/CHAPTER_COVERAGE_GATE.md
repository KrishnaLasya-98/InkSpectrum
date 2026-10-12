# Source-to-authored-output gate

New configurations require `content_policy.require_authored_coverage_audit`.
After shared composition authoring, before encoding/export, the runner writes
`artifacts/authored_coverage_audit.json`. Unresolved evidence blocks production.
Legacy configs remain report-only unless explicitly migrated. Dry runs report
issues without pretending their placeholder audio is production evidence.

For every required source block, the audit records its ID, PDF page, source
text, section IDs, authored screen times, actual panel text and narration text.
It does not count source-ID provenance alone as text coverage. Exercise blocks
require classified answers (textbook/derived/sample_response), verification
evidence, and answer text in both authored display and narration.

Conservative exact matching normalizes whitespace/case only. Rephrased titles,
equation pronunciation, diagrams and table restructuring may require review.
This first version does NOT accept semantic-review waivers or certify OCR,
question detection, mathematical truth, audio speech, or encoded pixels.
Do not make it pass by adding provenance text that never reaches the screen.
The next implementation is explicit reviewed equivalence/visual evidence for
non-verbatim presentation, granular question extraction and answer rendering.

## Shared question provenance

Before generation the runner writes `exercise_resolution.json`. In projects
requiring the teaching contract, unresolved exercise fragments or unsupported
answer evidence block paid generation. Printed answers use
`answer_evidence.source_block_ids` and must exactly match the cited text.
Numeric derived answers may use `answer_evidence.method: arithmetic` with an
`expression` appearing verbatim in the question. Only numeric addition,
subtraction, multiplication and division are evaluated, without code execution.
Units, diagrams, word-problem interpretation and open-ended answers remain
independent-review requirements; a free-text verification note cannot pass
this new gate. This verifies submitted question groups; it does not yet
automatically generate groups or answers for arbitrary PDFs.

Questions can reference ordered `source_block_ids` when a PDF question wraps
across extracted blocks or pages. The legacy `source_block_id` remains supported.
The question must equal the joined source fragments after whitespace
normalization; partial question text, missing IDs, duplicate IDs and conflicting
single/multiple references fail validation. Both planning and authored-output
checks use this shared rule. This does not automatically discover question
boundaries or verify answer correctness; those remain separate requirements.

Priority: repair and test these shared contracts before chapter-specific
regeneration. Existing chapters are regression fixtures, not exceptions to the
dynamic pipeline rules.

## Exercise discovery

The runner also writes `exercise_grouping_proposals.json` before the teaching
gate. Adjacent lines with compatible bounding boxes on the same page may be
proposed as a wrapped question when the prior text is unfinished or has an
open option parenthesis. New item labels, headings, figures, tables, page
changes and incompatible/missing geometry prevent automatic joins. Every
proposal retains source IDs and requires review; proposals do not alter the
approved plan or certify an answer. Cross-page groups can still be authored
explicitly and checked by the multi-block question validator.

The authored audit includes an `exercise_inventory`, produced by the shared
`tools.structure.exercise_inventory` module. It distinguishes instruction-only
headings, question candidates, uncertain text fragments, and visual exercises.
Instruction-only blocks still require display, narration, and timing evidence;
they no longer require an invented answer. Fragments and diagram/table exercises
retain answer-review requirements. No automatic merging, solving, or exemption
of uncertain content is performed. Detection currently relies on extracted
assessment metadata and English instruction patterns; it is not a universal
question detector. Reusable answer-screen rendering remains separate work.

## Ordered exercise timing

The narration syncer now accepts questions from `teaching_contract.questions`
(legacy `qa_pairs` remains supported). It resolves the complete question then
the complete answer in narration order; it no longer searches only an answer's
first word or substitutes a 2.5-second reveal. Requested thinking pauses must
exist between aligned speech words immediately after the question. Missing
phrases or pauses return a repair error. This can intentionally reject older
compressed narration or dry-run interpolation that contains no real pause.

Card props include section-relative question start, thinking start/end, and
answer reveal times. HyperFrames resolves these from the final global word
captions, displays one question card at a time, shows a thinking cue during
the requested pause, and reveals the answer when its aligned phrase starts.
MCQ choices and fill-blank answer text use the same card lifecycle. Authored
solution steps appear one at a time at their aligned spoken cue. Missing
phrase or pause evidence blocks composition. This is not yet a specialized
matching/diagram-interaction template or generated mathematical diagram animation.
The authored coverage audit reads rendered card text instead of the replaced
legacy panel body. Alignment quality and actual silence still require audio QA;
these checks validate the supplied timestamps, not the waveform itself.

## Exercise audio delivery

The shared runner forwards reviewed exercise questions to voice synthesis.
`exercise_delivery` splits the approved script after each ordered question,
preserving its words and punctuation. Voice synthesis renders the parts with
the same voice and joins them with exact PCM silence for each requested
thinking pause, in addition to title and topic-end pauses. Delivery parts are
included in the audio cache fingerprint. Mock-provider waveform tests verify
silence duration and cache reuse; live voice continuity still needs listening QA.

## Existing Maths Chapter 7 review

Report: projects/class-4-maths-part-2-chapter-7-basic-shapes/artifacts/
authored-coverage-review-20260929.json.

- Required blocks: 227; exact authored evidence: 28; review required: 199.
- Display review: 192; narration review: 191; answer evidence missing: 13.
- Counts overlap. No missing section-time mappings were reported.
- This is not proof of 199 omissions. It shows why provenance-only 100% coverage
  was insufficient. No existing video, script or source artifact was changed.
