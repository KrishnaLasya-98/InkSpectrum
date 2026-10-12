"""Hash-bound, fail-closed approval receipt for educational composition."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.structure.educational_regression_gates import (
    validate_interval_labeling,
    validate_stable_visual_exceptions,
    validate_pre_render_timeline,
    validate_timed_narration,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rows(value: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in keys:
            if isinstance(value.get(key), list):
                return value[key]
    raise ValueError(f"Expected a list or one of wrapper keys {keys}")


def create_pre_render_receipt(
    *,
    project_path: str | Path,
    intervals_path: str | Path,
    assignments_path: str | Path,
    teaching_pages_path: str | Path,
    narration_manifest_path: str | Path,
    output_path: str | Path,
    voice_id: str,
    model_id: str,
    speed: float,
    require_stable_visual_exceptions: bool = False,
) -> dict[str, Any]:
    """Validate the full reviewed timeline and bind approval to every input byte."""

    project = Path(project_path).resolve()
    named = {
        "intervals": Path(intervals_path).resolve(),
        "assignments": Path(assignments_path).resolve(),
        "teaching_pages": Path(teaching_pages_path).resolve(),
        "narration_manifest": Path(narration_manifest_path).resolve(),
    }
    missing = [str(path) for path in named.values() if not path.is_file()]
    if missing:
        raise ValueError(f"Pre-render receipt inputs missing: {missing}")

    intervals = _rows(_load(named["intervals"]), "intervals", "routes")
    assignments = _rows(_load(named["assignments"]), "assignments", "routes")
    teaching_pages = _rows(_load(named["teaching_pages"]), "teaching_pages", "pages")
    narration = _load(named["narration_manifest"])
    gates = {
        "interval_labeling": validate_interval_labeling(intervals),
        "pre_render_timeline": validate_pre_render_timeline(
            intervals, assignments, teaching_pages
        ),
        "timed_narration": validate_timed_narration(
            narration, voice_id=voice_id, model_id=model_id, speed=speed
        ),
    }
    if require_stable_visual_exceptions:
        gates["stable_visual_exceptions"] = validate_stable_visual_exceptions(
            intervals, assignments
        )

    input_hashes = {name: _sha256(path) for name, path in named.items()}
    media_hashes: dict[str, str] = {}
    for row in assignments:
        raw = str(row.get("media_path") or "").strip()
        if not raw:
            continue
        media = Path(raw)
        if not media.is_absolute():
            media = (project / media).resolve()
        if not media.is_file():
            raise ValueError(f"Assigned media missing: {media}")
        media_hashes[str(media)] = _sha256(media)

    receipt = {
        "version": "1.0",
        "status": "pass",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_path": str(project),
        "inputs": {name: str(path) for name, path in named.items()},
        "input_sha256": input_hashes,
        "media_sha256": media_hashes,
        "locks": {"voice_id": voice_id, "model_id": model_id, "speed": speed},
        "required_gates": (["stable_visual_exceptions"] if require_stable_visual_exceptions else []),
        "gates": gates,
    }
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    return receipt


def verify_pre_render_receipt(receipt_path: str | Path) -> dict[str, Any]:
    """Reject stale approvals whenever an artifact or assigned media byte changes."""

    path = Path(receipt_path).resolve()
    receipt = _load(path)
    if receipt.get("status") != "pass":
        raise ValueError("Pre-render regression receipt is not passed")
    for gate in receipt.get("required_gates", []):
        if receipt.get("gates", {}).get(gate, {}).get("status") != "pass":
            raise ValueError(f"Pre-render required gate missing or failed: {gate}")
    issues: list[str] = []
    for name, expected in receipt.get("input_sha256", {}).items():
        source = Path(receipt.get("inputs", {}).get(name, ""))
        if not source.is_file():
            issues.append(f"{name}: input missing")
        elif _sha256(source) != expected:
            issues.append(f"{name}: input changed after approval")
    for raw, expected in receipt.get("media_sha256", {}).items():
        media = Path(raw)
        if not media.is_file():
            issues.append(f"media missing: {media}")
        elif _sha256(media) != expected:
            issues.append(f"media changed after approval: {media}")
    if issues:
        raise ValueError("; ".join(issues))
    return {
        "status": "pass",
        "receipt_path": str(path),
        "inputs_verified": len(receipt.get("input_sha256", {})),
        "media_verified": len(receipt.get("media_sha256", {})),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--intervals", required=True)
    parser.add_argument("--assignments", required=True)
    parser.add_argument("--teaching-pages", required=True)
    parser.add_argument("--narration-manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--voice-id", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--speed", required=True, type=float)
    args = parser.parse_args()
    receipt = create_pre_render_receipt(
        project_path=args.project,
        intervals_path=args.intervals,
        assignments_path=args.assignments,
        teaching_pages_path=args.teaching_pages,
        narration_manifest_path=args.narration_manifest,
        output_path=args.output,
        voice_id=args.voice_id,
        model_id=args.model_id,
        speed=args.speed,
    )
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
