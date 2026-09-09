# Project Roadmap: InkSpectrum Video Pipeline

**Project:** InkSpectrum — Textbook-to-Video Automation
**Current Phase:** MVP Complete → Production Ready
**Target:** End-to-end automated pipeline from PDF to MP4
**Timeline:** 4 weeks to production-ready

---

## Current State Assessment

| Component | Status | Health |
|-----------|--------|--------|
| Phase 1: PDF Extraction | ✅ Working | Good |
| Phase 2: Script Generation | ✅ Working (AI-driven) | Good |
| Phase 3: TTS Audio | ✅ Working (ModelsLab + Edge) | Good |
| Phase 3.5: Asset Generation | 🔲 Just Created | Needs Testing |
| Phase 4: Video Rendering | ✅ Working (Pillow + FFmpeg) | Basic |
| End-to-End Pipeline | 🔲 Partial | Needs Orchestrator |
| Remotion Integration | 🔲 Optional | Not Started |
| Character Consistency | 🔲 Planned | Not Started |
| Subtitles/STT | 🔲 Planned | Not Started |

---

## Week 1: Stabilization & Asset Pipeline

### Days 1-2: Code Debugging & Schema Fixes

| Task | Priority | Effort | Status |
|------|----------|--------|--------|
| Fix ScriptScene schema (add asset fields) | P0 | 2h | ✅ Done |
| Add markdown sanitization | P0 | 1h | ✅ Done |
| Fix ModelsLab I2V endpoint (v6) | P0 | 2h | ✅ Done |
| Fix ModelsLab poll endpoint | P0 | 1h | ✅ Done |
| Install edge-tts dependency | P0 | 15m | ✅ Done |

### Days 3-5: Phase 3.5 Asset Generation

| Task | Priority | Effort | Status |
|------|----------|--------|--------|
| Create asset_generator.py module | P0 | 4h | ✅ Done |
| Create run_phase35_assets.py runner | P0 | 1h | ✅ Done |
| Test T2I generation (hidream-o1) | P0 | 2h | 🔲 Pending |
| Test I2V generation (h3-minimax-r2v) | P0 | 2h | 🔲 Pending |
| Add character reference library | P1 | 4h | 🔲 Pending |
| Add cost tracking per generation | P1 | 2h | 🔲 Pending |

**Deliverable:** Working Phase 3.5 that generates T2I images and I2V clips for EVS Chapter 8.

---

## Week 2: Pipeline Integration & Consistency

### Days 6-7: Renderer Updates

| Task | Priority | Effort | Status |
|------|----------|--------|--------|
| Update renderer to use AI assets | P0 | 3h | 🔲 Pending |
| Add fallback logic (Pillow if no AI asset) | P0 | 1h | 🔲 Pending |
| Test full render with AI assets | P0 | 2h | 🔲 Pending |
| Add subtitle burn-in (FFmpeg) | P1 | 2h | 🔲 Pending |

### Days 8-9: Scene Planning & Character Consistency

| Task | Priority | Effort | Status |
|------|----------|--------|--------|
| Generate character reference library | P0 | 4h | 🔲 Pending |
| Lock character prompts (consistency anchors) | P0 | 2h | 🔲 Pending |
| Implement I2V with init_image = reference | P0 | 2h | 🔲 Pending |
| Add img2img strength parameter | P1 | 1h | 🔲 Pending |
| Create environment background library | P1 | 3h | 🔲 Pending |

### Day 10: Prompt Optimization

| Task | Priority | Effort | Status |
|------|----------|--------|--------|
| Add motion-only constraint to all video_prompts | P0 | 2h | 🔲 Pending |
| Remove zoom references from prompts | P0 | 1h | 🔲 Pending |
| Optimize T2I prompts for educational style | P1 | 2h | 🔲 Pending |
| Add negative prompts (no text, no scary elements) | P1 | 1h | 🔲 Pending |

**Deliverable:** Complete EVS Chapter 8 video with AI-generated assets and consistent characters.

---

## Week 3: Orchestrator & Automation

### Days 11-12: End-to-End Orchestrator

| Task | Priority | Effort | Status |
|------|----------|--------|--------|
| Design orchestrator architecture | P0 | 2h | 🔲 Pending |
| Implement orchestrator.py | P0 | 6h | 🔲 Pending |
| Add checkpoint/resume logic | P0 | 3h | 🔲 Pending |
| Add error recovery per phase | P0 | 2h | 🔲 Pending |
| Add progress reporting | P1 | 2h | 🔲 Pending |

### Days 13-14: Font & Typography System

| Task | Priority | Effort | Status |
|------|----------|--------|--------|
| Download kid-friendly fonts (Nunito, Comic Neue) | P1 | 1h | 🔲 Pending |
| Create font_config.py module | P1 | 2h | 🔲 Pending |
| Update renderer to use new fonts | P1 | 2h | 🔲 Pending |
| Add Remotion font configuration | P2 | 2h | 🔲 Pending |

### Days 15-16: Testing & Validation

| Task | Priority | Effort | Status |
|------|----------|--------|--------|
| End-to-end test: PDF → MP4 | P0 | 3h | 🔲 Pending |
| Validate all 20 scenes have assets | P0 | 1h | 🔲 Pending |
| Audio-visual sync check | P0 | 1h | 🔲 Pending |
| Character consistency review | P1 | 2h | 🔲 Pending |
| Performance profiling | P1 | 2h | 🔲 Pending |

**Deliverable:** Single-command pipeline: `python run_pipeline.py --chapter evs_chapter8`

---

## Week 4: Production Hardening

### Days 17-18: Quality & Cost Governance

| Task | Priority | Effort | Status |
|------|----------|--------|--------|
| Add budget enforcement per chapter | P0 | 3h | 🔲 Pending |
| Add cost tracking dashboard | P1 | 3h | 🔲 Pending |
| Add quality metrics (FID, SSIM for images) | P1 | 4h | 🔲 Pending |
| Add VLM evaluation for generated assets | P2 | 4h | 🔲 Pending |

### Days 19-20: Documentation & Deployment

| Task | Priority | Effort | Status |
|------|----------|--------|--------|
| Update AGENTS.md with new workflows | P0 | 2h | 🔲 Pending |
| Create operator guide | P0 | 4h | 🔲 Pending |
| Add troubleshooting section | P1 | 2h | 🔲 Pending |
| Create Docker container | P2 | 4h | 🔲 Pending |
| Add CI/CD pipeline | P2 | 3h | 🔲 Pending |

**Deliverable:** Production-ready pipeline with documentation, cost controls, and deployment config.

---

## Technical Milestones

### Milestone 1: Stable Asset Generation (End of Week 1)
- **Criteria:** Phase 3.5 generates valid T2I + I2V assets for 6 EVS scenes
- **Validation:** All assets downloaded, valid format, reasonable quality
- **Gate:** Cannot proceed to Week 2 without this

### Milestone 2: Consistent Character Rendering (End of Week 2)
- **Criteria:** Same character looks consistent across 3+ scenes
- **Validation:** Visual inspection + SSIM > 0.85 between character reference and scene assets
- **Gate:** Cannot proceed to Week 3 without this

### Milestone 3: End-to-End Automation (End of Week 3)
- **Criteria:** `python run_pipeline.py` produces valid MP4 from PDF input
- **Validation:** MP4 plays correctly, audio sync < 100ms, file size < 500MB
- **Gate:** Cannot proceed to Week 4 without this

### Milestone 4: Production Ready (End of Week 4)
- **Criteria:** Pipeline handles errors, tracks costs, documented, deployable
- **Validation:** Budget tracking works, error recovery tested, docs complete
- **Gate:** Project complete

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| ModelsLab API changes | Medium | High | Maintain Edge TTS fallback, abstract API layer |
| Character inconsistency in I2V | High | Medium | Reference library + img2img strength tuning |
| Asset generation cost overrun | Medium | Medium | Budget caps per chapter, user approval flow |
| I2V generation timeout | Medium | High | Increase poll timeout, add webhook support |
| Font rendering issues on Windows | Low | Low | Test on target OS, bundle fonts |
| Remotion integration complexity | Medium | Low | Keep Pillow fallback, Remotion as opt-in |

---

## Decision Log

| Decision | Date | Rationale |
|----------|------|-----------|
| Use h3-minimax-r2v for I2V | 2026-09-09 | Works reliably, better consistency than start-end-frame |
| Use v6 endpoint for h3-minimax | 2026-09-09 | Official docs specify v6, v7 returns errors |
| Keep Pillow as fallback renderer | 2026-09-09 | Fast iteration, no Node.js dependency |
| AI-driven script generation | 2026-09-09 | No LLM API dependency, no rate limits |
| ModelsLab TTS + Edge TTS fallback | 2026-09-09 | Best quality with free backup |
| Motion-only constraint (no zoom) | 2026-09-09 | Age-appropriate for 6-7 year olds |

---

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Pipeline success rate** | > 95% | Chapters completed without manual intervention |
| **Asset generation cost** | < $15/chapter | API cost tracking |
| **Generation time** | < 60 min/chapter | End-to-end wall time |
| **Video duration accuracy** | ±5% of target | FFprobe duration vs script |
| **Audio-visual sync** | < 100ms | FFmpeg log analysis |
| **Character consistency** | SSIM > 0.85 | Image comparison |
| **User satisfaction** | > 4/5 rating | Post-delivery survey |
| **Code coverage** | > 80% | Pytest |

---

## Next Steps

1. **Immediate (Today):** Test Phase 3.5 with EVS Chapter 8 scenes
2. **Tomorrow:** Fix any issues found in testing, iterate on prompts
3. **This week:** Complete character reference library, lock prompts
4. **Next week:** Build orchestrator, integrate all phases
5. **Week 4:** Polish, document, deploy

---

*Roadmap version: 1.0 | Created: 2026-09-09 | Target: Production Ready by 2026-10-07*
