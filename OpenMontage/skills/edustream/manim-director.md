# Stage Director: manim_generation

## Overview
Execute the Manim generation stage for EduStream Pilot content.

## Pipeline
- Code2Video tri-agent pipeline: Planner → Coder → Critic
- EduGen self-healing loops integrated

## Agents
- **Planner**: Claude-4-Opus, storyboard → code plan
- **Coder**: Gemini 2.5 Pro, code plan → Manim Python code
- **Critic**: Gemini 2.5 Pro VLM, rendered video → layout feedback (2 rounds)

## Self-Healing
- ScopeRefineFixer: 3-stage repair (local fix → comprehensive review → complete rewrite, max 10)

## Code Constraints
- TeachingScene base class (6x6 grid) injected into all Manim code
- Constraints: no ImageMObject, no external images, only built-in Manim objects

## Math Rendering
- LaTeX → MathTex
- SymPy for symbolic validation

## Rendering
- `manim -ql` for trial
- `manim -qm` for final

## Parallel
- `ProcessPoolExecutor`(max_workers=CPU_cores-1, capped at 16)

## VLM Feedback
- GridCodeModifier applies VLM feedback (parse "Line X:" instructions)
