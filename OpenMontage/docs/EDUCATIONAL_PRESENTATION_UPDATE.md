# Shared presentation update — 2026-09-29

Implemented in the shared HyperFrames composer:

- Dark translucent opening card, subject/class metadata and optional source
  chapter-number badge. Opening footage starts while the title is spoken.
- Source-linked questions/topics are mandatory for We Learn/highlights scenes.
  No fallback to generic learning objectives. New chapter configurations no
  longer mandate those two opening cards for every PDF.
- Incoming topic text enters at the section narration boundary, not during
  the previous section. Context uses current_source_idea/source_text fields.
- Existing measured word captions and title-only hold masks remain in use.

Upstream plans must provide actual source_questions/source_topics and source
block IDs. Missing source content fails rather than inventing copy. PDF-text
accuracy still depends on the coverage/teaching contract; IDs alone do not prove
semantic fidelity. Multi-sentence narration needs corresponding granular scene
sections for per-sentence context changes.

Template package fingerprint has changed. Historical chapter configurations
retain their old lock intentionally and must be explicitly migrated/reviewed
before re-rendering; existing MP4s are untouched.

Validation: 21 combined startup/composer tests passed; after the final opening
timing adjustment, all 8 composer tests passed again. HyperFrames inspection of
the final sample at 0.8, 3, 6, 14 and 22 seconds reported 0 errors/0 warnings.
Five informational occlusion notices at 3s are the intentional title-only mask.

The diagnostic sample uses FFmpeg test patterns and quiet tones, not narration
or textbook media. Its synthetic caption timings cannot validate speech timing,
voice quality, 0.85x delivery, exercise answers, or end-to-end PDF fidelity.
Those require a real narrated source-grounded production sample.

Encoded smoke verification: `tmp/presentation-smoke-v2-20260929/presentation-check.mp4`
rendered successfully in 73.1 seconds in the new Conda environment with pinned
HyperFrames 0.8.82, one worker and streaming screenshot capture. ffprobe reports
24.000 seconds, 1920x1080, 30fps, H.264/AAC, 48kHz audio. Encoded screenshots at
0.8/3/14/22 seconds confirm the opening/badge, title-only hold, learning box and
corner context panel. This is not exact aesthetic parity: current shared font
choices remain Candara/Cambria (with OS fallbacks), unlike the rounded reference.
Cross-platform embedded fonts and a narrated Q&A sample remain to be verified.
