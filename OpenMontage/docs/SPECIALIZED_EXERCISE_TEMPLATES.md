# Matching and diagram-label templates

These are content slots in the shared HyperFrames reading panel, not
chapter-specific CSS. Existing subtitle, title-pause, question, thinking and
answer timing remains authoritative. Specialized exercises use the larger
stable reading panel even if a background clip exists.

## Matching

Add `qa_format: matching` and this data to a reviewed question:

```json
"exercise_visual": {
  "kind": "matching",
  "left": [{"id": "cat", "text": "Cat"}, {"id": "dog", "text": "Dog"}],
  "right": [{"id": "bark", "text": "Barks"}, {"id": "meow", "text": "Meows"}],
  "matches": [
    {"left_id": "cat", "right_id": "meow", "cue_text": "Cat meows."},
    {"left_id": "dog", "right_id": "bark", "cue_text": "Dog barks."}
  ]
}
```

Retain the PDF's column order. One-to-one matches must cover every item exactly
once. Every connection appears at its complete aligned narration cue, after
thinking time and before the next question. Missing cues fail composition.
The initial version supports one to four pairs. Many-to-one/image-column
matching and automatic pagination are not implemented.

## Diagram labels

Use `qa_format: diagram_label`, `visual_source_block_ids`, and:

```json
"exercise_visual": {
  "kind": "diagram_label",
  "source_block_id": "figure-1",
  "image_path": "assets/source/figure-1.png",
  "image_sha256": "SHA256_OF_REVIEWED_CROP",
  "labels": [
    {"text": "Roots", "x": 0.7, "y": 0.8,
     "target_x": 0.5, "target_y": 0.7, "cue_text": "These are the roots."}
  ]
}
```

Image paths resolve relative to the educational-plan artifact directory (or
may be absolute). Local PNG/JPEG/WebP crops only. The composer verifies image
decodability and SHA-256, copies it into the workspace, preserves aspect ratio,
and reveals each pointer/label at its spoken cue. Coordinates are normalized
to the original crop. Label centres must stay within 10–90% safe bounds; target
points may cover the full image. Up to four labels, 32 characters each.

The `exercise_visual` data participates in the review fingerprint: editing
pairings, label text/coordinates, cues, or the image hash invalidates approval.
The source-review gate checks answers; these templates do not decide whether
a label points to the correct object. Spatial overlap and readability still
require visual QA, especially for dense diagrams and long labels.

## Verification checkpoint

Unit tests cover pairing integrity, option order, speech-cue timing, missing
data, coordinate checks, raster hash/copy, aspect ratio, and HTML escaping.
The synthetic matching preview passed HyperFrames layout inspection at
thinking time and both answer reveals with zero errors/warnings. This is not
full encoded-output QA for a textbook chapter; diagram encoded-frame review
and dense-content cases remain required before production approval.
