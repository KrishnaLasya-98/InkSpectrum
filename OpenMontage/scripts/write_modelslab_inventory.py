"""Generate a Markdown inventory from cached ModelsLab catalog files."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


CACHE_DIR = Path("projects/modelslab")
OUTPUT = Path("docs/modelslab-model-inventory.md")
CATEGORIES = {
    "video_fusion": ("Video", "Video generation, image animation, video transformation, reference video, or lip sync."),
    "imagen": ("Image", "Image generation, image editing, image-to-image transformation, or inpainting."),
    "audio_gen": ("Audio", "Text-to-speech, speech-to-text, music, sound effects, dubbing, or voice transformation."),
    "llmaster": ("Chat / LLM", "Text generation, reasoning, coding, vision-language, or chat completion."),
    "threedverse": ("3D", "Text-to-3D or image-to-3D asset generation."),
}


def value(item: object) -> str:
    return "Not returned" if item in (None, "", []) else str(item)


def operation(model: dict[str, object], category: str) -> str:
    known = model.get("operation_type")
    if known:
        return str(known)
    return {
        "video_fusion": "Video generation / transformation; exact operation not returned",
        "imagen": "Image generation / editing; exact operation not returned",
        "audio_gen": "Audio generation / voice processing; exact operation not returned",
        "llmaster": "Chat / LLM completion; exact operation not returned",
        "threedverse": "3D asset generation; exact operation not returned",
    }[category]


def entitlement(model: dict[str, object]) -> str:
    unlimited = model.get("unlimited_usage")
    if unlimited is True:
        return "Unlimited Usage confirmed"
    if unlimited is False:
        return "Not Unlimited"
    return "Unknown; verify ModelsLab dashboard"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# ModelsLab Model Inventory",
        "",
        "Generated from the cached ModelsLab MCP catalog snapshots in `projects/modelslab/`.",
        "",
        "> This is a retrieved catalog inventory, not proof that every model is included in the $149 plan. The MCP response did not return subscription entitlement, cost, latency, or failure-rate metadata for most records. Confirm `Unlimited Usage` in the ModelsLab dashboard before batch use.",
        "",
        "## Snapshot Summary",
        "",
        "| Category | Cached models | Cache |",
        "|---|---:|---|",
    ]
    loaded: list[tuple[str, str, str, list[dict[str, object]]]] = []
    for key, (label, description) in CATEGORIES.items():
        path = CACHE_DIR / f"model_catalog_{key}.json"
        payload = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"models": []}
        models = payload.get("models", [])
        loaded.append((key, label, description, models))
        lines.append(f"| {label} | {len(models)} | `{path.as_posix()}` |")

    all_models = [model for _, _, _, models in loaded for model in models]
    source_counts = Counter(str(model.get("source_type") or "Unknown") for model in all_models)
    status_counts = Counter(str(model.get("status") or "Unknown") for model in all_models)
    unlimited_confirmed = sum(model.get("unlimited_usage") is True for model in all_models)
    lines.extend([
        "",
        "## Metadata Confirmation",
        "",
        f"- **Catalog records:** {len(all_models)}",
        f"- **Open Source Model:** {source_counts.get('Open Source Model', 0)}",
        f"- **Closed Source Model:** {source_counts.get('Closed Source Model', 0)}",
        f"- **Metadata source type missing:** {source_counts.get('Unknown', 0)}",
        f"- **Status `model_ready`:** {status_counts.get('model_ready', 0)}",
        f"- **Status missing:** {status_counts.get('Unknown', 0)}",
        f"- **Unlimited Usage confirmed by metadata:** {unlimited_confirmed}",
        "",
        "> Confirmation meaning: `Open Source Model` and `model_ready` are confirmed from the public model-page metadata. They do not confirm subscription inclusion. The Unlimited plan answer remains unknown unless the model metadata or dashboard explicitly says `Unlimited Usage`.",
        "",
    ])

    lines.extend(["", "## Model Details", ""])
    for key, label, description, models in loaded:
        lines.extend([f"### {label} ({len(models)})", "", description, ""])
        if not models:
            lines.extend(["No cache records found.", ""])
            continue
        lines.extend([
            "| Model ID | Provider | Operation / functionality | Tags | Source type | Status | Plan answer | Cost | Latency | Failure rate | Metadata page |",
            "|---|---|---|---|---|---|---|---:|---:|---:|---|",
        ])
        for model in sorted(models, key=lambda item: str(item.get("model_id", "")).lower()):
            model_id = value(model.get("model_id"))
            provider = value(model.get("provider"))
            functionality = operation(model, key)
            tags = ", ".join(str(tag) for tag in model.get("tags", [])) or "Not returned"
            source_type = value(model.get("source_type"))
            status = value(model.get("status"))
            cost = value(model.get("cost_usd"))
            latency = value(model.get("latency_seconds"))
            failure = value(model.get("failure_rate"))
            metadata_url = value(model.get("metadata_url"))
            lines.append(
                f"| `{model_id}` | {provider} | {functionality} | {tags} | {source_type} | {status} | {entitlement(model)} | {cost} | {latency} | {failure} | {metadata_url} |"
            )
        lines.append("")

    lines.extend([
        "## How To Refresh",
        "",
        "```powershell",
        "python scripts/modelslab_catalog.py fetch --feature video_fusion",
        "python scripts/modelslab_catalog.py fetch --feature imagen",
        "python scripts/modelslab_catalog.py fetch --feature audio_gen",
        "python scripts/modelslab_catalog.py fetch --feature llmaster",
        "python scripts/modelslab_catalog.py fetch --feature threedverse",
        "python scripts/modelslab_catalog.py enrich --feature video_fusion",
        "python scripts/write_modelslab_inventory.py",
        "```",
        "",
    ])
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUTPUT} with {sum(len(models) for _, _, _, models in loaded)} model records")


if __name__ == "__main__":
    main()