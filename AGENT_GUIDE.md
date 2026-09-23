# OpenMontage Agent Guide

## Project Overview
OpenMontage is a video editing/montage platform focused on educational video production. The project includes:
- Remotion-based composer for video generation
- HyperFrames-based educational video composition and rendering
- Educational content pipelines (EduQA scenes, Video Topic Compositions)
- Python testing framework for pipeline validation

## Routing Rules
- Current educational chapter production → `OpenMontage/projects/<project>/`
- HyperFrames compositions → `OpenMontage/projects/<project>/hyperframes-*`
- Remotion-only work → `OpenMontage/remotion-composer/`
- Testing → `OpenMontage/tests/`
- Database/API → `OpenMontage/backend/` (if present)

## Educational Video Production Rules
1. Treat the supplied textbook/PDF as the source of truth. Audit every topic, activity, glossary item, assessment, and life-skill statement before rendering.
2. Use grade-appropriate narration that preserves textbook meaning while adding only short, engaging transitions or explanations.
3. Default to polished, child-friendly **3D animated videos** for every chapter and subject. Use 2D animation only when the user explicitly approves it. Do not substitute still images unless explicitly approved.
4. Match each named animal, object, action, or habitat to the visual shown at that exact narration time.
5. Maintain continuous visual coverage. Do not leave blank, plain, or mostly empty screens during narration.
6. Use seamless crossfades and gentle camera movement so clips form one professional animated story.
7. Keep UI minimal and consistent: small cream section label, compact cream learning panel, clear visual hierarchy, and a stable bottom subtitle lane. Avoid duplicate labels and unnecessary text.
8. Generated-video audio must be muted. The approved narration track is authoritative.
9. Word-highlight subtitles must follow the aligned narration timestamps and remain inside the safe area.

## 3D Animation Standard
- Use `OpenMontage/projects/evs-lesson-8/_demo_3d.py` as the current reference implementation for generating 3D animated footage through the ModelsLab adapter.
- Generalize its prompt, output directory, subject, grade, chapter, scene description, duration, and model selection through project configuration; do not copy EVS Lesson 8 values into future chapters.
- The canonical appearance reference is `OpenMontage/projects/evs-lesson-8/hyperframes-professional-v1/renders/hyperframes-professional-v1_2026-09-17_17-37-17.mp4`.
- Future EVS, English, Mathematics, Science, and Social Studies chapters should preserve that reference's professional animated-story quality while adapting scenes and teaching UI to the subject.
- Generate clean clips without visible text, logos, watermarks, embedded subtitles, looping, replay, stutter, camera jumps, or malformed characters.
- Maintain character and environment consistency across adjacent story scenes when the lesson uses recurring characters.
- Create a fresh asset manifest for every chapter. Do not import video, images, narration, or generated media from an older chapter/render unless the user explicitly requests reuse.
- Use each story clip once by default. If narration is longer than the available motion, generate another relevant clip or retime the clip gently; do not visibly loop or replay it.

## Teaching Mode by Section
- Story, introduction, and explanation sections use continuously changing 3D animated footage synchronized to the exact narration concept.
- The opening must begin with relevant animated footage; the first spoken topic must never play over an empty title canvas.
- Recall, glossary, worked examples, questions, MCQs, activities, and life-skills sections may use intentionally stable teaching screens so learners can read and think.
- Stable teaching screens still require synchronized word-highlight subtitles and subtle UI motion; they must not look broken or unfinished.
- Keep different chapters and subjects in separate project workspaces, manifests, media directories, previews, and renders.

## HyperFrames Requirements
- Use HyperFrames for projects already authored in HyperFrames; do not silently switch renderers.
- Register every timed `<video>` and `<audio>` element statically in the authored HTML. Confirm `hyperframes info` reports the expected media counts before rendering.
- Run `hyperframes lint`, representative snapshots across the complete timeline, and transition-boundary snapshots before the final encode.
- For long local renders, use `--workers 1 --low-memory-mode` and confirm streaming encode is enabled.
- Preview changes in the local HyperFrames Studio and obtain visual approval before the expensive final render when practical.

## Final QA Gate
- Verify duration, resolution, frame rate, video codec, audio codec, channel count, and sample rate with `ffprobe`.
- Review contact sheets from the rendered MP4, not only browser snapshots.
- Check intro, every section boundary, every named visual cue, subtitles, assessment screens, closing frames, black frames, frozen frames, and audio/video synchronization.
- A render is not complete until the final MP4 passes these checks.

## Credentials
- Store provider keys only in ignored environment files or secret stores.
- Never print, commit, document, or repeat API keys supplied by the user. Recommend rotation when a key was exposed in chat.

## Getting Started
1. Check git status before making changes
2. Review existing educational video patterns before adding new ones
3. Read the relevant project artifacts and current renderer configuration
4. Run tests and proportional media QA before reporting completion
