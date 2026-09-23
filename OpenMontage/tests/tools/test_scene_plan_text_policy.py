import json
from pathlib import Path

from tools.structure.source_fidelity import display_policy


def test_evs_scene_plan_declares_source_preserving_motion_policy():
    policy = display_policy(Path("artifacts/source_text_manifest.json"))
    assert policy["display_case"] == "Tt"
    assert policy["preserve_punctuation"] is True
    assert policy["max_content_lines"] == 3
    assert policy["title_media_policy"] == "graphics_only"
    assert policy["content_media_policy"] == "motion_preferred"
    assert policy["image_policy"] == "fallback_only"
