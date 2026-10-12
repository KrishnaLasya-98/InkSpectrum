# Lightweight educational reference package

These 960x540 JPEGs were extracted at 2, 15 and 180 seconds from each of the
three user-approved reference videos. Their source IDs and full-video hashes
are in config/educational-reference-lock.json. They preserve appearance examples,
not a guarantee that every historical detail matches newer requirements.

English 180s shows the question/thinking layout; Maths 180s shows the number
chart and highlighted subtitle; EVS 15s shows the lesson-highlights overlay.
Filenames record source ID and timestamp. No source videos are needed on a VM.
Do not use these images as new-chapter footage or textbook content.

Required specification: styles/hyperframes-educational-v1.yaml and the
presentation_contract in config/educational-reference-lock.json. Newer timing
overrides take precedence over historical frames.

## VM validation

1. Run `python -m tools.structure.educational_agent_cli references`.
   Missing historical MP4s are reported as optional_missing. Missing/changed
   baselines fail. Use --require-full-video for archival verification.
2. Run `python -m pytest tests/tools/test_educational_startup.py
   tests/tools/test_educational_hyperframes_composer.py -q` on one command line.
   Fixed opening, concept and recall fixtures exercise the actual shared
   composer without external media/API calls. They test HTML/timeline contracts,
   NOT browser pixels (their media bytes are placeholders).
3. Render a real short chapter sample and compare layout to these images.
   Check headings, textbook boxes, subtitle safe area, question/answer display,
   and the source coverage report. Run HyperFrames lint/inspect as well.
4. Review the encoded sample for word timing, pauses, motion and audio.

Automated perceptual screenshot comparison is not implemented by this package.
Do not compare arbitrary chapters pixel-for-pixel: backgrounds and words differ.
Never approve a new video solely because the baseline hashes and unit tests pass.

The nine images total under 600 KB. They may be committed with the code; do not
publish them to a public repository without appropriate rights to the content.
