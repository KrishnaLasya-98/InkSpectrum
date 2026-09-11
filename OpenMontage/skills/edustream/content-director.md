# Stage Director: content_structuring

## Overview
Execute the content structuring stage for EduStream Pilot content.

## Gate
- **human_approval_default: true** (HUMAN GATE)

## Pedagogical Pipeline
Uses EduGen's 6-step pedagogical pipeline adapted for K-10:

1. **Topic Classification** — keyword matching → theory vs math
2. **Learning Objectives** — age-appropriate action verbs
3. **Content Structure Planning**
4. **Visual Element Design**
5. **Narration Script Development** — conversational tone, 50-100 words per section
6. **Assessment & Engagement Planning**

## LLM Routing
- Claude-4-Opus for high complexity
- Gemini 2.5 Pro for math-heavy
- GPT-4.1 for narrative flow

## Validation
- JSON schema validation against `schemas/artifacts/educational_plan.schema.json`
- 4-strategy JSON parsing with fallback template

## Checkpoint
- Write checkpoint as `status="awaiting_human"`, present plan, END TURN
