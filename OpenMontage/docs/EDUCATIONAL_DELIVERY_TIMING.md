# Approved delivery timing

User correction, 2026-09-29:

- Keep the approved English, EVS, and Class 1 Maths scripts, structure and visual reference outputs.
- Detailed explanations apply only to Maths problems and worked examples. Do not require expanded explanation narration for English, EVS, GK, or ordinary Maths topic text.
- Narration provider speed: 0.85 (an absolute TTS speed setting, not an additional 0.85 multiplier on previously slowed audio).
- Read each actual title/subtitle, then pause four seconds. During each such pause show only that heading on a cream screen; no body copy, footage, or subtitle lane is visible.
- Two seconds of silence after each topic is the implementation default. Set `topic_end: false` on continuation scenes belonging to the same topic.
- Keep the existing teaching screen during topic-ending silence; hide the subtitle lane.

## Implementation

`content_policy.delivery_timing` controls `narration_speed`, `spoken_heading_pause_seconds`, and `topic_end_pause_seconds`. The active Class 4 Maths project enables these settings. Archived reference MP4s are not modified.

The runner supplies title and optional string `subtitle` as `spoken_headings`. Duplicate exact titles are removed. Voice synthesis generates each heading separately, inserts exact silence, joins the body, and appends topic silence. Measured heading-hold intervals and body onset are recorded in the narration manifest and cached together with the audio settings.

The shared HyperFrames composer uses those intervals for opaque title-only masks and delays the section's visual clip until body narration starts. Spoken headings remain in subtitle alignment text. The final output must be regenerated and reviewed before claiming these settings are present in an MP4.

Verification: 18 focused tests passed, including actual synthetic WAV samples verifying four-second silent intervals, two-second tail silence, cached duration stability, title-only mask timing, delayed video onset, and the Maths-only detailed-explanation rule. This does not replace listening and encoded-video QA on the chapter narration.
