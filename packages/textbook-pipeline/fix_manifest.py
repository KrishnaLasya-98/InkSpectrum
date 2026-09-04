"""Update manifest to use .jpg instead of .mp4 (since we removed the mock video)."""

import json
from pathlib import Path

manifest_path = Path("D:/new_video_pip/textbook-pipeline/projects/english_class1_pymupdf/remotion_composition_manifest.json")

with open(manifest_path) as f:
    data = json.load(f)

for scene in data:
    bg = scene.get("background_asset", "")
    if bg and bg.endswith(".mp4"):
        new_bg = bg.replace(".mp4", ".jpg")
        scene["background_asset"] = new_bg
        print(f"Updated: {bg} -> {new_bg}")

# Also copy to remotion_renderer
src_manifest = Path("D:/new_video_pip/textbook-pipeline/remotion_renderer/src/manifest.json")
with open(src_manifest, "w") as f:
    json.dump(data, f, indent=2)

with open(manifest_path, "w") as f:
    json.dump(data, f, indent=2)

print("✅ Manifests updated")
