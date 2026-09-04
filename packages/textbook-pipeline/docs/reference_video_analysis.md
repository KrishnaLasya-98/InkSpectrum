# Reference Video Analysis

## Extracted from `D:\video_pipeline\write_script\FILM_APPROACH_ANALYSIS.md`

---

## Reference Videos

| # | Title | URL | Format | Key Style Traits |
|---|-------|-----|--------|------------------|
| 1 | Dr. Binocs - AI Explained | https://youtu.be/ttIOdAdQaUE | Character-driven 2D explainer | Fast-paced, host stays on-screen, bold text overlays synced to narration, limited character animation (expressions/gestures), energetic audio |
| 2 | English Easy Practice - Conversation Learning | https://youtu.be/1pUzaV33YCM | Two-character dialogue | Static character images, word-by-word highlighting, slower educational pace with repetition, listen-and-repeat structure, Q&A with thinking pauses |
| 3 | ChatGPT Animation Workflow Tutorial | https://youtu.be/TBYgP1afb9Q | Step-by-step AI production workflow | Shot-by-shot structure (narration + description + image prompt + video prompt), image→video pipeline, character reference re-upload for consistency, audio-first assembly, auto-captions, cross-dissolve transitions |

---

## Subject / Content Information

| Field | Value |
|-------|-------|
| **Primary Subject** | English Language Learning / Storytelling |
| **Lesson Context** | "Lesson 10" — narrative/story lesson featuring characters "Swami" (elderly Indian monk) and "Devotee" (young Indian man) |
| **Pedagogical Approach** | Film-like educational video: character-driven narrative + Q&A + vocabulary emphasis + repetition |
| **Visual Themes** | 3D cartoon educational illustration, peaceful hermitage on Ganges riverbank, warm golden-hour lighting, cinematic composition |
| **Character Design** | Swami: elderly Indian monk, saffron robe, white beard, kind smile; Devotee: young adult Indian man, white kurta, red tilak, folded hands |
| **Technical Pipeline Referenced** | Piper TTS → Whisper timestamps → Qwen images → Wan 2.2 I2V → FFmpeg compositing → Pillow text burn-in |
| **Pacing Rules** | 120–150 WPM narration, 2–5s image shots, 2–3s video shots for emotional beats, 0.3s cross-dissolve transitions, Ken Burns effect on stills |
| **Audio Strategy** | Narration-first timing, word-level sync, background music (low volume), sound effects |

---

## Core Production Principles

1. **TTS-First Pipeline**: Generate narration audio first, extract word-level timestamps, then time visuals to audio.
2. **Character Introduction Timing**: Characters appear exactly when first mentioned in narration.
3. **Shot Duration Rules**: Images 2–5s, videos 2–3s for emotional beats, 5s scenes = 2 images with cross-dissolve.
4. **Visual Pacing**: 120–150 WPM, hold shots for comprehension, simple cuts, Ken Burns on stills.
5. **Clean Composition**: No visual tax — remove secondary characters unless story-critical, simple backgrounds.
6. **Text Overlay Strategy**: Sync to audio, highlight key terms, Q&A format with thinking pauses.
7. **Audio-Visual Synchronization**: Every visual change corresponds to a narration beat.

---

## Shot Structure Template

```
Scene N:
  Shot 1:
    Narration: "..."
    Description: ...
    Image Prompt: "..."
    Video Prompt: "..."
    Duration: Xs
    Audio Sync: trigger word/time
```

---

*Saved for use as a reference guide in pipeline design and QA.*
