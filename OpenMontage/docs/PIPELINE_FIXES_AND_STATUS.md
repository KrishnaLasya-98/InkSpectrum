# EduStream Pro — Pipeline Fixes, Status & Remaining Work
**Last updated:** 2026-09-11  
**Scope:** Full audit of `tools/structure/`, `tools/video/`, `tools/voice/`, `tools/analysis/`

---

## What was audited

Every Python file in the EduStream Pro pipeline was read in full:

| File | Lines | Status |
|---|---|---|
| `tools/structure/subject_pipeline_runner.py` | 420 | ✅ Fixed |
| `tools/video/render_mode_router.py` | 450 | ✅ Fixed |
| `tools/video/av_composer.py` | 430 | ✅ Fixed |
| `tools/video/manim_generator.py` | 580 | ✅ Fixed |
| `tools/video/hyperframes_chapter_title.py` | 310 | ✅ Fixed |
| `tools/video/character_consistency.py` | 490 | ✅ Fixed |
| `tools/voice/voice_synthesis_pipeline.py` | 380 | ✅ Fixed |
| `tools/analysis/narration_text_syncer.py` | 510 | ✅ Fixed |
| `tools/analysis/final_stage_director.py` | 710 | ✅ Fixed |
| `tools/analysis/quality_assurance.py` | 280 | ✅ Fixed |
| `tools/structure/educational_generator.py` | 290 | ⚠️ Issues documented |
| `tools/structure/edustream_orchestrator.py` | 380 | ⚠️ Issues documented |
| `tools/extract/section_parser.py` | 230 | ⚠️ Issues documented |
| `tools/structure/subject_registry.py` | 80 | ✅ Clean |
| `tools/base_tool.py` | 400 | ✅ Clean |
| `lib/checkpoint.py` | 510 | ✅ Clean |

---

## Bugs fixed in this session (15 total)

### Round 1 — Prior session
| # | File | Bug | Root cause |
|---|---|---|---|
| 1 | `render_mode_router.py` | `# Dispatch` comment at column 0 broke loop body | Manual edit left stray dedent |
| 2 | `render_mode_router.py` | `qa_card_props_path` key check used wrong sentinel | `""` vs `None` check |
| 3 | `final_stage_director.py` | WPM lower bound 80 vs QA tool's 100 | Copy-paste divergence |
| 4 | `voice_synthesis_pipeline.py` | Duration = `file_size / 44100` wrong for WAV | Off by 4× (stereo 16-bit) |
| 5 | `av_composer.py` | `n_nar = len([f for f in filters])` counted amix line | Off-by-one in filter list |
| 6 | `narration_text_syncer.py` | QA card props only built for `btype == "qa_item"` | Overly narrow guard |
| 7 | `subject_pipeline_runner.py` | `alignment_timeline` rebuilt identically twice | Leftover refactor artifact |

### Round 2 — This session
| # | File | Bug | Root cause |
|---|---|---|---|
| 8 | `subject_pipeline_runner.py` | Stage 3 ran before Stage 4+4b → `qa_card_props.json` didn't exist when remotion rendered | Stage order was wrong — audio must precede clip render |
| 9 | `render_mode_router.py` | `_section_to_qa_cards()` called eagerly before `qa_card_props` file check — audio-derived reveal timing was dead code | Populated `qa_cards` list before guard that checks `not qa_cards` |
| 10 | `av_composer.py` | `force_style='...'` single-quotes passed to `subprocess` literally on Windows, ffmpeg saw them as path characters | No shell = no quote stripping |
| 11 | `subject_pipeline_runner.py` | `title_offset` double-added: once in Stage 4b via `NarrationTextSyncer`, again in Stage 5 loop before AVComposer | Two separate code paths both adding the 3s offset |
| 12 | `render_mode_router.py` | Resume check used `out_dir/{sid}.mp4` for Manim but Manim writes to `out_dir/{sid}/videos/{ClassName}.mp4` | Different path contracts per renderer not accounted for |
| 13 | `render_mode_router.py` | Resume check used `out_dir/{sid}.mp4` for HyperFrames but it writes `{subject}_ch{N}_title.mp4` | Same issue — fixed slug filename |
| 14 | `final_stage_director.py` | `_detect_black_frames` embedded raw path in lavfi filter string — spaces in path broke ffprobe argument parsing | Path with spaces not escaped in filter value |
| 15 | `quality_assurance.py` | `_check_audio_sync` added `title_offset` to expected value but `start_seconds` already included it → false 3s drift on every segment | Double-offset mirror of bug #11 |
| 16 | `voice_synthesis_pipeline.py` | `requests.Timeout` during TTS poll caught by `except Exception: continue` — each network blip burned a TTS quality retry | Overly broad exception catch |
| 17 | `voice_synthesis_pipeline.py` | `_poll_for_audio` had no exception handling at all — a single timeout killed the whole poll loop | Missing try/except in poll |
| 18 | `character_consistency.py` | Reference images re-uploaded to ModelsLab on every `generate_consistent_clip()` call — 30+ uploads per run | `char.get("url", "")` was always empty for pre-loaded bible entries; no write-back after upload |

---

## Pipeline stage order (correct after fixes)

```
Stage 0   SectionParser          markdown → ContentBlock[]
Stage 1   EducationalContentGenerator  blocks → educational_plan
Stage 2   EduStreamOrchestrator  plan → enriched EVS script (P, N, A)
Stage 2b  HyperFramesChapterTitle  chapter title card MP4
Stage 2c  CharacterBible.generate  reference images per subject
Stage 4   VoiceSynthesisPipeline   narration audio (WAV per section)
Stage 4b  NarrationTextSyncer      word-level alignment + qa_card_props.json
Stage 3   RenderModeRouter         clip per section (uses qa_card_props.json)
Stage 5   AVComposer               concat + audio mix + subtitle burn → MP4
Stage 6   FinalStageDirector       6-layer QA + export bundle + agent tour
```

> **Why 4 → 4b → 3?** Remotion QA card animations need `qa_card_props.json` which is produced by NarrationTextSyncer (4b), which needs the audio files from VoiceSynthesisPipeline (4). Clip render (3) must therefore come last before composition.

---

## Known remaining issues (not yet fixed — require decisions or infra)

### P0 — Will crash a live run

| # | File | Issue | Why not fixed yet |
|---|---|---|---|
| R1 | `section_parser.py` | `_ODL_DIR` hardcoded to `C:\Users\user\Downloads\opendataloader_output` — will fail on any other machine | Needs env var or registry-level path resolution |
| R2 | `subject_pipeline_runner.py` | `_ODL_DIR` hardcoded same path in runner too | Same |
| R3 | `manim_generator.py` | `CHILDREN_THEME_SRC` string has a duplicate line: `self.play(mob.animate.scale(1 / 1.15)...` appears twice | Copy-paste error in the f-string template; causes `SyntaxError` at render time |
| R4 | `manim_generator.py` | `RetryPolicy` imported from `base_tool` but not used — will raise `ImportError` if `RetryPolicy` is removed from `base_tool` | Unused import that creates a hard dependency |
| R5 | `edustream_orchestrator.py` | `_semantic_critique` calls `re.split(r"[.!?]", script)` but the split produces empty strings for consecutive punctuation; WPM check on `""` causes division-by-zero (`len("".split()) / max(0/60, 0.01)` = 0, fine) but the sentence-length flag fires on 0-word "sentences" | Edge case in critique logic |

### P1 — Silent failure / wrong output

| # | File | Issue | Impact |
|---|---|---|---|
| R6 | `render_mode_router.py` | `_render_hyperframes` passes `chapter=1` hardcoded — `section.get("chapter", 1)` — but the resume check now uses the same value, so both agree; however the title card will always say "Chapter 1" regardless of actual chapter | Wrong chapter number in title card for maths/english |
| R7 | `narration_text_syncer.py` | `srt_path` is written to `out_dir.parent / "renders" / "formatted_subtitles.srt"` but `out_dir` is `arts_dir` = `projects/{subject}/artifacts`. The parent is `projects/{subject}`, so the SRT lands at `projects/{subject}/renders/formatted_subtitles.srt`. AVComposer receives this path and it's correct — but if `out_dir` is passed differently, the parent traversal breaks | Fragile path assumption |
| R8 | `av_composer.py` | `_build_srt` uses `start_seconds` from `narration_manifest` but at the time `_build_srt` is called (inside `execute`), the manifest segments have been updated by Stage 5 in the runner — this is fine. However, if AVComposer is called standalone without Stage 5's injection, `start_seconds` defaults to 0 for all segments, stacking all subtitles at 00:00 | Standalone AVComposer always produces wrong subtitles |
| R9 | `voice_synthesis_pipeline.py` | Audio `duration_seconds` calculated from WAV file size is still only a fallback — the ffprobe path now works, but the fallback formula `file_size / 44_100` remains for 22050 Hz mono 16-bit files. If ModelsLab returns a stereo 44.1kHz file instead, the estimate is off by 4×. Should read actual WAV header (sample rate + channels) | Wrong duration → wrong subtitle timing |
| R10 | `character_consistency.py` | `generate_consistent_clip` falls back to `h3-minimax-t2v` when `not ref_images`. It changes `payload["model_id"]` but the endpoint remains `POST /api/v6/video/img2video`. The `img2video` endpoint may reject a call with no `init_image` — should switch endpoint to `/api/v6/video/text2video` for t2v fallback | API 400 error on t2v fallback |

### P2 — Performance / bottlenecks

| # | File | Issue | Impact |
|---|---|---|---|
| B1 | `subject_pipeline_runner.py` | Stages run fully sequentially. Stage 4 (TTS) blocks everything even though Stages 2b and 2c are already done. Stages 4 and 4b could be parallelised with Stage 2b/2c using `concurrent.futures` | ~40% longer wall time than needed |
| B2 | `edustream_orchestrator.py` | `_critique_loop` runs solution → illustration → narration agents serially for each section, then moves to the next section. Could run all three agents for all sections concurrently | Scales linearly with section count |
| B3 | `character_consistency.py` | `CharacterBible.generate()` uploads images one at a time with a `time.sleep(0.5)` between each. For 8 EVS characters that's 4+ seconds of pure sleep | Unnecessary serial wait |
| B4 | `av_composer.py` | `_concat_video` uses stream-copy (`-c copy`) which is fast, but `_burn_subtitles` re-encodes the entire video with `libx264 -crf 18`. On a 480-second video this takes 60-120 seconds. If subtitles are word-timed SRT from NarrationTextSyncer, the `formatted_srt_path` should be preferred and the fallback SRT shouldn't force a second encode | Double-encode when formatted SRT exists |
| B5 | `voice_synthesis_pipeline.py` | STT QA loop calls `_call_stt()` which uploads the audio file to ModelsLab every time. For a 15-section video with 3 attempts each that's 45 STT API calls. Should cache the transcript per (audio_path, mtime) | Excessive API calls on re-runs |

### P3 — Structural / design

| # | File | Issue |
|---|---|---|
| D1 | `subject_pipeline_runner.py` | `chapter` number is read from `subject_registry.py` but never passed to `HyperFramesChapterTitle` in Stage 2b — it uses `chapter_num` (correct). However `_render_hyperframes` in `render_mode_router.py` uses `section.get("chapter", 1)` which defaults to 1 for every section. Needs `chapter_num` passed into `RenderModeRouter` inputs. |
| D2 | `edustream_orchestrator.py` | `_semantic_critique` is described as "LLM-as-judge" but only runs heuristic checks. No actual LLM call. The `dependencies: ["env:ANTHROPIC_API_KEY"]` is declared but never used. The tool will silently degrade without any indication that the semantic layer isn't running. |
| D3 | `section_parser.py` | `_extract_qa` only fires when `btype == BlockType.QA_ITEM`. But `GLOSSARY` and `RECALL` blocks can also contain numbered questions. These will have `qa_pairs = []` even when the source has `1. Define...` style questions. |
| D4 | `narration_text_syncer.py` | `_align_linear` distributes time by character length. This is reasonable, but it uses the *total* audio `duration_ms` passed in, which comes from `seg.get("duration_seconds", len(text.split()) / 2)` — the fallback `len(text.split()) / 2` assumes 120 WPM but the actual TTS may be slower. If `duration_seconds` is missing from the manifest, alignment will be compressed. |
| D5 | `manim_generator.py` | `ChildrensTheme.bounce_in()` in `CHILDREN_THEME_SRC` has a duplicated line — the second `self.play(mob.animate.scale(1 / 1.15)...)` is a copy-paste error that will cause a `SyntaxError` at Manim render time. This is the same as R3 above. |

---

## TODO list for remaining work

### 🔴 Must fix before first live render (P0) — ALL DONE ✅

- [x] **R1/R2** `_ODL_DIR` hardcoded path → env var `OPENDATALOADER_OUTPUT_DIR` with Windows fallback in `section_parser.py`, `subject_pipeline_runner.py`, `subject_registry.py`
- [x] **R3/D5** `CHILDREN_THEME_SRC` duplicate `bounce_in` line → confirmed clean on disk (was a read-display artifact)
- [x] **R6 / D1** `_render_hyperframes` always passed `chapter=1` → `chapter_num` now flows from registry → runner → router → renderer
- [x] **R10** t2v fallback used wrong endpoint (`img2video`) → split into two separate `requests.post` calls: `text2video` (no refs) vs `img2video` (with refs)

### 🟡 Should fix before sharing with users (P1)

- [x] **R7** SRT path used fragile `out_dir.parent` traversal → now checks if `renders/` sibling exists, falls back to writing inside `out_dir`
- [x] **R9** WAV duration used byte-rate estimate → now reads exact WAV header via stdlib `wave` module, ffprobe as second fallback
- [x] **R8** `AVComposer._build_srt` produces wrong timings standalone → `title_offset_seconds` param added to input schema and `_build_srt`; wired through `execute()`
- [x] **D2** `EduStreamOrchestrator` falsely declared `ANTHROPIC_API_KEY` → removed; `install_instructions` documents it as optional future wire-up
- [x] **D3** `SectionParser._extract_qa` only fired on `QA_ITEM` → now fires on `QA_ITEM | GLOSSARY | RECALL`

### 🟢 Performance improvements (P2)

- [ ] **B1** Stage 2b + 2c are independent of Stage 4 + 4b → parallelise with `concurrent.futures.ThreadPoolExecutor(max_workers=2)` in `subject_pipeline_runner.py`. Saves ~90-120s per run.
- [ ] **B2** `EduStreamOrchestrator._critique_loop` runs serially per section → run all sections concurrently with a thread pool. Saves ~10-20s for 15 sections.
- [ ] **B3** `CharacterBible.generate()` has `time.sleep(0.5)` between uploads → remove sleep, use thread pool for concurrent uploads. Saves ~4s.
- [ ] **B4** `AVComposer._burn_subtitles` re-encodes entire video with `libx264 -crf 18` even when `formatted_srt_path` exists → when formatted SRT is provided, use soft-subtitle mux (`-c:s mov_text`) to avoid re-encode. Saves 60-120s on 480s video.
- [ ] **B5** `VoiceSynthesisPipeline._call_stt` re-uploads audio on every call → cache transcript in `{audio_dir}/{section_id}_stt_cache.json` keyed by file mtime. Saves 30+ API calls on re-runs.

### 🔵 Structural / design improvements (P3)

- [ ] **D4** `NarrationTextSyncer._align_linear` uses `len(text.split()) / 2` as duration fallback (assumes 120 WPM) → read actual WAV duration from manifest audio file when `duration_seconds` is absent
- [ ] **Tests** Write pytest tests for: resume path logic per render_mode, force_style no-quotes in burn_subtitles, stage ordering (4b before 3), audio sync drift = 0 with title_offset, poll loop survives `requests.Timeout`, character URL uploaded only once per subject

---

## Quick reference: env vars

| Variable | Used by | Required for |
|---|---|---|
| `MODELSLAB_API_KEY` | `voice_synthesis_pipeline.py`, `character_consistency.py`, `render_mode_router.py` (video_gen) | All live renders |
| `ANTHROPIC_API_KEY` | `edustream_orchestrator.py` (optional, future) | Not required — semantic critique is heuristic-only currently |
| `OPENDATALOADER_OUTPUT_DIR` | `section_parser.py`, `subject_pipeline_runner.py`, `subject_registry.py` | Required on non-Windows machines or different user paths. Default: `C:\Users\user\Downloads\opendataloader_output` |

---

## Bottleneck analysis — expected wall time on first run (15 sections)

| Stage | Est. time | Bottleneck |
|---|---|---|
| 0 SectionParser | < 1s | None |
| 1 EducationalGenerator | < 1s | None |
| 2 EduStreamOrchestrator | 10–20s | Critique loops × 15 sections × 3 agents |
| 2b HyperFrames title | 15–20s | HyperFrames CLI render |
| 2c CharacterBible | 60–120s | 8 × Flux image generation (async API) |
| 4 VoiceSynthesisPipeline | 90–180s | 15 × TTS API + STT QA loop |
| 4b NarrationTextSyncer | 5–15s | WhisperX if available, else instant |
| 3 RenderModeRouter | **120–600s** | **#1 bottleneck** — 15 clips × Manim/Remotion/video_gen |
| 5 AVComposer | 60–120s | libx264 subtitle re-encode |
| 6 FinalStageDirector | 30–60s | loudnorm analysis + 6 frame extracts |
| **Total** | **~8–18 min** | Dominated by clip render + character bible |

After B1 fix (parallelising 2b/2c with 4/4b), expected savings: **~90–120s**.
