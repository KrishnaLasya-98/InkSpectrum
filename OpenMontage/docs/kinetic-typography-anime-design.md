# Kinetic Typography & Motion Design System — Anime-Style Aesthetic

## 1. System Overview

This design defines a **word-level kinetic typography (KT) engine** for OpenMontage Remotion/HyperFrames compositions. It treats every spoken word as a discrete animated entity whose timing, position, scale, color, and effects are derived from **Pillar 1 audio alignment data** (`transcript.json` with `word_timestamps`).

The aesthetic is **anime explainer** — think Bakemonogatari title cards, {O}verflow motion-graphics explainers, and Pixar-style children's shorts (e.g. "The Last Banana") — where text enters with physicality, highlights pulse in sync with voice amplitude, and emphasis triggers stylized particle/speed-line effects.

---

## 2. Pillar 1 Integration Contract

### 2.1 Input Schema (`transcript.json`)

```json
{
  "word_timestamps": [
    { "word": "Welcome", "start": 0.52, "end": 0.88 },
    { "word": "to",      "start": 0.90, "end": 1.05 },
    { "word": "the",     "start": 1.07, "end": 1.18 }
  ],
  "sentences": [
    {
      "text": "Welcome to the jungle.",
      "start": 0.52,
      "end": 2.40,
      "role": "statement"
    }
  ],
  "audio_metadata": {
    "sample_rate": 48000,
    "channels": 1,
    "duration_seconds": 120.0,
    "rms_amplitude": [
      { "time": 0.00, "rms": 0.12 },
      { "time": 0.02, "rms": 0.45 }
    ]
  }
}
```

### 2.2 Derived Data Structures

The KT engine precomputes these at load time from `word_timestamps` + `rms_amplitude`:

| Derived Field | Source | Purpose |
|---------------|--------|---------|
| `word.durationMs` | `(end - start) * 1000` | Entrance/exit timing |
| `word.pauseAfterMs` | `next.start - end` | Gap before next word |
| `word.amplitude` | Nearest RMS sample | Audio-reactive scale |
| `word.isPlosive` | Regex `/[ptkbdg]/` on `word` | Consonant pop trigger |
| `sentence.role` | Capitalization, trailing `?`, prefix `emoji` | Placement/emotion mapping |
| `sentence.lineCount` | Word count / maxWordsPerLine | Layout decision |
| `word.highlightGroup` | Sequential non-pause words | Stagger animation group |

### 2.3 Data Flow

```
transcript.json
    │
    ▼
[Pillar1Adapter] ──► WordAlignment[] ──► SentenceAlignment[]
    │                      │
    │                      ▼
    │              [AudioAnalyzer] ──► RMS envelope, plosive map
    │                      │
    ▼                      ▼
[KTConfig] ◄────────── [LayoutEngine] ──► WordPlacement[]
    │
    ▼
[AnimeEffectsLayer] ◄── [WordComponent] (per frame)
```

---

## 3. Word Segmentation & Placement Algorithm

### 3.1 Sentence Role Classification

```typescript
type SentenceRole = "statement" | "question" | "definition" | "example" | "character_name" | "emphasis";

function classifySentenceRole(sentence: string, prevRole?: SentenceRole): SentenceRole {
  const trimmed = sentence.trim();
  if (/^[\p{Emoji_Presentation}\p{Extended_Pictographic}]/u.test(trimmed)) return "character_name";
  if (trimmed.endsWith("?")) return "question";
  if (/^(Definition|Define|What is|A \w+ is)/i.test(trimmed)) return "definition";
  if (/^(For example|Example|e\.g\.|Like)/i.test(trimmed)) return "example";
  if (/^(Important|Key|Note|Remember|Watch)/i.test(trimmed)) return "emphasis";
  return "statement";
}
```

### 3.2 Line Wrapping Algorithm

**Constraints:** Max 7 words per line, max 2 lines on screen.

```typescript
interface WrapResult {
  lines: string[][];
  totalLines: number;
  overflow: boolean;
}

function wrapWordsToLines(words: string[], maxWordsPerLine: number): WrapResult {
  const lines: string[][] = [];
  let currentLine: string[] = [];

  for (const word of words) {
    if (currentLine.length >= maxWordsPerLine) {
      lines.push(currentLine);
      currentLine = [];
    }
    currentLine.push(word);
  }

  if (currentLine.length > 0) lines.push(currentLine);

  return {
    lines,
    totalLines: lines.length,
    overflow: lines.length > 2,
  };
}
```

**Overflow handling:** If >2 lines, reduce font size by 10% and re-wrap. If still >2 lines, truncate last line with "…" and render remainder as smaller caption below.

### 3.3 Position Calculation

```typescript
type EntryDirection = "left" | "right" | "bounce" | "top" | "center-scale";

interface PositionConfig {
  anchor: "top-left" | "top-center" | "center" | "bottom-center" | "bottom-left";
  entryDirection: EntryDirection;
  yOffsetPx: number;      // vertical offset from anchor
  maxWidthPercent: number; // constraint for wrapping
}

function getPositionConfig(role: SentenceRole, lineCount: number): PositionConfig {
  switch (role) {
    case "question":
      return { anchor: "top-center", entryDirection: "bounce", yOffsetPx: -80, maxWidthPercent: 70 };
    case "definition":
      return { anchor: "center", entryDirection: "center-scale", yOffsetPx: 0, maxWidthPercent: 60 };
    case "character_name":
      return { anchor: "bottom-left", entryDirection: "left", yOffsetPx: 60, maxWidthPercent: 40 };
    case "emphasis":
      return { anchor: "center", entryDirection: "bounce", yOffsetPx: 0, maxWidthPercent: 80 };
    case "example":
      return { anchor: "bottom-center", entryDirection: "right", yOffsetPx: 40, maxWidthPercent: 75 };
    default: // statement
      return { anchor: "top-left", entryDirection: "left", yOffsetPx: 60, maxWidthPercent: 85 };
  }
}
```

---

## 4. Typographic Hierarchy System

### 4.1 Scale Matrix

| Role | Font Size Range | Weight | Line Height | Tracking | Typical Use |
|------|-----------------|--------|-------------|----------|-------------|
| `heading` | 72–96px | 700–800 | 1.1 | -0.02em | Scene titles, episode openers |
| `key_term` | 48–60px | 600–700 | 1.2 | 0em | Vocabulary, bold claims, numbers |
| `body` | 36–44px | 400–500 | 1.35 | 0.01em | Narration text, explanations |
| `caption` | 24–30px | 300–400 | 1.4 | 0.02em | Subtitles, metadata, examples |

### 4.2 Color Palette System

```yaml
kinetic_typography:
  color_palette:
    # Primary scene colors (rotated per scene)
    primary_voice: "#FF6B9D"    # Narrator voice color
    secondary_voice: "#4ECDC4"  # Second speaker / character
    highlight: "#FFD93D"        # Active word highlight
    emphasis: "#FF8C42"         # Key term accent
    
    # Semantic colors
    question: "#A78BFA"         # Question sentences
    definition_bg: "rgba(78, 205, 196, 0.15)"
    definition_border: "#4ECDC4"
    example_bg: "rgba(255, 107, 157, 0.1)"
    example_border: "#FF6B9D"
    
    # Background gradient (anime dark theme default)
    background_gradient: "linear-gradient(135deg, #0A0A1A 0%, #1A1A2E 50%, #16213E 100%)"
    
    # Glow/shadow tokens
    glow_primary: "0 0 20px rgba(255, 107, 157, 0.5)"
    glow_highlight: "0 0 15px rgba(255, 217, 61, 0.6)"
    text_shadow: "0 2px 8px rgba(0,0,0,0.4)"
```

### 4.3 Font Recommendations

| Font | Role | Rationale |
|------|------|-----------|
| `Noto Sans JP` | Body / headings | Clean Japanese-inspired geometry, excellent CJK+Latin harmony |
| `Nunito` | Body (child content) | Rounded, friendly, EEG-validated for ages 5–7 |
| `Zen Kaku Gothic New` | Key terms | Modern Japanese gothic with personality |
| `Space Grotesk` | Headings (tech) | Geometric, slightly quirky anime UI feel |
| `Fredoka` | Questions/emoji | Bouncy, kawaii-compatible |
| `M PLUS 1p` | Definition boxes | Highly readable Japanese-inspired sans |

---

## 5. Animation Timing Table

### 5.1 Entrance Animations

| Animation | Duration | Easing | Trigger | Description |
|-----------|----------|--------|---------|-------------|
| `slide-scale-bounce` | 150ms | `spring({fps, config: {damping: 14, stiffness: 180}})` | Word start | Word slides in from entry direction with overshoot bounce |
| `typewriter` | 30ms/char | `linear` | Word start + char index | Each character appears sequentially; used for headings |
| `pop-in` | 200ms | `spring({fps, config: {damping: 10, stiffness: 200}})` | Key term | Scale 0→1.1→1 with glow flash |
| `fade-slide-up` | 250ms | `ease-out` | Sentence start | Entire sentence fades in with upward drift |
| `character-reveal` | 300ms | `cubic-bezier(0.34, 1.56, 0.64, 1)` | Character name | Bouncy scale + voice-color fill |

### 5.2 Exit Animations

| Animation | Duration | Easing | Trigger |
|-----------|----------|--------|---------|
| `fade-slide` | 200ms | `ease-in` | Word end (next word starts) |
| `dissolve` | 100ms | `linear` | Scene transition |
| `scale-fly-out` | 180ms | `ease-in-back` | Emphasis word after highlight |
| `blur-out` | 150ms | `ease-out` | Background text (lower layer words) |

### 5.3 Idle Animations

| Animation | Duration | Easing | Loop | Description |
|-----------|----------|--------|------|-------------|
| `floating` | 0.5s | `ease-in-out` | Infinite | Subtle translateY ±3px |
| `breathing` | 1.2s | `ease-in-out` | Infinite | Scale 1.0 → 1.03 → 1.0 |
| `glow-pulse` | 1.5s | `ease-in-out` | Infinite | Opacity/glow intensity oscillate |
| `underline-dash` | 0.8s | `linear` | Infinite | Dashed underline stroke-dashoffset animation |

### 5.4 Audio-Reactive Animations

| Animation | Trigger | Intensity | Description |
|-----------|---------|-----------|-------------|
| `amplitude-scale` | RMS amplitude per frame | 0–15% | Word scale linked to `audio_metadata.rms_amplitude` at current time |
| `consonant-pop` | Plosive onset (`ptkbdg`) | +20% scale, 50ms | Sharp scale pop at consonant boundary; mapped to word start + plosive offset |
| `vowel-drift` | Sustained vowel | ±2px X drift | Very subtle horizontal drift during long vowels (duration > 300ms) |
| `sentence-breath` | Sentence gap (> 400ms pause) | -5% opacity | Background words dim slightly during long pauses |

### 5.5 Transition Animations (Between Words)

| Animation | Duration | Delay | Overlap | Description |
|-----------|----------|-------|---------|-------------|
| `overlap` | 30% of word duration | — | 30% | New word starts before old word fully exits |
| `stagger` | 50ms/word | 50ms per word index | None | Sequential word reveal with fixed delay |
| `cascade` | 40ms/word | 0ms | 50% | Each word slides from slightly different height |

### 5.6 Complete Timing Reference Table

```
┌─────────────────────┬──────────┬───────────────────────────────────┬───────────────────────┐
│ Animation           │ Duration │ Easing                            │ Applied To            │
├─────────────────────┼──────────┼───────────────────────────────────┼───────────────────────┤
│ slide-scale-bounce  │ 150ms    │ spring(d=14, s=180)               │ All words             │
│ typewriter          │ 30ms/char│ linear                            │ Headings only         │
│ pop-in              │ 200ms    │ spring(d=10, s=200)               │ Key terms             │
│ fade-slide-up       │ 250ms    │ ease-out                          │ Sentence start        │
│ character-reveal    │ 300ms    │ cubic-bezier(0.34,1.56,0.64,1)   │ Character names       │
│ fade-slide          │ 200ms    │ ease-in                           │ Word exit             │
│ dissolve            │ 100ms    │ linear                            │ Scene transition      │
│ scale-fly-out       │ 180ms    │ ease-in-back                      │ Emphasis exit         │
│ blur-out            │ 150ms    │ ease-out                          │ Background words      │
│ floating            │ 500ms    │ ease-in-out (loop)                │ Idle state            │
│ breathing           │ 1200ms   │ ease-in-out (loop)                │ Idle state            │
│ amplitude-scale     │ per frame│ linear (RMS lookup)               │ All active words      │
│ consonant-pop       │ 50ms     │ spring(d=8, s=300)                │ Plosive onsets        │
│ overlap             │ 30% word │ —                                 │ Transition            │
│ stagger             │ 50ms/word│ —                                 │ Transition            │
│ cascade             │ 40ms/word│ —                                 │ Transition            │
└─────────────────────┴──────────┴───────────────────────────────────┴───────────────────────┘
```

---

## 6. Anime-Style Effect Catalog

### 6.1 Speed Lines

```typescript
interface SpeedLineConfig {
  enabled: boolean;
  trigger: "emphasis" | "question" | "key_term";
  intensity: number;        // 0–1
  direction: "radial" | "horizontal" | "diagonal";
  color: string;
  lineCount: number;        // 12–40
  lengthPx: number;         // 40–200
  opacity: number;          // 0.1–0.4
  durationMs: number;       // 300–600
}

const DEFAULT_SPEED_LINES: SpeedLineConfig = {
  enabled: true,
  trigger: "emphasis",
  intensity: 0.7,
  direction: "radial",
  color: "#FFFFFF",
  lineCount: 24,
  lengthPx: 120,
  opacity: 0.25,
  durationMs: 400,
};
```

**Trigger Conditions:**
- `emphasis`: Sentence role is `"emphasis"` AND contains a word tagged `isEmphasis: true`
- `question`: Sentence ends with `?` AND voice pitch rises (detected via amplitude spike + duration)
- `key_term`: Word font size >= 48px

**Implementation:** Canvas-drawn lines with `transform: rotate()` and `scaleY` animation. Lines emanate from text bounding box center outward.

### 6.2 Particle Effects on Key Terms

Reuses and extends the existing `ParticleType` system:

| Particle Type | Trigger | Color | Count | Behavior |
|---------------|---------|-------|-------|----------|
| `sparkles` | Key term highlight | `highlight` (#FFD93D) | 8–12 | Burst outward from word center, 600ms lifespan |
| `burst` | Definition reveal | `secondary_voice` | 16–24 | Radial burst with gravity fall |
| `swirl` | Scene transition | `primary_voice` | 20–30 | Vortex pattern fading across screen |
| `stardust` | Character name | `highlight` | 10–15 | Gentle upward drift with twinkle |

### 6.3 Swirl/Fade Scene Transitions

```typescript
interface SwirlTransitionConfig {
  durationMs: number;       // 500–900
  direction: "in" | "out";
  rotationDeg: number;      // 90–180
  scaleFrom: number;        // 0.8
  scaleTo: number;          // 1.0
  blurPx: number;           // 0→8→0
}
```

**Trigger:** Sentence role changes OR scene composition changes. Applied as a full-screen overlay using `interpolate` on `frame`.

### 6.4 Character Reaction Pops

```typescript
interface ReactionPopConfig {
  characterImage?: string;   // SVG/PNG path
  emojiFallback: string;     // "😲", "✨", "💡", "🎉"
  trigger: "key_term" | "question" | "definition" | "emphasis";
  position: "top-right" | "bottom-left" | "floating";
  scale: number;             // 0.6–1.0 relative to text
  enterDurationMs: number;   // 200
  exitDurationMs: number;    // 300
  loop: boolean;             // true for floating emoji
}
```

**Behavior:** On trigger, an emoji or character image scales from 0→1.2→1.0 with a spring bounce, then either exits or floats gently above the text for the sentence duration.

---

## 7. Remotion Component Structure

### 7.1 Component Hierarchy

```
<KineticTypography>                          // Parent: manages scene, audio data, layout
  <KineticTypographyLayout>                  // Layout wrapper: position, wrapping, line calc
    <KineticTypographyLine>                  // One line of words
      <KineticWord>                           // Single word: entrance/exit/idle/audio-reactive
        <AnimeEffectsLayer />                 // Effect overlay per-word (speed lines, particles)
      </KineticWord>
    </KineticTypographyLine>
  </KineticTypographyLayout>
  <AnimeEffectsLayer sceneLevel />            // Full-scene effects (swirl, speed lines, reaction pops)
</KineticTypography>
```

### 7.2 Parent Component: `KineticTypography.tsx`

**Props:**

```typescript
interface KineticTypographyProps {
  /** Word-level transcript from Pillar 1 */
  transcript: TranscriptData;
  /** RMS amplitude envelope for audio-reactive animation */
  audioEnvelope: RMSFrame[];
  /** Scene-level configuration */
  config?: Partial<KineticTypographyConfig>;
  /** Background style */
  background?: React.ReactNode | string;
  /** Optional character/reaction layer */
  reactions?: ReactionConfig[];
  /** Current playback time in seconds (from Remotion timeline) */
  currentTime: number;
}
```

**Responsibilities:**
- Parse `transcript.word_timestamps` into typed word objects
- Compute layout (lines, positions, wrapping) using `LayoutEngine`
- Map `currentTime` to active word index
- Provide context (sentence role, active word, RMS amplitude) to children via render props or context
- Manage scene-level effects layer visibility

### 7.3 Word Component: `KineticWord.tsx`

**Props:**

```typescript
interface KineticWordProps {
  word: WordAlignment;
  /** Pre-computed layout info */
  layout: WordLayout;
  /** Current frame for animation calculations */
  frame: number;
  /** FPS */
  fps: number;
  /** RMS amplitude at this word's time */
  amplitude: number;
  /** Whether this word is the currently spoken word */
  isActive: boolean;
  /** Whether this word was recently spoken (highlight phase) */
  isHighlighted: boolean;
  /** Sentence role for styling */
  sentenceRole: SentenceRole;
  /** Animation configuration */
  animConfig: WordAnimationConfig;
  /** Whether to render effects for this word */
  showEffects: boolean;
  /** Callback when word entrance begins */
  onEnter?: (word: WordAlignment) => void;
  /** Callback when word is spoken */
  onSpeak?: (word: WordAlignment) => void;
}
```

**Internal State Machine:**

```
┌──────────┐     word.start      ┌──────────┐     word.end      ┌──────────┐
│ Waiting  │ ──────────────────► │ Entering │ ──────────────────► │ Speaking │
│          │                     │ (150ms)  │                     │          │
└──────────┘                     └──────────┘                     └──────────┘
                                                                   │
                                                             pauseAfterMs
                                                                   │
                                                              ┌──────▼──────┐
                                                              │   Exiting   │
                                                              │   (200ms)   │
                                                              └─────────────┘
```

**Animation Logic:**

```typescript
const WORD_ENTER_DURATION = Math.round(fps * 0.15);  // 150ms
const WORD_EXIT_DURATION = Math.round(fps * 0.20);   // 200ms
const WORD_SPEAK_DURATION = Math.round(fps * 0.10);  // 100ms highlight hold

function getWordState(frame: number, word: WordAlignment, fps: number): WordState {
  const enterStart = Math.round(word.start * fps);
  const enterEnd = enterStart + WORD_ENTER_DURATION;
  const speakEnd = enterEnd + WORD_SPEAK_DURATION;
  const exitEnd = Math.round(word.end * fps) + WORD_EXIT_DURATION;

  if (frame < enterStart) return "waiting";
  if (frame < enterEnd) return "entering";
  if (frame < speakEnd) return "speaking";
  if (frame < exitEnd) return "exiting";
  return "exited";
}
```

**Style Application by State:**

| State | Opacity | Scale | TranslateY | Glow | Color |
|-------|---------|-------|------------|------|-------|
| `waiting` | 0 | 0.8 | +20px | none | `text` |
| `entering` | 0→1 | 0.8→1→1.05→1 | +20px→0 | none→`glow_highlight` | `text`→`highlight` |
| `speaking` | 1 | 1→1+amplitude*0.15 | 0 | `glow_highlight` | `highlight` |
| `exiting` | 1→0 | 1→0.9 | 0→-10px | none | `highlight`→`text` |
| `exited` | 0 | 1 | 0 | none | `text` |

### 7.4 Effects Layer: `AnimeEffectsLayer.tsx`

**Props:**

```typescript
interface AnimeEffectsLayerProps {
  type: "word" | "sentence" | "scene";
  effect: AnimeEffectType;
  config: AnimeEffectConfig;
  frame: number;
  fps: number;
  bounds?: { x: number; y: number; width: number; height: number };
}
```

**Supported Effects:**

| Effect | Type | Trigger | Implementation |
|--------|------|---------|----------------|
| `speed-lines` | scene/emphasis | `sentence.role === "emphasis"` | Canvas or SVG lines with `interpolate` rotation/scale |
| `particles-sparkles` | word | `word.size >= 48` | Extends `ParticleOverlay` with burst timing |
| `particles-burst` | sentence | Definition reveal | One-shot particle burst at word center |
| `particles-swirl` | scene | Scene transition | Full-screen vortex `transform: rotate()` |
| `particles-stardust` | word | Character name | Upward drifting sparkles |
| `reaction-pop` | sentence | Any emphasis trigger | Emoji/character image spring animation |
| `screen-shake` | scene | Impact word (plosive cluster) | `translateX/Y` random offset ±4px, 100ms |

### 7.5 Integration with Existing Components

The new KT system composes with existing Remotion components:

```tsx
// Example: Explainer composition using KineticTypography
<Sequence from={sceneStart} durationInFrames={sceneDuration}>
  <AnimeScene images={sceneImages} particles="fireflies">
    <KineticTypography
      transcript={sceneTranscript}
      audioEnvelope={sceneAudioEnvelope}
      config={kineticConfig}
    />
  </AnimeScene>
</Sequence>
```

---

## 8. Style Playbook Extension

The anime-kinetic style playbook extends the base schema with KT-specific fields:

```yaml
# styles/anime-kinetic.yaml
identity:
  name: "Anime Kinetic Typography"
  category: motion-graphics
  mood: energetic, playful, emphatic, warm
  pace: moderate
  best_for: >
    Animated explainers, educational content, children's videos, social shorts,
    any narrative with narration where text should feel alive and audio-synced.

visual_language:
  color_palette:
    primary: ["#FF6B9D", "#4ECDC4"]
    accent: ["#FFD93D", "#FF8C42", "#A78BFA"]
    background: "#0A0A1A"
    text: "#F5F0E8"
    muted: "#8B9A7E"

typography:
  headings:
    font: "Space Grotesk"
    weight: 700
    size_range: [72, 96]
  key_terms:
    font: "Zen Kaku Gothic New"
    weight: 700
    size_range: [48, 60]
  body:
    font: "Noto Sans"
    weight: 500
    size_range: [36, 44]
  caption:
    font: "Noto Sans"
    weight: 400
    size_range: [24, 30]
  scale_system: major_third
  weight_matrix:
    title: 800
    heading: 700
    body: 500
    caption: 400

motion:
  transitions: [slide-scale-bounce, dissolve, swirl]
  animation_style: >
    spring-heavy with audio-reactive amplitude scaling.
    Per-word entrance: slide + scale bounce (150ms, d=14, s=180).
    Per-word exit: fade + slide (200ms, ease-in).
    Idle: floating (500ms loop) + breathing (1200ms scale 1.0→1.03).
  pacing_rules:
    min_word_hold_seconds: 0.3
    max_words_per_line: 7
    max_lines_on_screen: 2
    overlap_ratio: 0.3
    stagger_delay_ms: 50
  entrance: slide-scale-bounce (150ms, spring d=14 s=180)
  exit: fade-slide (200ms, ease-in)
  idle: floating + breathing + glow-pulse

kinetic_typography:
  enabled: true
  max_words_per_line: 7
  max_lines: 2
  word_enter_duration_ms: 150
  word_exit_duration_ms: 200
  word_highlight_duration_ms: 100
  stagger_delay_ms: 50
  overlap_ratio: 0.3
  amplitude_scale_range: [0, 0.15]
  consonant_pop_scale: 0.20
  consonant_pop_duration_ms: 50
  floating_duration_ms: 500
  breathing_duration_ms: 1200
  breathing_scale_range: [1.0, 1.03]
  speed_lines:
    enabled: true
    default_trigger: emphasis
    default_count: 24
  particles:
    enabled: true
    default_type: sparkles
    default_count: 10
  reaction_pops:
    enabled: true
    emoji_set: ["😲", "✨", "💡", "🎉", "⭐", "🔥"]

audio:
  voice_style: energetic, warm, clear articulation with intentional pauses
  music_mood: upbeat acoustic, gentle electronic, kawaii-pop
  music_volume: 0.12
  sfx_style: subtle whooshes, light chimes on emphasis, no harsh impacts
  ducking_threshold_db: -4

overlays:
  definition_box:
    bg: "rgba(78, 205, 196, 0.15)"
    border: "#4ECDC4"
    border_width: 2
    radius: 12
    padding: "12px 20px"
  example_box:
    bg: "rgba(255, 107, 157, 0.1)"
    border: "#FF6B9D"
    border_width: 2
    radius: 8
    padding: "10px 16px"
  question_badge:
    prefix_emoji: "❓"
    text_color: "#A78BFA"
    scale: 1.05

quality_rules:
  - "Maximum 7 words per line, maximum 2 lines visible at once"
  - "Every word must have deterministic entrance/exit tied to transcript timestamps"
  - "Audio-reactive scale must use pre-computed RMS envelope (no per-frame audio decode)"
  - "Plosive detection triggers consonant-pop within ±30ms of word onset"
  - "Speed lines must fade in/out, never appear/disappear instantly"
  - "Particle counts capped at 30 per word, 60 per scene to maintain 30fps"
  - "All animation values must be clamped to [0, 1] before Remotion interpolation"
  - "No Math.random() or Date.now() — all randomness seeded from word index"
```

---

## 9. HyperFrames Integration

For HyperFrames atelier mode, the same logic maps to CSS custom properties and keyframes:

```css
/* HyperFrames CSS variable bridge */
:root {
  --kt-word-enter-duration: 150ms;
  --kt-word-exit-duration: 200ms;
  --kt-stagger-delay: 50ms;
  --kt-floating-duration: 500ms;
  --kt-breathing-duration: 1200ms;
  --kt-amplitude-scale-max: 1.15;
  --kt-consonant-pop-scale: 1.20;
  --kt-speed-line-count: 24;
  --kt-particle-count: 10;
}

.word-kinetic {
  animation: kt-enter var(--kt-word-enter-duration) cubic-bezier(0.34, 1.56, 0.64, 1) both;
}

.word-kinetic.active {
  animation: kt-highlight 100ms ease-out, kt-breathing 1200ms ease-in-out infinite;
}

@keyframes kt-enter {
  from { opacity: 0; transform: translateY(20px) scale(0.8); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

@keyframes kt-highlight {
  0% { transform: scale(1); text-shadow: none; }
  50% { transform: scale(1.05); text-shadow: 0 0 20px var(--kt-glow-color); }
  100% { transform: scale(1); text-shadow: none; }
}

@keyframes kt-breathing {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.03); }
}
```

The HyperFrames bridge (`lib/hyperframes_style_bridge.py`) maps `kinetic_typography` playbook fields to these CSS variables.

---

## 10. Performance & Determinism Requirements

| Constraint | Rule | Rationale |
|------------|------|-----------|
| No `Math.random()` | Use `seededRandom(seed)` where `seed = wordIndex * PRIME` | Remotion determinism |
| No `Date.now()` | All timing from `useCurrentFrame()` / `useVideoConfig().fps` | Frame-accurate seeking |
| No `requestAnimationFrame` | Remotion controls render loop | Prevents desync |
| No `repeat: -1` in Remotion | Loop via frame math, not CSS infinite | Deterministic scrubbing |
| Particle cap | Max 30 particles per word, 60 per scene | 30fps target on mid-range hardware |
| Pre-compute RMS | Envelope sampled at build time, not render time | Avoid per-frame audio decode |
| Will-change hints | `willChange: "transform, opacity"` on animated elements | GPU compositor promotion |

---

## 11. Testing Strategy

| Test | Tool | What It Validates |
|------|------|-------------------|
| Frame snapshot tests | Remotion `renderFrames` | Word positions at t=0, t=mid, t=end |
| Timing regression | `vitest` + custom assertions | Word enter/exit frames match transcript |
| Overflow tests | `renderFrames` at max 7 words | No text clips beyond 2 lines |
| Plosive pop tests | Unit test `detectPlosives()` | Correct consonant classification |
| Amplitude sync | Golden master comparison | Scale values match pre-computed envelope |
| Performance | Remotion `renderFrames` profiling | 30fps maintained with 60 particles |

---

## 12. Summary

This system provides:

1. **Pillar 1-native word placement** — every word is positioned, wrapped, and timed from `transcript.json`
2. **Anime-aesthetic motion** — spring-based entrances, breathing idle, amplitude-reactive scaling
3. **Effect catalog** — speed lines, particles, swirls, reaction pops with explicit trigger conditions
4. **Remotion component architecture** — 3-component hierarchy (`KineticTypography` → `KineticWord` → `AnimeEffectsLayer`)
5. **HyperFrames compatibility** — CSS variable bridge for atelier mode
6. **Performance safety** — deterministic, capped particles, pre-computed audio data

The design is ready for implementation in `remotion-composer/src/components/KineticTypography/` and registration in `remotion-composer/src/components/index.ts`.
