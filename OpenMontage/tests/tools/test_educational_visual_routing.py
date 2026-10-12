from __future__ import annotations

import pytest

from tools.structure.educational_visual_routing import (
    find_sequential_page_cue,
    select_accepted_same_section_motion,
    validate_pre_generation_routes,
)


def test_complete_page_matching_skips_earlier_repeated_prefix() -> None:
    words = [
        {"word": token, "start_ms": index * 100}
        for index, token in enumerate(
            "Location In North America they are called prairies and later they are called downs In India".split()
        )
    ]

    first, last, at = find_sequential_page_cue(words, "they are called downs In India", 6)

    assert (first, last, at) == (10, 15, 1.0)


def test_accepted_motion_is_not_blanket_excluded_from_figure_sections() -> None:
    jobs = [
        {"shot_id": "figure-motion", "section_id": "s10", "visual_review": "accepted"},
        {"shot_id": "ordinary-motion", "section_id": "s12", "visual_review": "accepted"},
        {"shot_id": "bad", "section_id": "s10", "visual_review": "rejected"},
    ]

    selected = select_accepted_same_section_motion(jobs)

    assert [row["shot_id"] for row in selected] == ["figure-motion", "ordinary-motion"]


def test_pre_generation_guard_rejects_unneeded_stable_card_asset() -> None:
    routes = [{
        "section_id": "s02-objectives",
        "primary": "stable_source_card",
        "stable_card": True,
        "provider_motion_required": False,
        "provider_submission_status": "submitted",
    }]

    with pytest.raises(ValueError, match="unneeded provider asset was submitted"):
        validate_pre_generation_routes(routes)


def test_pre_generation_guard_requires_both_parts_of_figure_motion_route() -> None:
    route = {
        "section_id": "s10-earthquake-during",
        "primary": "exact_figure_plus_motion",
        "stable_card": False,
        "exact_source_figure": "images/earthquake-damage.png",
        "provider_motion_required": True,
        "provider_submission_status": "not_submitted",
    }

    report = validate_pre_generation_routes([route])

    assert report == {
        "status": "pass",
        "route_count": 1,
        "provider_motion_sections": 1,
        "stable_card_sections": 0,
        "exact_figure_plus_motion_sections": 1,
    }


def test_pre_generation_guard_rejects_figure_only_downgrade() -> None:
    route = {
        "section_id": "s10-earthquake-during",
        "primary": "exact_figure_plus_motion",
        "stable_card": False,
        "exact_source_figure": "images/earthquake-damage.png",
        "provider_motion_required": False,
        "provider_submission_status": "not_submitted",
    }

    with pytest.raises(ValueError, match="must retain its planned motion interval"):
        validate_pre_generation_routes([route])
