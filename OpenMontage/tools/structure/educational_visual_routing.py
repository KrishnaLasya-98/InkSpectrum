"""Guards for source-figure and provider-motion routing in educational videos."""
from __future__ import annotations

from typing import Any, Iterable


def find_sequential_page_cue(
    words: list[dict[str, Any]], page_text: str, previous_word_index: int = -1,
) -> tuple[int, int, float]:
    """Find a complete page after the prior page, avoiding repeated-prefix jumps."""

    def normalized(value: str) -> str:
        return "".join(character for character in value.casefold() if character.isalnum())

    wanted = [normalized(item) for item in page_text.split() if normalized(item)]
    observed = [(i, normalized(str(word["word"]))) for i, word in enumerate(words) if normalized(str(word["word"]))]
    for i in range(len(observed) - len(wanted) + 1):
        selected = observed[i:i + len(wanted)]
        indexes = [index for index, _ in selected]
        if indexes[0] > previous_word_index and [value for _, value in selected] == wanted:
            return indexes[0], indexes[-1], float(words[indexes[0]]["start_ms"]) / 1000
    raise ValueError(f"Unmatched sequential teaching page: {page_text}")


def select_accepted_same_section_motion(
    submitted_jobs: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep accepted clips even when their section also has an exact figure."""

    return [row for row in submitted_jobs if row.get("visual_review") == "accepted"]


def validate_pre_generation_routes(routes: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Fail before paid generation when route intent is contradictory."""

    rows = list(routes)
    section_ids = [str(row.get("section_id") or "") for row in rows]
    issues: list[str] = []
    if any(not section_id for section_id in section_ids):
        issues.append("every route requires a section_id")
    duplicates = sorted({section_id for section_id in section_ids if section_ids.count(section_id) > 1})
    if duplicates:
        issues.append(f"duplicate section routes: {duplicates}")

    for row in rows:
        sid = str(row.get("section_id") or "<missing>")
        primary = row.get("primary")
        wants_motion = bool(row.get("provider_motion_required"))
        if row.get("stable_card") and wants_motion:
            issues.append(f"{sid}: stable cards must not request provider motion")
        if primary == "stable_source_card" and not row.get("stable_card"):
            issues.append(f"{sid}: stable_source_card must set stable_card=true")
        if primary == "exact_figure_plus_motion":
            if not row.get("exact_source_figure"):
                issues.append(f"{sid}: exact_figure_plus_motion requires an exact source figure")
            if not wants_motion:
                issues.append(f"{sid}: exact_figure_plus_motion must retain its planned motion interval")
        if not wants_motion and row.get("provider_submission_status") not in {None, "not_submitted"}:
            issues.append(f"{sid}: unneeded provider asset was submitted")

    if issues:
        raise ValueError("; ".join(issues))
    return {
        "status": "pass",
        "route_count": len(rows),
        "provider_motion_sections": sum(bool(row.get("provider_motion_required")) for row in rows),
        "stable_card_sections": sum(bool(row.get("stable_card")) for row in rows),
        "exact_figure_plus_motion_sections": sum(row.get("primary") == "exact_figure_plus_motion" for row in rows),
    }
