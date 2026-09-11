from __future__ import annotations

from pathlib import Path

from lib.modelslab_catalog import (
    BenchmarkProfile,
    fetch_catalog,
    fetch_catalog_mcp,
    enrich_model_from_page,
    load_catalog,
    normalize_model,
    recommend_models,
    save_catalog,
)


def test_feature_cache_names_are_distinct():
    from scripts.modelslab_catalog import default_cache

    assert default_cache("video_fusion") != default_cache("imagen")
    assert default_cache("threedverse").name == "model_catalog_threedverse.json"


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _Session:
    def __init__(self):
        self.calls = []

    def get(self, endpoint, *, params, timeout):
        self.calls.append((endpoint, params, timeout))
        if params["page"] == 1:
            return _Response({"data": [{"model_id": "wan2.6-t2v", "provider": "alibaba_cloud", "tags": ["Open Source Model", "Unlimited Usage"], "latency_seconds": 40}]})
        return _Response({"data": []})


class _McpSession:
    def post(self, endpoint, *, headers, json, timeout):
        assert headers["Authorization"] == "Bearer test-key"
        assert json["params"]["name"] == "list-models"
        assert json["params"]["arguments"]["feature"] == "videofusion"
        assert json["params"]["arguments"]["tags"] == ["Unlimited Usage"]
        return _ResponseText('event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"{\\"models\\":[{\\"model_id\\":\\"wan2.6-t2v\\",\\"tags\\":[\\"Unlimited Usage\\"]}]}"}]}}')


class _ResponseText:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


class _PageSession:
    def get(self, endpoint, *, timeout):
        return _PageResponse("""## Overview\n- **Source Type**: Open Source Model\n- **Status**: model_ready\nUnlimited Usage""")


class _PageResponse:
    status_code = 200

    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


def test_normalize_model_detects_unlimited_metadata_and_operation():
    model = normalize_model({
        "model_id": "wan2.6-t2v",
        "provider": "alibaba_cloud",
        "tags": ["Open Source Model", "Unlimited Usage"],
    })

    assert model.unlimited_usage is True
    assert model.operation_type == "text_to_video"
    assert model.cost_usd is None


def test_fetch_catalog_paginates_and_deduplicates():
    session = _Session()
    models = fetch_catalog("test-key", feature="video_fusion", page_size=1, session=session)

    assert [model.model_id for model in models] == ["wan2.6-t2v"]
    assert session.calls[0][1]["feature"] == "video_fusion"
    assert len(session.calls) == 2


def test_fetch_catalog_mcp_uses_list_models_tool():
    models = fetch_catalog_mcp("test-key", feature="video_fusion", tags=["Unlimited Usage"], session=_McpSession())

    assert models[0].model_id == "wan2.6-t2v"
    assert models[0].unlimited_usage is True


def test_save_and_load_catalog_round_trip(tmp_path: Path):
    source = [normalize_model({"model_id": "flux", "tags": ["Unlimited Usage"]})]
    path = save_catalog(source, tmp_path / "catalog.json")

    loaded = load_catalog(path)
    assert loaded[0].model_id == "flux"
    assert loaded[0].unlimited_usage is True


def test_enrich_model_from_public_page_reads_source_and_unlimited_tag():
    model = normalize_model({"model_id": "h3-minimax-start-end-frame", "provider": "modelslab"})
    enriched = enrich_model_from_page(model, session=_PageSession())

    assert enriched.source_type == "Open Source Model"
    assert enriched.status == "model_ready"
    assert enriched.unlimited_usage is True


def test_recommend_models_prioritizes_unlimited_researched_family():
    models = [
        normalize_model({"model_id": "wan2.6-t2v", "tags": ["Unlimited Usage"]}),
        normalize_model({"model_id": "seedance-2.5-t2v", "cost": 0.30}),
    ]
    benchmarks = (BenchmarkProfile("wan", ("text_to_video",), 0.8, 0.95, (), "efficient"),)

    recommendations = recommend_models(models, operation="text_to_video", benchmarks=benchmarks)

    assert recommendations[0].model_id == "wan2.6-t2v"
    assert "Unlimited Usage tag" in recommendations[0].reasons
