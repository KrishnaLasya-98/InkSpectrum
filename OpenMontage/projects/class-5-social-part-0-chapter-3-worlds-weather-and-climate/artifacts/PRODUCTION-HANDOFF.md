# Chapter 3 production handoff - 2026-10-06

## Actual state, not a completion claim

Class 5 Social Chapter 3 is **not yet an encoded final MP4**.
Source: the original Chapter 3 split PDF. Only pages 1-7, opening through
Word Bank inclusive; assessments beginning on page 8 remain excluded.
All 80 scoped blocks are mapped across 28 narration sections. The ten exact
PDF figure crops are retained. Do not use the incorrect 4th-class footer.

Narration: selected ElevenLabs voice zJrRUu1KEcKH8qdpNaPJ, eleven_v4, speed 0.85.
Timed duration: 548.233958 seconds. `audio-waveform-qa-v1.json` measures all
28 actual heading silence intervals at 2.000 seconds. Captions preserve exact
punctuation and use measured acoustic CTC, not proportional estimates.
Unconstrained CTC transcripts provide additional pronunciation triage, not
human-listening approval. No narration needs to be submitted again.

29 new Wan 2.2 jobs have downloaded successfully in motion-batch-01 through
04. All have actual 81-frame, 16-fps, 5.0625-second output, including jobs
that requested 120 frames. This is a measured provider limitation: do not
assume requested frame counts or declared durations were honored. Do not
resubmit these jobs or silently change provider. Sampled-frame visual review
is available in `motion-review-v1`; whole-clip and encoded QA remain required.

A real sequential local process runs `render_precision.py`, using the existing
isolated Manim environment, at 720p24, no new dependencies. Consult
`precision-render-v2/progress.json` and individual logs for live evidence.
It renders 24 fresh full-section geometry/landscape clips. Do not launch a
second local render while it is active. The earlier precision-v1 attempt was
stopped because -qm defaults to 30 fps and its expected output path was wrong;
keep those incomplete diagnostic artifacts out of the composition.

## Important repairs and checks

- Heading pause must use measured waveform silence, not simply the last CTC
  word boundary. The opening had a 112 ms discrepancy; it is corrected.
- The timed narration checkpoint predates that 112 ms correction. After the
  current media worker ends, rerun `finalize_audio.py` normally to reconcile
  voice/alignment checkpoints, then revalidate and finish render_clips in
  manifest order. This invalidates downstream status, not the preserved files.
- Sea-breeze day/night arrows must be removed as explicitly added groups; a
  stale arrow must not survive into the opposite direction. Dark arrows keep
  the head visible above blue water. Review both day and night frames.
- The Chapter 1 presentation adapter used Chapter 2 IDs for Remember/list
  formatting. Shared source-title and semantic-type handling now work for
  Chapter 3. Word Bank uses the exact structured 12-cell source table, not raw
  Markdown. 37 focused composer/subtitle/frame-budget tests passed.
- Approved UI YAML version 1.0.3, palette and geometry stay unchanged. Current
  implementation fingerprint is
  043693b98a939d5b92f0bcc4c70df358ba22c7735c2de3f042040f563eee871c.
- No old chapter media, loops, frozen end extensions or Ken Burns substitutes.
  Every explanatory section gets full-length authored motion underneath its
  unique paragraph-matched Wan cutaways. Stable objectives, Recall, Remember
  and Word Bank remain readable cream cards.
- The opening uses two unique related moving shots with an unchanged title
  card; no extra title screen is introduced mid-narration.

## Resume in order

1. Inspect the running local process and precision-render-v2 progress. Resume
   that same sequential worker only if it stopped; never start another copy.
2. Reconcile the corrected audio/alignment checkpoints after the worker stops.
   Revalidate actual media durations, motion, cues and provenance; finish the
   render_clips checkpoint with real media evidence, not an empty manifest.
3. `prepare_composition.py --audit-only` checks source and word/heading timing.
   Full mode refuses missing geometry clips and creates the HyperFrames HTML
   with exact cards, all figures and actual cue-based cuts. It sequentially
   normalizes video seekability; no local render may run concurrently.
4. Verify source display coverage, paragraph-by-paragraph visuals, table cells,
   punctuation, heading-only pauses and all scene boundaries. Inspect snapshots
   and lint/validate/layout before one-worker low-memory HyperFrames rendering.
5. Recheck free disk space. Last check: C 11.01 GB, D 183.29 GB. Use D for
   temporary capture, not C. These amounts are snapshots, not guarantees.
6. Encoded QA must include source/reference comparison, audio correlation,
   titles, word highlight timing, black/frozen intervals, transitions and
   ending. Do not mark the chapter complete before this evidence exists.
7. Move the verified final MP4, keeping only one canonical final file, to
   `D:/InkSpectrum/OpenMontage/final-videos/Class-5-Social/Class-5-Social-Chapter-03-Worlds-Weather-and-Climate.mp4`.
   Update collection production plan and final index only after encoded QA.
   Do not start Chapter 4 in parallel or resume the paused follow-up automation.

The foreground agent is not a 24/7 background daemon. Only the explicitly
launched local media worker continues after the turn. It stops on failure;
it does not automatically approve or deliver an unreviewed video.

## Cloud queue safeguards added 2026-10-06

The shared motion submitter now admits up to 15 asynchronous ModelsLab jobs,
with an account lock, pre-HTTP reservations and conservative 18/30-minute and
35/hour submission windows. `educational_motion_worker` recovers then fills
approved batches. The current four Chapter 3 batches were checked with this
worker: all 29 existing clips were retained, zero new submissions, status
`media_downloaded_qa_pending`. No cloud worker remains necessary for these
already completed batches. The existing precision worker is unchanged.

The persistent generic chapter worker now refuses advancement past failed or
attention jobs and validates final MP4 hash + encoded QA evidence before
accepting live completion. 42 focused tests pass. Do not confuse these new
guards with a running fully unattended Chapter 3-to-13 operator or with a
future chat notification mechanism. See `docs/MODELSLAB_PARALLEL_CHAPTER_WORKER.md`.
