# Stage Director: composition

## Overview
Execute the composition stage for EduStream Pilot content.

## Composition
- Audio-video composition using OpenMontage's `video_compose` + `audio_mixer`
- ffmpeg concat demuxer for video merging

## Sync
- Audio-video sync alignment (< 100ms tolerance)

## Music
- Background music: Suno API or royalty-free from Pexels/PixBay
- Music ducking during narration (12 dB reduction)

## Sound Effects
- Pexels/SFX for emphasis (math operations, transitions)

## Mastering
- Audio mastering: ITU-R BS.1770-4 loudness normalization

## Lip-Sync
- Lip-sync alignment if avatar present (Wav2Lip/Kling)

## Output
- `final_render.mp4` (1920x1080, 30fps, H.264+AAC)
