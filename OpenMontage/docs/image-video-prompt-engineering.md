# Production Prompt Engineering for Image and Image-to-Video Models

This guide defines a technical prompt framework for open-source image generators and controlled image-to-video workflows. It is designed for Stable Diffusion and SDXL-style diffusion systems, Flux-style flow/transformer systems, ControlNet, and hosted image-to-video APIs such as Runway, Luma Dream Machine, and Kling.

The prompt is only one control surface. Production quality also depends on the checkpoint, VAE, LoRA or adapter, sampler, scheduler, denoising strength, control image, seed, resolution, frame rate, duration, and post-generation inspection. Record all of them with the prompt.

## 1. Separate the Prompt Layers

Use four layers rather than one unstructured paragraph:

```text
[content] + [composition] + [light and atmosphere] + [style and finish]
```

For image-to-video, use a different motion layer:

```text
[reference invariants] + [subject motion] + [camera motion] + [temporal constraints] + [negative motion constraints]
```

The image prompt establishes what exists. The video prompt describes what changes. Re-describing every visual detail in the motion prompt can cause the video model to reinterpret the reference instead of animating it.

### Production animation policy

For production video, image-to-video means real animated content, not a still image with a zoom, pan, or Ken Burns effect. Every generated clip must include at least one observable subject or environmental motion event: locomotion, breathing, blinking, gestures, object interaction, cloth or hair response, foliage, smoke, water, dust, particles, or another physically legible state change.

Camera movement is secondary. A camera dolly, pan, tilt, zoom, or parallax move over an otherwise static image is an animatic or editorial fallback and is not sufficient as the primary motion treatment. If the subject cannot visibly change state across the clip, classify the asset as a still/graphics shot and compose it with intentional motion graphics instead of presenting it as AI-generated animation.

Recommended prompt metadata:

```yaml
model_id: sdxl-1.0
checkpoint_sha256: "..."
vae: "..."
loras:
  - name: natural-history-illustration
    weight: 0.72
seed: 48192
sampler: DPM++ 2M Karras
steps:  thirty
cfg_or_guidance: 6.5
width: 1536
height: 864
prompt: "..."
negative_prompt: "..."
control_inputs: []
```

Use the exact model-specific field names in an API request. Do not assume that `cfg`, `guidance_scale`, `strength`, `motion_bucket`, `duration`, or `seed` have the same meaning across providers.

## 2. Content and Composition Control

### Subject specification

Describe the subject before the environment. Use concrete nouns, visible attributes, and countable objects.

```text
one red fox, full body, alert posture, thick winter coat, white chest, dark lower legs
```

Avoid adjective piles that do not control pixels:

```text
beautiful amazing stunning incredible fox
```

For a recurring subject, define an identity anchor and reuse it verbatim:

```text
Mara: short black bob, amber round glasses, olive field jacket, blue canvas satchel
```

Repeat the same 3-6 attributes in every shot. Do not replace them with `the same character`; diffusion and video models often treat that as weak context.

### Spatial placement

Use screen-relative descriptors and depth planes:

```text
subject in the right third of frame, facing left toward the center
foreground: wet grass and two out-of-focus reeds
midground: fox resting beside a moss-covered log
background: dark spruce forest fading into mist
clear negative space in the upper-left for later typography
```

Useful placement vocabulary:

- left third, right third, centered, lower third, upper-left quadrant
- foreground, middle ground, background
- near edge of frame, partially cropped, isolated against negative space
- symmetrical, asymmetrical, rule of thirds, centered axial composition
- front-facing, profile, three-quarter view, over-the-shoulder
- headroom, lead room, look room, walking room

Use spatial terms only when they serve the shot. Excessive coordinates compete with the subject description.

### Framing and camera angle

```text
wide establishing shot, eye-level camera, 28mm wide-angle lens
```

```text
medium close-up, camera at eye level, 85mm portrait lens, shoulders and face dominant
```

```text
extreme close-up of the compound eye, macro lens, shallow focus, textured surface filling frame
```

Use the correct distinction:

- `wide shot` describes framing and context.
- `high angle` describes the camera looking down.
- `bird's-eye view` means strict top-down.
- `aerial` describes camera height, not necessarily a top-down angle.
- `dolly in` moves the camera through space.
- `zoom in` changes focal length without translating the camera.
- `pan` rotates left or right.
- `truck` translates left or right.

### Depth of field and optics

Prefer physically related combinations:

```text
50mm lens, f/2.0, subject plane sharp, background rendered as soft circular bokeh
```

```text
24mm lens, f/8, deep focus from foreground stones to distant ridge
```

```text
100mm macro lens, f/4, razor-thin focus on the leaf vein, gradual falloff behind it
```

Useful controls:

- `deep focus`: foreground through background sharp
- `shallow depth of field`: subject sharp, background soft
- `rack focus`: focus changes during the shot
- `focus tracking`: focus follows a moving subject
- `anamorphic`: stretched highlights and characteristic horizontal flare
- `barrel distortion`: mild outward bowing of straight lines
- `fisheye`: strong edge curvature

Do not combine contradictory instructions such as `deep focus` and `extreme bokeh` unless the change is explicitly temporal.

## 3. Lighting and Atmospheric Physics

### Lighting construction

Describe source, direction, softness, contrast, and color temperature in that order:

```text
large north-facing window as the soft key from camera-left, subtle cool fill from the sky,
weak warm rim from a practical lamp behind the subject, low contrast, soft contact shadows
```

Lighting templates:

```text
high-key daylight, 5600K neutral daylight, broad softbox key, gentle fill, low shadow density,
clean neutral background, soft ambient occlusion
```

```text
low-key moonlight, 4300K cool blue key from camera-right, negative fill on the near side,
dense directional shadows, narrow warm rim from a distant window
```

```text
warm tungsten practicals at 3200K against cool 6500K window light, motivated mixed lighting,
moderate contrast, controlled halation on bright bulbs
```

Color-temperature guide:

- 2700-3200K: warm tungsten, amber, interior practicals
- 4000-4500K: neutral-to-cool moonlight or mixed light
- 5000-5600K: neutral daylight
- 6500-7500K: cool overcast or blue skylight

Kelvin values are guidance, not a guarantee. Reinforce the value with color words such as `amber tungsten`, `neutral daylight`, or `cool blue skylight`.

### Shadow control

Specify density and edge quality:

```text
soft-edged shadows, low density, broad penumbra
```

```text
dense contact shadows beneath the object, hard-edged cast shadow extending to camera-left
```

```text
ambient occlusion in the creases, restrained shadow detail, no crushed blacks
```

Avoid `cinematic lighting` alone. It is too broad to control the result. State the actual key, fill, rim, shadow, and contrast behavior.

### Atmosphere and particulate effects

```text
thin morning haze, visible volumetric shafts through the trees, fine suspended dust catching backlight,
subtle Tyndall scattering, distant contrast reduced by atmospheric perspective
```

```text
humid coastal air, low-lying mist near the ground, soft diffusion around highlights,
light rain particles visible only in the backlight, no heavy fog obscuring the subject
```

Use atmosphere as a depth cue, not as an excuse to hide the subject. Include a limit such as `thin`, `subtle`, or `subject remains clearly readable`.

## 4. Temporal and Motion Dynamics

Image-to-video models are more reliable when each clip has one primary subject action and one camera behavior. Separate motion into four questions:

1. What moves?
2. In which direction?
3. At what speed or acceleration?
4. What remains stable?

### Subject motion syntax

```text
The fox takes three slow steps from right to left, pauses, raises its head, and looks toward the light.
Movement is deliberate and anatomically natural; paws maintain contact with the ground.
```

```text
A single water droplet falls vertically, accelerates under gravity, strikes the surface,
forms a circular ripple, and settles. Preserve the droplet silhouette until impact.
```

Use temporal order for multiple events:

```text
first..., then..., finally...
```

Avoid vague verbs such as `moves dynamically`, `comes alive`, or `does something interesting`.

### Camera motion syntax

Name the primitive and direction:

```text
slow dolly forward toward the subject, no zoom, eye-level height, stabilized movement
```

```text
locked camera, then a gentle pan from left to right following the bird's flight path
```

```text
slow pedestal upward from ground level to reveal the canopy, no orbit, no sudden acceleration
```

```text
subtle arc around the subject from front-left to front-right, constant radius, subject remains centered
```

Camera vocabulary:

- translation: dolly, truck, pedestal
- rotation: pan, tilt, roll
- lens-only: zoom, rack focus, pull focus
- hybrid: orbit, arc, crane, tracking shot, dolly zoom
- stability: locked-off, stabilized, gentle handheld, controlled micro-shake

Never write `static camera` with `rack focus`, `zoom`, or `camera movement`. A static shot has no camera translation, rotation, or lens change.

### Speed and physicality

```text
slow, constant velocity, no abrupt acceleration
```

```text
gentle ease-in, brief pause, smooth ease-out
```

```text
real-time motion, gravity-consistent trajectory, realistic inertia and drag
```

```text
slow motion at 40 percent speed, fluid deformation preserved, no frame interpolation artifacts
```

Use physical constraints when they matter:

```text
cloth follows the body with delayed secondary motion; leaves respond to the same wind direction;
reflections remain attached to the water surface; shadows track the moving subject
```

### Image-to-video invariants

State what must not change:

```text
Preserve the reference image's subject identity, silhouette, colors, camera angle, lens perspective,
lighting direction, background geometry, and composition. Animate only the specified motion.
```

This is especially important for educational diagrams, products, faces, animals, and recurring characters.

## 5. Style and Identity Consistency

### Seed management

A seed is useful only when the model and all other settings remain compatible. Record:

- model and checkpoint identifier
- checkpoint or adapter hash
- seed
- sampler and scheduler
- steps and guidance
- resolution and aspect ratio
- LoRA names and weights
- ControlNet type and conditioning scale
- denoising strength
- prompt and negative prompt

Changing resolution, sampler, LoRA weight, or denoising strength can change the result even with the same seed.

### Descriptor locking

Create a style block and copy it verbatim:

```text
STYLE_LOCK = clean natural-history illustration, soft gouache texture, restrained teal and ochre palette,
clear silhouette, matte paper grain, gentle daylight, high legibility, no text
```

Then vary only the shot-specific block:

```text
STYLE_LOCK + SUBJECT_BLOCK + COMPOSITION_BLOCK + LIGHT_BLOCK
```

Do not alternate between near-synonyms such as `gouache`, `painted`, `storybook`, and `watercolor` when consistency matters. Token changes can change the visual language.

### LoRA and embedding weights

Weight syntax varies by ecosystem. Common Stable Diffusion UIs accept forms such as:

```text
<lora:natural-history:0.72>
```

or:

```text
(natural-history illustration:1.15)
```

Treat these as UI or checkpoint conventions, not universal API syntax. If the backend does not document weighting syntax, use explicit words and provider-native adapter fields instead.

Start with moderate weights. Excessive LoRA or token weights can produce oversaturated colors, repeated textures, anatomy errors, or loss of prompt adherence. Change one weight at a time and compare contact sheets.

### ControlNet and structural control

Use ControlNet when composition, pose, edges, depth, or layout matter more than unconstrained creativity:

```text
prompt: a red fox beside a moss-covered log, clean natural-history illustration
control: Canny edge map from the approved composition
conditioning scale: 0.65
```

Choose the control signal deliberately:

- Canny or lineart: preserve contours and graphic layout
- Depth: preserve spatial planes and camera structure
- OpenPose: preserve human pose
- Scribble: preserve rough composition while allowing redesign
- Segmentation: preserve semantic regions

Do not stack multiple strong controls without testing. Competing controls reduce flexibility and can create rigid or broken anatomy.

## 6. Architecture-Specific Workflows

### A. Stable Diffusion / SDXL direct diffusion syntax

Use weighted concepts, explicit negative prompts, and a separate technical parameter block. Keep the positive prompt readable and use weights sparingly.

```text
Positive:
professional wildlife photograph of one red fox, full body, right third of frame, facing left,
standing beside a moss-covered log in a spruce forest, foreground wet grass, misty background,
35mm lens, eye-level medium-wide shot, f/4, shallow depth of field, soft overcast daylight,
5600K neutral light, subtle rim light, restrained natural colors, fine fur detail, realistic anatomy

Negative:
text, logo, watermark, duplicate animal, extra legs, malformed paws, deformed face, cropped tail,
cut-off ears, floating subject, harsh oversaturation, crushed shadows, plastic fur, motion blur
```

Recommended iteration order:

1. composition and subject count
2. pose and anatomy
3. lighting and atmosphere
4. style and texture
5. negative prompt refinement
6. sampler, steps, guidance, and LoRA weights

Do not use a negative prompt to repair a fundamentally unclear positive prompt. State the desired composition first.

### B. Flux-style transformer or flow model

Flux-style systems generally respond better to natural language than to long comma-separated tag lists. Use a short narrative with explicit spatial and optical facts.

```text
A single red fox stands in the right third of a misty spruce forest, facing left toward open space.
The camera is at eye level in a medium-wide 35mm shot. Wet grass is softly out of focus in the foreground;
a moss-covered log sits behind the fox. Soft overcast daylight at approximately 5600K creates gentle
contact shadows and a restrained rim along the fur. Natural colors, accurate anatomy, detailed fur,
clear silhouette, no text, no logo, no watermark, no duplicate animals.
```

Use provider-native negative prompts only when supported. Otherwise phrase exclusions naturally: `The frame contains one fox and no typography or logos.`

### C. LLM prompt expansion for diffusion

Use an LLM as a constrained compiler, not as an autonomous art director. Give it a schema and prohibit unrequested concepts.

```text
Expand the following seed into a production image prompt.
Return JSON with exactly: subject, action, environment, composition, lens, lighting, atmosphere,
style, negatives, and parameters.
Rules:
- preserve the subject, count, action, and aspect ratio exactly;
- add no new characters, objects, brands, text, or narrative events;
- use physically compatible lens, lighting, and depth-of-field terms;
- keep the positive prompt under 120 words;
- use concrete visible nouns;
- negatives must describe likely defects, not abstract quality claims.
Seed: "one red fox beside a moss-covered log in a misty spruce forest, 16:9"
```

Validate the expansion before sending it to a model:

- subject count is unchanged
- no copyrighted character or brand was introduced
- requested action is visible
- camera and lighting terms are not contradictory
- negative terms do not negate required content
- output dimensions match the composition

### D. Image-to-video APIs: Runway, Luma, Kling, and similar systems

Hosted video systems are not open-source architectures, but the following motion syntax is portable across their image-to-video workflows. Treat the supplied image as the visual authority and prompt motion only.

```text
Preserve the reference image exactly: one red fox, right-third placement, profile facing left,
moss-covered log, misty spruce forest, soft overcast light, and the original lens perspective.
The fox takes three slow steps left, pauses, and raises its head. The camera performs a gentle
forward dolly of less than one meter at eye level. Keep the horizon stable, preserve the silhouette,
and maintain consistent shadows and fur texture. No cuts, no new animals, no morphing, no text,
no logo, no watermark, no sudden camera shake.
```

For Runway-style motion-first prompts:

```text
The fox takes three slow steps left and pauses. The camera gently dollies forward at eye level.
Maintain the reference composition, silhouette, lighting, and background. Stable, natural motion;
no cuts, no new objects, no morphing.
```

For Luma-style descriptive prompts:

```text
Animate the reference as one continuous shot. A red fox walks slowly left beside the moss-covered log,
then pauses and looks toward the mist. Gentle eye-level dolly forward, soft overcast daylight,
subtle fur and grass movement, stable anatomy and background geometry, no scene change.
```

For Kling-style structured prompts:

```text
Subject: one red fox beside a moss-covered log.
Motion: ++three slow steps left++, then pauses and raises its head.
Camera: gentle eye-level dolly forward, stabilized, no zoom.
Environment: misty spruce forest, soft overcast light, grass moves in one consistent breeze.
Constraints: preserve identity and composition; no cuts, morphing, duplicate animals, text, or watermark.
```

Provider syntax is not interchangeable. `++emphasis++`, image placeholders, motion-strength controls, and duration fields are provider-specific; keep them in the adapter layer or provider skill, not in a universal prompt artifact.

## 7. Reusable Template Library

### Still image: controlled cinematic frame

```text
[one subject with 3-6 identity attributes], [visible action or pose],
[environment and time of day]. [shot size], [camera height and angle],
[subject placement and depth planes], [lens and focus behavior].
[key light direction], [fill/rim], [shadow density], [color temperature].
[atmospheric effect with intensity]. [style and material].
[aspect ratio], clean composition, no text, no logo, no watermark.
```

### Still image: diagram or technical visual

```text
A clean [diagram/technical illustration] showing [single concept].
Orthographic or three-quarter view, centered layout, consistent scale, high-contrast edges,
separate labeled regions reserved for typography added in post, neutral background,
limited palette, no decorative clutter, no generated words or numbers.
```

### Image-to-video: subject-led motion

```text
Use the reference image as the visual authority. Preserve [identity, silhouette, pose, colors,
lighting, camera angle, background geometry]. Animate only [single action] at [speed].
Camera performs [one camera move] from [start] to [end]. Keep [physical invariants] stable.
One continuous shot, no cuts, no new subjects, no morphing, no text, no watermark.
```

The `[single action]` must be a visible state change, such as `the bird flaps twice and lands`,
`the fox walks three steps and raises its head`, or `the water droplet falls, strikes the surface,
and creates a ripple`. Do not use `slow zoom`, `gentle pan`, or `subtle push-in` as the only action.

### Image-to-video: object or fluid dynamics

```text
Preserve the reference object and camera. [Object/fluid] moves [direction] with [speed/acceleration].
Describe the cause and physical response: [gravity, drag, collision, ripple, cloth lag, smoke drift].
Camera remains [locked/stabilized/defined move]. Keep reflections, shadows, and contact points coherent.
One continuous shot, no geometry changes, no extra objects, no text.
```

### Multi-shot identity anchor

```text
Shot 1: Mara — short black bob, amber round glasses, olive field jacket, blue canvas satchel —
stands beside the doorway, medium shot, warm window light.
Shot 2: Mara — short black bob, amber round glasses, olive field jacket, blue canvas satchel —
walks into the room, side tracking shot, same wardrobe and lighting direction.
Shot 3: Mara — short black bob, amber round glasses, olive field jacket, blue canvas satchel —
turns toward the table, gentle push-in, same face and proportions.
```

Use multi-shot prompts only when the model documents multi-shot support. Otherwise render separate clips and assemble them in OpenMontage.

## 8. Quality Control and Failure Diagnosis

### Common failure: subject drift

Symptoms: changing face, colors, anatomy, or clothing.

Fixes:

- use image-to-video instead of text-to-video
- require subject or environmental animation; reject camera-only motion
- repeat the identity anchor verbatim
- reduce motion complexity
- use a stronger reference or ControlNet input
- shorten the clip and chain approved segments

### Common failure: camera-motion confusion

Symptoms: a dolly becomes a zoom, a pan becomes a truck, or the subject rotates unexpectedly.

Fixes:

- request one camera primitive
- state `no zoom` when requesting a dolly
- state `horizon remains level`
- remove decorative camera adjectives
- specify start and end framing

### Common failure: temporal melting

Symptoms: limbs, objects, or fluids morph between frames.

Fixes:

- reduce the number of simultaneous actions
- use slow, continuous motion
- add contact and physicality constraints
- avoid long chained clauses
- render shorter clips and cut between stable moments

### Common failure: lighting instability

Symptoms: flicker, changing shadow direction, inconsistent exposure.

Fixes:

- name one dominant key direction
- state `constant exposure and stable shadow direction`
- remove conflicting time-of-day terms
- use an approved keyframe as the source image

### Common failure: unreadable generated text

Do not ask diffusion or video models to render educational labels, captions, URLs, or assessment questions. Generate clean artwork and add typography during composition. Validate final text after rendering.

### Contact-sheet review

For image generation, render 4-8 candidates with fixed settings and vary only the intended variable. Review the contact sheet for:

- subject count and anatomy
- silhouette and framing
- lighting direction
- background continuity
- negative-space availability for titles
- compatibility with the next image-to-video stage

For video generation, inspect:

- first, middle, and final frames
- motion continuity at 2x speed
- subject identity and contact points
- camera trajectory
- flicker and exposure
- audio sync if audio is generated
- codec, resolution, frame rate, and duration

## 9. Production Checklist

Before generation:

- lock model, checkpoint, adapter, seed policy, aspect ratio, and output dimensions
- define the identity anchor and style block
- choose one primary action and one camera behavior
- specify what must remain unchanged
- reserve negative space for post-composed typography
- prepare a model-appropriate negative prompt or exclusion block

After a sample:

- verify the output file and media metadata
- inspect representative frames, not only the thumbnail
- compare prompt intent with visible motion
- record the request ID, prompt hash, seed, timing, and cost
- approve the model and prompt pattern before batch generation

During batch generation:

- checkpoint every scene
- retry only bounded, classifiable failures
- do not silently switch providers or model families
- keep rejected outputs and failure reasons for diagnosis
- regenerate only the affected scene when possible

A production prompt is successful when it produces a controllable, inspectable asset. More adjectives are not a substitute for explicit subject identity, spatial composition, physical motion, stable lighting, and recorded generation parameters.
