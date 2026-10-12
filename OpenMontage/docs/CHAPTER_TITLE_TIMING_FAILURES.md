# Title and subtitle timing: failures and prevention

This record applies to educational chapter videos. The Class 5 Social Studies Chapter 2 revision exposed these failures; the approved visual reference remains the Class 5 Chapter 1 / English / EVS HyperFrames scene style.

## What went wrong

1. **Duplicate title cards.** A heading was already shown as a corner label over the lesson scene, but the composer added an opaque, full-screen heading mask immediately afterward. This interrupted the visual story, including around 30–31 seconds in a Chapter 2 draft.
2. **Audio cut at an estimated word boundary.** The previous finalizer split generated speech at a speech-recognizer word endpoint, which is not guaranteed to be a quiet edit point. In Chapter 2, one boundary had no nearby silence. The resulting splice could sound like bits of separate recordings.
3. **Too much synthetic silence.** The previous finalizer inserted a full two seconds even where the voice had already paused naturally, and added further silence after many topics. The reported pause and the actual onset of the next spoken word therefore differed.
4. **Speech alignment missed quiet gaps.** In a Chapter 2 candidate, ASR positioned the first body word inside a real 0.8-second pause for Learning Objectives and Revolution. Adding two seconds from that guessed boundary created 2.84-second acoustic gaps and early subtitle highlighting. Detect the acoustic quiet interval in the original waveform, then correct the affected word edges before rebasing captions.
5. **Timing drift across modalities.** Media placements were proportionally scaled from an older audio timeline. A visual could begin before or after the word naming it. `body_start_seconds` was also computed from the splice, not the measured next-word onset.
6. **Empty title pauses.** Hiding the whole teaching panel during a two-second pause produced a tiny corner label on an otherwise empty pale frame. The approved Chapter 2 screenshot instead retains the cream source-content panel and relevant moving visual beneath the corner heading.
7. **Insufficient encoded-output inspection.** A preview or source-coverage pass alone cannot establish that the final MP4 has correct title placement, clean audio joins, or word-level subtitle synchronisation.

## Required contract for every chapter

- Narrate each source-derived title and subtitle exactly once. Keep its label in the established corner/scene layout; do **not** insert a second full-screen title card between the label and the teaching scene.
- After the final spoken heading word, provide **two seconds total before the next spoken content word**. Count natural silence already present in the recording. Do not add two more seconds on top of it.
- During that pause, the heading remains visible in the scene; the compact source-content panel may remain visible, as in the approved screenshot. Keep a relevant visual/diagram in the scene where available, rather than an empty full-frame background. The opening title artwork remains on screen during its post-title pause.
- Find the heading's acoustic end and next-word onset from a quiet interval in the original waveform near the current narration alignment. Insert only the missing silence at the midpoint of that interval, with a very short fade. Correct any ASR word edges that overlap the detected silence. Never cut in the middle of a word or regenerate only a phrase without continuity review.
- Re-align subtitles after any audio edit. Store the measured `heading_duration_seconds`, `body_start_seconds`, and section durations in the narration manifest. Rebuild the multimedia sync plan and scene manifest from these timings, not from an earlier render.
- Place subject visuals at the measured spoken cue. Do not stretch old offsets proportionally or loop/reuse unrelated video to fill a gap.
- Before delivery, inspect the **encoded MP4** at the opening and every heading transition. Check the label, pause length, absence of duplicate masks, teaching-panel reveal, first word highlight, moving visual onset, audio continuity, and ending. Run source-block coverage plus black/frozen-frame and long-silence checks. Preserve the previous delivered render until the replacement passes.

## Chapter 2 evidence and regression gate

- Original Eleven v4 speech is in `projects/class-5-social-part-0-chapter-2-earth-movement/assets/audio/narration-elevenlabs-zJrRUu1KEcKH8qdpNaPJ-v1`.
- The prior output added silence to every heading and most topic ends; its 461.24-second audio was about 51 seconds longer than the 410.24-second unaltered narration.
- The no-extra-card v2 composition removed full-screen masks and passed 56/56 source blocks, but it did **not** include the newly required measured two-second pauses. It is an intermediate diagnostic render, not final delivery.
- The replacement must pass an automated check that every heading-to-body interval is at least 2.00 seconds (within one audio frame), there are zero full-screen heading holds, and the source coverage remains 56/56. Review actual frames on both sides of every section boundary.

For Chapter 2's current replacement timeline, the intended global pause windows (seconds) are: opening 5.25–7.25; Learning Objectives 8.52–10.52; Start-Up Activity 37.45–39.45; spherical Earth 56.74–58.74; two movements 89.98–91.98; rotation 105.27–107.27; Do You Know 156.18–158.18; revolution 170.04–172.04; day length 226.49–228.49; solstice 243.88–245.88; inertia 293.40–295.40; equinox 312.02–314.02; Recall 345.41–347.41; Let's Remember 370.40–372.40; and Word Bank 404.63–406.64. These times are generated from the current manifest and must be recalculated if narration changes.

### Encoded v4 check (2026-10-06)

- Rendered `hyperframes-elevenlabs-title-pause-v4/renders/class5-social-chapter2-earth-movement-title-pause-v4.mp4`: 428.867 seconds, 1920x1080, 30 fps H.264, AAC stereo 48 kHz.
- Encoded-video black detection found no black intervals of 0.15 seconds or longer; audio silence detection found no gap of 2.5 seconds or longer at -38 dB.
- The source-content audit passed 56/56 required blocks, including 56/56 verbatim panel or figure blocks.
- Inspected encoded frames at the opening, 30–31 seconds, Start-Up at 38–40 seconds, Revolution at 170 seconds, and Word Bank at 420 seconds. The 30–31-second duplicate full-screen heading card is absent; Start-Up shows the blue ball, corner heading, source-text panel, and subtitle in one scene.
- The versioned reviewed MP4 is `final-videos/Class-5-Social/Class-5-Social-Chapter-02-Earth-Movement-title-pause-v4.mp4`. The previous delivery was not overwritten.

### User-discovered v4 failures: supersedes any final-quality claim above

The limited checks above did not prove scientific correctness or full semantic
synchronisation. The user identified incorrect rotation/revolution and a mismatch
near 1:21. Do not treat v4 as an approved regression reference for those scenes.

- The old rotation geometry tilted the sphere and then rotated the whole group
  about the world vertical, rather than spinning the surface about its fixed
  tilted polar axis. For revolution, Earth must translate around the Sun without
  turning its axis to follow the orbit. Verify axis direction at multiple frames.
- Sparse short clips left substantial uncovered intervals, including rotation
  near 120 and 150 seconds. Audit the union of visible media intervals, not only
  whether each section has an asset. A static source diagram is a deliberate
  teaching element, not evidence of continuous animated background coverage.
- ASR failed to recognise the Magellan sentence. Interpolated timestamps then
  placed “Ferdinand” at 84.396 s, whereas acoustic CTC alignment places it at
  82.153 s. Never label interpolated timestamps as measured word alignment.
- Section-wide or proportional timing shifts cannot fix this. Re-anchor each
  spoken concept and teaching panel using aligned words in the final waveform.
- New v5 assets, alignment and composition are work in progress. Require encoded
  checks around 81–87 s and throughout rotation/revolution before changing the
  delivery link. Black/silence detection and source coverage are necessary but
  do not establish visual relevance or correct science.
- In v5 preview, fading contextual clips over a persistent globe produced a
  ghost globe inside the sailing ship. Support explicit, word-timed clean cuts
  for these concept changes while retaining the established scene transitions.
- The old 180 ms caption-group gap threshold fragmented CTC-aligned speech into
  isolated words. Use sentence/page boundaries and a 650 ms phrase-gap threshold;
  retain exact word-highlight onsets. Grouping changes must not shift audio.
- Manim and generated-video defaults can have 5–10 second keyframe gaps. Preserve
  the original assets, then create 30fps H.264 presentation copies with a
  one-second GOP and fast-start metadata. Verify complete decoded-frame coverage
  for the render and test seeking separately in the web preview.
