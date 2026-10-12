# Stage Director: voice_synthesis

## Overview
Execute the voice synthesis stage for EduStream Pilot content.

## TTS Integration
- VoiceStudio TTS integration (18 engines)
- Prefer ElevenLabs `eleven_v4` for new educational narration while the account has usable access and credits. Check account/model/voice availability at the start of each chapter; do not assume the promotional allowance remains active.
- For the Class 5 Social Studies collection, keep the approved `zJrRUu1KEcKH8qdpNaPJ` voice consistent unless the user changes it. Use chapter-scoped manifests and a short sample before a new book or voice.
- If Eleven v4 is unavailable or the allowance is exhausted, record the reason and obtain approval before changing the voice/provider. OmniVoice (`k2-fsa/OmniVoice`) remains a fallback candidate, not an automatic substitution for an approved voice.

## Voice Characteristics
- K-10: child-friendly, clear pronunciation, moderate pace

## Script Schema
- Delivery cues from `script.schema.json`: pace, energy, emphasis_words, pause_before/after

## SSML
- SSML support for ElevenLabs, Azure, Google TTS

## Parallel Generation
- `ThreadPoolExecutor` (max_workers=6)

## GPU Pool
- 2-clock timeout (queue=1800s, exec=300s), heartbeat liveness

## Post-Processing
- Audio post-processing: loudness normalization (-14 LUFS ITU-R BS.1770-4)
- Idle engine unload after 900s

## Output
- `narration_manifest.json` with audio file paths
