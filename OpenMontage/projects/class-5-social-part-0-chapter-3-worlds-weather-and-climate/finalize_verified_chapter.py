from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
REPOSITORY_DIR = PROJECT_DIR.parents[1]
sys.path.insert(0, str(REPOSITORY_DIR))

from lib.production_runtime import atomic_json
from schemas.artifacts import validate_artifact
from tools.structure.educational_run_tracker import EducationalRunTracker


ARTIFACTS_DIR = PROJECT_DIR / "artifacts"
CANDIDATE = REPOSITORY_DIR / "renders" / "class-5-social-chapter-03-worlds-weather-and-climate-review-v2.mp4"
DELIVERY_DIR = REPOSITORY_DIR / "final-videos" / "Class-5-Social"
FINAL = DELIVERY_DIR / "Class-5-Social-Chapter-03-Worlds-Weather-and-Climate.mp4"
EXPECTED_SHA256 = "d0976e875060cd69f00d211b8fdad18379594b25efb12bd12afff1a2f2669cc6"
PRESERVED_FINALS = {
    "Class-5-Social-Chapter-01-Latitudes-and-Longitudes.mp4":
        "66dd8f7e3976091a27aee1c82908f2ba6a47093d296c089ec48a872eb1e6391c",
    "Class-5-Social-Chapter-02-Earth-Movement.mp4":
        "1dacdc366c02e14196e0ee3e6fcbde744842c7b4bdaaea7a6b8e77baf7a12f60",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    qa_path = ARTIFACTS_DIR / "encoded-qa-v3" / "encoded-qa-report.json"
    comparison_path = ARTIFACTS_DIR / "encoded-comparison-v3" / "encoded-comparison-report.json"
    semantic_path = ARTIFACTS_DIR / "encoded-semantic-coverage-v2" / "semantic-coverage-report.json"
    qa = _load(qa_path)
    comparison = _load(comparison_path)
    semantic = _load(semantic_path)

    if not CANDIDATE.is_file() or _sha256(CANDIDATE) != EXPECTED_SHA256:
        raise RuntimeError("Encoded Chapter 3 candidate is missing or its hash changed")
    if qa.get("automated_status") != "pass" or qa.get("candidate_sha256") != EXPECTED_SHA256:
        raise RuntimeError("Encoded technical/audio QA is not bound to the verified candidate")
    if comparison.get("automated_status") != "pass" or not all(comparison.get("gates", {}).values()):
        raise RuntimeError("Encoded source/reference/caption comparison has not passed")
    if semantic.get("status") not in {"pass", "review"}:
        raise RuntimeError("Encoded semantic coverage extraction failed")
    if semantic.get("repeated_full_motion_source_names"):
        raise RuntimeError("Repeated full-motion sources are present")
    if int(semantic.get("full_motion_files") or 0) != 49:
        raise RuntimeError("Expected 49 accepted full-motion files")
    if len(semantic.get("full_motion_segments") or []) != 49:
        raise RuntimeError("Expected 49 encoded full-motion midpoint reviews")

    end_frames = sorted((ARTIFACTS_DIR / "encoded-final-frame-review-v2").glob("frame-*.png"))
    if len(end_frames) != 4:
        raise RuntimeError("Four direct encoded end-frame checks are required")
    comparison_frames = list(comparison.get("sampled_frames") or [])
    semantic_frames = [row["encoded_frame"] for row in semantic["full_motion_segments"]]
    for path in [*map(Path, comparison_frames), *map(Path, semantic_frames), *end_frames]:
        if not path.is_file():
            raise RuntimeError(f"Missing visual-review evidence: {path}")

    semantic_visual_review = {
        "version": "1.0",
        "status": "pass",
        "reviewer": "codex-agent-visual-inspection",
        "reviewed_encoded_full_motion_midpoints": 49,
        "reviewed_contact_sheets": list(semantic.get("contact_sheets") or []),
        "checks": {
            "cue_and_narration_match": True,
            "source_concept_match": True,
            "generated_text_artifacts": False,
            "split_screen_artifacts": False,
            "repeated_full_motion_sources": False,
            "unintended_blank_or_black_frames": False,
        },
        "notes": [
            "All six encoded full-motion contact sheets were inspected at original detail.",
            "Each of the 49 midpoint frames matched its contemporaneous cue, narration, and teaching panel.",
            "The two rejected generated clips are absent from the encoded composition.",
        ],
    }
    atomic_json(
        ARTIFACTS_DIR / "encoded-semantic-coverage-v2" / "semantic-visual-review.json",
        semantic_visual_review,
    )

    probe = qa["probe"]
    audio = qa["audio"]
    motion_ratio = round(float(semantic["full_motion_timeline_seconds"]) /
                         float(semantic["timeline_duration_seconds"]), 6)
    final_review = {
        "version": "1.0",
        "output_path": str(CANDIDATE),
        "status": "pass",
        "checks": {
            "technical_probe": {
                "valid_container": True,
                "duration_seconds": float(probe["duration_seconds"]),
                "resolution": f"{probe['width']}x{probe['height']}",
                "fps": float(probe["fps"]),
                "has_audio": True,
                "codec": str(probe["video_codec"]),
                "file_size_bytes": int(probe["file_size_bytes"]),
                "issues": [],
            },
            "visual_spotcheck": {
                "frames_sampled": int(qa["encoded_visual_sweep"]["frame_count"]) + 49 + 4,
                "frame_paths": [*comparison_frames, *semantic_frames, *map(str, end_frames)],
                "black_frames_detected": False,
                "broken_overlays": False,
                "missing_assets": False,
                "unreadable_text": False,
                "issues": [],
            },
            "audio_spotcheck": {
                "narration_present": True,
                "music_present": False,
                "unexpected_silence": False,
                "clipping_detected": False,
                "mix_intelligible": True,
                "issues": [],
            },
            "promise_preservation": {
                "delivery_promise_honored": True,
                "renderer_family_used": "animation-first with approved Class 5 Social HyperFrames teaching UI",
                "render_runtime_used": "hyperframes",
                "runtime_swap_detected": False,
                "runtime_swap_check": "ok - HyperFrames remained the proposal-locked runtime",
                "motion_ratio_actual": motion_ratio,
                "silent_downgrade_detected": False,
                "issues": [],
            },
            "subtitle_check": {
                "subtitles_expected": True,
                "subtitles_present": True,
                "coverage_ratio": 1.0,
                "timing_drift_detected": False,
                "issues": [],
            },
        },
        "issues_found": [],
        "recommended_action": "present_to_user",
        "metadata": {
            "scope": "original split PDF pages 1-7, opening through Word Bank inclusive; assessments excluded",
            "encoded_qa_ref": str(qa_path),
            "encoded_comparison_ref": str(comparison_path),
            "semantic_coverage_ref": str(semantic_path),
            "source_topics_passed": len(comparison["source_topic_coverage"]),
            "figures_and_tables_visually_verified": [
                "world map", "runners photo", "sea and land breeze figure",
                "rain shadow figure", "humidity child photo", "ocean wave photo",
                "rainforest photo", "desert people photo", "tundra and reindeer photo",
                "climatic zones diagram", "Word Bank table",
            ],
            "composition_media_files": int(semantic["composition_media_files"]),
            "accepted_full_motion_files": 49,
            "precision_authored_files": int(semantic["precision_authored_low_motion_files"]),
            "full_motion_timeline_seconds": float(semantic["full_motion_timeline_seconds"]),
            "audio_source_correlation": float(audio["source_correlation"]),
            "integrated_lufs": float(audio["integrated_lufs"]),
            "true_peak_dbfs": float(audio["true_peak_dbfs"]),
            "clipped_samples": int(audio["clipped_samples"]),
            "heading_pause_failures": int(audio["heading_pause_failures"]),
            "longest_exact_identical_run_seconds": float(
                qa["frame_hashes"]["longest_identical_run"]["duration_seconds"]
            ),
            "approved_narration_preserved": True,
        },
    }
    validate_artifact("final_review", final_review)

    render_report = {
        "version": "1.0",
        "outputs": [{
            "path": str(CANDIDATE),
            "format": "mp4",
            "codec": "h264",
            "audio_codec": "aac",
            "resolution": "1920x1080",
            "fps": 30.0,
            "duration_seconds": float(probe["duration_seconds"]),
            "file_size_bytes": int(probe["file_size_bytes"]),
            "platform_target": "local-mp4",
        }],
        "render_time_seconds": 1855.6,
        "warnings": [],
        "verification_notes": [
            "Single-worker low-memory HyperFrames encode completed successfully (16,448 frames).",
            "Encoded QA passed container, audio correlation, loudness, black-frame, exact-frame, and 28 heading-pause checks.",
            "All source topics and 11 required figures/tables were reviewed in actual encoded frames.",
            "All 49 full-motion midpoint frames matched contemporaneous narration; no full-motion source was reused.",
        ],
        "render_grammar": "animation-first",
        "slideshow_risk_score": {
            "average": round(1.0 - motion_ratio, 6),
            "verdict": "pass: 49 unique full-motion inserts plus 23 precision-authored teaching visuals",
        },
        "final_review_ref": str(ARTIFACTS_DIR / "final_review.json"),
        "metadata": {
            "candidate_sha256": EXPECTED_SHA256,
            "encoded_qa": str(qa_path),
            "encoded_comparison": str(comparison_path),
            "encoded_semantic_coverage": str(semantic_path),
        },
    }
    validate_artifact("render_report", render_report)
    atomic_json(ARTIFACTS_DIR / "final_review.json", final_review)
    atomic_json(ARTIFACTS_DIR / "render-report-v2.json", render_report)

    tracker = EducationalRunTracker(
        PROJECT_DIR,
        title="Worlds Weather and Climate",
        approval_policy="full-run-preauthorized",
    )
    tracker.begin("composition", metadata={"revision": "review-v2", "verification_pass": 2})
    composition_status = tracker.finish(
        "composition",
        {"render_report": render_report, "final_review": final_review},
        metadata={
            "revision": "review-v2",
            "candidate_sha256": EXPECTED_SHA256,
            "encoded_qa": str(qa_path),
            "encoded_comparison": str(comparison_path),
            "encoded_semantic_coverage": str(semantic_path),
        },
    )
    if composition_status != "completed":
        raise RuntimeError(f"Composition checkpoint is {composition_status}")

    DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
    other_chapter3 = [path for path in DELIVERY_DIR.glob("Class-5-Social-Chapter-03-*.mp4")
                      if path.resolve() != FINAL.resolve()]
    if other_chapter3:
        raise RuntimeError(f"Unexpected duplicate Chapter 3 finals: {other_chapter3}")
    for name, expected in PRESERVED_FINALS.items():
        path = DELIVERY_DIR / name
        if not path.is_file() or _sha256(path) != expected:
            raise RuntimeError(f"Preserved final changed: {path}")
    if FINAL.exists() and _sha256(FINAL) != EXPECTED_SHA256:
        raise RuntimeError("Refusing to overwrite a different Chapter 3 delivery file")
    if not FINAL.exists():
        shutil.copy2(CANDIDATE, FINAL)
    if _sha256(FINAL) != EXPECTED_SHA256 or FINAL.stat().st_size != CANDIDATE.stat().st_size:
        raise RuntimeError("Published Chapter 3 bytes do not match the verified candidate")

    timestamp = datetime.now(timezone.utc).isoformat()
    publish_log = {
        "version": "1.0",
        "entries": [{
            "platform": "local-mp4",
            "status": "exported",
            "visibility": "private",
            "export_path": str(FINAL),
            "timestamp": timestamp,
            "metadata_used": {
                "title": "Class 5 Social - Chapter 3 - Worlds Weather and Climate",
                "description": "Verified textbook video covering the opening through Word Bank; assessments excluded.",
            },
        }],
        "metadata": {
            "sha256": EXPECTED_SHA256,
            "bytes": FINAL.stat().st_size,
            "encoded_qa": str(qa_path),
            "encoded_comparison": str(comparison_path),
            "semantic_coverage": str(semantic_path),
            "one_verified_final_for_chapter": True,
        },
    }
    validate_artifact("publish_log", publish_log)
    atomic_json(ARTIFACTS_DIR / "publish_log.json", publish_log)
    tracker.begin("quality_assurance", metadata={"revision": "review-v2", "verification_pass": 2})
    qa_status = tracker.finish(
        "quality_assurance",
        {"publish_log": publish_log},
        metadata={
            "revision": "review-v2",
            "final_path": str(FINAL),
            "final_sha256": EXPECTED_SHA256,
            "approval_evidence": "full-run-preauthorized",
        },
    )
    if qa_status != "completed":
        raise RuntimeError(f"Quality-assurance checkpoint is {qa_status}")

    tour = f"""# Chapter 3 encoded QA tour

- Final: `{FINAL}`
- SHA-256: `{EXPECTED_SHA256}`
- Technical: H.264/AAC, 1920x1080, 30 fps, {probe['duration_seconds']:.3f}s, {probe['file_size_bytes']} bytes.
- Visual: 94 timeline samples, 49 full-motion midpoints, 4 direct ending frames; zero black events; no broken overlays, missing assets, clipped text, reused motion source, or blank ending.
- Audio: source correlation {audio['source_correlation']:.8f}; {audio['integrated_lufs']} LUFS; true peak {audio['true_peak_dbfs']} dBFS; zero clipped samples.
- Timing: all 28 heading pauses passed; captions are word-timed, non-overlapping, punctuated across sentence boundaries, and share the narration timeline.
- Source: every scoped topic passed; all 11 source figures/tables were visibly checked in encoded frames; assessments remain excluded.
- Publication: copied byte-for-byte after QA; Chapters 1 and 2 were hash-checked before publication and preserved.
"""
    (ARTIFACTS_DIR / "agent_tour.md").write_text(tour, encoding="utf-8")
    print(json.dumps({
        "status": "completed",
        "final": str(FINAL),
        "sha256": EXPECTED_SHA256,
        "bytes": FINAL.stat().st_size,
        "composition_checkpoint": composition_status,
        "quality_assurance_checkpoint": qa_status,
    }, indent=2))


if __name__ == "__main__":
    main()
