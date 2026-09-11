# ModelsLab Production Model Selection

## Evidence Boundary

The workspace does not contain the 64 `llm.txt` files locally. This assessment uses the live ModelsLab `llm.txt` documents that were retrievable for the strongest candidates, plus the supplied 64-name list and the cached catalog. It does **not** treat the earlier name-based architecture guesses as documentation evidence.

The reviewed documentation consistently exposes:

- `model_ready` status
- HTTP POST endpoints
- required and optional parameters with types or ranges
- cURL, Python, and JavaScript examples
- CLI, MCP, agent-skill, and SDK integration references for many models

The reviewed documentation does **not** establish:

- uptime or latency SLA
- rate limits or concurrency limits
- regional availability
- queue guarantees
- measured failure rates
- data retention or privacy guarantees
- account-level plan entitlement

Therefore, the selections below are the best documented integration candidates. Before production launch, OpenMontage must add provider health checks, bounded retries, idempotency, polling timeouts, cost controls, and an account-specific load test.

## Selection Summary

| Pipeline role | Selected model | Documentation evidence | Decision |
|---|---|---|---|
| Canonical text-to-video | `wan2.2` | Open Source Model, `model_ready`, explicit v6 endpoint, model ID, prompt, portrait, negative prompt, FPS and frame-count controls, MP4/MOV output, Python/cURL/JS examples | **Primary for EVS** after adding its v6 adapter route |
| Open-source text-to-video with native scene audio | `h3-minimax-t2v` | Open Source Model, `model_ready`, explicit v6 `/video/text2video` endpoint, required 5-15 second duration, 768 resolution example, Python/cURL/JS examples | **Secondary video candidate** for narrated or ambient shots; benchmark against Wan 2.2 |
| Reference-driven multi-modal video | `h3-minimax-r2v` | Open Source Model, `model_ready`, explicit v6 `/video/img2video` endpoint, image/video/audio reference arrays, 5-15 second duration, prompt references assets by order | **Specialist candidate** for controlled reference scenes; not a default T2V fallback |
| Canonical image-to-video | `ltx-2-3-pro-i2v` | Closed Source Model, `model_ready`, v7 Video Fusion endpoint, required `init_image` and prompt, 6/8/10 second durations, FHD/2K/4K, 25/50 FPS, optional audio | **Primary controlled animation fallback** |
| Fast/open text-to-video | `ltx-2.3` | Open Source Model, `model_ready`, v6 endpoint, 5-12 second duration range, 1:1/16:9/9:16 resolution options, API examples | **Secondary text-to-video path**, pending adapter support |
| Premium text-to-video | `ltx-2-3-pro-t2v` | Closed Source Model, `model_ready`, v7 Video Fusion endpoint, typed prompt/resolution/duration/audio/FPS parameters, API examples | **Optional quality path** where account access and budget justify it |
| Narration | `text-to-speech` | Open Source Model, `model_ready`, v6 voice endpoint, explicit voice list, language list, speed range 0.5-2, Python/cURL/JS examples | **Primary narration service** |
| Narration QA and captions | `speech-to-text` | Open Source Model, `model_ready`, v6 endpoint, WAV/MP3/FLAC/OPUS support, 5 seconds to 1 hour input range, language parameter | **Required QA companion** |
| Music bed | `ai-music-generator` | Open Source Model, `model_ready`, v6 music endpoint, 30-480 second duration, bitrate and WAV/MP3/FLAC output controls | **Optional music layer**; contract requires `init_audio`, so do not make it a hard dependency |
| Resolution finishing | `ultra_resolution` / `ImageUpscaler` | Open Source Model, `model_ready`, v6 super-resolution endpoint, required image and scale 1-4 | **Pre-animation image finishing** |
| Structural conditioning | `qrcode-v8` / ControlNet endpoint | Open Source Model, `model_ready`, v5 ControlNet endpoint, explicit control types, conditioning scale, samples, guidance, inference-step controls | **Conditional utility only**; the retrieved file describes QR/ControlNet rather than a general standalone ControlNet model |
| 3D asset creation from text | `text-to-3d` | Open Source Model, `model_ready`, v6 endpoint, GLB/STL/PLY/OBJ output, resolution and foreground controls | **Optional 3D asset path** |
| 3D asset creation from reference | `image-to-3d` | Open Source Model, `model_ready`, v6 endpoint, required image, GLB/OBJ/STL/PLY outputs | **Optional reference-conditioned 3D path** |

## Recommended Production Set

### Tier 1: Build the EVS Lesson 8 pipeline around these

#### 1. `wan2.2`

The live `llm.txt` documents this as an open-source, `model_ready` video model with the endpoint:

```text
POST https://modelslab.com/api/v6/video/text2video_ultra
```

Its documented contract includes a required prompt and model ID, a portrait toggle, negative prompt, output format, FPS range 16-25, and frame count range 81-120. The documentation includes cURL, Python, JavaScript, CLI, MCP, agent-skill, and SDK integration references.

Why it fits EVS:

- Open-source route is a better cost and governance fit than third-party premium models.
- Explicit negative-prompt and frame controls help reduce malformed animal motion.
- The route was verified in this repository with a real 5-second EVS sample: 832x480 H.264 MP4, 5.06 seconds.
- It is the canonical target for the deprecated Wan Ultra names.

Risk and mitigation:

- The current OpenMontage adapter uses the v7 Video Fusion route for generic models; `wan2.2` requires the documented v6 route. Add a model-specific route and parameter mapping.
- The provider does not document SLA or concurrency. Use a queue, exponential backoff, request IDs, and a circuit breaker.

#### 2. `ltx-2-3-pro-i2v`

The live documentation identifies a `model_ready` closed-source model using:

```text
POST https://modelslab.com/api/v7/video-fusion/image-to-video
```

The contract requires `init_image` and a prompt, supports 1920x1080, 2560x1440, and 3840x2160 output, 6/8/10 second duration, optional generated audio, and 25/50 FPS.

Why it fits EVS:

- Image-to-video begins from a reviewed keyframe, which is safer for factual animal identity, habitat layout, and visual consistency than unconstrained text-to-video.
- The v7 endpoint matches the existing OpenMontage ModelsLab adapter family.
- Explicit resolution, duration, audio, and FPS controls are suitable for predictable scene contracts.
- The prompt contract can require real subject or environmental animation; camera-only zooms and pans are not acceptable as production scene motion.

Risk and mitigation:

- It is closed source and entitlement is not proven by `model_ready`; verify plan access.
- Build a low-resolution smoke profile and a production profile; do not default every scene to 4K.

#### 3. `text-to-speech`

The live documentation identifies an open-source, `model_ready` voice service at:

```text
POST https://modelslab.com/api/v6/voice/text_to_speech
```

It documents voice IDs, language choices including English and Hindi, and speed from 0.5 to 2.

Why it fits EVS:

- The exact narration text remains under pipeline control.
- Language and speed are explicit, supporting child-paced delivery.
- It is an independent audio stage, so visual retries do not regenerate narration.

Risk and mitigation:

- The documentation labels the category `voice cloning`, so confirm the exact voice-generation policy and permitted usage before production.
- Run generated narration through `speech-to-text` and compare the transcript with the approved script.

#### 4. `speech-to-text`

The documented service accepts WAV, MP3, FLAC, and OPUS files from 5 seconds to 1 hour and exposes a language parameter.

Why it fits EVS:

- It provides an automated narration and caption QA gate.
- The input duration range supports both scene-level and full-lesson checks.
- It is a low-risk, deterministic post-generation validation stage compared with adding another generative model.

#### 5. `ultra_resolution` / ImageUpscaler

The documented model ID is `ultra_resolution`, with a v6 super-resolution endpoint and scale range 1-4.

Why it fits EVS:

- Upscaling reviewed keyframes before animation can improve the image-to-video input.
- It has a narrow contract and bounded scale control.
- It should be used as an optional finishing stage, not as a substitute for poor source composition.

### Tier 2: Add after the core pipeline is stable

#### `h3-minimax-t2v`

The live documentation identifies this as an open-source, `model_ready` model using:

```text
POST https://modelslab.com/api/v6/video/text2video
```

It requires a prompt and duration from 5 to 15 seconds, with resolution documented as an optional text field and `768` shown in the example. The documentation also describes natural speech, lip movement, and environmental audio in its example prompt, although that does not establish a guaranteed audio contract.

Why it fits:

- It is a documented open-source alternative to Wan 2.2.
- The 5-15 second range fits short educational scene generation.
- The v6 route is now represented explicitly in the OpenMontage adapter.

Use it for a controlled benchmark, not as an untested batch default. Compare factual visual stability, audio usefulness, latency, failure rate, and cost against `wan2.2`.

#### `h3-minimax-r2v`

The live documentation identifies this as an open-source, `model_ready` reference-to-video model using:

```text
POST https://modelslab.com/api/v6/video/img2video
```

It documents `init_image`, `init_video`, and `init_audio` arrays, with references addressed in the prompt as Image 1, Video 1, and Audio 1. Reference images, videos, and audio are limited to at most 12 files, and audio references cannot be the only input.

Why it fits:

- It can preserve a reviewed animal illustration, storyboard clip, or approved audio cue across a generated sequence.
- The explicit reference ordering is useful for multi-shot continuity.
- The adapter now maps these documented arrays rather than sending the v7 `reference_image_urls` shape.

Use it for continuity-heavy scenes only. It should not replace the simpler Wan or LTX path for every scene because reference preparation and asset hosting add operational complexity.

#### `ltx-2.3`

The open-source `model_ready` documentation exposes the v6 text-to-video route with 5-12 second durations and aspect/resolution choices. It is a good lower-cost or high-throughput alternative, but the current OpenMontage adapter does not yet map its v6 contract. Add it after the Wan route is generalized.

#### `ltx-2-3-pro-t2v`

The v7 text-to-video contract is clear and production-friendly: prompt, 1920x1080/2560x1440/3840x2160 resolution, 6/8/10 seconds, optional audio, and 25/50 FPS. Use it for hero shots only after verifying entitlement and measuring cost, latency, and failure behavior.

#### `ai-music-generator`

The documented endpoint supports 30-480 seconds, 128k/192k/320k bitrate, and WAV/MP3/FLAC. However, `init_audio` is required, making this less suitable as the default background-music generator for a fresh lesson. Keep it optional or provide a seed audio asset.

#### `text-to-3d` and `image-to-3d`

Both are documented as open-source, `model_ready`, v6 endpoints. They have explicit output formats and are useful for optional interactive animal or habitat assets. They should not block a 2D educational video render because mesh topology, materials, scale, and visual QA requirements are not specified in the `llm.txt` files.

## Models Not Selected as Core Dependencies

| Group | Names | Reason for exclusion from the core path |
|---|---|---|
| Deprecated aliases | Wan Text to Video Ultra; Wan Image to Video Ultra | Route to `wan2.2`; targeting aliases creates migration and observability ambiguity. |
| Unverified image generators | Krea-2 turbo; Hidream-O1; Flux Klein 9B; Z Image; Flux.2 Dev; Qwen Text to Image; Flux Text to Image | The corresponding exact `llm.txt` files were not available locally, and several guessed URLs returned 404. Do not claim documented stability or endpoint compatibility until exact model pages are retrieved. |
| Unverified editing tools | Object Removal; Qwen Image Edit; Scenario Changer; Room Decorator; ReplaceObject; OutPainting; RemoveBackground | Useful capabilities, but the supplied names do not prove exact endpoint contracts, mask formats, output behavior, or retry semantics. |
| Voice identity tools | Qwen Voice cloning; Voice cloning; Voice Cover; Voice Changer | Require consent, identity governance, abuse controls, and provenance. They are not needed for a classroom narration MVP. |
| Watermark remover | Sora Watermark Remover | Exclude from the pipeline by default. Only process content owned or authorized by the project, and prefer source assets without watermarks. |
| Training workflows | Stable Diffusion Trainer; Flux Lora Trainer; Z-Image-TurboLoraTrainer | Training adds dataset governance, reproducibility, cost, and artifact versioning requirements. Use only after a baseline pipeline proves the visual need. |
| Style and vertical presets | Ghibli-ArtStyle; Fashion; Interior; Interior Mixer; Exterior Restorer; Specific Floor Planning | Narrow or unclear scope for EVS Lesson 8 and insufficient documentation evidence for a core dependency. |
| Generic or ambiguous labels | Image to Image; Image to Text; Lyrics Generator; ImageUpscaler; ObjectRemover; `wan2.2` duplicate listing | Names do not uniquely identify an endpoint or model contract. Use the canonical documented IDs where available. |

## Production Readiness Gate

A selected model is not production-ready merely because its page says `model_ready`. Promote it from candidate to production only after all checks pass:

1. **Contract test:** required fields, accepted values, response ID, poll endpoint, output URL, and output format.
2. **Reliability test:** at least 20 representative requests with recorded success rate, latency percentiles, timeout rate, and retry outcomes.
3. **Concurrency test:** determine safe worker count without violating provider limits.
4. **Cost test:** reserve and reconcile per-scene cost; enforce a hard lesson budget.
5. **Artifact test:** verify codec, duration, resolution, frame rate, audio tracks, and corruption after download.
6. **Content test:** check animal identity, habitat facts, child safety, script fidelity, and caption accuracy.
7. **Recovery test:** retry a failed poll, resume after process restart, and avoid duplicate charges where possible.
8. **Entitlement test:** verify the account's plan, wallet, regional access, and model-specific billing in the dashboard.
9. **Observability test:** persist model ID, endpoint, request ID, prompt hash, seed, timing, status, and output checksum.
10. **Fallback test:** prove a usable fallback for each critical stage before batch rendering.

## Final Recommendation for OpenMontage

Use this dependency graph for the first production implementation:

```text
Approved EVS script
  -> reviewed keyframe generator [exact image model page still required]
  -> wan2.2 v6 text-to-video OR ltx-2-3-pro-i2v v7 image-to-video
  -> text-to-speech v6 narration
  -> speech-to-text v6 transcript/caption QA
  -> optional ultra_resolution image finishing
  -> OpenMontage composition and render QA
```

Recommended priority:

1. Implement `wan2.2` v6 as a first-class provider route.
2. Benchmark `h3-minimax-t2v` against Wan 2.2 using identical EVS prompts.
3. Use `h3-minimax-r2v` for reference-driven continuity experiments.
4. Implement `ltx-2-3-pro-i2v` as the controlled image-to-video fallback.
5. Add `text-to-speech` and `speech-to-text` as independent audio and QA stages.
6. Add `ltx-2.3` and `ltx-2-3-pro-t2v` only after measuring the first video routes.
7. Keep music and 3D optional so they cannot block delivery of the educational lesson.

This is the smallest documented set that covers the end-to-end EVS workflow while keeping visual generation, narration, QA, and finishing independently replaceable.

### Motion acceptance rule

The production pipeline is animation-first. A scene passes motion review only when the subject or environment visibly changes state during the clip: locomotion, gesture, breathing, blinking, flight, swimming, object interaction, cloth or foliage response, fluid dynamics, particles, or another physically legible event. A zoom, pan, tilt, or parallax move over an otherwise static image is not sufficient and must be treated as a still/graphics fallback, not as generated animation.
