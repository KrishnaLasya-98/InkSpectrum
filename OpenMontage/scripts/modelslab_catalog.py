"""Fetch, cache, and rank the ModelsLab catalog.

Examples:
    python scripts/modelslab_catalog.py fetch --feature video_fusion
    python scripts/modelslab_catalog.py recommend --operation text_to_video --unlimited-only
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from lib.modelslab_catalog import (
    enrich_catalog_from_web,
    fetch_catalog,
    fetch_catalog_mcp,
    load_catalog,
    recommend_models,
    save_catalog,
)


DEFAULT_CACHE_DIR = Path("projects/modelslab")


def default_cache(feature: str | None) -> Path:
    """Keep each ModelsLab feature catalog in its own cache file."""
    suffix = (feature or "all").lower().replace("-", "_")
    return DEFAULT_CACHE_DIR / f"model_catalog_{suffix}.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the ModelsLab model catalog")
    parser.add_argument("command", choices=("fetch", "enrich", "recommend"))
    parser.add_argument("--feature", help="ModelsLab feature filter, e.g. video_fusion or imagen")
    parser.add_argument("--source", choices=("mcp", "api"), default="mcp")
    parser.add_argument("--operation", help="Normalized operation for recommendations")
    parser.add_argument("--cache", type=Path, help="Cache path; defaults to a feature-specific file")
    parser.add_argument("--unlimited-only", action="store_true")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    cache_path = args.cache or default_cache(args.feature)

    if args.command == "fetch":
        fetcher = fetch_catalog_mcp if args.source == "mcp" else fetch_catalog
        fetch_kwargs = {"feature": args.feature}
        if args.unlimited_only and args.source == "mcp":
            fetch_kwargs["tags"] = ["Unlimited Usage"]
        try:
            models = fetcher(**fetch_kwargs)
        except RuntimeError as exc:
            if not args.unlimited_only or "no model records" not in str(exc):
                raise
            print(json.dumps({
                "cache": str(cache_path),
                "count": 0,
                "unlimited_usage_metadata": False,
                "message": (
                    "ModelsLab MCP returned no models for the Unlimited Usage tag. "
                    "The dashboard is required to confirm subscription entitlements. "
                    "The existing full catalog cache was preserved."
                ),
            }, indent=2))
            return 0
        save_catalog(models, cache_path)
        print(json.dumps({"cache": str(cache_path), "count": len(models)}, indent=2))
        return 0

    if args.command == "enrich":
        if not cache_path.is_file():
            parser.error(f"catalog cache not found: {cache_path}; run fetch first")
        models = enrich_catalog_from_web(load_catalog(cache_path))
        save_catalog(models, cache_path)
        unlimited = sum(model.unlimited_usage is True for model in models)
        print(json.dumps({"cache": str(cache_path), "count": len(models), "unlimited_tagged": unlimited}, indent=2))
        return 0

    if not args.operation:
        parser.error("recommend requires --operation")
    if not cache_path.is_file():
        parser.error(f"catalog cache not found: {cache_path}; run fetch first or pass --cache")
    recommendations = recommend_models(
        load_catalog(cache_path),
        operation=args.operation,
        unlimited_only=args.unlimited_only,
        limit=args.limit,
    )
    print(json.dumps([
        {
            "model_id": item.model_id,
            "score": item.score,
            "provider": item.model.provider,
            "unlimited_usage": item.model.unlimited_usage,
            "cost_usd": item.model.cost_usd,
            "latency_seconds": item.model.latency_seconds,
            "failure_rate": item.model.failure_rate,
            "reasons": item.reasons,
        }
        for item in recommendations
    ], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())