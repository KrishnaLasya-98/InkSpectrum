# Educational Media Research Director

Run after the scene plan and before asset selection. Use
`educational_media_research_planner` to classify the subject and produce a
search plan for every scene.

For scenes marked `search_required`, search only the plan's preferred sources.
Use `direct_clip_search` when several providers are appropriate; use the direct
Pexels/Pixabay image or video tools for a narrow query. Results are candidates,
not approved assets.

Review thumbnails and metadata for semantic fit, age suitability, resolution,
watermarks, factual accuracy, source URL, and license. Record rejected as well
as shortlisted candidates. Do not treat synthetic footage as documentary
evidence and do not search stock for mathematical symbols, grammar animation,
or software behavior when deterministic graphics are clearer.

Persist `media_research_plan.json`. The following asset stage makes the final
existing/stock/generated/diagram decision and owns the human approval gate.
