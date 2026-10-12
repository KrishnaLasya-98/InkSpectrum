"""Cross-chapter regression gates for source-grounded educational videos."""
from __future__ import annotations

from typing import Any, Iterable


_STABLE_EXCEPTION_TYPES = {
    "objectives", "question_hold", "answer_reveal", "recall", "remember",
    "word_bank", "deliberate_exact_figure_hold", "native_animated_visual",
}


def validate_stable_visual_exceptions(
    intervals: Iterable[dict[str, Any]], assignments: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Require an explicit reviewed reason for every stable narrated interval."""
    rows = list(intervals)
    routed = {str(row.get("route_id")): row for row in assignments}
    issues: list[str] = []
    stable_count = 0
    for row in rows:
        if row.get("kind") != "stable_source_card":
            continue
        stable_count += 1
        route_id = str(row.get("route_id") or "<missing>")
        exception = str(row.get("stable_exception_type") or "")
        assignment = routed.get(route_id, {})
        if exception not in _STABLE_EXCEPTION_TYPES:
            issues.append(f"{route_id}: unreviewed stable visual exception {exception!r}")
        if assignment.get("stable_exception_type") != exception:
            issues.append(f"{route_id}: stable exception differs from assignment")
        if row.get("stable_exception_reviewed") is not True or assignment.get("stable_exception_reviewed") is not True:
            issues.append(f"{route_id}: stable exception lacks independent review")
        if exception == "native_animated_visual" and assignment.get("native_visual_verified") is not True:
            issues.append(f"{route_id}: native animation is not verified")
    if issues:
        raise ValueError("; ".join(issues))
    return {"status": "pass", "intervals_checked": len(rows),
            "stable_exceptions_checked": stable_count}


def validate_stable_card_scope(
    intervals: Iterable[dict[str, Any]], *, allowed_section_ids: set[str]
) -> dict[str, Any]:
    """Keep narrated explanation routes from silently becoming text-only cards.

    The caller supplies the reviewed sections whose stable teaching screens are
    intentional (for example objectives, Recall, Remember, and Word Bank).
    A section with an authored animated native visual may also be included.
    """

    rows = list(intervals)
    unexpected = [
        str(row.get("interval_id") or row.get("route_id") or "<missing>")
        for row in rows
        if row.get("kind") == "stable_source_card"
        and row.get("section_id") not in allowed_section_ids
    ]
    if unexpected:
        raise ValueError(f"Narrated explanation has text-only visual routes: {unexpected}")
    return {"status": "pass", "intervals_checked": len(rows),
            "stable_sections_allowed": sorted(allowed_section_ids)}


def validate_timed_narration(
    manifest: dict[str, Any],
    *,
    voice_id: str,
    model_id: str,
    speed: float,
    heading_pause_seconds: float = 2.0,
    tolerance_seconds: float = 0.08,
) -> dict[str, Any]:
    """Validate every section, not a sample, against the locked audio contract."""

    issues: list[str] = []
    if manifest.get("voice_name") != voice_id:
        issues.append("voice lock changed")
    metadata = manifest.get("metadata", {})
    observed_model = metadata.get("model_id", manifest.get("model_id"))
    observed_speed = metadata.get("speed", manifest.get("speed"))
    if observed_model != model_id:
        issues.append("narration model changed")
    if float(observed_speed or 0) != float(speed):
        issues.append("narration speed changed")
    if manifest.get("pronunciation_qa_status") not in {"passed", "pass"}:
        issues.append("pronunciation QA is not passed")
    segments = manifest.get("segments", [])
    for row in segments:
        sid = row.get("section_id", "<missing>")
        heading = str(row.get("spoken_heading") or "").strip()
        if not heading:
            issues.append(f"{sid}: spoken heading missing")
            continue
        measured = float(row.get("measured_title_pause_seconds", -1))
        if abs(measured - heading_pause_seconds) > tolerance_seconds:
            issues.append(f"{sid}: heading pause {measured:.3f}s")
        if row.get("heading_pause_presentation") != "inline":
            issues.append(f"{sid}: heading is not in the normal scene layout")
        if float(row.get("title_card_hold_seconds", 0)) != 0:
            issues.append(f"{sid}: duplicate title-card hold is present")
    if issues:
        raise ValueError("; ".join(issues))
    return {"status": "pass", "sections_checked": len(segments)}


def validate_complete_visual_routes(
    routes: Iterable[dict[str, Any]],
    accepted_motion: Iterable[dict[str, Any]],
    *,
    allowed_non_provider_kinds: set[str] | None = None,
) -> dict[str, Any]:
    """Prevent figure displacement, dropped useful motion, and primitive fallbacks."""

    rows = list(routes)
    accepted = list(accepted_motion)
    accepted_sections = {str(row.get("section_id")) for row in accepted}
    allowed = allowed_non_provider_kinds or {
        "stable_source_card", "exact_source_figure", "precision_diagram"
    }
    issues: list[str] = []
    for row in rows:
        sid = str(row.get("section_id") or "<missing>")
        if row.get("fallback_kind") and row.get("fallback_kind") not in allowed:
            issues.append(f"{sid}: primitive or irrelevant fallback {row.get('fallback_kind')}")
        if row.get("provider_motion_required") and row.get("provider_submission_status") == "accepted":
            if sid not in accepted_sections:
                issues.append(f"{sid}: approved useful motion was silently dropped")
        if row.get("exact_source_figure") and row.get("provider_motion_required"):
            if row.get("provider_submission_status") == "accepted" and sid not in accepted_sections:
                issues.append(f"{sid}: exact figure blanket-displaced accepted motion")
    if issues:
        raise ValueError("; ".join(issues))
    return {
        "status": "pass",
        "routes_checked": len(rows),
        "accepted_motion_checked": len(accepted),
    }


def validate_interval_labeling(intervals: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Require controlled, source-grounded labels for every rendered visual interval."""

    rows = list(intervals)
    issues: list[str] = []
    for index, row in enumerate(rows):
        sid = str(row.get("section_id") or "<missing>")
        prefix = f"{sid}[{index}]"
        if not str(row.get("overlay_label") or "").strip():
            issues.append(f"{prefix}: overlay label missing")
        if row.get("overlay_label_source") != "reviewed_textbook_section_title":
            issues.append(f"{prefix}: label is not grounded in the reviewed textbook heading")
        if row.get("overlay_label_style") != "lesson2_small_cream_section_label":
            issues.append(f"{prefix}: label style differs from the Lesson 2 reference")
        if row.get("embedded_generated_text_allowed") is not False:
            issues.append(f"{prefix}: generated embedded text is not explicitly forbidden")
        if row.get("kind") == "exact_source_figure" and row.get("preserve_source_labels") is not True:
            issues.append(f"{prefix}: exact source labels are not preserved")
        if row.get("kind") == "precision_diagram" and row.get("authored_diagram_labels_reviewed") is not True:
            issues.append(f"{prefix}: authored diagram labels are not reviewed")
    if issues:
        raise ValueError("; ".join(issues))
    return {"status": "pass", "intervals_checked": len(rows)}


def validate_full_timeline_semantic_review(
    technical_qa: dict[str, Any], semantic_review: dict[str, Any], expected_sections: Iterable[str],
) -> dict[str, Any]:
    """Require a separate encoded semantic review over every expected section."""

    expected = set(expected_sections)
    reviewed = set(semantic_review.get("sections_reviewed", []))
    issues: list[str] = []
    if technical_qa is semantic_review or technical_qa.get("review_id") == semantic_review.get("review_id"):
        issues.append("semantic review is not distinct from technical QA")
    if technical_qa.get("automated_status") != "pass":
        issues.append("technical encoded QA is not passed")
    if semantic_review.get("status") != "pass":
        issues.append("encoded semantic review is not passed")
    missing = sorted(expected - reviewed)
    if missing:
        issues.append(f"semantic timeline sections missing: {missing}")
    for key in ("clipped_text_or_subtitles", "semantic_visual_mismatches", "unreadable_source_figures"):
        if int(semantic_review.get(key, -1)) != 0:
            issues.append(f"{key} is not zero")
    if issues:
        raise ValueError("; ".join(issues))
    return {"status": "pass", "sections_checked": len(expected)}


def validate_pre_render_timeline(
    intervals: Iterable[dict[str, Any]],
    assignments: Iterable[dict[str, Any]],
    teaching_pages: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Require exact phrase/page/figure/motion routing before composition.

    ``route_id`` defaults to ``section:start:kind`` from the reviewed visual
    plan. Each interval must have exactly one assignment.
    """
    planned = list(intervals)
    routed = list(assignments)
    pages = list(teaching_pages)
    issues: list[str] = []
    plan_by_id: dict[str, dict[str, Any]] = {}
    for row in planned:
        route_id = str(row.get("route_id") or (
            f"{row.get('section_id', '<missing>')}:{float(row.get('start_offset_seconds', -1)):.3f}:"
            f"{row.get('kind', '<missing>')}"
        ))
        if route_id in plan_by_id:
            issues.append(f"duplicate visual interval route_id: {route_id}")
        else:
            plan_by_id[route_id] = row
    assignment_by_id: dict[str, dict[str, Any]] = {}
    motion_paths: list[str] = []
    for row in routed:
        route_id = str(row.get("route_id") or "")
        if route_id in assignment_by_id:
            issues.append(f"duplicate rendered assignment: {route_id}")
            continue
        assignment_by_id[route_id] = row
        planned_row = plan_by_id.get(route_id)
        if not planned_row:
            issues.append(f"unplanned rendered assignment: {route_id}")
            continue
        if row.get("section_id") != planned_row.get("section_id"):
            issues.append(f"{route_id}: section routing changed")
        if row.get("kind") != planned_row.get("kind"):
            issues.append(f"{route_id}: visual kind changed")
        if row.get("phrase_verified") is not True or not str(row.get("phrase_text") or "").strip():
            issues.append(f"{route_id}: narration phrase cue is not verified")
        kind = planned_row.get("kind")
        if kind in {"provider_motion", "precision_diagram"}:
            media_path = str(row.get("media_path") or "")
            if not media_path:
                issues.append(f"{route_id}: motion path missing")
            else:
                motion_paths.append(media_path)
            if row.get("encoded_review_status") != "accepted":
                issues.append(f"{route_id}: motion is not encoded-review accepted")
        if kind == "exact_source_figure":
            if not str(row.get("source_sha256") or ""):
                issues.append(f"{route_id}: exact figure hash missing")
            if row.get("preserve_source_labels") is not True:
                issues.append(f"{route_id}: exact figure labels are not preserved")
    missing = sorted(set(plan_by_id) - set(assignment_by_id))
    if missing:
        issues.append(f"visual intervals missing assignments: {missing}")
    if len(motion_paths) != len(set(motion_paths)):
        issues.append("motion media path is reused across visual intervals")
    for page in pages:
        page_id = str(page.get("page_id") or "<missing>")
        if page.get("source_text_exact") is not True:
            issues.append(f"{page_id}: teaching page text is not source-exact")
        if page.get("phrase_verified") is not True:
            issues.append(f"{page_id}: teaching page phrase boundary is not verified")
        start = float(page.get("start_offset_seconds", -1))
        end = float(page.get("end_offset_seconds", -1))
        if start < 0 or end <= start:
            issues.append(f"{page_id}: teaching page timing is invalid")
    if issues:
        raise ValueError("; ".join(issues))
    return {
        "status": "pass", "intervals_checked": len(planned),
        "assignments_checked": len(routed), "teaching_pages_checked": len(pages),
        "unique_motion_paths": len(motion_paths),
    }
