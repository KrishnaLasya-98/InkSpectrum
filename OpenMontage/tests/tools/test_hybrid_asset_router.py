from tools.video.hybrid_asset_router import HybridAssetRouter, choose_asset_strategy


def test_reviewed_existing_asset_wins():
    decision = choose_asset_strategy({
        "scene_id": "s1",
        "content_type": "factual",
        "source_asset_available": True,
        "stock_matches": ["candidate"],
    })
    assert decision["selected_strategy"] == "existing_asset"


def test_factual_scene_prefers_licensed_stock():
    decision = choose_asset_strategy({
        "scene_id": "s2",
        "content_type": "real_world",
        "stock_matches": ["pexels:123"],
        "generation_available": True,
    })
    assert decision["selected_strategy"] == "stock_video"
    assert decision["requires_provenance"] is True


def test_abstract_scene_routes_to_authored_graphics():
    decision = choose_asset_strategy({
        "scene_id": "s3",
        "content_type": "mathematics",
        "motion_requirement": "specific",
    })
    assert decision["selected_strategy"] == "diagram_animation"


def test_generation_requires_approval_when_paid():
    decision = choose_asset_strategy({
        "scene_id": "s4",
        "content_type": "narrative",
        "identity_continuity_required": True,
        "estimated_generation_cost_usd": 0.25,
    })
    assert decision["selected_strategy"] == "generated_video"
    assert decision["approval_required"] is True


def test_motion_scene_blocks_when_no_route_exists():
    result = HybridAssetRouter().execute({
        "scenes": [{
            "scene_id": "s5",
            "content_type": "narrative",
            "motion_requirement": "specific",
            "generation_available": False,
        }],
        "policy": {"allow_generation": False},
    })
    assert result.success is False
    assert result.data["blocked_scene_ids"] == ["s5"]
