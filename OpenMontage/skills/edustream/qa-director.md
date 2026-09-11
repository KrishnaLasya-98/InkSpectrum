# Stage Director: quality_assurance (EduStream Pro)

## Overview
Execute the final-stage quality assurance for EduStream Pro chapter videos.
This stage runs **FinalStageDirector** — a six-layer inspection that produces
an `agent_tour.md` report the agent reads to understand the finished video
completely before presenting it to the user.

## Gate
- **human_approval_default: true** (HUMAN GATE)
- Present the agent tour summary to the user before asking for approval.

---

## What This Stage Produces

| Artifact | Path | Purpose |
|---|---|---|
| `agent_tour.md` | `artifacts/agent_tour.md` | Plain-language tour — read this first |
| `final_review.json` | `artifacts/final_review.json` | Schema-valid final_review artifact |
| `qa_report.json` | `artifacts/qa_report.json` | Detailed QA check results |
| `narration_aligned.json` | `artifacts/narration_aligned.json` | Word-level audio timestamps |
| `word_captions.json` | `artifacts/word_captions.json` | Remotion CaptionOverlay props |
| `formatted_subtitles.srt` | `renders/formatted_subtitles.srt` | Properly phrased word-timed SRT |
| `qa_card_props.json` | `artifacts/qa_card_props.json` | EduQAScene card props with audio-derived reveal timings |
| Frame snapshots | `renders/snapshots/frame_*.jpg` | 6 visual grabs at key positions |
| Export bundle | `exports/{subject}/` | Final video + SRT + metadata.json + chapters.txt |

---

## Step-by-Step

### 1. Run FinalStageDirector

```python
from tools.analysis.final_stage_director import FinalStageDirector
result = FinalStageDirector().execute({
    "video_path":           "projects/evs/renders/{subject}_chapter.mp4",
    "srt_path":             "projects/evs/renders/formatted_subtitles.srt",
    "subject":              "evs",       # or "english" / "maths" / any registered subject
    "chapter_title":        "Animal Life",
    "narration_manifest":   narration_manifest,
    "educational_plan":     educational_plan,
    "clip_manifest":        clip_manifest,
    "evs_alignment":        evs_script["A"],
    "scenes":               educational_plan["sections"],
    "title_offset_seconds": 3.0,         # title card duration
    "output_dir":           "projects/evs",
})
```

### 2. Read the agent tour

The tour is printed to stdout automatically AND saved to `artifacts/agent_tour.md`.
Read it top to bottom. It covers:

```
Layer 1  Technical probe     — duration, codec, fps, resolution, audio stream present
Layer 2  Visual spotcheck    — 6 frame grabs + black frame detection
Layer 3  Audio spotcheck     — LUFS level, silence detection, clipping check
Layer 4  Subtitle check      — SRT coverage ratio, timing drift
Layer 5  Content fidelity    — section count, WPM per segment, failed clips
Layer 6  QA gate summary     — pacing / audio sync / WCAG contrast / slideshow risk / WPM
```

### 3. Interpret status and act

| Status | Meaning | Action |
|---|---|---|
| `pass` + `present_to_user` | All checks green | Present to user with export bundle path |
| `revise` + `revise_edit` | Subtitle timing drift or low coverage | Rerun `NarrationTextSyncer` then `AVComposer` |
| `revise` + `revise_assets` | One or more clips failed | Fix the failing section, rerun `RenderModeRouter` for that section only |
| `fail` + `re_render` | No audio stream or corrupt container | Fix `AVComposer` inputs and rerun Stage 5 |
| `fail` + `block` | Multiple critical failures | Rerun from Stage 3 |

### 4. Text/audio sync check (new — most common source of issues)

The `NarrationTextSyncer` (Stage 4b) produces word-level alignment so:
- Each word in a subtitle appears **exactly when it is spoken**, not at section start
- Q&A answer cards reveal **exactly when the narrator says the answer word**
- Subtitles are phrased in 4–7 word chunks respecting sentence boundaries

If the `formatted_subtitles.srt` was used by `AVComposer`, the subtitle check
in Layer 4 will show `coverage_ratio > 0.9` and `timing_drift_detected: false`.

If alignment used linear interpolation (no WhisperX installed), timing will be
approximately correct but not exact. Install WhisperX for production:
```bash
pip install whisperx torch
```

### 5. Present to user

When `status == "pass"`:

```
## Stage Complete: quality_assurance — awaiting your approval

### Video Details
- Subject: EVS — Animal Life
- Duration: 8m 12s
- Resolution: 1920×1080 @ 30fps
- Audio: present, -14.0 LUFS (target met)
- Subtitles: 94% coverage, word-timed

### QA Results
✅ Pacing: all clips 3–60s
✅ Audio sync: max drift 45ms (< 200ms threshold)
✅ Contrast: all 7 colour pairs pass WCAG 4.5:1
✅ Slideshow risk: 0.18 (strong)
✅ Narration WPM: all segments 110–135 WPM

### Export Bundle
projects/evs/exports/
  video/output.mp4           — final video
  video/subtitles.srt        — word-timed subtitles
  metadata/metadata.json     — title, tags, chapters
  metadata/chapters.txt      — chapter timestamps
  snapshots/frame_*.jpg      — 6 visual reference frames

### Cost: $0.00 (all open-source models)

Please review the frame snapshots and approve to complete.
```

END YOUR TURN and wait for user approval.

---

## Text Formatting Rules (how text appears on screen)

These are enforced by `NarrationTextSyncer` + `EduQAScene`:

| Content type | Font size | Highlight colour | Words per line |
|---|---|---|---|
| Concept explanations | 64px | Orange `#FF8C42` | 6 |
| Q&A questions | 52px | Coral `#FF6B9D` | 5 |
| Fill-in-blank answers | 56px | Coral `#FF6B9D` | 4 |
| MCQ choices | 44px | Green `#6BCB77` (correct) | 6 |
| Glossary terms | 52px | Yellow `#FFD93D` | 5 |
| Recall summaries | 48px | Teal `#4ECDC4` | 6 |
| Chapter titles | 72px | Orange `#FF8C42` | 4 |

All text uses Nunito font (graceful fallback to DejaVu Sans if not installed).
Background: warm cream `#FFFDF0` with `rgba(255,253,240,0.90)` caption backing.
Subtitle blocks: max 2 lines, min 400ms display, 80ms gap between blocks.
