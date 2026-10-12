# Chapter 2 synchronization and scientific-motion repair

## Delivery state

V5 rendered successfully and was delivered on 2026-10-06 to the sole canonical
path `D:/InkSpectrum/OpenMontage/final-videos/Class-5-Social/Class-5-Social-Chapter-02-Earth-Movement.mp4`.
The file was moved, not copied; the project render copy is absent. Two superseded
Chapter 2 deliveries were moved to the Recycle Bin (recoverable). Chapter 1 is
unchanged. Delivery evidence: `delivery-sync-v5.json`; SHA-256:
`1dacdc366c02e14196e0ee3e6fcbde744842c7b4bdaaea7a6b8e77baf7a12f60`.

Encoded QA: technical pass, 1920x1080/30fps, 428.867 seconds, 56/56 source
blocks, 30 audio comparison windows with maximum 2 ms placement difference and
minimum waveform correlation 0.99812. Targeted encoded frames and overview
reviewed; no detected black intervals >=0.15 s or silence >=2.5 s. This is not
exhaustive human playback/listening. Static source/recall/vocabulary cards remain;
an inherited Start-Up background gap at 51.03-54.33 s and three low-confidence
word endings are disclosed in `encoded-sync-v5-qa.json`. User approval is pending.
No render or provider job remains active. Do not regenerate or duplicate output.

## Confirmed findings and completed work

- Old rotation used the world vertical after tilting the globe. The replacement
  rotates only surface markings around the fixed 23.5-degree polar axis.
- Revolution translates Earth along an orbit while preserving axial direction.
  NASA Earth Facts and Space Place Seasons were used to verify the geometry;
  the reviewed textbook remains the source of teaching text.
- The old `Ferdinand` timestamp was 84.396 s. Local acoustic forced alignment
  locates it at 82.153 s, a 2.243 s correction. Rebuild teaching panels and video
  cues from the final audio, not proportional stretching of older timelines.
- `align_ctc_v5.py` completed 861 words across all 15 sections. Exact narration
  text, punctuation, monotonically ordered word intervals, unchanged audio
  hashes and the existing two-second heading-pause metadata pass
  `audit_sync_v5.py`. Three low-confidence word endings are explicitly recorded
  in `artifacts/alignment-ctc-v5/audit-all.json`; this is not human listening QA.
- `build_teaching_pages.py` maps all nine paged sections with no unmatched
  spoken anchors. `test_precision_v5.py` passes all three geometry tests.
- Existing composer/subtitle regression tests: 30 passed. This does not prove
  encoded visual quality.
- The ElevenLabs forced-alignment endpoint returned HTTP 401 once. No retry or
  new narration was submitted. Local Wav2Vec2 CTC alignment uses the approved
  Eleven v4 audio unchanged. Optional dependencies/model-cache provenance are
  recorded in `requirements-alignment-ctc.txt` and `docs/INSTALLATION_GUIDE.md`.

## New contextual footage: resume, do not resubmit

Batch: `assets/video/motion-batch-12-sync-repair.json`.

| Shot | Durable ModelsLab job | Purpose |
| --- | --- | --- |
| voyage-ship-12 | 188613056 | New GPT-reference sailing ship for Magellan's voyage |
| spherical-earth-context-12 | 188613067 | New Wan 2.2 spherical-Earth context |

Both jobs completed and were recovered at 09:42 UTC / 15:12 IST on 2026-10-06.
The evidence is `motion-batch-12-sync-repair-recovery.json`. Five sampled frames
from each clip show coherent ship/ocean or Earth motion; inspect contact sheets
in `artifacts/wan-*-v5-contact.jpg`. No duplicate jobs were submitted.

GPT ship reference: `assets/images/gpt-reference-v1/voyage-ship-v5.png`.
It depicts a generic illustrative period ship, not a claimed reconstruction
of a specific historical vessel. It is only an input to animation.

## Local rendering history and reproducible sequence

`precision_earth_v5.py` rendered all four new chapter-specific 3D clips in the
existing `openmontage-maths-manim` environment, sequentially at 1280x720/24fps.
The render exited 0 at 15:09 IST on 2026-10-06. No Manim render remains active.
Outputs: `assets/video/science-v5/videos/precision_earth_v5/720p24/`.
Check the running process before any new local render. Never launch duplicate
renders. Rotation, revolution and contrast contact frames are in `artifacts/`.
The composition builder initially stopped on missing Wan media. After recovery
it completed the isolated v5 workspace successfully. Source coverage passes
56/56, structural alignment passes 861 words, and video intervals fully cover
spherical Earth, two movements, rotation and revolution. HyperFrames lint has
zero errors (one large-HTML maintainability warning); layout inspection at
81, 82.3, 85, 110, 120, 145, 150, 175, 185, 200 and 210 s reports no overflow.
Encoded output and sampled perceptual checks are now recorded above.
Preview caught a globe ghosting through the incoming ship. The shared composer
now accepts `transition: cut` on a visual segment; v5 uses measured clean cuts
inside scenes. Section transitions and the approved cream layout remain intact.
The caption grouping gap threshold is 650 ms instead of 180 ms, preventing
isolated conjunctions without shifting word highlights. The first render was
intentionally stopped early to include this fix. New media is re-encoded with
one-second GOPs and 30fps for reliable web seeking. The restarted render is the
only local render at that time; it has now finished successfully.

When all four local clips and both Wan clips exist and probe successfully:

1. Inspect moving frames from the new Wan clips for coherence and relevance.
2. Run `build_sync_repair_v5.py` with repository root on `PYTHONPATH`. This
   retains the cream teaching layout and approved audio, re-anchors all clips
   and panels to CTC words, reserves subtitle space in scientific clips, and
   refuses missing/too-short media. It writes an isolated v5 composition.
3. Run `audit_sync_v5.py` and `audit_elevenlabs_coverage.py` with version
   `elevenlabs-sync-repair-v5`, the unchanged title-pause-v4 narration manifest,
   and `hyperframes-elevenlabs-sync-repair-v5/timeline.json`.
4. Lint/inspect HyperFrames, visually verify 81–87 s, 105–155 s, 169–225 s,
   heading pauses and source diagrams. Ensure no source panel covers the
   explanatory objects and no labels occupy the subtitle lane.
5. Only after local asset rendering is finished, render HyperFrames with one
   worker, low-memory mode, D-drive temporary/cache paths and disk checks.
6. Inspect the encoded MP4, including audio/caption onset, concept changes,
   scientific motion, transitions, black/frozen frames and ending. Source
   coverage should remain 56/56. Save evidence; do not treat preview as final.
7. Latest user instruction: keep one final Chapter 2 video only in
   `final-videos/Class-5-Social`. MOVE the verified render to canonical
   `Class-5-Social-Chapter-02-Earth-Movement.mp4`; do not copy it or retain a
   duplicate new render in the project folder. After new-output QA, recycle the
   two superseded Chapter 2 deliveries in that final folder (canonical and
   title-pause-v4), preserving recovery and leaving Chapter 1 untouched. Update
   delivery metadata and report what was recycled. Do not restart another
   chapter or a paused follow-up.

Scientific references:
- https://science.nasa.gov/earth/facts/
- https://spaceplace.nasa.gov/seasons/en/
