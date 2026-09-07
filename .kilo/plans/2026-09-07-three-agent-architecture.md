---
title: Three-Agent Development Architecture
status: design
agents: coding, engineering, execution
---

# Three-Agent Development Architecture

## 1. Purpose

Define a tri-agent system that separates **design**, **implementation**, and **runtime validation** into three specialized agents with explicit handoffs, a shared contract, and no overlapping authority.

| Agent | Role | Authority | Forbidden From |
|-------|------|-----------|----------------|
| **Engineering** | System design, architecture, documentation, standards enforcement | Owns the plan, owns the contract, owns the standards | Writing source code, running code |
| **Coding** | Implement, refactor, optimize source | Owns the source tree | Designing architecture, validating runtime behavior |
| **Execution** | Run, observe, capture, report | Owns the runtime, owns the logs | Modifying source, redefining scope |

---

## 2. Agent Responsibilities in Detail

### 2.1 Engineering Agent

**Inputs:** Requirements (from user or ticket), existing codebase state, prior reports.

**Outputs:**
- Architecture plan (`.kilo/plans/<plan-id>.md`)
- Contract schemas (Pydantic models, TS interfaces, OpenAPI, JSON Schema)
- Coding standards reference (lint config, style guide)
- Acceptance criteria (testable, machine-checkable)

**Activities:**
1. Read existing code and prior reports
2. Resolve design decisions by interviewing the user
3. Write the plan with: scope, affected files, data flow, failure modes, validation plan
4. Hand off to Coding with the plan + contract + acceptance criteria

**Refuses to:**
- Edit `.py`, `.ts`, `.js`, `.rs`, `.go` source files
- Run mutable commands
- Approve without explicit user confirmation

### 2.2 Coding Agent

**Inputs:** Engineering plan, contract schemas, acceptance criteria, source tree.

**Outputs:**
- Source code edits
- New modules / files
- Unit tests where contract permits
- `CODE_REVIEW_REQUEST.md` to Engineering when design assumptions change

**Activities:**
1. Read the plan, identify first concrete subtask
2. Implement against the contract (not against the runtime)
3. Run `ruff check` / `tsc --noEmit` / `cargo check` locally
4. Hand off to Execution with: changed file list, install/import instructions, expected outputs

**Refuses to:**
- Change the contract without re-requesting plan from Engineering
- Run the full program (only static checks)
- Declare success without Execution validation

### 2.3 Execution Agent

**Inputs:** Code handoff (file list, commands, expected output), environment spec.

**Outputs:**
- Captured stdout/stderr
- Exit codes
- Log diffs against expected output
- `EXECUTION_REPORT.md` to Engineering with: pass/fail, regressions, perf numbers

**Activities:**
1. Activate venv / install dependencies per Engineering spec
2. Run the test command exactly as specified
3. Capture all output verbatim
4. If failure: classify (compile / runtime / contract / env), report back
5. Hand off to Engineering for retry decision

**Refuses to:**
- Modify source to "make it pass"
- Reinterpret the contract
- Continue past a hard failure without re-approval

---

## 3. Workflow — The Three-Phase Loop

```
USER REQUIREMENT
       │
       ▼
┌──────────────────┐
│   ENGINEERING    │  → plan.md + contract + acceptance criteria
└────────┬─────────┘
         │  HANDS_OFF_PLAN
         ▼
┌──────────────────┐
│     CODING       │  → source edits + static checks pass
└────────┬─────────┘
         │  HANDS_OFF_CODE
         ▼
┌──────────────────┐
│    EXECUTION     │  → EXECUTION_REPORT.md (pass/fail + logs)
└────────┬─────────┘
         │
         ├── PASS ──► USER (deliverable)
         │
         └── FAIL ──► ENGINEERING (re-plan, loop back)
                       OR
                       CODING (targeted fix, skip re-plan)
```

### Handoff Rules

1. **Plan → Code:** Engineering writes plan to disk, returns plan path. Coding reads it as the first action.
2. **Code → Execution:** Coding commits to a worktree (or scratch dir), writes `RUN.md` with exact commands, returns the path.
3. **Execution → User or Engineering:** On pass, Execution reports to user. On fail, Execution reports to Engineering with the failing command + log excerpt.

### Why Engineering can skip on retry

A **targeted fix** for a known failure does not require a new plan. Coding can patch the implementation directly when the failure is purely mechanical (typo, off-by-one, missing import). Engineering is invoked only when the failure reveals a design flaw.

---

## 4. Communication Protocol

### 4.1 Shared Artifacts (the contract)

All three agents read and write the same set of files. This is the only communication channel that survives across agent boundaries.

| Artifact | Path | Owner | Read by |
|----------|------|-------|---------|
| Plan | `.kilo/plans/<plan-id>.md` | Engineering | Coding, Execution |
| Contract | `packages/<pkg>/models/*.py` (or equivalent) | Engineering | Coding, Execution |
| Acceptance criteria | `plans/<plan-id>/acceptance.md` | Engineering | Coding, Execution |
| RUN.md | `.kilo/handoffs/<handoff-id>/RUN.md` | Coding | Execution |
| Code state | Source tree | Coding | Execution, Engineering |
| Execution report | `.kilo/handoffs/<handoff-id>/EXECUTION_REPORT.md` | Execution | Engineering, User |

### 4.2 Handoff Document Schema

Every handoff is a Markdown file with this exact shape. No prose outside these fields.

```markdown
# Handoff <id>
**From:** <agent>
**To:** <agent>
**Type:** PLAN | CODE | EXECUTION
**Timestamp:** <ISO-8601>
**Status:** READY | BLOCKED | FAILED

## Inputs
- <path or reference>

## Outputs expected
- <path or reference>

## Acceptance criteria
- [ ] <machine-checkable criterion>

## Failure handling
- On FAIL: return to <agent> with EXECUTION_REPORT.md
```

### 4.3 In-Chat Protocol

- Agents do NOT carry context between invocations.
- Every chat message between agents begins with: `AGENT: <name>` and `TASK: <one-line summary>`.
- Every chat message ends with: `NEXT: <agent> | <handoff-id>` or `DONE`.
- Length budget: max 8 lines per inter-agent message. Detail lives in the artifact, not the chat.

### 4.4 Conflict Resolution

When two agents disagree:
1. **Engineering > Coding > Execution** on scope and contract questions.
2. **Execution > Coding** on "does it actually work" — Execution is the final word on runtime behavior.
3. **User > all** on priority, requirements, and acceptance.

---

## 5. Runtime Environment Contract

Execution owns the environment, but the contract is set by Engineering. The contract covers:

- Python version, virtualenv path, install command
- Node version, package manager, install command
- Required env vars (referenced by name, never by value in shared docs)
- Expected wall-clock time per test command
- Required GPU/CPU/disk for the task

If Execution finds the environment cannot meet the contract, it returns BLOCKED, not FAILED, and Engineering revises the plan.

---

## 6. Quality Gates

Each handoff must clear these gates before moving forward.

### 6.1 Plan → Coding gate (Engineering exit)
- [ ] All design decisions resolved or marked out of scope
- [ ] Affected files enumerated
- [ ] Contract schemas written and importable
- [ ] Acceptance criteria are machine-checkable
- [ ] User has confirmed "Finalize and save the plan"

### 6.2 Coding → Execution gate (Coding exit)
- [ ] All planned files created/modified
- [ ] Static checks pass (`ruff`, `tsc`, `cargo check`)
- [ ] `RUN.md` written with exact commands
- [ ] No contract changes since plan

### 6.3 Execution → User/Engineering gate (Execution exit)
- [ ] All acceptance criteria evaluated
- [ ] EXECUTION_REPORT.md written
- [ ] Pass: report deliverable to user
- [ ] Fail: classified failure mode + minimum log excerpt (max 50 lines)

---

## 7. Failure Modes and Recovery

| Mode | Detected by | Symptom | Recovery |
|------|-------------|---------|----------|
| **Contract drift** | Coding | Code uses fields not in contract | Coding opens `CODE_REVIEW_REQUEST.md`, Engineering re-issues plan |
| **Environment mismatch** | Execution | ImportError, missing binary | Execution returns BLOCKED, Engineering revises plan |
| **Plan ambiguity** | Coding | Cannot determine intent from plan | Coding returns BLOCKED with specific question, Engineering clarifies |
| **Flaky test** | Execution | Pass on retry, fail on re-run | Execution reports flake, Engineering adds flake tolerance or fixes test |
| **Cascading failure** | Execution | One failure blocks 5+ downstream checks | Execution halts, reports cascade root cause |

---

## 8. Worked Example — Textbook Pipeline (this repo)

**User request:** "Fix the script generation schema mismatch and run it on the English PDF."

**Engineering:**
- Inspects `models/script.py` and `core/script/writer.py`
- Identifies mismatch: `writer.py` passes `section_id`, `estimated_duration` to `ScriptScene` but the model uses `section_ref`, `duration_seconds`
- Identifies enum mismatch: `writer.py` system prompt asks for `TITLE`, `WORD_HIGHLIGHT` (uppercase) but `SceneStepType` values are lowercase
- Writes plan to `.kilo/plans/1788753330415-fix-script-schema.md` with: files to change, new fields, validation steps
- User approves

**Coding:**
- Edits `models/script.py` to add missing enum members (POEM_CARD, DIALOGUE_BUBBLE, etc.)
- Edits `core/script/writer.py` to use lowercase enum values in prompt and correct field names in `ScriptScene` construction
- Runs `python -m pytest packages/textbook-pipeline/tests/test_schemas.py -v` → 17 passed
- Writes `.kilo/handoffs/2026-09-07-english-script/RUN.md` with the run command and expected output

**Execution:**
- Activates `.venv\Scripts\Activate.ps1`
- Runs `python packages/textbook-pipeline/scripts/run_english_pipeline.py`
- Captures: chapter extracted (20 sections), script generation failed (401 Groq key)
- Writes `.kilo/handoffs/2026-09-07-english-script/EXECUTION_REPORT.md`
- Status: PARTIAL_PASS — extraction works, script generation blocked by external API key

**Engineering decision:** API key is external. Return PARTIAL_PASS to user with a note that a valid `GROQ_API_KEY` is needed to complete the script step.

---

## 9. Open Questions for the User

1. Should the Execution agent have permission to **commit** to a feature branch, or only report back to Coding?
2. Should the Engineering agent have access to the LLM (Groq) for design-time code exploration, or rely only on ripgrep/AST?
3. When Execution finds an environment mismatch (BLOCKED), should it auto-create a venv/install, or only report the gap?
4. Should the three agents be **three separate model invocations** in a CLI workflow, or **three system prompts** in a single conversation with role-locked sections?
