# HyperFrames textbook-video template comparison

Audit date: 2026-09-29. Read alongside `EDUCATIONAL_DYNAMIC_AUDIT_2026-09-29.md`.

## Evidence and limits

The inventory tool read all 14 HyperFrames HTML files under the project tree, including historical templates and one compiled preview, plus existing local JavaScript dependencies. The machine-readable inventory contains file hashes, media references, component classes, timing metadata, and missing static references. Representative production builders, source audits, storyboards, subject configuration, and shared pipeline code were also inspected.

This is a source-template comparison. It does not establish which exact source revision produced each historical MP4, and is not a claim of watching every frame of all final videos. Current HTML can have changed after encoding. Static counts exclude images/cards constructed at runtime and CSS background images. Missing references in the compiled preview are relative-path artifacts and must not be confused with failures in the source project.

## Actual template families

| Project / composition | Presentation and teaching components | Media architecture | Current authored static counts |
|---|---|---|---|
| English Class 1, `hyperframes-final` | Animated beach story; compact overlays; dedicated glossary, comprehension, vocabulary, grammar, life-skills and assessment cards; picture exercises, letter marking, and answer reveals | Separate silent story clips and narration; PDF exercise artwork; runtime-created teaching UI and captions | 27 video, 26 audio |
| EVS Lesson 8, `hyperframes-agnes-final` | Full-frame animal story with cream We Learn/highlight panels; textbook content, recall, glossary, assessment and activity treatments; bottom word-highlight captions | Static registered clips plus separate narration; runtime UI; opening image | 44 video, 16 audio, 1 image |
| Maths Class 1, `hyperframes-final` | Animated story opening, Spiral Learning and Recall; counters and tens/ones; number charts, number names, blanks, matching lines, ticks/crosses, skip-counting and expanded-form panels | `production-data.js` + `maths-ui-v3.js`; deterministic browser animation; selected Manim precision clips; separate narration | 5 video, 19 audio |
| GK Class 1, `hyperframes-final` | Green/cream nature style; compact facts; Fun Too riddle; environmental action cards with ticks/crosses; five-image herb matching and answer reveals | Story video layer, narrated track, runtime plant/exercise images, word-aligned captions and highlights | 10 video, 1 audio |
| Maths Class 4, current `hyperframes-final` | Shared `hyperframes-educational-v1` authoring; opening, We Learn, highlights, concepts, worked examples, activities, blanks, recap | 17 geometry/precision videos; 29 narration tracks; newly approved GPT intro as CSS background | 17 video, 29 audio |

These are custom template families, not evidence that every chapter uses an identical named starter template. The newer shared template is an attempt to consolidate them; it has not yet reproduced all the richer exercise behavior from the older projects.

## What should be common

- One reusable visual system: readable source headings, cream content panels, safe subtitle lane, consistent active-word treatment, calm transitions, and grade-scaled typography.
- One source model preserving PDF page, bounding box, exact text, tables, figures, question order, and source errors/errata.
- One narration model with textbook reading, teacher explanation, pronunciation overrides, heading speech, pauses, and answer reveals as distinct authored fields.
- One measured cue timeline controlling narration, subtitles, relevant media, diagram steps, highlights, and answer visibility.
- One media manifest identifying provenance, generation model, job ID, licensing where relevant, hash, duration, and scene association.
- One QA process covering source, answers, pronunciation, display overflow, word timing, semantic media matching, encoded motion, and final delivery.

Sections must be discovered from the PDF. English's source audit explicitly says that this chapter has no We Learn or Highlights section. The shared framework must not insert those headings into every book just because EVS has them.

## What must vary by subject

| Subject | Required explanation / animation plan | Questions and answers |
|---|---|---|
| Mathematics | Given values and units, exact question, method, individual operations, animated counters/lines/shapes, then verified result. Diagram labels and animation geometry must take values from the scene data. | Preserve question and supplied examples; compute/check derived answers; reveal each narrated solution step and final answer after learner time. |
| English | Exact reading passage, intentional pauses, speaker interpretation recorded separately, consistent characters, vocabulary meaning, grammar/phonics demonstration, and PDF picture tasks. | Source-grounded comprehension answers; explicit sample responses for personal questions; preserve activities needing teacher input. |
| EVS / Science | Exact factual text plus age-appropriate explanations; identify the correct animal, habitat, object, or process at the spoken cue; precision diagrams for mechanisms where needed. | Factual answers checked against the source; distinguish open-ended care/life-skills responses from unique correct answers. |
| GK | Short source facts with recognizable plant/object footage; preserve riddle, identification, matching and tick/cross activities. | Check every image-label association and factual answer; do not invent a glossary or extra unsupported facts. |
| Other subjects | Extend subject profiles and reviewed components; maps, timelines, experiments, and technical notation need specialized validation. | No blanket promise that a generic animation or answer generator covers all disciplines. |

## Textbook accuracy and natural narration

Maintain immutable textbook wording separately from teacher bridges and derived answers. Exact display text should preserve the source, with explicit errata when a printed mistake needs correction. Spoken forms of numbers, abbreviations, and punctuation may need reviewed pronunciation transformations; these should be recorded instead of silently modifying the source. Subtitles must reflect what is actually spoken with correct punctuation and measured word timing.

There are existing conflicting policies: English preserves source errors on cards, while the Class 1 Maths audit says source errors are corrected and logged. Resolve this per source using an explicit errata policy rather than assuming one approach is universally accurate. No OCR engine or generative model can promise literal and factual correctness for arbitrary PDFs without verification.

## Changes implemented in this audit

1. `tools/analysis/hyperframes_template_inventory.py`: reusable full-file HTML/local-script inventory with hashes, template vocabulary, media counts, missing static references, and dynamic-DOM indicators.
2. `tools/structure/teaching_contract.py`: checks exact source excerpts and authored display text, source reading, separate narrated explanations, spoken animation cues, source-linked questions, answers, solution steps, answer provenance, and thinking-pause values.
3. `subject_pipeline_runner.py`: writes `artifacts/teaching_contract_review.json` after orchestration. `content_policy.require_teaching_contract=true` makes incomplete authored plans stop before paid generation. Historical plans receive reports without being silently certified or automatically rewritten.
4. Focused tests cover changed values, absent evidence, missing answers, unspoken animation cues/solution steps, empty authority, and heading deduplication.
5. Q&A inheritance in the runner now uses exact source block IDs and preserves authored Q&A. Previously it selected the first block with the same type, which could attach another exercise's answers to a section.

The contract validates authored evidence. It does not yet render every new field, independently verify an answer, resolve animation cues to measured timestamps, or certify the final encoded video. Enabling strict mode on an old plan will correctly report missing evidence; migration is required.

## Remaining production limitations

- Chapter-specific scene dictionaries, hardcoded exercise coordinates, source-line selections, and section-ID branches remain in the reference productions.
- Maths templates contain fixed numerical examples. Unsupported concepts can fall back to generic visuals; safe generalization needs parameterized templates and explicit unsupported-case handling.
- The deterministic planner chunks source text. Complete explanations and solved exercises require additional authored reasoning and verification.
- Current source coverage is primarily provenance coverage. Pixel-level PDF fidelity and spoken/displayed meaning need separate verification.
- Heading speech and four-second pauses are not fully wired through all shared stages.
- Legacy and modern chapter configuration formats differ, including TTS settings and grade-dependent field names.
- Word alignment, image recognition, and generative motion may fail or be uncertain. Review and targeted repair remain necessary.
- File naming a render `final` does not prove it corresponds to the current HTML or passed QA. Persist source hashes alongside each delivered MP4.
- Provider credits, rate limits, queue delays, outages, disk capacity, model changes, and rendering resources prevent an unconditional unlimited/uninterrupted guarantee.

## Scalable target and efficient work order

Aim for an unattended queue that resumes safely and holds uncertain chapters for repair, with consistent quality gates. There is no fixed chapter-count limit inherent to that architecture; infrastructure and provider budgets determine throughput.

1. Migrate source-specific builders into reusable scene components driven by a versioned schema.
2. Parameterize Maths and add verified solver/answer evidence; preserve personal-response activities as sample responses.
3. Add automatic PDF figure/table extraction with confidence and visual checks.
4. Finish the shared speech/pause/cue compiler and make it drive every UI and animation event.
5. Cache immutable artifacts by their real dependencies. Rebuild only affected audio, media, scenes, and timing after a correction.
6. Persist external job IDs before polling; use bounded concurrency, provider backoff, retry limits, and idempotent resumes. Do not silently lower quality when a provider fails.
7. Render small representative previews before full encoding. Associate every final with its exact source/config/media/template hashes.
8. Validate unseen chapters across grades and subjects, including scanned PDFs and difficult exercises, through actual encoded-output QA.

This is a dynamic production framework under consolidation, not yet a fully verified universal autonomous video factory.

## Authoring the new contract

Add `teaching_contract` to each plan section. Example for a source block whose exact text is `What is 2 + 3?`:

```json
{
  "source_excerpts": [
    {
      "block_id": "q1",
      "verbatim_text": "What is 2 + 3?",
      "display_text": "What is 2 + 3?",
      "narrate_verbatim": true
    }
  ],
  "explanations": ["Count two, then three more."],
  "animation_beats": [
    {
      "cue_text": "Count two",
      "visual": "Two counters",
      "action": "Reveal two counters, then add three at the next spoken cue."
    }
  ],
  "questions": [
    {
      "source_block_id": "q1",
      "question": "What is 2 + 3?",
      "answer": "The answer is five.",
      "answer_kind": "derived",
      "solution_steps": ["Count two, then three more."],
      "verification_evidence": "Independent integer arithmetic check: 2 + 3 = 5.",
      "thinking_pause_seconds": 4
    }
  ]
}
```

The section's narration must include the source reading, explanation, solution steps, and answer. Verification evidence is an auditable assertion and still needs an independent checker. Do not mark a produced answer as a textbook answer unless the source actually supplies it.
