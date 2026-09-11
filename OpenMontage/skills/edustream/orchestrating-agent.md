# Stage Director: orchestrating-agent

## Overview

Execute the orchestration stage for EduStream Pro. This skill teaches the
AI agent how to run the LASEV-pattern multi-agent orchestrator
(`EduStreamOrchestrator`) and manage the critique-revision loop.

## Gate
- **human_approval_default: false** (auto-proceed if first_pass_rate ≥ 0.7)

## What This Stage Produces

An Executable Video Script (EVS) triplet:
- **P** (Pedagogical content) — enriched sections with solution_steps,
  animation_plan, and Manim skeleton code
- **N** (Narration) — validated narration scripts normalised to 120 WPM
- **A** (Alignment) — timing timeline mapping section_id → start/end seconds

## Step-by-Step

### 1. Load the educational_plan artifact

```python
import json
plan = json.loads(open("projects/{subject}/artifacts/educational_plan.json").read())
```

Verify every section has a `render_mode` field. If any are missing, use the
`_infer_render_mode()` heuristic in `educational_generator.py` to fill them.

### 2. Call EduStreamOrchestrator

```python
from tools.structure.edustream_orchestrator import EduStreamOrchestrator
result = EduStreamOrchestrator().execute({
    "educational_plan": plan,
    "subject": "evs",          # or "english" / "maths"
    "dry_run": False,
})
```

### 3. Review critique_log

Check `result.data["critique_log"]` for any sections that required 3 retries
(max attempts). If any working-agent loop hit max retries and still has issues:
1. Read the failing section's issues list
2. Manually fix the section in the plan (vocabulary, sentence length, etc.)
3. Re-run the orchestrator on that section only

### 4. Inspect Manim skeletons

For any section with `render_mode: "manim"`, the orchestrator generates
`manim_code` in the section dict. Review these skeletons:
- Must inherit `ChildrensTheme`
- Must use `Nunito` font
- Must reference at least one Sunshine Classroom colour

If skeletons look incomplete, the ManimGenerator will complete them during
Stage 3. The skeleton is a starting point, not final code.

### 5. Write EVS artifacts

```python
import json
evs = result.data["evs_script"]
open("projects/{subject}/artifacts/evs_script.json", "w").write(
    json.dumps(evs, indent=2)
)
```

### 6. Checkpoint

```python
from lib.checkpoint import write_checkpoint
write_checkpoint(
    pipeline_dir=...,
    project_name="edustream-{subject}",
    stage="orchestration",
    status="completed",
    artifacts={"evs_script": evs},
)
```

## Critique Dimensions

| Critique | What it checks | Auto-fix |
|---|---|---|
| Semantic | Vocabulary ≤2 syllables, sentences ≤12 words, no jargon | Trim narration |
| Tool | Manim code AST-valid, ChildrensTheme inherited | Swap parent class |
| Rule | Required fields present, render_mode valid, duration 3–120s | Fill defaults |

## Quality Thresholds

- `first_pass_rate` ≥ 0.7 → proceed automatically
- `first_pass_rate` < 0.7 → present failures to human before proceeding
- Any section with `attempt == 3` and `passed == false` → flag for human review

## Common Issues

**"Sentence too long"** — narration_script has a sentence > 12 words.
Fix: break the sentence at a conjunction or after a comma.

**"Manim class must inherit ChildrensTheme"** — the coder agent used `Scene`
as the base. The auto-fix replaces `(Scene)` with `(ChildrensTheme)`.

**"No Sunshine Classroom palette colour"** — the coder agent used generic
Manim colours (WHITE, BLUE). Replace with `ManimColor("#FF8C42")` etc.

**"duration_seconds out of range"** — a section has duration > 120s.
This usually means the LLM combined two sections. Split manually.
