# OpenMontage - Hermes and Generic Agent Instructions

Read `AGENT_GUIDE.md` before acting. For textbook/PDF-to-video work, also read
`.agents/skills/openmontage-educational-video/SKILL.md` and
`pipeline_defs/educational-video.yaml`.

The supported integration boundary is agent-neutral: invoke
`python -m tools.structure.educational_agent_cli`, parse JSON and exit codes,
and inspect `project.json`, `checkpoint_*.json`, `events.jsonl`, and files in
`artifacts/`. Credentials belong in environment variables only. Never bypass a
manifest human gate or present an output before encoded-output QA passes.
