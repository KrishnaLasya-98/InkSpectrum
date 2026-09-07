# InkSpectrum — Refined Technical Architecture with Agent Orchestration

## 1. Executive Summary

InkSpectrum is an AI-powered educational video generation pipeline that transforms K-10 textbook PDFs into polished, pedagogically sound video lectures. The system uses a multi-agent architecture where specialized AI agents—modeled after the `agency-agents` framework—orchestrate extraction, script generation, asset creation, and rendering.

**Core Principle:** Every pipeline stage is managed by a specialized agent with a defined personality, mission, rules, deliverables, and success metrics.

---

## 2. Agent Orchestration Layer

Inspired by: https://github.com/msitarzewski/agency-agents

### Agent Format

Each agent is defined as a Markdown skill file with the following structure:

```yaml
---
name: agent-name
description: One-line specialty description
emoji: 🎯
vibe: Personality hook
tools: [Tool1, Tool2]
---
```

Body sections:
1. **🧠 Identity & Memory** — Role, expertise, experience
2. **🎯 Core Mission** — Primary responsibilities
3. **🚨 Critical Rules** — Non-negotiables
4. **📋 Technical Deliverables** — Code templates, schemas
5. **🔄 Workflow Process** — Step-by-step methodology
6. **💭 Communication Style** — Tone, voice
7. **🎯 Success Metrics** — KPIs and benchmarks

### Agent Roster for InkSpectrum

| Agent | Division | Purpose | Tools/Skills |
|-------|----------|---------|--------------|
| **Extraction Agent** | `specialized/` | PDF → ChapterNode | Marker, PyMuPDF, OpenDataLoader |
| **Subject Router Agent** | `specialized/` | Chapter → Subject | AnyAPI LLM, keyword scoring |
| **Script Writer Agent** | `specialized/` | ChapterNode → ScriptScene | Groq LLM, SceneStep vocabulary |
| **Image Asset Agent** | `design/` | Script → hidream-o1 prompts | ModelsLab Image API, prompt engineering |
| **Video Asset Agent** | `specialized/` | Script → h3-minimax-r2v clips | ModelsLab Video API, motion design |
| **TTS Agent** | `engineering/` | Script → voiceover audio | ModelsLab Voice API |
| **Manim Renderer Agent** | `engineering/` | Math scenes → animation | Manim Community, LaTeX |
| **Remotion Renderer Agent** | `engineering/` | Scenes → React video | Remotion, MoviePy, FFmpeg |
| **QA Fidelity Agent** | `testing/` | Output vs source validation | Diff algorithms, LLM comparison |
| **Studio Producer Agent** | `project-management/` | End-to-end orchestration | Pipeline state, error recovery |

---

## 3. Updated Workflow Diagram

```
PDF Input
  ↓
[AGENT: Extraction Agent]
  ↓
ChapterNode (JSON)
  ↓
[AGENT: Subject Router Agent]
  ↓
ChapterNode + Subject Tag
  ↓
[AGENT: Script Writer Agent] ← Groq LLM (openai/gpt-oss-120b)
  ↓
ScriptScene List (JSON)
  ↓
┌─────────────────────────────────────────────────────────────┐
│                    ASSET GENERATION AGENTS                   │
├─────────────┬──────────────────┬─────────────────────────────┤
│   English   │      Math        │   EVS/Science    │   Social  │
├─────────────┼──────────────────┼─────────────────────────────┤
│[Image Agent]│                  │[Image Agent]      │[Image Agent]│
│ hidream-o1  │                  │ hidream-o1        │ hidream-o1 │
│Illustrations│[Manim Renderer]  │Diagrams           │Maps        │
│             │ Agent            │                   │            │
│             │ Manim + LaTeX    │                   │            │
│             │                  │                   │            │
│[Video Agent]│                  │[Video Agent]      │[Video Agent]│
│h3-minimax-  │                  │h3-minimax-r2v     │h3-minimax- │
│  r2v        │                  │                   │  r2v       │
│Scene motion │                  │Process animation  │Timeline    │
│             │                  │                   │panning     │
├─────────────┴──────────────────┴─────────────────────────────┤
│              [AGENT: TTS Agent]                              │
│           text-to-speech → voiceover audio                   │
└─────────────────────────────────────────────────────────────┘
  ↓
[AGENT: Remotion/MoviePy Renderer Agent]
  ↓
Final MP4 Video + Subtitles
  ↓
[AGENT: QA Fidelity Agent]
  ↓
Validated Output
```

---

## 4. Skills Coverage Matrix

| Pipeline Stage | Skill File | Covers | Status |
|---------------|-----------|--------|--------|
| **PDF Extraction** | `pdf`, `pdf-processing-pro`, `react-pdf` | PDF parsing, OCR, table extraction | ✅ Existing |
| **Subject Routing** | `prompt-engineering-patterns` | LLM classification prompts | ✅ Existing |
| **Script Generation** | `inkspectrum-script-generation` | LLM prompts, SceneStep vocabulary, renderer routing | ✅ Created |
| **Image Generation** | `modelslab-image-generation`, `ai-image-generation`, `image-enhancer`, `canvas-design` | hidream-o1 T2I/I2I, prompt templates, enhancement | ✅ Existing |
| **Video Generation** | `modelslab-video-generation`, `ai-video-generation`, `video-edit` | h3-minimax-start-end-frame, h3-minimax-r2v, motion design | ✅ Existing |
| **TTS/Audio** | `modelslab-audio-generation`, `godot-audio`, `music-video-subtitle-generator`, `add-sfx` | text-to-speech, voice selection, audio mixing | ✅ Existing |
| **Math Rendering** | `manimce-best-practices`, `manim-video` | Manim scenes, LaTeX, animations | ✅ Existing |
| **Video Rendering** | `video-use`, `ffmpeg`, `hyperframes-cli` | Remotion, MoviePy, FFmpeg composition | ✅ Existing |
| **QA/Fidelity** | `prompt-engineering-patterns` | Content verification, diff, LLM comparison | ✅ Existing |
| **Orchestration** | `workflow-orchestration-patterns`, `agent-orchestration-improve-agent`, `managed-deep-agents` | Pipeline state, error recovery, agent coordination | ✅ Existing |

---

## 5. Agent Definitions

### 5.1 Extraction Agent

```yaml
---
name: inkspectrum-extraction
description: Extract structured chapter data from PDFs using Marker, PyMuPDF, or OpenDataLoader
emoji: 📄
tools: [Marker, PyMuPDF, OpenDataLoader]
---
```

**Identity:** Expert document analyst specializing in educational PDFs  
**Mission:** Convert raw PDFs into clean, structured ChapterNode JSON with sections, figures, and page ranges  
**Rules:**
- Preserve reading order
- Extract images with bounding boxes
- Filter headers/footers/noise
- Validate page ranges
- Fallback from Marker → PyMuPDF on failure

**Deliverables:** `ChapterNode` JSON, extraction report with confidence scores

---

### 5.2 Subject Router Agent

```yaml
---
name: inkspectrum-subject-router
description: Classify textbook content into English, Math, EVS, or Social
emoji: 🎯
tools: [AnyAPI LLM, Keyword Scoring]
---
```

**Identity:** Pedagogical content classifier  
**Mission:** Route extracted content to the correct subject-specific pipeline  
**Rules:**
- Three-tier fallback: filename → keywords → LLM
- Never guess — return UNKNOWN if ambiguous
- Log confidence score

**Deliverables:** `Subject` enum, confidence score, classification rationale

---

### 5.3 Script Writer Agent

```yaml
---
name: inkspectrum-script-writer
description: Convert ChapterNode into pedagogical video scripts with narration and visuals
emoji: 🎬
tools: [Groq LLM, SceneStep Vocabulary, ModelsLab Prompts]
---
```

**Identity:** Expert educational video scriptwriter  
**Mission:** Transform chapter structure into scene-by-scene video scripts  
**Rules:**
- Preserve textbook text VERBATIM
- Use ONLY allowed SceneStepType values per subject
- Include visual prompts for EVERY scene
- Estimate realistic speaking duration
- Add pedagogical notes for QA

**Deliverables:** `ScriptScene` list, visual prompts, timing data

---

### 5.4 Image Asset Agent

```yaml
---
name: inkspectrum-image-asset
description: Generate and manage scene illustrations using hidream-o1
emoji: 🎨
tools: [ModelsLab Image API, Prompt Engineering]
---
```

**Identity:** Educational illustration director  
**Mission:** Create or select appropriate images for each scene  
**Rules:**
- Use hidream-o1 for all generation
- Match style to subject (cartoon for English, diagram for EVS, map for Social)
- Preserve content fidelity — no hallucinated elements
- Cache generated assets by scene ID

**Deliverables:** Image URLs, asset manifest, style consistency report

---

### 5.5 Video Asset Agent

```yaml
---
name: inkspectrum-video-asset
description: Animate static images into video clips using h3-minimax-r2v
emoji: 🎥
tools: [ModelsLab Video API, Motion Design]
---
```

**Identity:** Educational motion designer  
**Mission:** Add subtle, pedagogically appropriate motion to static assets  
**Rules:**
- Use h3-minimax-r2v for reference-to-video animation
- Motion must serve learning, not distract
- Max 4-8 seconds per clip
- Sync motion to narration timing

**Deliverables:** Video URLs, motion descriptions, timing alignment

---

### 5.6 TTS Agent

```yaml
---
name: inkspectrum-tts
description: Convert script narration to natural-sounding voiceover audio
emoji: 🔊
tools: [ModelsLab Voice API]
---
```

**Identity:** Audio producer and voice director  
**Mission:** Generate clear, engaging voiceover for all narration text  
**Rules:**
- Use text-to-speech model by default
- Match voice characteristics to subject/grade
- Generate word-level timestamps for subtitle sync
- Normalize audio levels across scenes

**Deliverables:** Audio URLs, subtitle SRT, word-level timestamps

---

### 5.7 Manim Renderer Agent

```yaml
---
name: inkspectrum-manim-renderer
description: Render Math scenes using Manim Community Edition
emoji: 📐
tools: [Manim, LaTeX, Python]
---
```

**Identity:** Mathematical visualization specialist  
**Mission:** Produce precise, animated math visuals  
**Rules:**
- ALL equations must be LaTeX-rendered
- Use constrained SceneStepType vocabulary
- Sync animations to narration timing
- Output 1080p 30fps video segments

**Deliverables:** Manim scene files, rendered video segments, LaTeX source

---

### 5.8 Remotion Renderer Agent

```yaml
---
name: inkspectrum-remotion-renderer
description: Composite final video using Remotion, MoviePy, and FFmpeg
emoji: 🎞️
tools: [Remotion, MoviePy, FFmpeg]
---
```

**Identity:** Video production compositor  
**Mission:** Assemble all assets into final polished video  
**Rules:**
- Follow ScriptScene timing exactly
- Layer: background → images → text → animations → audio → subtitles
- Output 1080p 30fps MP4 with burned-in subtitles
- Quality check: no dropped frames, audio sync

**Deliverables:** Final MP4, SRT subtitles, production manifest

---

### 5.9 QA Fidelity Agent

```yaml
---
name: inkspectrum-fidelity
description: Verify generated content matches source material
emoji: ✅
tools: [Diff Algorithms, LLM Comparison]
---
```

**Identity:** Quality assurance auditor  
**Mission:** Ensure 100% content fidelity from source to final video  
**Rules:**
- Compare extracted text against source PDF
- Verify all images are present and correctly captioned
- Check narration matches textbook verbatim
- Flag hallucinations, omissions, reorderings

**Deliverables:** Fidelity report, pass/fail score, discrepancy list

---

### 5.10 Studio Producer Agent

```yaml
---
name: inkspectrum-studio-producer
description: Orchestrate the entire pipeline from PDF to final video
emoji: 🎬
tools: [Pipeline State, Error Recovery, Agent Coordination]
---
```

**Identity:** End-to-end pipeline orchestrator  
**Mission:** Coordinate all agents, manage state, handle failures  
**Rules:**
- Never skip QA gates
- Retry failed stages with exponential backoff
- Log all agent interactions for debugging
- Provide progress updates to user

**Deliverables:** Final video package, pipeline manifest, agent execution log

---

## 6. Complete Pipeline with Agents

```
PDF Input
  ↓
[Studio Producer Agent] ← Orchestrates all stages
  ↓
[Extraction Agent] → ChapterNode
  ↓
[Subject Router Agent] → Subject Tag
  ↓
[Script Writer Agent] → ScriptScene List
  ↓
[Image Asset Agent] → Scene Images (hidream-o1)
[Video Asset Agent] → Scene Videos (h3-minimax-r2v)
[TTS Agent] → Voiceover Audio (text-to-speech)
[Manim Renderer Agent] → Math Animations (Manim)
  ↓
[Remotion Renderer Agent] → Final MP4
  ↓
[QA Fidelity Agent] → Validation Report
  ↓
Final Output
```

---

## 7. Subject-Specific Agent Routing

| Subject | Primary Renderer | Image Model | Video Model | Specialized Agent |
|---------|------------------|-------------|-------------|-------------------|
| English | Remotion | hidream-o1 | h3-minimax-r2v | Image Asset Agent |
| Math | Manim | — | — | Manim Renderer Agent |
| EVS/Science | Remotion | hidream-o1 | h3-minimax-r2v | Image Asset Agent |
| Social | Remotion | hidream-o1 | h3-minimax-r2v | Image Asset Agent |

---

## 8. Configuration Reference

### .env Variables

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

### Model Endpoints

| Service | Endpoint | Model ID |
|---------|----------|----------|
| ModelsLab Image T2I | `POST /api/v7/images/text-to-image` | `hidream-o1` |
| ModelsLab Image I2I | `POST /api/v7/images/image-to-image` | `hidream-o1` |
| ModelsLab Video T2V | `POST /api/v7/video-fusion/text-to-video` | `h3-minimax-start-end-frame` |
| ModelsLab Video I2V | `POST /api/v7/video-fusion/image-to-video` | `h3-minimax-r2v` |
| ModelsLab TTS | `POST /api/v7/voice/text-to-speech` | `text-to-speech` |
| Groq LLM | `https://api.groq.com/openai/v1` | `openai/gpt-oss-120b` |
| AnyAPI Router | `https://api.anyapi.ai/v1` | `qwen3.8-27b` |

---

## 9. Implementation Checklist

### Phase 1: Foundation ✅
- [x] Unified `textbook_pipeline` package structure
- [x] Fixed PyMuPDF extractor with image extraction
- [x] Created ModelsLab API clients (TTS, Image, Video)
- [x] Updated `.env` with correct model IDs
- [x] Created `inkspectrum-script-generation` skill
- [x] Verified all pipeline skills exist in `.kilo/skills/`

### Phase 2: Agent Orchestration ⏳
- [ ] Create `inkspectrum-extraction` agent skill (wraps `pdf`, `pdf-processing-pro`, `react-pdf`)
- [ ] Create `inkspectrum-subject-router` agent skill (wraps `prompt-engineering-patterns`)
- [ ] Create `inkspectrum-image-asset` agent skill (wraps `modelslab-image-generation`, `ai-image-generation`)
- [ ] Create `inkspectrum-video-asset` agent skill (wraps `modelslab-video-generation`, `ai-video-generation`)
- [ ] Create `inkspectrum-tts` agent skill (wraps `modelslab-audio-generation`)
- [ ] Create `inkspectrum-manim-renderer` agent skill (wraps `manimce-best-practices`, `manim-video`)
- [ ] Create `inkspectrum-remotion-renderer` agent skill (wraps `video-use`, `ffmpeg`)
- [ ] Create `inkspectrum-fidelity` agent skill (wraps `prompt-engineering-patterns`)
- [ ] Create `inkspectrum-orchestrator` agent skill (wraps `workflow-orchestration-patterns`)
- [ ] Wire all agents into `StudioProducer` orchestrator

### Phase 3: Renderer Implementation ⏳
- [ ] Build Manim renderer for Math scenes
- [ ] Build Remotion renderer for English/EVS/Social
- [ ] Implement asset download/caching layer
- [ ] Implement FFmpeg final assembly

### Phase 4: Validation & Testing ⏳
- [ ] Test Marker on all 3 PDFs (English, EVS, Math)
- [ ] Validate ModelsLab APIs (image, video, TTS)
- [ ] End-to-end pipeline test: PDF → final video
- [ ] Fidelity audit on generated content

---

## 10. Immediate Next Steps

1. **Create remaining agent skills** — Extract, Subject Router, Image Asset, Video Asset, TTS, Manim, Remotion, QA, Orchestrator
2. **Build Studio Producer orchestrator** — Wire all agents into a state machine with retry/fallback logic
3. **Test Marker on Math PDF** — Validate extraction quality for math equations and images
4. **Validate ModelsLab APIs** — Test hidream-o1, h3-minimax-r2v, and text-to-speech with real API keys
5. **Run full pipeline demo** — English PDF → script → assets → render → video
6. **Build Manim renderer** — Start with Math Grade 1 content
7. **Build Remotion renderer** — Start with English Grade 1 content

---

## 11. System Summary

**InkSpectrum** is a multi-agent educational video generation system that:

1. **Extracts** textbook structure from PDFs using Marker/PyMuPDF
2. **Routes** content to subject-specific pipelines via LLM classification
3. **Generates** pedagogical scripts using Groq LLM with constrained SceneStep vocabulary
4. **Creates** assets via ModelsLab:
   - `hidream-o1` for illustrations
   - `h3-minimax-r2v` for image animation
   - `text-to-speech` for voiceover
5. **Renders** final videos via Manim (Math) or Remotion (English/EVS/Social)
6. **Validates** content fidelity against source material

**Key Innovation:** The agent orchestration layer ensures each stage is handled by a specialized expert with defined rules, deliverables, and success metrics—preventing the “generic AI” failure mode where one model tries to do everything.

**Model Stack:**
- LLM: `openai/gpt-oss-120b` (Groq)
- Image: `hidream-o1` (ModelsLab)
- Video: `h3-minimax-r2v` (ModelsLab)
- TTS: `text-to-speech` (ModelsLab)
- Extraction: Marker + PyMuPDF
