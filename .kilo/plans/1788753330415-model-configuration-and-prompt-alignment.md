# InkSpectrum — Model Configuration & Prompt Alignment

## 1. Model Inventory

### LLM (Script Generation)
| Model | Provider | Purpose | Config Key |
|-------|----------|---------|------------|
| `openai/gpt-oss-120b` | Groq | Script generation for all subjects | `GROQ_API_KEY` |

### Image Generation
| Model | Provider | Purpose | Config Key |
|-------|----------|---------|------------|
| `hidream-o1` | ModelsLab | Text-to-image for scene illustrations | `MODELSLAB_IMAGE_MODEL` |
| `hidream-o1` | ModelsLab | Image-to-image transformations | `MODELSLAB_IMAGE_MODEL_I2I` |

### Video Generation
| Model | Provider | Purpose | Config Key |
|-------|----------|---------|------------|
| `h3-minimax-start-end-frame` | ModelsLab | Start-end frame video generation | `MODELSLAB_VIDEO_MODEL` |
| `h3-minimax-r2v` | ModelsLab | Reference-to-video animation | `MODELSLAB_VIDEO_MODEL_R2V` |

### TTS / Audio
| Model | Provider | Purpose | Config Key |
|-------|----------|---------|------------|
| `text-to-speech` | ModelsLab | Text-to-speech voiceover | `MODELSLAB_TTS_MODEL` |
| `eleven_multilingual_v2` | ModelsLab | Multilingual TTS (fallback) | `MODELSLAB_TTS_MODEL` |

### PDF Extraction
| Tool | Purpose | Status |
|------|---------|--------|
| PyMuPDF | Fast fallback extractor | ✅ Working |
| Marker | Primary extractor (math/images/tables) | ⏳ Testing |
| OpenDataLoader | Alternative extractor | ✅ Working |

### Subject Router
| Model | Provider | Purpose |
|-------|----------|---------|
| `qwen3.8-27b` | AnyAPI | Subject classification |
| `google/gemma-4-26b-a4b-it:free` | AnyAPI | Fallback classifier |

---

## 2. Renderer Routing Logic

```
ChapterNode
  ↓
Subject Detection
  ↓
┌─────────────┬──────────────┬──────────────┬──────────────┐
│   English   │     Math     │   EVS/Sci    │    Social    │
├─────────────┼──────────────┼──────────────┼──────────────┤
│  Remotion   │    Manim     │  Remotion    │  Remotion    │
│  + Images   │  + LaTeX     │  + Images    │  + Images    │
│  + hidream  │  + Manim     │  + hidream   │  + hidream   │
│             │              │  + h3-minimax│  + h3-minimax│
└─────────────┴──────────────┴──────────────┴──────────────┘
  ↓           ↓              ↓              ↓
TTS         TTS            TTS            TTS
(text-to-   (text-to-      (text-to-      (text-to-
  speech)     speech)        speech)        speech)
```

---

## 3. Subject-Specific Prompt Alignment

### English (Grade 1-5)
**Renderer:** Remotion  
**LLM Model:** `openai/gpt-oss-120b` via Groq  
**Image Model:** `hidream-o1`  
**Video Model:** `h3-minimax-r2v`  
**TTS Model:** `text-to-speech`

**Prompt Strategy:**
```
You are a warm, encouraging primary teacher creating English video scripts.

PEDAGOGY:
- Phonics: vocabulary cards + word highlights + pronunciation guides
- Stories: storyboard frames + dialogue bubbles + scene illustrations
- Poems: poem cards with rhythm cues
- Exercises: question cards with guided answers

VISUAL GENERATION:
- Use hidream-o1 for all illustrations
- Style: bright colors, cartoon, friendly characters
- Prompts: "Children reading books in a sunny classroom, cartoon style"
- Animation: Use h3-minimax-r2v for subtle scene motion

SCENE VOCABULARY:
TITLE, SUBTITLE, TEXT, CLEAR, WORD_HIGHLIGHT, SENTENCE_TOKEN,
VOCABULARY_CARD, PRONUNCIATION_GUIDE, POEM_CARD, DIALOGUE_BUBBLE,
STORYBOARD_FRAME, QUESTION_CARD, WORKED_STEP, ANSWER_REVEAL

OUTPUT: JSON array of ScriptScene objects with visual_prompts for each scene.
```

### Math (Grade 1-5)
**Renderer:** Manim  
**LLM Model:** `openai/gpt-oss-120b` via Groq  
**TTS Model:** `text-to-speech`

**Prompt Strategy:**
```
You are a patient, logical math teacher creating step-by-step video scripts.

PEDAGOGY:
- Concepts: Concrete examples → abstract rules
- Problems: Worked examples with thinking aloud
- Practice: Question → guided steps → answer reveal

VISUAL GENERATION:
- Manim renders all visuals programmatically
- LaTeX for ALL equations
- Step-by-step reveals using WORKED_STEP
- Animations: number lines, shapes, graphs, fraction bars

SCENE VOCABULARY:
TITLE, SUBTITLE, TEXT, CLEAR, LATEX_INLINE, LATEX_BLOCK,
POLYGON, CIRCLE, RECTANGLE, TRIANGLE, ANGLE_ARC, AXES_2D,
PLOT_CURVE, NUMBER_LINE, FRACTION_BAR, GRID,
QUESTION_CARD, WORKED_STEP, ANSWER_REVEAL

OUTPUT: JSON array of ScriptScene objects with LaTeX equations.
```

### EVS / Science (Grade 1-5)
**Renderer:** Remotion + Images  
**LLM Model:** `openai/gpt-oss-120b` via Groq  
**Image Model:** `hidream-o1`  
**Video Model:** `h3-minimax-r2v`  
**TTS Model:** `text-to-speech`

**Prompt Strategy:**
```
You are a curious science guide encouraging observation and questioning.

PEDAGOGY:
- Concepts: Real-world connections + diagrams
- Processes: Cause-effect chains + labeled images
- Comparisons: Comparison tables + visual aids

VISUAL GENERATION:
- Use hidream-o1 for diagrams and photos
- Style: realistic, labeled, educational
- Prompts: "Diagram of water cycle with labels, educational illustration"
- Animation: Use h3-minimax-r2v for subtle motion (flowing water, growing plants)

SCENE VOCABULARY:
TITLE, SUBTITLE, TEXT, CLEAR, DIAGRAM, IMAGE, LABEL,
CAUSE_EFFECT_CHAIN, COMPARISON_TABLE, QUESTION_CARD, WORKED_STEP, ANSWER_REVEAL

OUTPUT: JSON array of ScriptScene objects with visual_prompts for each scene.
```

### Social (Grade 1-5)
**Renderer:** Remotion + Images  
**LLM Model:** `openai/gpt-oss-120b` via Groq  
**Image Model:** `hidream-o1`  
**Video Model:** `h3-minimax-r2v`  
**TTS Model:** `text-to-speech`

**Prompt Strategy:**
```
You are an engaging storyteller connecting past to present.

PEDAGOGY:
- History: Timelines + historical figures + primary sources
- Geography: Maps + markers + geographic features
- Civics: Comparison tables + cause-effect chains

VISUAL GENERATION:
- Use hidream-o1 for maps, historical figures, places
- Style: illustrative, map-like, historical
- Prompts: "Map of India with state boundaries, educational illustration"
- Animation: Use h3-minimax-r2v for map panning, timeline progression

SCENE VOCABULARY:
TITLE, SUBTITLE, TEXT, CLEAR, TIMELINE, MAP_MARKER,
HISTORICAL_FIGURE, GEOGRAPHIC_MAP, PRIMARY_SOURCE,
COMPARISON_TABLE, QUESTION_CARD, WORKED_STEP, ANSWER_REVEAL

OUTPUT: JSON array of ScriptScene objects with visual_prompts for each scene.
```

---

## 4. Visual Prompt Templates

### hidream-o1 (Text-to-Image)
```python
IMAGE_PROMPT_TEMPLATE = """
{subject} educational illustration for Grade {grade}: {description}.
Style: {style}
Mood: {mood}
Quality: high quality, clear, educational, textbook illustration
"""

# Example:
# "English educational illustration for Grade 1: children building sandcastle at beach"
# Style: cartoon, bright colors
# Mood: playful, sunny
```

### h3-minimax-r2v (Reference-to-Video)
```python
VIDEO_PROMPT_TEMPLATE = """
Animate this {subject} illustration: {description}.
Motion: {motion_type}
Camera: {camera_movement}
Pacing: {pacing}
Quality: smooth, educational, suitable for children
"""

# Example:
# "Animate this English illustration: children playing at beach"
# Motion: gentle wave movement, sandcastle building
# Camera: slow pan across scene
# Pacing: slow, gentle
```

---

## 5. Complete Pipeline Flow

```
PDF Input
  ↓
[1] EXTRACT (Marker / PyMuPDF / OpenDataLoader)
  ↓ ChapterNode
[2] ROUTE (Subject Router → English/Math/EVS/Social)
  ↓ ChapterNode + Subject
[3] SCRIPT (Groq LLM → ScriptScene list)
  ↓ ScriptScene list
[4] ASSETS (ModelsLab + Manim)
  ├── hidream-o1 → scene images
  ├── h3-minimax-r2v → image animation
  ├── Manim → math animations
  └── text-to-speech → voiceover audio
  ↓
[5] RENDER (Remotion / MoviePy / Manim)
  ↓
Final MP4 Video
```

---

## 6. Configuration Summary

**`.env` entries:**
```env
# LLM
GROQ_API_KEY=<REDACTED-SET-IN-ENV>

# ModelsLab
MODELSLAB_API_KEY=IDeCo2HNbL6x8p5DickQwqkwIN9C5F8xod0goQYddeBWMNWKQSJGzV7xRfSP
MODELSLAB_IMAGE_MODEL=hidream-o1
MODELSLAB_IMAGE_MODEL_I2I=hidream-o1
MODELSLAB_TTS_MODEL=text-to-speech
MODELSLAB_TTS_VOICE_ID=
MODELSLAB_VIDEO_MODEL=h3-minimax-start-end-frame
MODELSLAB_VIDEO_MODEL_R2V=h3-minimax-r2v

# AnyAPI (Subject Router)
ANYAPI_API_KEY=sk-NzDbxx2lufa8gpQj-72paQ
```

---

## 7. Implementation Checklist

- [x] `.env` updated with correct ModelsLab models
- [x] `modelslab_tts.py` created (v7 Voice API)
- [x] `modelslab_image.py` created (v7 Images API)
- [x] `modelslab_video.py` created (v7 Video Fusion API)
- [x] Skill `inkspectrum-script-generation` created
- [ ] `ScriptWriter` updated to load skill prompts
- [ ] `ScenePlanner` updated for renderer routing
- [ ] Demo script `demo_script_generation.py` created
- [ ] Integration test for all 3 subjects
- [ ] ModelsLab API validation tests

---

## 8. Next Steps

1. **Run demo:** `python packages/textbook-pipeline/scripts/demo_script_generation.py`
2. **Validate ModelsLab:** Test hidream-o1 image generation
3. **Validate ModelsLab:** Test h3-minimax-r2v video generation
4. **Validate ModelsLab:** Test text-to-speech generation
5. **Wire skill into ScriptWriter:** Load SKILL.md prompts dynamically
6. **Build Manim renderer:** For Math subjects
7. **Build Remotion renderer:** For English/EVS/Social
