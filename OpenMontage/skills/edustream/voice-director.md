# Stage Director: voice_synthesis

## Overview
Execute the voice synthesis stage for EduStream Pilot content.

## TTS Integration
- VoiceStudio TTS integration (18 engines)
- Default: OmniVoice (`k2-fsa/OmniVoice`, 600+ languages, zero-shot cloning)

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
