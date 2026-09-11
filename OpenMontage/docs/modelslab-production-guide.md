# ModelLab End-to-End Multimedia Production Guide

> Canonical technical reference for producing image, video, and audio assets with the
> ModelsLab API, from initial concept to final delivery. This guide governs every
> ModelLab-backed production in this repository, including the EVS Lesson 8 /
> Animal Life educational video (`projects/evs-lesson-8`).
>
> Companion documents:
> - `docs/image-video-prompt-engineering.md` — generic prompt layer framework
> - `docs/modelslab-production-model-selection.md` — evidence-based model choices
> - `docs/modelslab-model-inventory.md` — model catalog inventory
> - `.agents/skills/modelslab-{video,image,audio,model}-generation/SKILL.md` — API skill sheets
> - `schemas/artifacts/*.schema.json` — artifact contracts

---

## 1. Production Doctrine (read first)

Every model the production uses — video generator, image generator, or audio
generator — is a *stage in a pipeline*, not a final output. Production quality is
decided by the reviewer, not by the generator.

**Doctrine 1 — The prompt is only one control surface.**
Record the model ID, endpoint version, all parameters, seed, duration, resolution,
and the generation timestamp with every asset. See the `asset_manifest` schema.

**Doctrine 2 — All text enters in composition, never in generated imagery.**
Educational labels, titles, definitions, questions, and answer reveals are added
during composition (typography overlays). Prompts must never request embedded text
and must never contain a chapter title prefix that the model could render as a
watermark or hallucinated logo.

**Doctrine 3 — Animation-first, linear motion only.**
A video asset must contain continuous, linear subject or environmental motion.
Looping videos, replays, cyclical patterns, artificial scaling, and camera-only
moves (zoom in/out, Ken Burns, pan/tilt/dolly over a still) are prohibited as the
primary motion treatment. Section 4 of this guide defines that contract exactly.

**Doctrine 4 — One narrator, source-faithful script.**
Spoken narration stays close to the source text. Interaction and engagement come
from direct address, response pauses, and animated demonstrations — not from
commentary invented by the scriptwriter. Section 6 defines the narration contract.

**Doctrine 5 — Nothing ships without an artifact trail.**
Every stage writes a schema-valid artifact: `extracted_content`, `educational_plan`,
`scene_plan`, `asset_manifest`, `narration_manifest`, `render_report`,
`final_review`, `publish_log`, and `cost_log`. Validation and parity checks run
before each downstream stage consumes an artifact.

---

## 2. ModelLab API Foundation

### 2.1 Authentication

All ModelLab requests send the API key in the JSON body as `key`.

```python
import os
import requests

API_KEY = os.environ.get("MODELSLAB_API_KEY")  # never hard-code; load from .env
```

In this repository the key lives in `.env` and must be loaded with `python-dotenv`
(or the repo launcher) before any tool runs. Key names that matter:

| Purpose | Environment variable | ModelLab feature |
|---|---|---|
| Video / image / audio generation | `MODELSLAB_API_KEY` | all |
| Video fallback (native Hailuo route) | `MINIMAX_API_KEY` | video-fusion |
| Narration (premium route) | `ELEVENLABS_API_KEY` | audio_gen |
| Album/music route | `SUNO_API_KEY` | audio_gen |

### 2.2 Endpoint families

ModelLab exposes two stable API generations:

| Version | Endpoint roots | Notes |
|---|---|---|
| v6 | `/api/v6/video/text2video`, `/api/v6/video/img2video`, `/api/v6/voice/text_to_speech`, `/api/v6/images/text2img`, ... | Legacy but supported; required by h3-minimax and wan2.2 model families |
| v7 | `/api/v7/video-fusion/{op}`, `/api/v7/voice/{op}`, `/api/v7/images/{op}` | Current; parameter names changed (e.g. `text` -> `prompt`, `audio` -> `init_audio`) |

Generic rule used by `tools/video/modelslab_video.py`:

- `h3-minimax-t2v`, `h3-minimax-start-end-frame`, `h3-minimax-r2v` -> **v6** with strict
  `duration` (string, 5-15) and optional `resolution` (`"768P"` only).
- All other models -> **v7 video-fusion**.

### 2.3 Async submission and polling

Generation is asynchronous. Submit, read `id`, poll `fetch` until `success`,
`failed`, or timeout. The repository implements this in
`tools/video/_modelslab_shared.py` (`submit_modelslab`, `poll_modelslab`,
`download_modelslab_output`) — reuse those helpers instead of reimplementing.
### 2.4 Model discovery

```bash
# CLI (modelslab SDK)
modelslab models search --feature video_fusion --search "wan"
modelslab models detail --id wan2.2

# Per-model llm.txt contract doc (ground truth for params)
# https://modelslab.com/models/{provider}/{model_id}/llms.txt
```

Always verify parameter names, ranges, and required fields against the live
`llms.txt` for the exact model before writing a production call. Model names are
not documentation; the llms.txt contract is.

### 2.5 Cost controls

- Pre-estimate with `estimate_modelslab_cost(model_id, duration)` in
  `tools/video/_modelslab_shared.py` (per-second rates by family).
- Budget per generation batch before launch; abort the batch if the running total
  exceeds the approved budget.
- Record actual `cost_usd` per asset in the `asset_manifest`.

---

## 3. Image Generation Playbook

Use images for: reference keyframes for image-to-video, diagram/background
surfaces, character or object identity anchors, and the pre-animation "image
finishing" step. Images are never final output for an animated project — they
become inputs to video or composition surfaces.

### 3.1 Endpoints

| Operation | v7 endpoint | v6 endpoint |
|---|---|---|
| Text to image | `POST /api/v7/images/text-to-image` | `/api/v6/images/text2img` |
| Image to image | `POST /api/v7/images/image-to-image` | `/api/v6/images/img2img` |
| Inpainting | `POST /api/v7/images/inpaint` | — |
| Fetch result | `POST /api/v7/images/fetch/{id}` | `/api/v6/images/fetch/{id}` |

### 3.2 Minimum viable request

```python
payload = {
    "model_id": "flux",                 # or sdxl, imagen-3, midjourney, community models
    "prompt": "<layered prompt>",
    "negative_prompt": "blurry, low quality, distorted, text, watermark",
    "width": 1024,
    "height": 1024,
    "samples": 1,
    "guidance_scale": 7.5,
    "seed": 48192,                       # set for reproducibility
}
```

### 3.3 Prompt layer structure

Use four layers, never one adjective pile:

```text
[content] + [composition] + [light and atmosphere] + [style and finish]
```

Example (identity anchor first, reused verbatim across future shots):

```text
one red fox, full body, alert posture, thick winter coat, white chest, dark lower legs
| subject in the right third of frame, facing left toward the center,
  foreground wet grass, midground moss-covered log, background dark spruce forest
| soft overcast daylight, gentle rim light, quiet mood
| natural-history illustration, clean vector-style finish, child-safe, no text, no watermark
```

Rules:
- Concrete nouns, visible attributes, countable objects. No `beautiful amazing stunning`.
- Reserve negative space for later composition typography.
- Keep the same 3-6 identity attributes verbatim in every shot of the same subject.
- Do not write any in-image text into the prompt.

### 3.4 Image QA gate

Reject an image if any of these hold and regenerate (new seed, then fix the prompt):
- unwanted text, watermarks, or logos baked in
- wrong anatomy (six legs on a dog, wing on a fish)
- clashing style against the established identity anchor
- busy background that fights composition overlays
- resolution below the canvas needed for the scene's use

Approve an image before it is promoted to an image-to-video keyframe. Record
`type: image`, `model`, `seed`, `provider`, and the exact `prompt` in the
`asset_manifest`.

---

## 4. Video Generation Playbook — Motion Dynamics and Camera Constraints

This section is the **mandatory binding contract** for all video assets in the
repository. It enforces two rules on every generated clip.

### 4.1 Motion Dynamics (mandatory)

1. **Continuous and linear.** Every clip is one continuous forward temporal
   progression. There must be no reset of the subject to a starting pose, no
   rewind, and no cut-back that re-establishes frame one inside the clip.
2. **No looping.** A usable loop is a clip whose last frame can be stitched to its
   first frame to make a cycle. Looping is prohibited — the end of every clip must
   be in a visibly different state from its first frame.
3. **No replays.** The same motion event shown twice inside one clip
   (e.g. the same fish trajectory twice) is prohibited. Each action occurs exactly
   once per clip.
4. **No cyclical patterns.** No repeating gestures, bouncing on a pivot, wing
   flapping at a fixed recurrence, back-and-forth pendulum motion. One hop, one
   turn, one wing-open, one step per scene. After the action, the subject *dwells*
   with continuous micro-motion (breathing, ripple, grass sway, ear twitch) rather
   than re-triggering the action.
5. **Fluid, non-repetitive motion.** Motion is continuous and interpolated. No
   stutter, no double-imaged frames, no pose teleporting, no strobing.
6. **No artificial scaling or cyclical transformation.** An object must never
   appear to scale up/down unless the real contour of a subject changed for a
   documented reason, and never to simulate a zoom. No expansion-contraction
   cycles that simulate breathing only at one rate.

**Negative-prompt terms that must always accompany video generation:**

```text
loop, looping, seamless loop, replay, repeat, cycle, cyclical, restart, rewind,
back and forth, oscillation, pendulum, bounce in place, zoom in, zoom out,
push in, pull out, Ken Burns, pan, dolly, camera move
```

### 4.2 Camera Constraints (mandatory)

1. **No zooming in or out.** Focal length is fixed for the entire clip.
2. **No Ken Burns effects.** The slow push-in or pull-out of a still image is
   prohibited. Camera movement may never be the *only* motion in a shot.
3. **No camera move over a still image.** Pan, tilt, dolly, and track moves are
   only acceptable as an incidental framing aid while at least one subject or
   environment element performs continuous, linear animation. A rendered static
   image moved by the camera is classified not as animation and is rejected.
4. **No framing-driven artificial scaleup.** The occurrence of a subject seeming
   bigger (scale-up) as the camera approaches, or smaller after a push-out, is
   prohibited. Cameras stay fixed and constant-zoom, subjects move.
5. **Default mode = fixed camera + moving subject/environment.**

**Positive physics to prompt instead of camera movement:**

| Instead of writing | Write this |
|---|---|
| `zoom in on the fox` | `the fox turns its head and takes one step forward; whiskers and fur react` |
| `slow push-in on the nest` | `the bird lowers a twig onto the nest, then settles with a visible breath` |
| `pan across the pond` | `the fish glides from the left reeds to the right edge, continuous fin motion` |
| `Ken Burns forest` | `the tiger's shoulder shifts and it advances one stride; grass bends under its paw` |

### 4.3 Endpoints and operation matrix

| Operation | Representative models | Endpoint |
|---|---|---|
| Text to video | `wan2.2`, `h3-minimax-t2v`, `seedance-t2v`, `Hailuo-2.3-t2v` | v6 `/api/v6/video/text2video`; v7 `/api/v7/video-fusion/text-to-video` |
| Image to video | `h3-minimax-r2v`, `ltx-2-3-pro-i2v`, `seedance-i2v` | v6 `/api/v6/video/img2video`; v7 `/api/v7/video-fusion/image-to-video` |
| Video to video | `wan2.1`, `kling-v2-1-v2v` | v7 `/api/v7/video-fusion/video-to-video` |
| Lip sync | `lipsync-2` | v7 `/api/v7/video-fusion/lip-sync` |
| Fetch result | — | v6 `/api/v6/video/fetch/{id}`; v7 `/api/v7/video-fusion/fetch/{id}` |

### 4.4 Text-to-video request template

```python
payload = {
    "model_id": "h3-minimax-t2v",
    "prompt": (
        "A fish glides continuously once from the left reeds to the right side "
        "of the pond, tail waving rhythmically, water rippling softly, "
        "one linear educational shot, fixed camera, accurate fish anatomy, "
        "child-safe illustrated style, calm natural water motion, "
        "no text, no watermark, no zoom, no pan"
    ),
    "negative_prompt": (
        "loop, looping, seamless loop, replay, repeat, restart, cycle, cyclical, "
        "oscillation, bounce, back and forth, zoom in, zoom out, push in, pull out, "
        "Ken Burns, pan, dolly, camera movement, static image, text, watermark, "
        "distorted anatomy, stutter, frame jump, double image"
    ),
    "duration": "5",          # string; v6 h3-minimax requires 5-15
    "resolution": "768P",     # v6 h3-minimax only
    "seed": 20240910,
    "output_path": "projects/evs-lesson-8/assets/video/s01/s01-fish.mp4",
}
```

### 4.5 Video QA gate (every clip, before timeline entry)

Run `ffprobe` (`probe_output` in `tools/video/_shared.py`) and inspect sample
frames before accepting any clip:

1. **Linear motion** — one subject/environment action advancing forward once.
2. **No loop seam** — first frame and last frame differ; last frame does not
   return to the first pose.
3. **No camera move** — background geometry stays in fixed perspective; no scale
   drift of static elements.
4. **No repeated gesture** — each action occurs once; the remainder is held
   micro-motion.
5. **Anatomy stable** — correct limb counts and proportions in every sampled frame.
6. **No baked text** — no captions, labels, or watermarks burned into frames.
7. **Duration/resolution match** — probe equals the scene contract (e.g. 5.0s @ 768P).
8. **Slideshow risk < 0.6** — the clip reads as a living scene, not a dressed still.

Failures of 1-3 or 5 are hard rejections: regenerate with a new seed; if two
regenerations fail, re-write the prompt using the table in 4.2 and check the model
contract in `llms.txt`. Log accept/reject and the final prompt in
`asset_manifest.json` per asset (`generation_summary`, `model`, `seed`,
`cost_usd`, `provider`).

### 4.6 Scene plan and manifest integration

- Every clip is planned in `scene_plan.json` (scene id, type, start/end seconds,
  `shot_language`, `movement`, `required_assets`) before generation.
- Every accepted clip is recorded in `asset_manifest.json` tied to its
  `scene_id`, with the exact prompt used for generation.
- The `educational_plan.metadata` values (animation-first policy, text in
  composition, one narrator, approval gate) are authoritative for the EVS series;
  this video section is the how-to for that policy.

---

## 5. Audio Generation Playbook (narration, music, sound effects)

Audio is produced as three separate production layers — narration, bed, and SFX —
and mixed in composition (see Section 8). The EVS series narration pipeline lives
in `tools/voice/voice_synthesis_pipeline.py` and records its outputs in
`narration_manifest.json`.

### 5.1 Text to speech (narration)

| Engine route | Model | Use when |
|---|---|---|
| Edge TTS (repository preference) | `en-US-EmmaNeural` / `en-US-AvaNeural` | zero-cost child-friendly narration; used for EVS Lesson 8 |
| ModelLab v7 voice | `eleven_multilingual_v2` with a chosen ElevenLabs `voice_id` | premium voice quality, voice cloning |
| ModelLab v6 voice | `text-to-speech` model, voice list endpoint | repository fallback chain |

```python
# ModelLab v7 TTS
payload = {
    "model_id": "eleven_multilingual_v2",
    "prompt": "Hello students! In today's chapter, we are going to learn all about animals.",
    "voice_id": "21m00Tcm4TlvDq8ikWAM",
}
# POST https://modelslab.com/api/v7/voice/text-to-speech   (then poll fetch/{id})
```

Repository local route (free, offline-capable):

```python
import asyncio
import edge_tts

async def synth(text: str, out: str, voice: str = "en-US-EmmaNeural") -> None:
    await edge_tts.Communicate(text, voice=voice).save(out)

asyncio.run(synth("Hello students! We will explore Animal Life.", "s01.mp3"))
```

Policies:
- **One voice per video.** The same voice name is used for all sixteen EVS sections.
- **Pauses.** Delivery cues from the script (`pause_before_seconds`,
  `pause_after_seconds`) are applied as section gaps in composition, not stretched
  into TTS audio. Leave 1-2s response pauses after direct-address questions.
- **Normalize to -14 LUFS** (ITU-R BS.1770-4) via `ffmpeg loudnorm` at mix time:
  `ffmpeg -i in.wav -af loudnorm=I=-14:TP=-1.5:LRA=11 out.wav`.
- **Verify.** Run speech-to-text on the produced audio and diff against the
  approved `provider_text`. Mismatches in vocabulary, number words ("six"), or
  names ("parrot") force a regeneration of that section only.

### 5.2 Music bed

| Route | Model / command | Notes |
|---|---|---|
| ModelLab v7 | `music_v1` via `/api/v7/voice/music-gen` | 30-480s, ideal ambient bed, use `init_audio` for continuation |
| Local | `ffmpeg sine` or generated pad | last-resort ambience only |
| Stock | licensed BGMs referenced in `asset_manifest` | prefer when available |

The bed ships in the mix as a **sidechained ducked track**: full bed level during
transitions, ducked whenever narration is present. Target integrated loudness of
the mixed master remains -14 LUFS.

### 5.3 Sound effects (SFX)

| Route | Model / command | Notes |
|---|---|---|
| ModelLab v7 | `eleven_sound_effect` via `/api/v7/voice/sound-generation` | water, bird, soft ambient, animal sounds |
| Local | `ffmpeg` synthesized tones/noise | folley for transitions only |

SFX cues are placed at precise timestamps in composition (e.g. the moment a fish
"glides", a bird "lands", a page "turns"). SFX never plays over narration
segments; they are ducked with the bed.

### 5.4 Audio QA gate

1. **Narration present and intelligible** — speech-to-text word accuracy >= 0.95.
2. **Correct speaker** — the same voice for the full video; no accidental switches.
3. **No sibilant clipping / blown-out** — peak probes below 0 dBFS.
4. **Bed ducked during narration** — measured narration-to-bed ratio
   (`loudnorm` spot-check at a narration timestamp and at a transition timestamp).
5. **Sync within 100 ms** — see Section 7.3.
6. **Duration matches plan** — total narration fits the plan within 5%; each
   section's audio fits its `start_seconds`..`end_seconds` window.

---

## 6. Scriptwriting and Narration Protocols

These protocols govern how the spoken track is authored, checked, and shipped.
They are what make an educational video both engaging ("documentary-to-video"
direct address) and defensible (textbook-faithful).

### 6.1 Interactive scripting — "documentary-to-video" narration

Write the narration the way a documentary narrator talks to a viewer who can
answer back: engage, invite, then instruct.

1. **Direct address.** Open every video by addressing the student by name-style
   address and state the chapter topic in one line:
   `Hello students! In today's chapter, we are going to learn all about animals.`
2. **Rhetorical invitation with a real pause.** Ask the learner to answer before
   the content is explained. The pause is a planned gap in the timeline (2
   seconds after the question, before the reveal):
   `Do you have any pet animals?` -> 2s pause -> `Today we will explore Animal Life.`
3. **One idea per sentence.** Every sentence advances exactly one concept. Short
   sentences win for young and ESL audiences.
4. **Source-faithful bodies.** Facts, definitions, lists, and assessments are read
   straight from the textbook with minimal adaptation (only joining/ending fixes).
   Avoid inserted commentary such as "Isn't that wonderful?" or invented facts.
5. **Narration is not the visuals.** Swimming, hopping, flapping, and building are
   visual demonstrations. If the textbook does not state the action in words, the
   script must not narrate it — the animation shows it instead. Engagement comes
   from the animation, not from describing what is on screen.
6. **End with a calm, actionable close** (protect, draw, remember) rather than an
   outro chatter line.

### 6.2 Source-faithful QC cross-checking workflow (before any asset generation)

Every script line is verified against the source artifact before TTS or video
generation begins. Run this triple check on every revision:

**Step 1 — Section-by-section source diff.**
For each section, compare the spoken text against the extracted source passage.
Record each diff; accept only join-edits, never meaning changes. Reject invented
"teaching commentary" not present in the source.

**Step 2 — Artifact parity.**
`script.json.sections[].text` and `educational_plan.json.sections[].narration_script`
must be character-for-character identical for every section id (the parity check
`{s['id']: s['text']} == {p['section_id']: p['narration_script']}`). Any drift is
corrected in the script before proceeding.

**Step 3 — Contract validation.**
Run `schemas/artifacts` `validate_artifact` on `script` and `educational_plan`;
assert times are contiguous, total duration matches, and the approved opening
("Hello students!...") is present.

**Step 4 — Reading-style verification.**
A reviewer must read the narration aloud against the scene plan to confirm that
each spoken phrase maps to a visual cue that exists in the scene plan, and that
no speaking survives a visual gap.

Only a passing Steps 1-4 allows the `educational_plan.metadata.approval` to flip
from `awaiting_human` to `approved` (the required gate before asset generation).

### 6.3 Narration delivery contract

- One consistent narrator voice for the entire video (`voice_name` and
  characteristics recorded once in `narration_manifest.json`).
- `pause_before_seconds` and `pause_after_seconds` from script delivery cues are
  honored by the composition timeline, not stretched TTS audio.
- Emphasis is applied per-cue (`emphasis_words`) without changing readability.
- Provider settings are captured in the manifest per segment
  (`delivery_cues_applied`, `provider_text_used`).
- All narration is speech-to-text verified for correct word accuracy (see 5.1).

### 6.4 Timing ledger (before video layout)

Write each chapter section's time line from the script in a flat table that
records the absolute offsets the final video must hit:

| Section | start_s | end_s | audio_dur | pause_after | label |
|---|---|---|---|---|---|
| s01 | 0.0 | 30.0 | tts-s01 | 2.0 | opening |
| ... | ... | ... | ... | ... | ... |
| s16 | 460 | 480 | tts-s16 | 1.0 | close |

This ledger is used by the composer (Section 8) to place narration and is the
definition of "in sync" during final QA.

---

## 7. Synchronization — Narration Placed on the Visual Timeline

Synchronization is defined as narration audio starting at an exact absolute
timestamp that lands on the scene designed for it, staying within 100 ms of the
script's section boundaries.

### 7.1 The load map

The composition plan (from `scene_plan.json` + the timing ledger in 6.4) decides
where each narration segment begins. For each section the composer stores:

```yaml
section_id: s03
scene_id: s03-water-land
start_seconds: 60.0      # absolute
audio: narration/s03.wav
audio_lead: 0.30         # narration starts slightly after scene visual start
visual_marker: 63.5      # moment the "Water Animals" label appears
pause_after: 2.0         # response pause before reveal
```

### 7.2 Placement and trimming

1. Every narration clip is trimmed so its audible start lands at
   `scene_start + audio_lead`.
2. Use `ffmpeg -ss`/`-t` on the narration only when trimming, never downmixing;
   duration glitches must be checked with `ffprobe` after every trim.
3. The response pause for a question (e.g. the 2s pause after `...pet animals?`)
   is added as silence in the mix between that audio file and the next reveal,
   not by stretching the narration.
4. Music and SFX receive the same absolute placement so they land on their visual
   markers (a bird landing, a page turning) with the same 100 ms tolerance.

### 7.3 AV sync verification

At composition time run:

- `ffprobe` format duration, stream durations, av_offset on the final file
  (`ffmpeg -i final.mp4` and `-show_streams` for `start_time` of a/v).
- A 4-point sample check at `t=0.1, 0.5, 0.9` and a mid-clip index: extract a
  frame and play 100 ms of audio at the same time; lips/action must correspond to
  the narration word.
- `-vsync` and `-af aresample=async=1` used to absorb sub-frame drift.
- The `final_review.checks.audio_spotcheck` flags any unexplained silence,
  clipping, or drift before the output may be presented.

A drift of more than 100 ms at any sampled point forces a revise of the
composition with re-spliced narration placement.

---

## 8. End-to-End Production Workflow

The complete delivery chain for a documentary-style chapter, matching the
`educational-video` pipeline (`pipeline_defs/educational-video.yaml`):

### Stage 0 — Input ingestion
Extract the source chapter (PDF/markdown) to `extracted_content.json`; validate
schema; confirm >= 90% page coverage. Source file for EVS: the textbook text
`RPS - EVS - CLASS 1 - ...pages-2.md`.

### Stage 1 — Content structuring
Build `educational_plan.json` + `script.json` from the extracted source using the
interactive-scripting protocol (6.1). Learn objectives, narration scripts for 100%
of the duration, glossary, assessments, activity, life skills. **Requires human
approval** (`metadata.approval.status=approved`) before assets.

### Stage 2 — Scene plan & assets
`scene_plan.json` — every narration beat mapped to a scene with 6x6 grid position,
animation movement, overlays, required assets, prompt references.
`asset_manifest.json` — one entry per generated/sourced asset (path, model,
prompt, seed, provider, license, cost, quality score).

### Stage 3 — Voice synthesis
`narration_manifest.json` — all sections, one voice, cues applied, loudness
normalized to -14 LUFS, speech-to-text verified (scripting protocol 6.2-6.4).

### Stage 4 — Animation (video generation)
Generate every section clip via Section 4 (Motion Dynamics + Camera Constraints),
run the video QA gate 4.5, record in asset manifest. Pilot approve representative
examples before batch.

### Stage 5 — Composition
Combine scenes, narration, subtitles, chapter labels, assessment answer reveals,
music, SFX, transitions using Section 7 sync rules. Music ducked during
narration. Target `final_render.mp4` 1920x1080@30 H.264/AAC.

### Stage 6 — Quality assurance
Run the QA gates in 4.5, 5.4, and 7.3 (technical probe, visual spotcheck, audio
spotcheck, promise preservation, subtitle check, transcript comparison), then
write `final_review.json` (status pass) and optionally `publish_log.json`.

### Stage 7 — Publish package
`final_render.mp4`, `script.json`, `educational_plan.json`, `scene_plan.json`,
`asset_manifest.json`, `narration_manifest.json`, `render_report.json`,
`final_review.json`, `publish_log.json`, thumbnail, and metadata.

---

## 9. Production-Ready Checklist

- [ ] `educational_plan` and `script` validated; narration parity exact (6.2)
- [ ] narration approved; human gate satisfied before asset spend (6.2/8 S1)
- [ ] scene plan covers all sections, no timeline gaps (8 S2)
- [ ] asset manifest complete with prompts, models, seeds, costs (8 S2)
- [ ] all video clips pass Motion Dynamics + Camera Constraints (4.5)
- [ ] no baked-in text or title in any generated frame (Doctrine 2)
- [ ] one narration voice; -14 LUFS; speech-to-text verified (5.1)
- [ ] synchronization within 100 ms at all scene boundaries (7.3)
- [ ] total duration matches plan; no missing sections (8 S4/S5)
- [ ] final QA passes technical, visual, audio, subtitle checks (8 S6)
- [ ] publish bundle contains all artifacts and thumbnail (8 S7)