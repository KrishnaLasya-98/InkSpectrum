# Dynamic Educational Chapter Workflow

Educational chapters are configured with `projects/<project-id>/chapter_config.json`.
The rendering and synchronization code must not contain chapter names, textbook
sentences, animal lists, assessment questions, grade-specific pacing, or provider
choices.

All chapters use the locked `hyperframes-educational-v1` UI contract and the
`source-faithful-book-v1` presentation contract in
`styles/hyperframes-educational-v1.yaml`. Chapter content remains dynamic, but
changing the approved layout system requires an explicit template-version update.

## Required flow

PDF ingestion -> source audit -> educational plan -> approved script -> scene plan
-> asset strategy -> narration -> word alignment -> animated clips -> multimedia
synchronization -> HyperFrames composition -> encoded-output QA.

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
`--chapter-config` so no core-code edit is needed.

## One-command PDF to video

For the standard automated path, provide only the PDF:

```powershell
python -m tools.structure.pdf_to_video_pipeline "D:\path\chapter.pdf"
```

The command infers the chapter metadata, creates the project workspace and
dynamic profile, runs the educational production pipeline, and returns the
final video path. Inference can be overridden with `--grade`, `--chapter`,
`--title`, `--subject`, or `--subject-type` when a source document is ambiguous.

Use `--dry-run` to validate a new PDF without cloud media generation.
