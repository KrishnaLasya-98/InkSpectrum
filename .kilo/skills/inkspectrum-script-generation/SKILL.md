---
name: inkspectrum-script-generation
description: Generate pedagogical video scripts for K-10 textbooks. Use when converting ChapterNode into ScriptScene lists with narration, visuals, timing, and renderer-specific constraints for Remotion, Manim, and ModelsLab asset generation.
---

# InkSpectrum Script Generation Skill

Generate production-ready video scripts from extracted textbook chapters. This skill defines the LLM prompt contract, renderer constraints, and model-specific requirements for image/video generation.

## When to Use

- Converting `ChapterNode` → `ScriptScene` list
- Generating narration text for TTS
- Creating visual descriptions for image/video generation
- Planning scene timing and transitions
- Routing subjects to correct renderer (Remotion vs Manim)

## LLM Configuration

**Model:** `openai/gpt-oss-120b` via Groq  
**Temperature:** 0.3  
**Max retries:** 2  
**Context window:** 8192 tokens

## Renderer Routing

| Subject | Renderer | Reason |
|---------|----------|--------|
| Math | Manim | Equation-heavy, precise animations |
| English | Remotion | Text-centric, illustrations, vocabulary cards |
| EVS/Science | Remotion + Images | Diagrams, photos, labeled illustrations |
| Social | Remotion + Images | Maps, timelines, historical figures |
| Hindi/Other | Remotion | Text + illustrations |

## SceneStep Vocabulary by Subject

### Universal (All Subjects)
- `TITLE` - Big centered title card
- `SUBTITLE` - Secondary text
- `TEXT` - Body text / narration
- `CLEAR` - Wipe before next concept

### Math (Manim Renderer)
- `LATEX_INLINE` - Inline equation
- `LATEX_BLOCK` - Display equation
- `POLYGON` / `CIRCLE` / `RECTANGLE` / `TRIANGLE` - Geometry shapes
- `ANGLE_ARC` - Angle markers
- `AXES_2D` / `AXES_3D` - Coordinate systems
- `PLOT_CURVE` - Function graphs
- `NUMBER_LINE` - Number line with marks
- `FRACTION_BAR` - Visual fractions
- `GRID` - Grid background
- `WORKED_STEP` - Step-by-step solution
- `ANSWER_REVEAL` - Final answer highlight
- `QUESTION_CARD` - Exercise question

### English (Remotion Renderer)
- `WORD_HIGHLIGHT` - Highlight word in sentence
- `SENTENCE_TOKEN` - Break into tokens
- `VOCABULARY_CARD` - Word + definition + example
- `PRONUNCIATION_GUIDE` - Phonetic guide
- `POEM_CARD` - Poem display
- `DIALOGUE_BUBBLE` - Character dialogue
- `STORYBOARD_FRAME` - Story scene

### EVS/Science (Remotion + Images)
- `DIAGRAM` - Labeled diagram
- `IMAGE` - Photograph/illustration
- `LABEL` - Annotation callout
- `CAUSE_EFFECT_CHAIN` - Process flow
- `COMPARISON_TABLE` - Compare/contrast

### Social (Remotion + Images)
- `TIMELINE` - Historical timeline
- `MAP_MARKER` - Location on map
- `HISTORICAL_FIGURE` - Person card
- `GEOGRAPHIC_MAP` - Region map
- `PRIMARY_SOURCE` - Historical document

## ModelsLab Integration

### Image Generation
**Model:** `hidream-o1`  
**Endpoint:** `POST /api/v7/images/text-to-image`  
**Use for:** Scene illustrations, diagrams, vocabulary cards, story scenes

**Prompt format for LLM:**
```
VISUAL: Generate an illustration of [description].
Style: [cartoon/realistic/diagram]
Mood: [bright/calm/playful]
```

### Video Generation
**Model:** `h3-minimax-start-end-frame` (start-end frame)  
**Model:** `h3-minimax-r2v` (reference-to-video)  
**Endpoint:** `POST /api/v7/video-fusion/image-to-video`  
**Use for:** Animating static images, scene motion

**Prompt format for LLM:**
```
ANIMATION: Animate [image description].
Motion: [camera pan/zoom/object movement]
Duration: 4-8 seconds
Style: [smooth/subtle]
```

### TTS
**Model:** `text-to-speech`  
**Endpoint:** `POST /api/v7/voice/text-to-speech`  
**Voice:** Configurable via `MODELSLAB_TTS_VOICE_ID`  
**Use for:** All narration voiceover

## Subject-Specific Pedagogical Strategies

### English Grade 1-3
- **Tone:** Warm, encouraging, playful
- **Pacing:** Slow, with pronunciation pauses
- **Scenes:** 
  - Phonics → vocabulary cards + word highlight
  - Stories → storyboard frames + dialogue bubbles
  - Poems → poem cards with rhythm cues
- **Visuals:** Bright colors, simple illustrations, large text

### Math Grade 1-5
- **Tone:** Patient, logical, step-by-step
- **Pacing:** Deliberate, with thinking time
- **Scenes:**
  - Concepts → Manim animations (shapes, numbers, axes)
  - Examples → WORKED_STEP with numbered steps
  - Practice → QUESTION_CARD → ANSWER_REVEAL
- **Visuals:** Clean diagrams, numbered steps, highlighted answers

### EVS/Science Grade 1-5
- **Tone:** Curious, wonder-driven, observational
- **Pacing:** Moderate, with discovery pauses
- **Scenes:**
  - Concepts → Diagrams + IMAGE + LABEL
  - Processes → CAUSE_EFFECT_CHAIN
  - Comparisons → COMPARISON_TABLE
- **Visuals:** Realistic images, labeled diagrams, nature scenes

### Social Grade 1-5
- **Tone:** Storytelling, empathetic, connective
- **Pacing:** Narrative flow, reflective pauses
- **Scenes:**
  - History → TIMELINE + HISTORICAL_FIGURE
  - Geography → MAP_MARKER + GEOGRAPHIC_MAP
  - Civics → PRIMARY_SOURCE + comparison tables
- **Visuals:** Maps, historical photos, timelines

## Prompt Template

```
You are an expert educational video scriptwriter for Grade {grade} {subject}.

INPUT CHAPTER:
{chapter_json}

PEDAGOGICAL STRATEGY:
{subject_strategy}

RENDERER: {renderer}
SCENE VOCABULARY: {allowed_step_types}

MODELS LAB ASSETS:
- Images: Use hidream-o1 for illustrations
- Video: Use h3-minimax-r2v for image animation
- Audio: Use ModelsLab TTS for voiceover

OUTPUT FORMAT:
{script_schema_json}

CRITICAL RULES:
1. Preserve textbook text VERBATIM in narration
2. Use ONLY allowed SceneStepType values
3. Include visual descriptions for ALL scenes
4. Estimate realistic speaking duration
5. Add pedagogical notes for QA
6. For Math: ALWAYS use Manim renderer with LaTeX
7. For English: Use vocabulary cards and story frames
8. For EVS/Science: Use diagrams and real images
9. For Social: Use maps and timelines
```

## Output Schema

```json
[
  {
    "id": "scene_001",
    "title": "Introduction",
    "section_ref": "sec_1",
    "section_type": "theoretical",
    "render_mode": "remotion",
    "estimated_duration": 15.0,
    "voiceover_lines": [
      {
        "text": "Narration text here",
        "duration_seconds": 5.0,
        "pause_after": 0.5
      }
    ],
    "scene_steps": [
      {
        "at": 0,
        "type": "TITLE",
        "text": "Lesson 1",
        "size": "xl",
        "color": "saffron"
      },
      {
        "at": 3,
        "type": "VOCABULARY_CARD",
        "text": "beach",
        "definition": "sandy shore by the ocean",
        "example": "We played on the beach."
      }
    ],
    "visual_prompts": [
      {
        "type": "image",
        "model": "hidream-o1",
        "prompt": "Children building a sandcastle at a sunny beach, cartoon style, bright colors",
        "negative_prompt": "blurry, dark, scary"
      }
    ],
    "notes": "Pedagogical notes for QA"
  }
]
```

## Quality Checklist

Before returning script JSON, ensure:
- [ ] All narration preserves textbook text verbatim
- [ ] Scene steps use ONLY allowed vocabulary for the subject
- [ ] Every scene has at least one visual prompt
- [ ] Durations are realistic for Grade level
- [ ] Math equations are in LaTeX format
- [ ] Images use hidream-o1 with appropriate style prompts
- [ ] Video animations use h3-minimax-r2v with motion descriptions
- [ ] TTS text is clean, punctuation-complete sentences
