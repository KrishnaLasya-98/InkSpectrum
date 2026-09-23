from schemas.artifacts import validate_artifact
from tools.analysis.educational_media_research_planner import (
    EducationalMediaResearchPlanner,
    build_media_research_plan,
    classify_subject,
)


def test_subject_classification_is_dynamic():
    assert classify_subject("Class 6 Geography") == "social_studies"
    assert classify_subject("Advanced Mathematics") == "mathematics"
    assert classify_subject("Robotics") == "general"


def test_science_prefers_attributable_real_world_sources():
    plan = build_media_research_plan("Science", [{
        "scene_id": "water-cycle",
        "title": "Water evaporating from a lake",
        "content_type": "factual",
    }])
    scene = plan["scenes"][0]
    assert scene["search_required"] is True
    assert "wikimedia" in scene["preferred_sources"]
    assert scene["fallback_strategy"] == "diagram_animation"
    validate_artifact("media_research_plan", plan)


def test_math_uses_authored_graphics_without_stock_search():
    result = EducationalMediaResearchPlanner().execute({
        "subject": "Maths",
        "scenes": [{
            "scene_id": "fractions",
            "title": "Compare one half and one quarter",
            "content_type": "mathematics",
        }],
    })
    scene = result.data["media_research_plan"]["scenes"][0]
    assert result.success is True
    assert scene["search_required"] is False
    assert scene["recommended_treatment"] == "diagram_animation"


def test_english_story_prioritizes_continuity_over_generic_stock():
    plan = build_media_research_plan("English", [{
        "scene_id": "story-1",
        "title": "Mina visits the market",
        "content_type": "story",
    }])
    scene = plan["scenes"][0]
    assert scene["search_required"] is False
    assert scene["fallback_strategy"] == "generated_image_or_video_with_character_reference"


def test_general_subject_routes_from_scene_factuality():
    plan = build_media_research_plan("Robotics", [{
        "scene_id": "robot-arm",
        "visual_description": "industrial robot arm in a factory",
        "content_type": "real_world",
    }])
    assert plan["subject_family"] == "general"
    assert plan["scenes"][0]["search_required"] is True
