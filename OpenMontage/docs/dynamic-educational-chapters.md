# Dynamic Educational Chapter Workflow

Educational chapters are configured with `projects/<project-id>/chapter_config.json`.
The rendering and synchronization code must not contain chapter names, textbook
sentences, animal lists, assessment questions, grade-specific pacing, or provider
choices.

All chapters use the locked `hyperframes-educational-v1` UI contract and the
`source-faithful-book-v1` presentation contract in
`styles/hyperframes-educational-v1.yaml`. Chapter content remains dynamic, but
changing the approved layout system requires an explicit template-version update.

The loader resolves and records `ui_template_version`,
`ui_template_contract_path`, `ui_template_sha256`, and
`ui_template_package_sha256` in every chapter's effective `render_policy`.
The package hash covers both the YAML contract and the HTML/CSS/GSAP compiler,
so changing implementation geometry while retaining the same YAML identity also
fails closed. The educational pipeline manifest independently pins the same
values. A chapter may populate the declared content slots, but it cannot
override the template palette, layout, component geometry, runtime, or subtitle
lane.

## Template change control

Do not edit the locked template to solve a single chapter's content problem.
Use its supported content slots or improve the relevant subject renderer. When
the shared visual system genuinely must change:

1. create a new template ID or increment its semantic version;
2. review hero frames for opening, explanation, recall, glossary, and assessment;
3. update the canonical hash in `chapter_config.py` and
   `pipeline_defs/educational-video.yaml` in the same reviewed change;
4. run the template-contract and pipeline-catalog tests; and
5. migrate chapter profiles explicitly rather than changing their appearance
   silently.

## Required flow

PDF ingestion -> source audit -> educational plan -> approved script -> scene plan
-> asset strategy -> narration -> word alignment -> animated clips -> multimedia
synchronization -> HyperFrames composition -> encoded-output QA.

The one-command runner now materializes that flow instead of treating it as a
documentation-only diagram. It writes schema-valid `proposal_packet.json`,
`scene_plan.json`, `asset_strategy.json`, and `asset_manifest.json`; every scene
keeps its source block IDs. The asset manifest is finalized with concrete clip
paths, content fingerprints, and QA status after rendering. Unknown render modes
block before media generation.

## ModelsLab provider boundary

The generated chapter profile selects ModelsLab for narration and animated
media. OpenMontage still owns PDF/source interpretation, coverage validation,
subject routing, the authoritative timing map, HyperFrames composition, and
encoded-output QA. Generated clip audio is disabled and removed after download;
the chapter's locked ModelsLab narrator is the only speech authority.

Provider model IDs live in `chapter_config.json`, not in chapter-specific code.
The default profile uses Wan 2.2 text-to-video, Wan 2.2 image-to-video when a
reference frame exists, and H3 MiniMax text-to-video as a configured fallback.
Model and operation compatibility is validated before an API request is sent.

Motion narration is split into punctuation-aware phrases that fit a generated
clip. If a motion clip is shorter than its measured narration, synchronization
fails and requests replacement coverage; the pipeline does not loop or freeze a
generated story clip. Stable recall, glossary, and assessment screens may hold
while learners read.

## Source completeness gate

PDF ingestion now writes `artifacts/chapter_document.json` and
`artifacts/coverage_contract.json`. Every required source block begins as
`pending`; planning must link it to narration, a screen, and a visual cue before
media generation is allowed. Tables remain structured as rows and cells.
The zero-shot planner carries the exact cell text, page number, semantic role,
and available source bounding box into each teaching section. Large tables are
paginated by rows, repeat their source header, and render as semantic HTML
tables rather than screenshots or Markdown pipes. Immediately before encoding,
`final_source_coverage.json` verifies that every required block still exists in
the final educational plan, narration manifest, clip manifest, and authored
HyperFrames timeline. Planning coverage alone is not accepted as final proof.

When the extraction backend cannot supply bounding boxes or text-box geometry,
the source artifact records that limitation and requires a visual PDF audit
instead of claiming that layout was preserved.

The independent PDF-layout pass also acts as a recovery source. If the Markdown
conversion omitted a detected table or boxed text block, the pipeline creates a
required `pdf-layout-recovery` source block, preserves every detected table cell,
page coordinates, normalized box coordinates, font size, bold/italic flags, and
reading order, then subjects that recovered block to the same coverage gate.
Partial geometry is reported as partial; one successful match can no longer make
the entire chapter claim complete box preservation.

## Dynamic subject routing

Subject behavior is stored in
`config/educational-subject-profiles.yaml`. Mathematics, English/language,
natural science and EVS, social studies, general knowledge, and the general
fallback profile declare aliases, subject type, default renderer, per-section
renderer choices, and ModelsLab prompt style as data. A new subject name can
use the general fallback immediately; adding a specialized subject requires a
YAML profile, not planner or renderer code changes.

The profile controls content treatment, not UI geometry. Mathematics may route
precise explanations to Manim, language stories to ModelsLab animation, and
tables or assessments to native HyperFrames teaching screens while all of them
retain the same locked educational layout.

## Media isolation and motion policy

- Generate a new asset manifest for each PDF/chapter and keep its media inside that project's asset directory.
- Do not use assets or rendered footage from a previous chapter unless reuse is explicitly approved.
- Default to polished, child-friendly 3D animated video with no embedded text, watermark, malformed anatomy, replay, or looping.
- Story clips are single-use by default. Generate additional clips or apply gentle deterministic retiming when coverage is insufficient.
- Align named people, animals, objects, actions, and places to the exact spoken interval.
- Use motion-first scenes for introductions and explanations. Never narrate the opening lesson over an empty canvas.
- Use stable reading screens for recall, glossary, exercises, MCQs, activities, and life skills when pedagogically useful. Add synchronized word highlighting and subtle panel motion rather than unnecessary footage changes.
- Keep each subject and chapter in a separate generation environment and render workspace.

## Text policy

- Use only the chapter title, source section headings, narration subtitles,
  assessment prompts, and answer reveals.
- Do not invent decorative labels, slogans, or filler transition cards.
- Do not repeat narration as a second paragraph when subtitles already carry it.
- Keep textbook wording where accuracy matters; teacher bridges may simplify the
  delivery but cannot replace or contradict source content.
- Grade delivery settings control pace, sentence length, subtitle density, and
  explanation depth.

## Mandatory synchronization and opening UI

- Every chapter starts over full-frame animated footage with a cream `We Learn`
  badge at top left, followed by a cream question card and a `Highlights of the
  Lesson` card at top right when those source blocks exist.
- The highlight card is populated from audited chapter topics; it is never a
  hard-coded EVS list.
- The approved narration audio is transcribed with word timestamps. The exact
  approved script words are projected onto those speech-derived timestamps.
- Linear duration-based word timing is a failure state for production renders.
- Audio, subtitle highlighting, visual subject cues, and teaching-card changes
  must consume the same authoritative timing map.
- A named person, animal, object, action, place, equation, or grammar example
  appears when its aligned word or phrase is spoken, not at an evenly divided
  percentage of the section.

## Book presentation order

1. Start with animated lesson footage, the source chapter title, and the first spoken line.
2. Show source `We Learn` questions, then source lesson highlights, over relevant motion.
3. Present every textbook heading in source order with only its current spoken idea visible.
4. Keep explanations visual and synchronized; do not reproduce full textbook paragraphs twice.
5. Present recall, glossary, exercises, MCQs, activities, and life skills as source-faithful reading screens.
6. Preserve every question, option, blank, instruction, and life-skill statement exactly.
7. Finish after the final source item and narration; do not add generic summary or filler cards.

## Starting another chapter

1. Copy `projects/evs-lesson-8/chapter_config.json` into the new project.
2. Change source paths, chapter metadata, grade settings, and providers.
3. Run `python -m tools.structure.subject_pipeline_runner --chapter-config <path> --dry-run`.
4. Review the generated source coverage, script, scene plan, and provider decisions
   before authorizing media generation.

The legacy `--subject` registry remains supported, but new chapters should use
the document command or `--chapter-config` so no core-code edit is needed.

## One-command document to video

The standard automated path accepts PDF, Markdown, plain text, and DOCX. New
runs are guided by default and stop at manifest approval gates:

```powershell
python -m tools.structure.pdf_to_video_pipeline "D:\path\chapter.pdf"
```

## Complete textbook to chapter videos

For a full textbook, the portable controller detects the contents table,
resolves printed page numbers to actual PDF pages, and writes a reviewable
chapter map before starting chapter generation:

```powershell
python -m tools.structure.educational_agent_cli book "D:\path\textbook.pdf"
```

After reviewing `chapter_map.json`, approve the split and perform a no-cost
end-to-end validation of every chapter:

```powershell
python -m tools.structure.educational_agent_cli book "D:\path\textbook.pdf" `
  --approve-chapter-map --dry-run
```

Use `--full-run-preauthorized` only with an approved budget. The orchestrator
creates one isolated educational project and one dynamic HyperFrames HTML
workspace per chapter. Final MP4s are gathered under the configurable delivery
root as `Class-{grade}-{subject}/Class-{grade}-{subject}-Part-{part}-Chapter-{number}-{title}.mp4`.
Parent book manifests, split source PDFs, and the generated collection HTML
index live under `OPENMONTAGE_COLLECTIONS_DIR`; final videos live under
`OPENMONTAGE_DELIVERY_DIR`. Both settings accept container or mounted cloud
volume paths, so no local Windows path is embedded in generated code.

Backlot state is available to any coding agent through the portable controller:

```powershell
python -m tools.structure.educational_agent_cli status projects\<project-id> --write
python -m tools.structure.educational_agent_cli approve projects\<project-id> proposal
```

Use `--full-run-preauthorized` only after the user has already approved the
proposal, provider spending, and delivery policy. `--dry-run` is automatically
preauthorized because it makes no provider calls and creates no encoded output.

PDF input retains the layout-aware extraction path. DOCX tables and document
order are normalized into the same source contract; formats without dependable
page coordinates remain explicitly flagged for layout review.

The command infers the chapter metadata, creates the project workspace and
dynamic profile, runs the educational production pipeline, and returns the
final video path. Inference can be overridden with `--grade`, `--chapter`,
`--book-part`, `--title`, `--subject`, or `--subject-type` when a source document
is ambiguous. Approved chapter videos are copied into the flat delivery folder
`final-videos/Class-{grade}-{subject}/` using
`Class-{grade}-{subject}-Part-{part}-Chapter-{number}-{title}.mp4`. A part is
inferred only from explicit `VOLUME`, `PART`, or `BOOK` filename tokens; suffixes
such as `pages-2` are never treated as a book part.

Use `--dry-run` to validate a new PDF without cloud media generation. It proves
source ingestion, schema compatibility, stage wiring, and HyperFrames authoring;
it does not prove ModelsLab output quality or encoded-video QA.

Models and the chapter narrator can be selected per run without editing Python:

```powershell
$env:MODELSLAB_API_KEY="<stored-secret>"
python -m tools.structure.pdf_to_video_pipeline "D:\path\chapter.pdf" `
  --voice-id "nova" --audio-model-id "text-to-speech" `
  --audio-language "english" --audio-speed 0.82 `
  --video-model-id "wan2.2" `
  --image-video-model-id "wan-2.2-i2v" `
  --reference-video-model-id "h3-minimax-r2v" `
  --fallback-video-model-id "h3-minimax-t2v"
```

For repeatable deployments, pass `--provider-config models.yaml`. The file may
contain only `audio` and `video` model/voice settings. Credentials, tokens, and
password fields are rejected; `MODELSLAB_API_KEY` must remain in the environment
or an ignored secret store. CLI values override the matching YAML values.

Before any paid request, `preflight_report.json` verifies the ModelsLab audio
and video provider selection, every configured model/operation contract, API
credential presence, FFmpeg/ffprobe, the local semantic-frame evaluator, disk
headroom, and the one-worker low-memory HyperFrames policy. Production stops at
preflight when any required capability is absent; dry-run validates routing and
model contracts without requiring cloud credentials.

## ModelsLab provider contract

ModelsLab is the configured cloud provider for both generated media types:

- `providers.audio` uses ModelsLab text-to-speech. One voice ID is locked for
  the whole chapter, and speech-to-text QA plus word alignment produce the
  authoritative subtitle timing.
- `providers.video` uses ModelsLab text-to-video, image-to-video, or
  reference-to-video according to the scene inputs and declared model
  capability. Provider-native sound is disabled and stripped if returned.

Narration and footage intentionally remain separate assets. HyperFrames mixes
the approved narration over silent video; this avoids character-to-character
voice changes and prevents a generated clip's incidental audio from shifting
the chapter timeline.

Every generated motion clip receives a source/provider fingerprint. A previous
clip is resumed only when that fingerprint still matches and its recorded QA
status passed. New clips are checked for a valid silent video stream, black
frames, frozen motion, and sampled-frame semantic relevance. The router tries
up to three deterministic seeds and records every accepted clip's QA evidence
in `clip_manifest.json`; exhausting those attempts stops the pipeline rather
than publishing the wrong visual.

Recurring characters are discovered from structured scene entities or repeated
proper names in the current chapter. Their ModelsLab reference images live under
that chapter's own `assets/characters` directory and carry a source fingerprint.
The router sends all relevant references to `h3-minimax-r2v`; changed source
descriptions invalidate the references. The production path never loads the
legacy EVS/English/Maths subject registry or a different chapter's character
bible.

Async ModelsLab submissions also write an adjacent
`<clip>.modelslab-job.json` receipt before polling. The receipt contains the
request ID, safe request fingerprint, endpoint family, timestamps, and output
path, but never the API key. A restarted process resumes the matching provider
request instead of buying a duplicate generation. Changed content fails closed
until the older recoverable request is reconciled.

Source-linked exercise presentation supports matching, diagram labels,
grammar-token correction, table-cell answer reveal, and worked-mathematics
steps. Every answer or correction reveal is bound to an exact spoken cue in the
authoritative word timeline. Dense or unreviewed layouts fail before HTML is
authored rather than shrinking into unreadable cards.

Backlot derives stage progress and ETA from checkpoint start times, configured
stage estimates, and item throughput when partial scene/item progress exists.
Completed projects report 100% and zero remaining ETA. ETA is an observed
estimate, not a promised completion time.

After encoding, run `tools.analysis.encoded_educational_comparison` with the
candidate MP4, source PDF/audit, production-data JSON, and reference lock. It
checks the encoded container, source-topic evidence, caption punctuation and
word timing, reference hashes/specifications, and writes a sampled contact
sheet. Pixel-level semantic/aesthetic review remains a human or VLM gate.

## What remains probabilistic

The orchestration is deterministic, but generative media is not. A successful
API response does not prove that a generated child, animal, object, place, or
action matches the spoken cue. Automated semantic sampling reduces this risk
and blocks/regenerates obvious mismatches, but it cannot guarantee pedagogical
judgment or perfect character continuity. The final encoded-video audit remains
mandatory before publication; it is an approval gate, not a manual editing
requirement for every chapter.
