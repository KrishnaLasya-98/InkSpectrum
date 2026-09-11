"""ModelsLab catalog discovery, caching, and recommendation utilities.

The ModelsLab catalog is provider-owned and changes over time. This module
keeps raw responses in a local cache, normalizes common response shapes, and
never invents latency, failure-rate, or pricing values when the API omits them.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import requests


MODELSLAB_MODELS_URL = "https://modelslab.com/api/v7/models"
MODELSLAB_MCP_URL = "https://modelslab.com/mcp/v7"
MCP_FEATURE_ALIASES = {
    "video_fusion": "videofusion",
    "video-fusion": "videofusion",
    "audio_gen": "audiogen",
    "audio-gen": "audiogen",
    "3d": "threedverse",
    "3dverse": "threedverse",
}


@dataclass(frozen=True)
class CatalogModel:
    model_id: str
    provider: str | None = None
    operation_type: str | None = None
    cost_usd: float | None = None
    unlimited_usage: bool | None = None
    latency_seconds: float | None = None
    failure_rate: float | None = None
    source_type: str | None = None
    status: str | None = None
    metadata_url: str | None = None
    tags: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class BenchmarkProfile:
    """A research-backed preference, not a measured provider benchmark."""

    model_family: str
    operations: tuple[str, ...]
    quality_score: float
    efficiency_score: float
    source_urls: tuple[str, ...]
    notes: str


@dataclass(frozen=True)
class Recommendation:
    model_id: str
    score: float
    reasons: tuple[str, ...]
    model: CatalogModel
    benchmark: BenchmarkProfile | None = None


DEFAULT_BENCHMARKS = (
    BenchmarkProfile(
        "wan",
        ("text_to_video", "image_to_video", "video_to_video"),
        0.82,
        0.95,
        ("https://modelslab.com/models",),
        "Open-source Wan family is the first high-volume video candidate; verify the exact plan tag per model.",
    ),
    BenchmarkProfile(
        "flux",
        ("text_to_image", "image_to_image", "inpaint"),
        0.88,
        0.95,
        ("https://modelslab.com/models", "https://docs.modelslab.com/guides/model-selection"),
        "Strong general-purpose image baseline for repeated storyboard and asset generation.",
    ),
    BenchmarkProfile(
        "sdxl",
        ("text_to_image", "image_to_image", "inpaint"),
        0.80,
        0.98,
        ("https://modelslab.com/models", "https://docs.modelslab.com/guides/model-selection"),
        "Mature open-source image family with broad fine-tune compatibility and high throughput.",
    ),
    BenchmarkProfile(
        "ltx",
        ("text_to_video", "image_to_video"),
        0.84,
        0.84,
        ("https://modelslab.com/models",),
        "Efficient video candidate; benchmark locally against Wan for quality per second.",
    ),
    BenchmarkProfile(
        "qwen",
        ("text_to_speech", "text_to_image", "chat"),
        0.82,
        0.90,
        ("https://modelslab.com/models", "https://docs.modelslab.com/guides/model-selection"),
        "Use only when the catalog operation and Unlimited tag match the requested Qwen variant.",
    ),
)


def _first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _flatten_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [item for part in value for item in _flatten_strings(part)]
    if isinstance(value, dict):
        return [item for part in value.values() for item in _flatten_strings(part)]
    return []


def _unlimited(metadata: dict[str, Any], tags: Iterable[str]) -> bool | None:
    explicit = _first(metadata, "unlimited_usage", "unlimited", "is_unlimited")
    if isinstance(explicit, bool):
        return explicit
    if isinstance(explicit, str) and explicit.lower() in {"true", "yes", "1"}:
        return True
    if isinstance(explicit, str) and explicit.lower() in {"false", "no", "0"}:
        return False
    normalized = " ".join(tags).lower().replace("_", " ").replace("-", " ")
    if "unlimited usage" in normalized or "unlimited" in normalized:
        return True
    return None


def _operation(metadata: dict[str, Any], tags: Iterable[str]) -> str | None:
    value = _first(metadata, "operation_type", "operation", "task", "feature", "type")
    if isinstance(value, str):
        return value
    text = " ".join([str(metadata.get("model_id", "")), *tags]).lower().replace("_", " ").replace("-", " ")
    for needle, result in (
        ("text to video", "text_to_video"),
        ("t2v", "text_to_video"),
        ("image to video", "image_to_video"),
        ("i2v", "image_to_video"),
        ("video to video", "video_to_video"),
        ("v2v", "video_to_video"),
        ("text to image", "text_to_image"),
        ("t2i", "text_to_image"),
        ("image to image", "image_to_image"),
        ("i2i", "image_to_image"),
        ("text to speech", "text_to_speech"),
        ("chat", "chat"),
    ):
        if needle in text:
            return result
    return None


def normalize_model(item: dict[str, Any]) -> CatalogModel:
    metadata_value = item.get("metadata")
    metadata: dict[str, Any] = metadata_value if isinstance(metadata_value, dict) else {}
    merged = {**metadata, **item}
    tags = tuple(dict.fromkeys(_flatten_strings(_first(merged, "tags", "labels", "badges", "category"))))
    return CatalogModel(
        model_id=str(_first(merged, "model_id", "id", "slug", "name") or ""),
        provider=_first(merged, "provider", "provider_name", "vendor"),
        operation_type=_operation(merged, tags),
        cost_usd=_as_float(_first(merged, "cost", "price", "cost_usd", "price_per_generation")),
        unlimited_usage=_unlimited(merged, tags),
        latency_seconds=_as_float(_first(merged, "latency", "latency_seconds", "estimated_latency")),
        failure_rate=_as_float(_first(merged, "failure_rate", "error_rate")),
        source_type=_first(merged, "source_type", "source", "sourceType"),
        status=_first(merged, "status", "model_status"),
        metadata_url=_first(merged, "metadata_url", "url", "page_url"),
        tags=tags,
        raw=item,
    )


def enrich_model_from_page(model: CatalogModel, *, session: requests.Session | None = None) -> CatalogModel:
    """Merge public ModelsLab ``llms.txt`` metadata into one catalog record."""
    provider = (model.provider or "modelslab").strip().lower().replace(" ", "_")
    url = f"https://modelslab.com/models/{provider}/{model.model_id}/llms.txt"
    client = session or requests.Session()
    response = client.get(url, timeout=30)
    if response.status_code == 404:
        return model
    response.raise_for_status()
    text = response.text

    def field(label: str) -> str | None:
        match = __import__("re").search(rf"\*\*{label}\*\*:\s*`?([^`\n]+)", text, __import__("re").IGNORECASE)
        return match.group(1).strip() if match else None

    source_type = field("Source Type")
    status = field("Status")
    tags = list(model.tags)
    if source_type:
        tags.append(source_type)
    if __import__("re").search(r"Unlimited Usage", text, __import__("re").IGNORECASE):
        tags.append("Unlimited Usage")
    metadata = dict(model.raw)
    metadata.update({"source_type": source_type, "status": status, "metadata_url": url, "tags": tags})
    normalized = normalize_model(metadata)
    return CatalogModel(
        model_id=model.model_id,
        provider=normalized.provider or model.provider,
        operation_type=normalized.operation_type or model.operation_type,
        cost_usd=normalized.cost_usd if normalized.cost_usd is not None else model.cost_usd,
        unlimited_usage=normalized.unlimited_usage if normalized.unlimited_usage is not None else model.unlimited_usage,
        latency_seconds=model.latency_seconds,
        failure_rate=model.failure_rate,
        source_type=source_type or model.source_type,
        status=status or model.status,
        metadata_url=url,
        tags=tuple(dict.fromkeys(tags)),
        raw=metadata,
    )


def enrich_catalog_from_web(models: Iterable[CatalogModel], *, session: requests.Session | None = None) -> list[CatalogModel]:
    """Best-effort public-page enrichment; unavailable pages remain unchanged."""
    return [enrich_model_from_page(model, session=session) for model in models]


def _items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("data", "models", "results", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _items(value)
            if nested:
                return nested
    return []


def _mcp_json_response(response_text: str) -> Any:
    """Extract the JSON-RPC result from JSON or Server-Sent Events."""
    candidates = [response_text.strip()]
    candidates.extend(
        line[6:].strip()
        for line in response_text.splitlines()
        if line.startswith("data:")
    )
    for candidate in reversed(candidates):
        if not candidate or candidate == "[DONE]":
            continue
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("error"):
            error = payload["error"]
            raise RuntimeError(f"ModelsLab MCP error {error.get('code')}: {error.get('message')}")
        return payload.get("result", payload) if isinstance(payload, dict) else payload
    raise RuntimeError("ModelsLab MCP returned no JSON-RPC result")


def fetch_catalog_mcp(
    api_key: str | None = None,
    *,
    feature: str | None = None,
    tags: list[str] | None = None,
    limit: int = 100,
    session: requests.Session | None = None,
    endpoint: str = MODELSLAB_MCP_URL,
) -> list[CatalogModel]:
    """Discover models through the documented ModelsLab MCP list-models tool."""
    key = api_key or os.environ.get("MODELSLAB_API_KEY")
    if not key:
        raise ValueError("MODELSLAB_API_KEY is required")
    client = session or requests.Session()
    arguments: dict[str, Any] = {"limit": limit}
    if feature:
        arguments["feature"] = MCP_FEATURE_ALIASES.get(feature.lower(), feature)
    if tags:
        arguments["tags"] = tags
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "list-models", "arguments": arguments},
    }
    response = client.post(
        endpoint,
        headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json, text/event-stream",
        },
        json=request,
        timeout=30,
    )
    response.raise_for_status()
    result = _mcp_json_response(response.text)
    content = result.get("content", []) if isinstance(result, dict) else []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            try:
                result = json.loads(item["text"])
                break
            except (TypeError, json.JSONDecodeError):
                continue
    models = _items(result)
    if not models:
        if isinstance(result, dict) and result.get("status") in {"error", "failed"}:
            raise RuntimeError(
                f"ModelsLab MCP list-models failed (code: {result.get('code')}; "
                f"message: {result.get('message') or 'no message'})"
            )
        raise RuntimeError(
            "ModelsLab MCP list-models returned no model records. "
            "Check the feature filter and API permissions."
        )
    return list({model.model_id: model for model in (normalize_model(item) for item in models) if model.model_id}.values())


def fetch_catalog(
    api_key: str | None = None,
    *,
    feature: str | None = None,
    page_size: int = 100,
    max_pages: int = 100,
    session: requests.Session | None = None,
    endpoint: str = MODELSLAB_MODELS_URL,
) -> list[CatalogModel]:
    """Fetch all pages exposed by the ModelsLab models endpoint."""
    key = api_key or os.environ.get("MODELSLAB_API_KEY")
    if not key:
        raise ValueError("MODELSLAB_API_KEY is required")
    client = session or requests.Session()
    output: list[CatalogModel] = []
    for page in range(1, max_pages + 1):
        params: dict[str, Any] = {"key": key, "page": page, "limit": page_size}
        if feature:
            params["feature"] = feature
        response = client.get(endpoint, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and str(payload.get("status", "")).lower() in {"error", "failed"}:
            message = payload.get("message") or payload.get("error") or "no message"
            keys = ", ".join(sorted(str(key) for key in payload))
            raise RuntimeError(
                f"ModelsLab catalog request failed (HTTP {response.status_code}; "
                f"API status: {payload.get('status')}; code: {payload.get('code')}; "
                f"response keys: {keys}; message: {message})"
            )
        batch = _items(payload)
        if not batch:
            if page == 1:
                raise RuntimeError(
                    "ModelsLab catalog returned no model records. "
                    "Check the feature filter and inspect the API response envelope."
                )
            break
        output.extend(normalize_model(item) for item in batch)
        if len(batch) < page_size:
            break
    return list({model.model_id: model for model in output if model.model_id}.values())


def save_catalog(models: Iterable[CatalogModel], path: str | Path) -> Path:
    """Write a versioned JSON cache atomically."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "models": [{key: value for key, value in asdict(model).items() if key != "raw"} for model in models],
    }
    with tempfile.NamedTemporaryFile("w", dir=destination.parent, delete=False, encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        temporary = Path(handle.name)
    temporary.replace(destination)
    return destination


def load_catalog(path: str | Path) -> list[CatalogModel]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return [normalize_model(item) for item in payload.get("models", [])]


def _benchmark_for(model: CatalogModel, benchmarks: Iterable[BenchmarkProfile]) -> BenchmarkProfile | None:
    model_text = model.model_id.lower()
    for benchmark in benchmarks:
        if benchmark.model_family in model_text and (
            not benchmark.operations or model.operation_type in benchmark.operations
        ):
            return benchmark
    return None


def recommend_models(
    models: Iterable[CatalogModel],
    *,
    operation: str,
    benchmarks: Iterable[BenchmarkProfile] = DEFAULT_BENCHMARKS,
    unlimited_only: bool = False,
    limit: int = 10,
) -> list[Recommendation]:
    """Rank catalog models using plan status, research profile, cost, and metrics."""
    recommendations: list[Recommendation] = []
    for model in models:
        if model.operation_type and model.operation_type != operation:
            continue
        if unlimited_only and model.unlimited_usage is not True:
            continue
        benchmark = _benchmark_for(model, benchmarks)
        score = (benchmark.quality_score * 0.35 if benchmark else 0.15)
        score += (benchmark.efficiency_score * 0.30 if benchmark else 0.10)
        score += 0.25 if model.unlimited_usage is True else 0.0
        if model.cost_usd is not None:
            score += max(0.0, 0.10 - min(model.cost_usd, 0.10))
        if model.latency_seconds is not None:
            score += max(0.0, 0.05 - min(model.latency_seconds / 10000, 0.05))
        if model.failure_rate is not None:
            score -= min(max(model.failure_rate, 0.0), 1.0) * 0.20
        reasons = []
        if model.unlimited_usage is True:
            reasons.append("Unlimited Usage tag")
        if benchmark:
            reasons.append(benchmark.notes)
        if model.cost_usd is None:
            reasons.append("cost not reported by catalog")
        recommendations.append(Recommendation(model.model_id, round(score, 4), tuple(reasons), model, benchmark))
    return sorted(recommendations, key=lambda item: item.score, reverse=True)[:limit]