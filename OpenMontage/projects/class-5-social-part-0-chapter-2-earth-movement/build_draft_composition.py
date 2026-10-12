"""Build a non-deliverable Chapter 2 HyperFrames layout for visual review.

The source PDF, reviewed plan, measured narration, and timed clip schedule are
authoritative. This draft must not be rendered/published as a final chapter.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.video.educational_hyperframes_composer import EducationalHyperFramesComposer


PROJECT = Path(__file__).resolve().parent
REPOSITORY = PROJECT.parents[1]


def main() -> None:
    clips = json.loads(
        (PROJECT / "artifacts/clip-manifest-draft-v1.json").read_text(encoding="utf-8")
    )
    if clips.get("status") != "draft_not_render_ready":
        raise ValueError("Chapter 2 clip schedule must remain an explicitly marked draft")
    pages = json.loads(
        (PROJECT / "artifacts/teaching-pages-draft-v1.json").read_text(encoding="utf-8")
    )
    if pages.get("unmatched_anchors"):
        raise ValueError("Teaching-page narration anchors require manual resolution")
    safe = json.loads(
        (PROJECT / "artifacts/render-safe-media-v1.json").read_text(encoding="utf-8")
    )
    safe_paths = {
        (record["section_id"], record["segment_index"]): record
        for record in safe["records"]
    }
    for clip in clips["clips"]:
        teaching_pages = pages["sections"].get(clip["section_id"])
        if teaching_pages:
            clip["teaching_pages"] = teaching_pages
        for index, segment in enumerate(clip.get("visual_segments") or [], 1):
            record = safe_paths[(clip["section_id"], index)]
            if segment["path"] != record["original_path"]:
                raise ValueError(f"Render-safe provenance mismatch for {clip['section_id']}")
            segment["path"] = record["render_safe_path"]
    result = EducationalHyperFramesComposer().execute({
        "workspace_path": str(PROJECT / "hyperframes-draft-v1"),
        "asset_base_dir": str(PROJECT),
        "template_contract": str(REPOSITORY / "styles/hyperframes-educational-v1.yaml"),
        "educational_plan": str(PROJECT / "artifacts/educational_plan.json"),
        "clip_manifest": clips,
        "narration_manifest": str(PROJECT / "assets/audio/narration-v1/narration_manifest.json"),
        "multimedia_sync_plan": str(PROJECT / "artifacts/multimedia-sync-draft-v1.json"),
        "word_captions": str(PROJECT / "artifacts/alignment-v1/word_captions.json"),
        "presentation_variant": json.loads((PROJECT / "chapter_config.json").read_text(encoding="utf-8"))["presentation_variant"],
    })
    if not result.success:
        raise RuntimeError(result.error)
    print(json.dumps(result.data, indent=2))


if __name__ == "__main__":
    main()
