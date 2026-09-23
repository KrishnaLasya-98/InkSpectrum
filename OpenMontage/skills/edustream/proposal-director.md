# Production Proposal Director

Use this stage after source ingestion and before educational content planning.
Summarize the audience, learning goal, estimated duration, source constraints,
asset strategy, cost envelope, and risks. Persist the result as
`proposal_packet.json`; do not start paid generation from this stage.

## Render runtime decision

Present both composition runtimes whenever both are feasible:

- `remotion` for React-driven layouts, assessment UI, and deterministic cards.
- `hyperframes` for browser-native sequences and existing HyperFrames projects.

Record the selected value as `render_runtime` and log the choice under
`render_runtime_selection` in the decision log. If the project is locked to a
runtime, surface that constraint explicitly instead of silently defaulting.

For this educational-video program, the user has selected `hyperframes` as the
preferred runtime because the approved EVS UI and current video workspace are
HyperFrames-native. Recommend and record HyperFrames unless a project-specific
requirement is genuinely Remotion-only. Retain Remotion and FFmpeg in
`options_considered`; do not ask the user to repeat a runtime choice already
recorded for the project. A runtime change requires a new approved decision.

The proposal requires human approval when it introduces paid generation,
licensed stock, a new visual identity, or a runtime change.
