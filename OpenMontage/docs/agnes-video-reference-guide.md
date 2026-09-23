# Agnes video reference guide

OpenMontage supports two Agnes API contracts:

- `agnes-video-v2.0`: text, image, and keyframe generation using explicit dimensions and frame counts.
- `agnes-video-2.5-flash`: text, keyframe, and reference generation at `720P`, with 4-12 second clips and 16:9 output normalized to 1280x704.
- `agnes-video-2.5`: the non-Flash route can additionally accept reference video inputs when the account is entitled.

For `agnes-video-2.5-flash` reference generation:

- Use at most five public reference-image URLs.
- Use at most three public reference-audio URLs.
- Do not send reference videos.
- Refer to inputs in the prompt as `<Picture 1>` and `<Audio 1>`.
- Poll `/agnesapi` with both `video_id` and `model_name`.

Reference generation is intended for future character and art-style continuity. It is optional for EVS Lesson 8 because the approved batch uses independent animal subjects rather than one recurring protagonist.

Source contract supplied by the user on 2026-09-18. Re-check `https://wiki.agnes-ai.com/llms.txt` before future production because model access and promotional pricing may change.
