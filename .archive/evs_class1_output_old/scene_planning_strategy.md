# Scene Planning Strategy for Primary School Educational Videos

**Target Audience:** Grade 1 students (6–7 years old)
**Subject:** EVS (Environmental Studies) — adaptable to English, Math, Social
**Style:** Bright, friendly, cartoon-based, motion-only animation

---

## 1. Character Consistency Framework

### 1.1 Character Design System

To maintain visual continuity across 20+ scenes, we use a **locked character reference system**:

| Element | Specification | Implementation |
|---------|---------------|----------------|
| **Species/Type** | Fixed per character (e.g., "lion", "elephant") | Prompt anchor: `"a friendly cartoon lion with golden mane"` |
| **Color Palette** | Exact hex values locked | Prompt anchor: `"golden #FFA500 mane, brown #8B4514 body"` |
| **Style** | 2D cartoon, thick outlines, large eyes | Prompt anchor: `"2D cartoon style, thick black outlines, large expressive eyes, preschool-friendly"` |
| **Proportions** | Consistent body ratios | Prompt anchor: `"big head, small body, chibi proportions"` |
| **Expression** | Neutral-to-happy, no scary faces | Negative prompt: `"scary, angry, aggressive, menacing"` |

### 1.2 I2V Consistency Strategy

**Problem:** I2V models can drift character appearance across clips.

**Solution: Three-layer consistency lock**

```
Layer 1: T2I Reference Image (locked)
  └── Generate ONE high-quality start frame per character
  └── Reuse SAME image as init_image for ALL scenes featuring that character
  └── Store in assets/characters/{character_name}_reference.png

Layer 2: Prompt Anchoring (consistent)
  └── Every prompt starts with the SAME character description
  └── Example: "A friendly cartoon lion with golden mane, 2D cartoon style,
                thick black outlines, large expressive eyes, big head, small body"
  └── Only the ACTION/MOTION part of the prompt changes per scene

Layer 3: Image-to-Image (style lock)
  └── Use img2img with strength=0.3-0.5 instead of pure I2V
  └── This preserves character design while adding motion
  └── Model: h3-minimax-r2v with init_image = character reference
```

### 1.3 Environmental Consistency

| Element | Lock Strategy |
|---------|---------------|
| **Background style** | Same art style across all scenes (flat cartoon, no 3D) |
| **Color temperature** | Warm daylight for outdoor, soft indoor for home scenes |
| **Lighting direction** | Top-left light source for all scenes |
| **Ground plane** | Consistent horizon line at 40% from bottom |

---

## 2. Model Selection Logic

### 2.1 Decision Matrix

| Use Case | Model | Reason |
|----------|-------|--------|
| **Character reference images** | `hidream-o1` or `flux-schnell` | Best quality, fast, consistent style |
| **Background/environment images** | `flux-schnell` | Fast, good for non-character scenes |
| **Character animation (I2V)** | `h3-minimax-r2v` | Best identity preservation, supports init_image array |
| **Motion-only scenes (no character)** | `h3-minimax-r2v` | Smooth motion, no character drift |
| **Text overlay scenes** | Pillow + FFmpeg | No AI needed, crisp text rendering |

### 2.2 Why NOT `h3-minimax-start-end-frame`

| Issue | Impact |
|-------|--------|
| Returns 500 on v7 endpoint | Cannot generate video |
| `end_image` not supported | Cannot control scene transitions |
| Fixed 768P only | Lower resolution than alternatives |
| No working implementation | Unreliable for production |

**Decision:** Use `h3-minimax-r2v` exclusively for I2V. It has proven reliability and better character consistency.

### 2.3 Why NOT pure T2V (text-to-video)

| Issue | Impact |
|-------|--------|
| No character control | Appearance changes every generation |
| No scene control | Backgrounds inconsistent |
| Higher cost | More API calls for same result |
| Slower iteration | Hard to debug visual issues |

**Decision:** Always generate T2I reference first, then animate with I2V.

---

## 3. Motion-Only Constraint Implementation

### 3.1 Prohibited Animations

| Animation Type | Status | Reason |
|----------------|--------|--------|
| Camera zoom in | ❌ FORBIDDEN | Disorienting for young children |
| Camera zoom out | ❌ FORBIDDEN | Disorienting for young children |
| Camera pan | ⚠️ LIMITED | Allowed only if very slow (< 10° over 5s) |
| Camera tilt | ⚠️ LIMITED | Allowed only for emphasis |
| Dolly in/out | ❌ FORBIDDEN | Simulates zoom |
| Whip pan | ❌ FORBIDDEN | Too fast for kids |

### 3.2 Allowed Motion Types

| Motion | Description | Example |
|--------|-------------|---------|
| **Idle animation** | Subtle breathing/bouncing | Character standing, slight up-down |
| **Walk cycle** | Character walking in place or across scene | Lion walking across savanna |
| **Swim motion** | Tail/fin movement for water animals | Fish swimming, whale gliding |
| **Fly motion** | Wing flapping for birds | Bird flapping wings, soaring |
| **Environmental** | Background elements moving | Clouds drifting, water rippling, leaves falling |
| **Particle effects** | Bubbles, hearts, stars | Underwater bubbles, sparkle effects |
| **Reaction** | Character responding to narration | Rabbit ears twitching, bird head tilt |

### 3.3 Prompt Engineering for Motion-Only

**Template:**
```
[CHARACTER DESCRIPTION]. [ACTION/MOTION]. Environmental motion: [BACKGROUND ELEMENTS]. Static camera, motion-only animation. NO zoom in or out. Educational cartoon style for children. Bright colors. No text.
```

**Example — Water Animals Scene:**
```
A friendly cartoon fish with orange fins, 2D cartoon style, thick black outlines, large expressive eyes. Swimming motion: gentle tail wiggle, fins moving smoothly. Environmental motion: bubbles rising slowly, water ripples, light rays filtering through blue water. Static camera, motion-only animation. NO zoom in or out. Educational documentary style for children. Bright blue colors. No text.
```

**Example — Lion Walking:**
```
A friendly cartoon lion with golden mane, 2D cartoon style, thick black outlines, large expressive eyes. Walking motion: smooth four-legged walk cycle, mane swaying gently. Environmental motion: grass swaying, dust particles. Static camera, motion-only animation. NO zoom in or out. Educational nature documentary style for children. Warm savanna colors. No text.
```

---

## 4. Scene Planning Strategy

### 4.1 Scene Classification

| Scene Type | Motion Requirement | Asset Strategy |
|------------|-------------------|----------------|
| **Title cards** | Text fade-in/out | Pillow + FFmpeg (no AI) |
| **Narration + static image** | Gentle idle animation | T2I image + idle motion I2V |
| **Animal showcase** | Walk/swim/fly cycle | T2I reference + I2V animation |
| **Comparison scenes** | Side-by-side static | T2I split image + no motion |
| **Exercise scenes** | Text reveal animation | Pillow + FFmpeg (no AI) |
| **Activity scenes** | Interactive feel | T2I image + gentle motion |

### 4.2 Scene Dependency Graph

```
Scene 1: Title Card
  └── NO assets needed (Pillow only)

Scene 2: Highlights
  └── T2I: Teacher character + mind-map background
  └── I2V: Gentle floating animation for icons

Scene 3: Water Animals
  └── T2I: Fish, dolphin, whale reference images (3 separate)
  └── I2V: Swimming animation for each (3 clips)
  └── Composite: FFmpeg overlay on underwater background

Scene 4: Land Animals
  └── T2I: Lion, elephant, tiger reference images (3 separate)
  └── I2V: Walking animation for each (3 clips)
  └── Composite: FFmpeg overlay on savanna background

Scene 5: Birds
  └── T2I: Duck, pigeon, parrot reference images (3 separate)
  └── I2V: Flying animation for each (3 clips)
  └── Composite: FFmpeg overlay on sky background

Scene 6: Insects
  └── T2I: Butterfly, housefly, grasshopper reference images (3 separate)
  └── I2V: Flying/crawling animation for each (3 clips)
  └── Composite: FFmpeg overlay on garden background

Scene 7: Animal Homes A
  └── T2I: Forest background, cave, burrow, nest, anthill
  └── I2V: Character movement toward homes (4 clips)

Scene 8: Animal Homes B
  └── T2I: Farm background, kennel, shed, stable
  └── I2V: Animal movement toward homes (3 clips)

Scene 9: Let's Recall
  └── NO new assets (reuse previous character images)

Scene 10-12: Exercises
  └── NO AI assets (Pillow text cards only)

Scene 13: Activity
  └── T2I: Simple crayon/paper illustration
  └── I2V: Gentle drawing motion (optional)
```

### 4.3 Character Reference Library

Create once, reuse everywhere:

```
assets/characters/
├── lion_reference.png          # Golden mane, friendly expression
├── elephant_reference.png      # Gray, big ears, trunk
├── tiger_reference.png         # Orange stripes, walking pose
├── fish_reference.png          # Orange fins, underwater
├── dolphin_reference.png       # Gray, jumping pose
├── whale_reference.png         # Blue, gliding pose
├── duck_reference.png          # Yellow, flying pose
├── pigeon_reference.png        # Gray, soaring pose
├── parrot_reference.png        # Green, flapping pose
├── butterfly_reference.png     # Colorful wings
├── housefly_reference.png      # Small, buzzing pose
├── grasshopper_reference.png   # Green, jumping pose
├── rabbit_reference.png        # White, hopping pose
├── bird_reference.png          # Small, nest-building pose
├── ant_reference.png           # Small, marching pose
├── dog_reference.png           # Brown, running to kennel
├── cow_reference.png           # White/brown, walking to shed
└── horse_reference.png         # Brown, trotting to stable
```

---

## 5. Technical Implementation Plan

### 5.1 Phase 3.5 Asset Generation Flow

```
Input: phase2_script_scenes.json (with image_prompt + video_prompt)

Step 1: Scan scenes for asset requirements
  └── Count scenes with image_prompt
  └── Count scenes with video_prompt
  └── Estimate cost: $0.10 per T2I + $1.33 per I2V (7s × $0.19)

Step 2: Generate T2I reference images (parallel where possible)
  └── For each unique character: generate ONE reference image
  └── For each unique environment: generate ONE background
  └── Cache to assets/characters/ and assets/environments/
  └── Reuse references across scenes

Step 3: Generate I2V video clips (sequential, one at a time)
  └── For each scene with video_prompt:
  │     ├── Select init_image from:
  │     │   ├── Scene-specific T2I image (if exists)
  │     │   └── Character reference image (fallback)
  │     ├── Call h3-minimax-r2v with:
  │     │   ├── prompt = scene.video_prompt
  │     │   ├── init_image = [selected_image_url]
  │     │   ├── duration = "7"
  │     │   └── resolution = "768P"
  │     └── Poll until success (max 600s)
  └── Download and cache to assets/videos/

Step 4: Update scene JSON with asset paths
  └── scene.generated_assets = {
  └──     "image": "assets/images/scene_003_start.png",
  └──     "video": "assets/videos/scene_003_clip.mp4"
  └── }
  └── scene.init_image_url = "assets/images/scene_003_start.png"

Step 5: Validate assets
  └── Check all images exist and are valid PNG
  └── Check all videos exist and are valid MP4 (ffprobe)
  └── Check video duration matches requested (±10%)
```

### 5.2 Cost Estimation

| Asset Type | Count | Unit Cost | Total |
|------------|-------|-----------|-------|
| Character references | 18 | $0.10 | $1.80 |
| Environment backgrounds | 6 | $0.10 | $0.60 |
| I2V video clips | 6 | $1.33 (7s × $0.19) | $7.98 |
| **Total** | | | **~$10.38** |

### 5.3 Time Estimation

| Phase | Duration |
|-------|----------|
| T2I reference generation | ~3 min (10s per image × 24) |
| I2V clip generation | ~36 min (6 min per clip × 6) |
| Download + validation | ~2 min |
| **Total** | **~41 min** |

---

## 6. Remotion Integration Plan

### 6.1 Current Status

The OpenMontage codebase has a `remotion_renderer/` directory at:
```
D:\new_video_pip\packages\textbook-pipeline\remotion_renderer\
```

This contains pre-built Remotion compositions for:
- `TitleCard.tsx`
- `TextCard.tsx`
- `VocabularyCard.tsx`
- `ComparisonTable.tsx`
- `SceneComposition.tsx`

### 6.2 Integration Strategy

**Option A: Python → Remotion Bridge (Recommended)**
```python
# renderer.py calls Remotion via subprocess
subprocess.run([
    "npx", "remotion", "render",
    "packages/textbook-pipeline/remotion_renderer/index.ts",
    "--composition", scene_composition,
    "--props", json.dumps(scene_props),
    "--output", str(output_path),
])
```

**Option B: Direct Python Rendering (Current)**
- Uses Pillow + FFmpeg
- Faster iteration, no Node.js dependency
- Lower quality (no animation)

**Decision:** Keep Option B as default, add Option A as premium render path.

### 6.3 Font Configuration for Remotion

| Font | Usage | File Path |
|------|-------|-----------|
| **Nunito** | Headings, titles | `assets/fonts/Nunito-Bold.ttf` |
| **Comic Neue** | Body text, kid-friendly | `assets/fonts/ComicNeue-Regular.ttf` |
| **Inter** | UI elements, metadata | `assets/fonts/Inter-Regular.ttf` |

**Installation:**
```bash
# Download fonts to assets/fonts/
mkdir -p assets/fonts
curl -o assets/fonts/Nunito-Bold.ttf "https://fonts.gstatic.com/s/nunito/v25/XRXX3I6li01BKofiOcW0.woff2"
curl -o assets/fonts/ComicNeue-Regular.ttf "https://fonts.gstatic.com/s/comicneue/v3/4UaDr7tF4xpT0ZPTg.woff2"
```

---

## 7. Quality Assurance Checklist

### 7.1 Pre-Generation

- [ ] All `image_prompt` fields populated and sanitized
- [ ] All `video_prompt` fields populated with motion-only constraint
- [ ] Character reference library generated
- [ ] Environment backgrounds generated
- [ ] API key valid and budget approved

### 7.2 Post-Generation

- [ ] All T2I images downloaded and valid PNG
- [ ] All I2V videos downloaded and valid MP4
- [ ] Video durations within ±10% of requested
- [ ] Character consistency verified (visual inspection)
- [ ] No zoom animations in video clips (frame analysis)
- [ ] All assets referenced in scene JSON exist on disk

### 7.3 Final Render

- [ ] All segments render without FFmpeg errors
- [ ] Audio sync within 100ms tolerance
- [ ] Final MP4 plays correctly (ffprobe validation)
- [ ] File size reasonable (< 500MB for 10 min video)
- [ ] Subtitles burned in (if applicable)

---

## 8. Summary

| Component | Status | Action Required |
|-----------|--------|----------------|
| Character consistency | 🔲 Planned | Generate reference library, lock prompts |
| I2V model selection | ✅ Fixed | Using `h3-minimax-r2v` on v6 endpoint |
| Motion-only constraint | 🔲 Planned | Add to all video_prompt templates |
| Asset generation pipeline | 🔲 In Progress | Phase 3.5 module created |
| Renderer integration | 🔲 Planned | Update create_scene_video_segment |
| Remotion bridge | 🔲 Optional | Python subprocess wrapper |
| Font configuration | 🔲 Planned | Download Nunito + Comic Neue |
