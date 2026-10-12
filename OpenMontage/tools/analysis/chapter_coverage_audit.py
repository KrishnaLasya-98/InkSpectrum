"""Conservative source-to-authored-timeline evidence audit (not pixel/OCR QA)."""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
from tools.structure.teaching_contract import question_source_ids, question_matches_source
from tools.structure.exercise_inventory import exercise_role, build_exercise_inventory


def normalized(value):
    return " ".join(str(value or "").split()).casefold()


def panel_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(panel_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(panel_text(item) for key, item in value.items()
                        if key in {"heading", "body", "items", "table", "cells", "text", "section_label", "opening_metadata"})
    return ""


def authored_display_text(screen):
    cards = screen.get("exercise_cards", [])
    if cards:
        panel = screen.get("panel", {})
        heading = " ".join(str(panel.get(k, "")) for k in ("heading", "section_label"))
        return heading + " " + " ".join(
            " ".join([str(c.get("question", "")), str(c.get("answer_text", "")),
                      " ".join(str(x) for x in c.get("choices", [])),
                      " ".join(str(x.get("text", "")) for x in c.get("solution_beats", [])),
                      exercise_visual_text(c.get("visual"))]) for c in cards)
    return panel_text(screen.get("panel", {}))


def exercise_visual_text(visual):
    if not visual: return ""
    return " ".join(str(item.get("text", "")) for key in ("left", "right", "labels")
                    for item in visual.get(key, []))


def audit_chapter(document, plan, narration, timeline):
    sections = plan.get("sections", [])
    audio = {s.get("section_id"): s for s in narration.get("segments", [])}
    screens = {s.get("section_id"): s for s in timeline.get("sections", [])}
    rows = []
    source_blocks = {b.get("block_id"): b for b in document.get("blocks", [])}
    for block in document.get("blocks", []):
        if not block.get("required_for_coverage", True):
            continue
        bid = block.get("block_id")
        source = normalized(block.get("source_text"))
        mapped = [s for s in sections if bid in s.get("source_block_ids", [])]
        evidence = []
        reasons = []
        if not mapped:
            reasons.append("unmapped_source")
        for section in mapped:
            sid = section.get("section_id")
            screen = screens.get(sid, {})
            segment = audio.get(sid, {})
            start, end = screen.get("start_seconds"), screen.get("end_seconds")
            valid_time = all(isinstance(x, (int, float)) and math.isfinite(x) for x in (start, end)) and 0 <= start < end
            evidence.append({"section_id": sid, "start_seconds": start, "end_seconds": end,
                "valid_timeline": valid_time and bid in screen.get("source_block_ids", []),
                "display_exact": bool(source and source in normalized(authored_display_text(screen))),
                "narration_exact": bool(source and source in normalized(segment.get("text"))),
                "narration_text": segment.get("text", ""),
                "display_text": authored_display_text(screen)})
        if not any(e["valid_timeline"] for e in evidence): reasons.append("missing_timed_screen")
        if not any(e["display_exact"] and e["valid_timeline"] for e in evidence): reasons.append("display_requires_review")
        if not any(e["narration_exact"] and e["valid_timeline"] for e in evidence): reasons.append("narration_requires_review")
        kind = block.get("block_type", "")
        answers = []
        exercise = exercise_role(block)
        if exercise not in {"not_exercise", "instruction"}:
            for section in mapped:
                for question in (section.get("teaching_contract") or {}).get("questions", []):
                    if bid in question_source_ids(question):
                        answers.append(question)
            if not answers: reasons.append("answer_evidence_required")
            for answer in answers:
                if not question_matches_source(answer, source_blocks):
                    reasons.append("question_source_mismatch")
                if answer.get("answer_kind") not in {"textbook", "derived", "sample_response"} or not answer.get("answer") or not answer.get("verification_evidence"):
                    reasons.append("answer_unverified")
                answer_text = normalized(answer.get("answer"))
                if not answer_text or not any(answer_text in normalized(e["display_text"]) and e["valid_timeline"] for e in evidence):
                    reasons.append("answer_display_requires_review")
                if not answer_text or not any(answer_text in normalized(e["narration_text"]) and e["valid_timeline"] for e in evidence):
                    reasons.append("answer_narration_requires_review")
        rows.append({"source_block_id": bid, "page_number": block.get("page_number"),
                     "block_type": kind, "source_text": block.get("source_text", ""),
                     "exercise_role": exercise,
                     "status": "verified_authored" if not reasons else "needs_review",
                     "issues": sorted(set(reasons)), "mappings": evidence, "answers": answers})
    unresolved = sum(bool(r["issues"]) for r in rows)
    return {"status": "pass" if rows and not unresolved else "blocked",
            "required_blocks": len(rows), "verified_authored_blocks": len(rows)-unresolved,
            "unresolved_blocks": unresolved, "blocks": rows,
            "exercise_inventory": build_exercise_inventory(document),
            "boundary": "Exact text evidence only, not semantic omission proof. Rephrasing, OCR, figures and tables need review. Does not verify encoded pixels, speech, or answer truth."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("--timeline", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    artifacts = Path(args.project) / "artifacts"
    def read(path): return json.loads(path.read_text(encoding="utf-8"))
    report = audit_chapter(read(artifacts / "chapter_document.json"),
                           read(artifacts / "educational_plan.json"),
                           read(artifacts / "narration_manifest.json"), read(Path(args.timeline)))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "blocks"}))
    raise SystemExit(0 if report["status"] == "pass" else 2)


if __name__ == "__main__": main()
