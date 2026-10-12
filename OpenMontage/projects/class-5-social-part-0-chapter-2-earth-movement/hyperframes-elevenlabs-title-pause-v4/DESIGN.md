# Educational HyperFrames Design Contract

## Template Lock

- ID: `hyperframes-educational-v1`
- Version: `1.0.3`
- Status: `locked`
- Presentation contract: `source-faithful-book-v1`
- Canonical SHA-256: `75eed8d0e813ef1b6523d247b6b6c49b46cc209930ebdab02a595d24627757fb`

## Style Prompt

A warm, source-faithful classroom film for young learners. Full-frame motion carries the story while compact cream teaching panels explain only the current textbook idea. The frame has clear edge anchors, generous safe areas, readable hierarchy, and one stable word-highlight subtitle lane.

## Colors

- Cream `#FFF9ED`: teaching panels and subtitle lane
- Ink `#123247`: primary text
- Teaching accent `#A83C2D`: headings and rules
- Active word `#B64132`: currently spoken word
- Inactive word `#526B78`: surrounding subtitle words

## Typography

- Source reading voice: Georgia, 400 and 700 weights
- Labels and subtitle voice: Nunito, Segoe UI, 400 and 700 weights
- Body text is never smaller than 28 px; display titles are at least 64 px.

## Motion

- Gentle 0.55-second crossfades connect related sections.
- Every section label and teaching panel receives a deterministic entrance.
- No pre-transition exits; the crossfade performs the visual handoff.
- Captions enter gently, highlight the measured active word, and receive a hard timed kill.

## Fixed Layout

- Source-derived label attached to its teaching panel
- Compact cream teaching panel in the top-right safe area for story scenes
- Full-frame animated teaching footage where motion is required
- Stable cream word-highlight subtitle lane in the bottom safe area
- Source-faithful centered reading treatment for recall, glossary, and assessment content

## What NOT to Do

- Do not override the chapter palette, spacing, component positions, or typography.
- Do not add invented labels, decorative copy, watermarks, or embedded media text.
- Do not play generated-video audio or place narration inside a video element.
- Do not loop or reuse story clips to fill missing motion.
- Do not cover faces or textbook prompts with the subtitle lane.

## Approved Class 5 Social Chapter 1 presentation

Use the verified Chapter 1 revision-v4 mint canvas, cream cards, left heading label, source figure layout, and bottom word-highlight lane. No dark-navy empty backgrounds or red hanging tabs.
