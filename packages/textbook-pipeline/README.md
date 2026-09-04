# Textbook Pipeline

Transform K-10 textbook PDFs (English, Math, Science/EVS) into chapter-by-chapter video lectures.

## What This Does

```
PDF (textbook)
  ↓  [1] Docling ingestion (layout-aware parsing)
Chapter tree (theoretical sections + exercise sections)
  ↓  [2] Pedagogical layer (subject routing, exercise detection, learning objectives)
Scripted scenes (narration + visual plan)
  ↓  [3] Scene vocabulary (constrained primitives, deterministic rendering)
Rendered video (Remotion)
  ↓  [4] TTS + subtitles + assembly
Final chapter video (.mp4)
```

## Status

**Phase 1 (in progress):** English, Math, Social/EVS
**Phase 2 (deferred):** GK, additional subjects

## Architecture

Built by composing the best parts of four proven repos:

| Repo | Used for |
|---|---|
| [docling-project/docling](https://github.com/docling-project/docling) | PDF parsing (layout, tables, formulas, figures) |
| [prajwal-y/video_explainer](https://github.com/prajwal-y/video_explainer) | Remotion scaffold + audio pipeline |
| [showlab/Code2Video](https://github.com/showlab/Code2Video) | Optional Manim renderer for math chapters |
| [lcy362/agnes-video-generator](https://github.com/lcy362/agnes-video-generator) | Multi-scene pipeline + character system |

The pedagogical layer (chapter grouping, exercise detection, subject routing, learning objectives) is original to this repo — no upstream covers it.

## Quick Start

```bash
# Install
pip install -e .

# Configure API keys
cp .env.example .env
# edit .env with your keys

# Run
python -m textbook_pipeline generate \
    --pdf path/to/textbook.pdf \
    --chapter 3 \
    --output projects/my_chapter
```

## Repo Structure

```
textbook-pipeline/
├── lib/                       # Core product code (the IP)
│   ├── textbook_ingest/      # Chapter grouping + exercise detection + subject routing
│   ├── scene_vocabulary/     # Constrained scene primitives (LLM output contract)
│   ├── script_writer/        # Two-track pedagogical script generator
│   ├── renderers/
│   │   ├── remotion/         # Primary renderer
│   │   └── manim/            # Optional, math-heavy chapters
│   ├── tts/                  # Edge TTS + ElevenLabs wrapper
│   ├── subtitles/            # SRT generation
│   └── compositor/           # ffmpeg/moviepy final assembly
├── wrappers/                 # Thin wrappers around external repos
├── prompts/                  # Versioned LLM prompt templates
├── schemas/                  # Pydantic + TS type definitions
├── data/
│   ├── subjects/             # Subject-specific templates (math/english/social)
│   └── grades/               # Grade-appropriate vocabulary
├── projects/                 # Generated lesson outputs (gitignored)
├── tests/
├── docs/
└── cli.py                    # Single CLI entry point
```

## License

MIT