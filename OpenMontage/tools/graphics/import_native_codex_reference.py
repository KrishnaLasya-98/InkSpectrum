"""Import a native Codex image result into a chapter with durable provenance.

The image generation itself is performed through Codex's native image tool,
not a local API-key wrapper. This command validates and atomically records the
downloaded result; it never makes a paid provider request.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image

from lib.production_runtime import atomic_json


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def import_reference(project: Path, request: Path, source: Path) -> dict:
    project = project.resolve()
    request = request.resolve()
    source = source.resolve()
    if not request.is_relative_to(project) or not request.is_file():
        raise ValueError("Native request manifest must be inside the chapter project")
    manifest = json.loads(request.read_text(encoding="utf-8"))
    if manifest.get("version") != "1.0" or manifest.get("provider") != "native_codex":
        raise ValueError("Not a native Codex reference request")
    prompt = str(manifest.get("prompt") or "")
    if hashlib.sha256(prompt.encode("utf-8")).hexdigest() != manifest.get("prompt_sha256"):
        raise ValueError("Native request prompt hash is invalid")
    if manifest.get("status") != "awaiting_native_codex_generation":
        raise ValueError("Native request is not awaiting an imported result")
    if not source.is_file():
        raise FileNotFoundError(source)
    with Image.open(source) as image:
        image.verify()
    with Image.open(source) as image:
        width, height = image.size
        image_format = image.format
    if width < 1024 or height < 768 or image_format not in {"PNG", "JPEG", "WEBP"}:
        raise ValueError("Native reference must be a valid PNG/JPEG/WEBP at least 1024x768")
    output = Path(str(manifest.get("output_path") or ""))
    if not output.is_absolute():
        raise ValueError("Native request output_path must be absolute")
    output = output.resolve()
    allowed = (project / "assets" / "images").resolve()
    if not output.is_relative_to(allowed):
        raise ValueError("Native reference output must be under the chapter assets/images directory")
    state = request.with_suffix(".result.json")
    if output.exists() or state.exists():
        raise FileExistsError("Durable native result already exists; do not overwrite or resubmit")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".partial")
    shutil.copyfile(source, temporary)
    temporary.replace(output)
    result = {
        "version": "1.0", "provider": "native_codex", "status": "imported",
        "target": manifest.get("target"), "prompt_sha256": manifest["prompt_sha256"],
        "output_path": str(output), "output_sha256": digest(output),
        "source_sha256": digest(source), "dimensions": [width, height],
        "paid_wrapper_used": False,
    }
    atomic_json(state, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(import_reference(args.project, args.request, args.source), indent=2))


if __name__ == "__main__":
    main()
