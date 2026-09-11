# ModelsLab 64-Model Technical Directory

This directory analyzes the 64 model and capability names supplied for the educational video workflow. It is a curated interpretation of names and public industry conventions, not a substitute for each model's current API documentation. Architecture labels marked **likely** are inferences; endpoint, parameter, plan, and entitlement details must be verified in the ModelsLab dashboard before production use.

## Scope and Caveats

- The list mixes trainable workflows, model families, UI capabilities, and inference models.
- `Wan Text to Video Ultra` and `Wan Image to Video Ultra` are deprecated aliases that route to `wan2.2`.
- `Sora Watermark Remover`, `Object Remover`, `ObjectRemoval`, `RemoveBackground`, and similar names describe post-processing capabilities rather than standalone foundation models.
- `Flux LoRA Trainer`, `Stable Diffusion Trainer`, and `Z-Image-TurboLoraTrainer` are training or adaptation workflows, not ordinary generation endpoints.
- Names such as `Interior`, `Fashion`, and `Ghibli-ArtStyle` are product or style presets; their underlying checkpoint may change.
- Open-source status does not by itself prove that an account has unlimited usage. Confirm billing and plan entitlement in the dashboard.

## Functional Groups

| Group | Count | Role in an educational video workflow |
|---|---:|---|
| Text-to-image | 10 | Generate chapter illustrations, diagrams, backgrounds, and keyframes |
| Image-to-image and image editing | 15 | Revise, restore, remove, replace, stylize, or extend assets |
| Video generation | 6 | Generate or animate chapter scenes from text or keyframes |
| Audio and voice | 15 | Narration, dubbing, music, SFX, transcription, and voice transformation |
| 3D generation | 2 | Create spatial assets or simple 3D teaching objects |
| Control, restoration, and utility | 8 | Pose/control, enhancement, QR codes, background removal, and specialized presets |
| Training and adaptation | 3 | Train LoRA or diffusion adaptations for recurring visual identity |
| **Total** | **64** | |

## Model-by-Model Technical Profile

Architecture descriptions are probable family-level interpretations based on names and common industry usage. Validate exact versions before relying on them for reproducibility.

| # | Model / capability | Functional group | Primary modality | Likely architecture | Specific capability and intended use |
|---:|---|---|---|---|---|
| 1 | Krea-2 turbo Text to Image | Text-to-image | Text -> Image | Likely diffusion or flow transformer | Fast concept and illustration generation; useful for rapid storyboard exploration. |
| 2 | Hidream-O1 Image to Image | Image editing | Image -> Image | Likely diffusion transformer | Transform an existing image while preserving broad composition and subject identity. |
| 3 | Hidream-O1 Text to Image | Text-to-image | Text -> Image | Likely diffusion transformer | High-quality prompt-driven image synthesis for keyframes and explanatory visuals. |
| 4 | LTX 2.3 Image to Video | Video generation | Image -> Video | Diffusion transformer video model | Animate a controlled still image into a short coherent shot. |
| 5 | LTX 2.3 Text to Video | Video generation | Text -> Video | Diffusion transformer video model | Generate short clips from scene descriptions; good for fast iteration. |
| 6 | Flux Klein 9B Image To Image | Image editing | Image -> Image | Likely transformer-based rectified-flow diffusion | High-throughput image transformation and controlled variations. |
| 7 | Flux Klein 9B | Text-to-image | Text -> Image | Likely transformer-based rectified-flow diffusion | General image generation with a speed or efficiency emphasis. |
| 8 | Qwen Voice Design | Audio and voice | Text -> Audio | Likely language-conditioned audio/voice model | Design a voice from textual attributes such as age, tone, pace, and mood. |
| 9 | Z-Image-TurboLoraTrainer | Training and adaptation | Image training | Diffusion + LoRA adaptation | Train a lightweight style or subject adapter for consistent educational artwork. |
| 10 | Qwen Voice cloning | Audio and voice | Audio -> Voice | Likely speaker-embedding plus neural codec/TTS | Clone a permitted reference voice for consistent narration. Obtain consent. |
| 11 | Z Image base | Text-to-image | Text -> Image | Likely diffusion or flow-based image model | General-purpose image generation baseline. |
| 12 | Qwen Image Edit 2511 | Image editing | Image -> Image | Vision-language instruction model plus diffusion decoder | Instruction-following image edits with semantic preservation. |
| 13 | Z Image Turbo Image To Image | Image editing | Image -> Image | Turbo diffusion or flow model | Fast image variations, restyling, and composition-preserving edits. |
| 14 | Z Imge Turbo | Text-to-image | Text -> Image | Likely turbo diffusion/flow model | Fast prompt-to-image generation; name spelling should be verified in the API. |
| 15 | Flux.2 Dev Image To Image (Image Editing) | Image editing | Image -> Image | Transformer-based rectified-flow diffusion | Structured image editing and controlled transformations. |
| 16 | Flux.2 Dev Text To Image | Text-to-image | Text -> Image | Transformer-based rectified-flow diffusion | High-quality prompt-to-image generation for chapter illustrations. |
| 17 | Interior Mixer | Specialized image editing | Image -> Image | Likely diffusion editing pipeline | Mix or redesign interior layouts and furnishings; useful for animal-home diagrams only when adapted carefully. |
| 18 | Object Removal | Image editing | Image -> Image | Mask-guided diffusion inpainting | Remove unwanted objects while reconstructing the background. |
| 19 | Qwen Image To Image | Image editing | Image -> Image | Vision-language model plus diffusion image generator | Instruction-based transformations with semantic understanding. |
| 20 | Qwen Text to Image | Text-to-image | Text -> Image | Diffusion transformer or multimodal generative model | Generate detailed educational images and diagrams from prompts. |
| 21 | Sora Watermark Remover | Image/video utility | Video or image -> Image/video | Likely detection plus inpainting | Remove visible watermarks only from content you own or have permission to modify. |
| 22 | Qwen Image Edit | Image editing | Image -> Image | Vision-language instruction model plus diffusion decoder | General semantic editing, replacement, cleanup, and restyling. |
| 23 | Image to Text | Vision analysis | Image -> Text | Vision-language encoder-decoder | Caption, inspect, or extract semantic content from generated assets for QA. |
| 24 | Stable Diffusion Trainer | Training and adaptation | Image training | Latent diffusion plus LoRA/DreamBooth-style adaptation | Train a custom visual style or recurring subject representation. |
| 25 | Flux Lora Trainer | Training and adaptation | Image training | Flux rectified-flow transformer plus LoRA | Adapt Flux to a consistent character, school brand, or illustration style. |
| 26 | Wan2.2 Image to Video | Video generation | Image -> Video | Video diffusion transformer | Animate prepared keyframes; recommended for controlled educational scenes. |
| 27 | Wan2.2 Text to Video | Video generation | Text -> Video | Video diffusion transformer | Generate short scenes from text; useful for establishing shots and simple motion. |
| 28 | Scenario Changer | Specialized image editing | Image -> Image | Likely instruction-guided diffusion | Change scene context or environment while retaining a subject. |
| 29 | Exterior Restorer | Image restoration | Image -> Image | Restoration network plus diffusion refinement | Restore or enhance outdoor imagery and damaged details. |
| 30 | Specific Floor Planning | Specialized image editing | Text/image -> Image | Layout-conditioned diffusion or vision-language pipeline | Create floor-plan or spatial planning visuals. |
| 31 | Room Decorator | Specialized image editing | Image -> Image | Instructed image-to-image diffusion | Redesign room appearance while maintaining geometry. |
| 32 | Sketch Renderer | Image generation/editing | Sketch -> Image | ControlNet-like conditioning plus diffusion | Convert line art or diagrams into polished illustrations. |
| 33 | Interior | Specialized image generation | Text/image -> Image | Likely diffusion preset | Generate interior scenes or room visualizations. |
| 34 | Flux Kontext Dev | Image editing | Image -> Image | Likely context-aware transformer diffusion | Multi-turn or context-preserving edits with improved instruction adherence. |
| 35 | CreateDubbing | Audio and voice | Video/text -> Audio/video | ASR + translation + TTS + alignment pipeline | Create translated or replacement narration synchronized to video. |
| 36 | SoundEffect (SFX) | Audio and voice | Text -> Audio | Text-conditioned audio diffusion or generative audio model | Generate short environmental and interaction sound effects. |
| 37 | Speech to Text | Audio and voice | Audio -> Text | Automatic speech recognition transformer | Transcribe narration, create captions, and support content QA. |
| 38 | Lyrics Generator | Audio and voice | Text -> Text | Language model | Draft lyrics or educational mnemonic text; not an audio synthesizer itself. |
| 39 | Song Generator | Audio and voice | Text -> Audio | Text-conditioned music generation model | Generate complete songs or musical educational segments. |
| 40 | Voice Isolation Audio | Audio and voice | Audio -> Audio | Speech separation or denoising neural network | Extract narration from mixed audio and reduce background sound. |
| 41 | AI Music Generator | Audio and voice | Text -> Audio | Diffusion, autoregressive, or codec language model | Create instrumental background music with mood and duration control. |
| 42 | Voice Cover | Audio and voice | Audio -> Audio | Voice conversion plus pitch/timbre modeling | Convert a vocal performance into a permitted target voice. |
| 43 | Voice cloning | Audio and voice | Audio -> Voice | Speaker-conditioned TTS or voice conversion | Reproduce a permitted speaker identity for consistent narration. |
| 44 | QR Code Generator | Utility | Text -> Image | Deterministic QR encoder plus image styling | Create scannable links to worksheets or supplemental lessons; validate decodeability. |
| 45 | Ghibli-ArtStyle | Style preset | Text/image -> Image | Likely style LoRA or diffusion preset | Apply a named illustrative style; use only where licensing and classroom appropriateness are clear. |
| 46 | Flux Text to Image | Text-to-image | Text -> Image | Transformer-based rectified-flow diffusion | High-quality general image generation. |
| 47 | ControlNet | Image control | Image/condition -> Image | Control branch attached to diffusion UNet/transformer | Enforce pose, edges, depth, segmentation, or layout while generating. |
| 48 | Image to Image | Image editing | Image -> Image | Generic diffusion img2img pipeline | Transform an existing image with a denoising-strength tradeoff. |
| 49 | Voice Changer | Audio and voice | Audio -> Audio | Neural voice conversion | Change speaker timbre while preserving timing and often linguistic content. |
| 50 | ReplaceObject (Inpaint) | Image editing | Image + mask -> Image | Mask-guided diffusion inpainting | Replace a selected object while matching lighting, perspective, and texture. |
| 51 | Wan Image to Video Ultra (deprecated) | Video generation | Image -> Video | Legacy alias to Wan 2.2 video diffusion | Do not target directly; migrate calls to `wan2.2` after confirming the current endpoint. |
| 52 | Image to 3D | 3D generation | Image -> 3D | Single-image reconstruction or 3D diffusion | Create a mesh or textured 3D asset from a reference image. |
| 53 | Realtime Text to Image | Text-to-image | Text -> Image | Distilled diffusion or latent consistency model | Low-latency interactive image generation and ideation. |
| 54 | Text to 3D | 3D generation | Text -> 3D | Text-conditioned 3D diffusion or multi-view reconstruction | Create simple 3D educational objects from descriptions. |
| 55 | SDXL Headshot | Specialized image generation | Text -> Image | SDXL latent diffusion plus face/portrait conditioning | Generate consistent portrait or presenter headshots. |
| 56 | ObjectRemover | Image editing | Image -> Image | Object detection/segmentation plus inpainting | Remove objects from images; functionally overlaps Object Removal. |
| 57 | Fashion | Specialized image editing | Text/image -> Image | Diffusion with fashion or garment conditioning | Generate apparel, try-on, or clothing variations. |
| 58 | OutPainting | Image editing | Image -> Image | Masked diffusion extension | Expand an image beyond its original borders while matching context. |
| 59 | Wan Text to Video Ultra (deprecated) | Video generation | Text -> Video | Legacy alias to Wan 2.2 video diffusion | Do not target directly; use `wan2.2` and its current documented text-to-video endpoint. |
| 60 | Text to Speech | Audio and voice | Text -> Audio | Neural TTS, often transformer plus neural codec | Generate narration with voice, pace, pronunciation, and emotion controls. |
| 61 | Flux Headshot | Specialized image generation | Text -> Image | Flux rectified-flow transformer with portrait prompting | Generate high-quality presenter or character portraits. |
| 62 | ImageUpscaler | Image restoration | Image -> Image | Super-resolution neural network, often diffusion-assisted | Increase resolution and recover detail before animation or compositing. |
| 63 | RemoveBackground | Image editing | Image -> Image with alpha | Segmentation matting network | Produce transparent-background subjects for compositing. |
| 64 | wan2.2 | Video generation | Text/image -> Video | Video diffusion transformer | Base open-source Wan 2.2 model; preferred canonical target for the deprecated Ultra aliases. |

## Prompt Engineering Framework

### Text-to-image

Use a structured visual specification. Put the subject and educational fact first, then composition, age appropriateness, style, lighting, and exclusions.

```text
Create a [educational illustration / diagram / scene] for [age group] about [learning objective].
Subject: [specific subject and count]. Action: [simple observable action].
Environment: [accurate habitat or setting]. Composition: [wide/medium/close shot],
[subject placement], clear negative space on [side] for later labels.
Visual language: [friendly 2D illustration / clean natural history plate / soft 3D cartoon],
accurate anatomy, simple shapes, high contrast, consistent palette [palette].
Output: 16:9, clean edges, classroom-safe, no text, no watermark, no logos.
Avoid: extra limbs, duplicate animals, distorted faces, ambiguous species, clutter.
```

For text rendering, generate artwork without labels and add typography during composition. Diffusion models are unreliable at exact educational spelling.

### Image-to-image and image editing

State what must remain invariant, then describe only the intended change. Use masks where the endpoint supports them.

```text
Edit the supplied image. Preserve [identity, pose, camera angle, anatomy, lighting,
color palette, and background geometry]. Change only [target region/object] to [desired result].
Match perspective, scale, shadows, occlusion, and material texture to the original.
Keep all other pixels conceptually unchanged. No new objects, no text, no watermark.
```

For inpainting:

```text
Masked region: [object or area]. Replace it with [replacement].
Context: [surrounding scene]. Match [light direction, focal length, depth of field,
color temperature, and grain]. Preserve the unmasked area exactly.
```

### Video generation

Prefer image-to-video for curriculum consistency. Describe one shot, one action, and one camera move.

```text
Educational shot for [grade] about [fact]. Start from the supplied keyframe.
Subject: [one primary subject]. Action: [single continuous action] over [duration].
Camera: [locked / slow push-in / gentle pan], [framing]. Motion is physically plausible,
calm, and easy for children to follow. Preserve subject identity, colors, and habitat.
Style: [consistent project style], bright but natural lighting, clean composition.
No text, captions, logos, watermarks, abrupt cuts, extra subjects, or morphing.
```

For text-to-video:

```text
Generate one continuous [5-10 second] educational scene: [subject] in [setting]
performs [single action]. Begin with [establishing composition], then [camera movement].
The visual must clearly communicate [learning fact]. Use accurate anatomy, stable geometry,
child-safe imagery, natural motion, and a clean ending frame for editing. No dialogue,
no on-screen text, no watermark, no scene changes.
```

### Audio, voice, and dubbing

Specify delivery rather than only topic. Keep educational narration separate from music and effects whenever possible.

```text
Voice: [age/role], [language/accent], [warmth], [pace in words per minute],
[energy], clear pronunciation for [grade]. Read exactly:
"[short narration]"
Pause [duration] after [key term]. Emphasize [terms]. No added words, music, or sound effects.
```

For music:

```text
Create a [duration] instrumental bed for a [grade] science lesson about [topic].
Mood: [curious / gentle / bright]. Tempo: [BPM range]. Instrumentation: [instruments].
Leave space for narration, use a clean intro and outro, no vocals, no copyrighted melody,
no sudden peaks, and loop cleanly if needed.
```

For SFX:

```text
Generate a short, isolated [sound] in [environment], [realistic/stylized] but child-safe.
Dry recording, no music, no voice, no reverb tail longer than [duration], normalized output.
```

### 3D generation

```text
Create a simple classroom-ready 3D asset: [object/animal].
Style: [low-poly / smooth educational illustration], readable silhouette, non-threatening,
accurate proportions, neutral pose, centered, front three-quarter view.
Materials: [matte materials], colors: [palette]. Deliver a clean watertight mesh with
simple topology, centered origin, usable scale, and no text or background clutter.
```

### Vision analysis and speech-to-text

Use constrained extraction prompts and request uncertainty instead of invented facts.

```text
Analyze this asset for curriculum QA. Return JSON with: visible_subjects, action,
habitat, factual_risks, text_present, text_accuracy, anatomy_errors, and confidence.
Do not infer facts that are not visible. Use null when uncertain.
```

## Selection Strategy

| Requirement | Recommended first choice | Why | Fallback |
|---|---|---|---|
| Fast storyboard ideation | Realtime Text to Image or Krea-2 turbo | Low-latency exploration | Flux Klein 9B |
| Highest controlled still quality | Flux.2 Dev Text To Image, Flux Text to Image, Qwen Text to Image | Strong general-purpose visual generation | Hidream-O1 Text to Image |
| Consistent chapter keyframes | Flux or Qwen text-to-image plus a fixed seed/style reference | Establishes a repeatable visual bible | SDXL Headshot for presenter portraits |
| Animate a prepared keyframe | Wan2.2 Image to Video | Preserves the designed composition better than pure T2V | LTX 2.3 Image to Video |
| Generate a simple shot from text | Wan2.2 Text to Video | Canonical open-source route in this list | LTX 2.3 Text to Video |
| Fast video iteration | LTX 2.3 Image/Text to Video | Speed-oriented family | Wan2.2 at lower resolution |
| Remove or replace an object | ReplaceObject (Inpaint) or Object Removal | Mask-guided edits are more predictable | Qwen Image Edit |
| Extend a frame | OutPainting | Explicitly designed for canvas expansion | Flux.2 Dev Image To Image |
| Remove the background | RemoveBackground | Produces a compositing-ready subject | Image editing with a segmentation mask |
| Restore low-quality source art | ImageUpscaler, Exterior Restorer | Improve source before animation | Qwen Image Edit |
| Keep a pose or edge layout | ControlNet | Adds explicit structural conditioning | Sketch Renderer |
| Narrate the lesson | Text to Speech | Direct control of words and delivery | Qwen Voice Design, then TTS |
| Translate or replace narration | CreateDubbing | Combines transcription, translation, synthesis, and alignment | Speech to Text + Text to Speech |
| Add classroom ambience | SoundEffect and AI Music Generator | Separate controllable layers | Song Generator for a mnemonic segment |
| Clean recorded narration | Voice Isolation Audio | Separates speech from noise/music | Speech-to-text QA plus rerecord |
| Produce a 3D teaching object | Image to 3D or Text to 3D | Select based on whether a reference image exists | 2D compositing if 3D is unnecessary |
| Train a recurring visual identity | Flux Lora Trainer or Stable Diffusion Trainer | Reusable style/subject adaptation | Fixed prompts, seeds, and references |

### Speed versus fidelity

- **Real-time or exploratory:** use Realtime Text to Image, Krea-2 turbo, Flux Klein, or LTX fast variants.
- **Balanced production:** use Flux/Qwen for keyframes, then Wan2.2 or LTX image-to-video.
- **High-fidelity hero shot:** use a controlled keyframe, image-to-video, higher resolution, and multiple candidate renders. Do not rely on a single text-to-video call for a fact-critical scene.
- **Deterministic educational graphics:** use diagrams, compositing, and typography tools rather than asking generative models to render exact words or numbers.

### Recommended EVS Lesson 8 pipeline

1. Extract facts and assessment items from the lesson source.
2. Create a style bible and generate a small set of reference keyframes with Flux or Qwen.
3. Use Wan2.2 image-to-video for habitats, birds, insects, and animal-home scenes.
4. Generate narration with Text to Speech and validate it with Speech to Text.
5. Add isolated SFX and low-volume music beneath narration.
6. Add all labels, glossary terms, and assessment questions in the composition layer.
7. Run image-to-text and media QA for factual accuracy, animal identity, caption spelling, and audio intelligibility.
8. Render a representative 5-second smoke scene before batch generation, then checkpoint every scene.

## Operational Checklist

- Verify the exact model ID and endpoint from the live model page.
- Confirm whether the model is open-source, included in the plan, or billed per generation.
- Check input requirements, output resolution, duration, aspect ratio, and polling endpoint.
- Use a cost estimate and a per-scene budget before batch generation.
- Record model ID, prompt, seed, source assets, API response ID, and output metadata.
- Keep generated text out of images; add it during composition for reliable spelling and accessibility.
- Obtain consent for voice cloning, voice covers, and any identifiable person likeness.
- Do not remove watermarks from third-party content without authorization.
- Treat architecture and capability labels in this document as hypotheses until confirmed by the model's current documentation.
