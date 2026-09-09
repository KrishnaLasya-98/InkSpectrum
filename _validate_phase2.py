"""Temporary Phase 2 validation per AGENTS.md verification rules."""
import json
from pathlib import Path

OUT = Path("packages/textbook-pipeline/projects/english_pipeline_output")
chapter = json.loads((OUT / "chapter.json").read_text(encoding="utf-8"))
scenes = json.loads((OUT / "phase2_script_scenes.json").read_text(encoding="utf-8"))

sections = {s["id"]: s for s in chapter["sections"]}
print(f"Sections: {len(sections)}  Scenes: {len(scenes)}")

TEACHING = {"title", "subtitle", "text", "clear", "word_highlight",
            "vocabulary_card", "dialogue_bubble", "pronunciation_guide", "poem_card"}
EXERCISE = {"question_card", "worked_step", "answer_reveal"}

errors, warnings = [], []
scene_refs = set()
for sc in scenes:
    sid = sc["id"]
    ref = sc.get("section_ref")
    scene_refs.add(ref)
    vo = sc.get("voiceover_lines", [])
    steps = sc.get("scene_steps", [])
    if len(vo) < 2:
        errors.append(f"{sid}: only {len(vo)} voiceover_lines (need >=2)")
    if len(steps) < 2:
        errors.append(f"{sid}: only {len(steps)} scene_steps (need >=2)")
    if ref not in sections:
        errors.append(f"{sid}: unknown section_ref {ref!r}")
        continue
    sectype = sections[ref].get("type")
    stypes = {st.get("type") for st in steps}
    if sectype == "exercise" and not (stypes & EXERCISE):
        warnings.append(f"{sid}: section type=exercise but steps lack exercise vocab ({stypes})")
    if sectype == "theoretical" and not (stypes & TEACHING):
        warnings.append(f"{sid}: section type=theoretical but steps lack teaching vocab ({stypes})")
    # quality heuristics
    for v in vo:
        t = v.get("text", "")
        if "![" in t or "imageFile" in t:
            warnings.append(f"{sid}: raw markdown/image markup in voiceover: {t[:60]!r}")
        if t.strip().startswith("Pay attention to") or "Let us learn about" in t:
            warnings.append(f"{sid}: generic fallback voiceover: {t[:60]!r}")

missing = set(sections) - scene_refs
if missing:
    errors.append(f"Sections without a scene: {sorted(missing)}")
extra = scene_refs - set(sections)
if extra:
    errors.append(f"Scenes referencing unknown sections: {sorted(extra)}")

print("\n--- ERRORS ---")
print("\n".join(errors) if errors else "none")
print("\n--- WARNINGS ---")
print("\n".join(warnings) if warnings else "none")
print(f"\nSummary: {len(errors)} errors, {len(warnings)} warnings")
