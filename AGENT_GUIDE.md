# AGENT_GUIDE.md

> The contract between the human and the AI agents that operate InkSpectrum.

InkSpectrum is an **agent-first video production platform** for K-10 textbooks. The LLM agent running in your IDE is the orchestrator; Python provides tools and persistence only.

## Who reads this

- You (the human operator)
- The LLM agent (Kilo, Claude, Cursor, etc.) when invoked against this repo
- Any new agent that joins the workflow

## What InkSpectrum does

Turn a PDF textbook page into a finished, narrated, captioned video. End-to-end.

## How to invoke the agent

Open the project in your AI coding assistant and say something like:

```
"Run the english_classroom pipeline on the RPS English Class 1 PDF."
```

The agent will:
1. Read `config.yaml` for runtime settings
2. Read `pipeline_defs/english_classroom.yaml` for the stage flow
3. For each stage, read the stage-director skill in `skills/pipelines/english_classroom/<stage>-director.md`
4. Call the appropriate tool from the registry (`lib/tool_registry.py`)
5. Write a checkpoint after each stage (`.kilo/checkpoints/<pipeline>/<run>/<stage>.json`)
6. Self-review against `skills/meta/reviewer.md` before the next stage
7. Halt for human approval at any stage with `human_approval_default: true`

## Pipeline manifest format

```yaml
name: english_classroom
category: generated
description: Primary school English lesson
mode: executive-producer
skill: pipelines/english_classroom/executive-producer
budget_default_usd: 2.00
max_revisions_per_stage: 3
compatible_playbooks:
  - clean-classroom
  - warm-primary

stages:
  - name: research
    skill: pipelines/english_classroom/research-director
    produces: [research_brief]
    tools_available: []
    checkpoint_required: false
    human_approval_default: false
    success_criteria:
      - chapter extracted
      - section count > 0
```

## Tools

Tools live in `tools/<category>/<name>.py` and inherit `BaseTool`. The registry auto-discovers them. To list available tools:

```bash
python -c "from lib.tool_registry import all_tools; [print(t.metadata.name, t.metadata.capability) for t in all_tools()]"
```

To check a tool's availability (binary, env, package deps):

```bash
python -c "from lib.tool_registry import get_tool; print(get_tool('opendataloader_extract').describe())"
```

## Skills

Skills are Markdown files that teach the agent how to execute a stage. Three layers:

1. **External tech** — `.agents/skills/` (or `.kilo/skills/`) for third-party tools (FFmpeg, ModelsLab, Manim, etc.)
2. **Project core** — `skills/core/` for stage-agnostic InkSpectrum patterns
3. **Per-pipeline stage director** — `skills/pipelines/<pipeline>/<stage>-director.md`

Always read the stage-director skill before executing a stage.

## Checkpoints

Every stage that declares `checkpoint_required: true` writes `.kilo/checkpoints/<pipeline>/<run>/<stage>.json`. To resume a failed run, the agent reads the last completed stage and re-runs from there.

## Budget

The cost tracker (`.kilo/cost/<pipeline>/<run>.json`) reserves before each tool call and reconciles after. A pipeline that exceeds `budget_default_usd` halts and asks the human for approval.

## Secrets

Secrets live in `.env` (gitignored). Required:

- `GROQ_API_KEY` — for the script writer
- `MODELSLAB_API_KEY` — for TTS, image, video
- Optional: `PEXELS_API_KEY`, `PIXABAY_API_KEY` for stock media

## What the human controls

- Approval gates (`human_approval_default: true` stages)
- Budget overrides
- Style playbook selection
- Final composition choices

## What the agent does NOT do

- Modify the contract (Pydantic models) without re-issuing the plan
- Spend over budget silently
- Skip the reviewer skill
- Edit source files in `lib/` or `tools/` directly — propose the change, get approval, then edit
