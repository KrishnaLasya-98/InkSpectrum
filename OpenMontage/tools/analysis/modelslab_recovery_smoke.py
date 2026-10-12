"""Live submit/persist/resume smoke test for the ModelsLab video adapter.

This intentionally performs one paid generation. It never prints or persists
the provider credential. The first adapter instance submits only; a fresh
instance then recovers the same request from its durable sidecar and downloads
the result, proving that a restarted agent does not submit a duplicate job.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from tools.video.modelslab_video import ModelsLabVideo, upload_modelslab_media


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-id", default="wan2.2")
    parser.add_argument(
        "--operation",
        choices=("text_to_video", "image_to_video", "reference_to_video"),
        default="text_to_video",
    )
    parser.add_argument("--reference-image", type=Path)
    parser.add_argument("--duration", default="5")
    parser.add_argument("--resolution", default="768")
    parser.add_argument("--fps", type=int, default=18)
    parser.add_argument("--num-frames", type=int, default=90)
    parser.add_argument("--prompt-file", type=Path, help="Source-grounded scene prompt for this smoke test")
    parser.add_argument("--resume-job", type=Path, help="Recover a saved provider job only; never submit a new job")
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.resume_job:
        state = json.loads(args.resume_job.read_text(encoding="utf-8"))
        if state.get("provider") != "modelslab" or not state.get("request_id"):
            raise SystemExit("A ModelsLab job sidecar with a request ID is required")
        result = ModelsLabVideo().execute({
            "resume_request_id": str(state["request_id"]),
            "model_id": state["model_id"],
            "operation": state["operation"],
            "generate_audio": False, "educational_mode": True,
            "output_path": str(output),
        })
        report = {
            "status": "recovered" if result.success else "blocked",
            "request_id": str(state["request_id"]),
            "model_id": state["model_id"], "new_submission": False,
            "output_path": str(output), "error": result.error,
            "output_bytes": output.stat().st_size if output.is_file() else 0,
        }
        output.with_suffix(".recovery-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0 if result.success else 2
    request = {
        "prompt": (
            "A polished child-friendly 3D animated red kite gently moving in a "
            "sunny blue sky above a green school playground, steady camera, "
            "clear natural motion, no text, no logos"
        ),
        "negative_prompt": (
            "still image, frozen frame, text, watermark, duplicated objects, "
            "distortion, camera shake"
        ),
        "operation": "text_to_video",
        "model_id": args.model_id,
        "duration": args.duration,
        "resolution": args.resolution,
        "fps": args.fps,
        "num_frames": args.num_frames,
        "educational_mode": True,
        "generate_audio": False,
        "output_path": str(output),
    }
    if args.operation != "text_to_video":
        request["operation"] = args.operation
    if args.reference_image:
        reference_path = args.reference_image.resolve()
        if not reference_path.is_file():
            raise SystemExit(f"Reference image not found: {reference_path}")
        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
        api_key = os.environ.get("MODELSLAB_API_KEY", "")
        if not api_key:
            raise SystemExit("MODELSLAB_API_KEY is not configured")
        reference_url = upload_modelslab_media(str(reference_path), api_key)
        if args.operation == "image_to_video":
            request["image_url"] = reference_url
        elif args.operation == "reference_to_video":
            request["reference_image_urls"] = [reference_url]
        else:
            raise SystemExit("--reference-image requires an image/reference-to-video operation")
        request["prompt"] = (
            "Use Image 1 as the exact character and garden reference. Animate "
            "the child walking slowly along the garden path while leaves sway, "
            "a butterfly flutters naturally, and pond water ripples. Preserve "
            "the child's face, clothes, proportions, and polished child-friendly "
            "3D animated style. Smooth steady camera, no text, no logos."
        )
    if args.prompt_file:
        request["prompt"] = args.prompt_file.read_text(encoding="utf-8").strip()
        if not request["prompt"]:
            raise SystemExit("Prompt file must not be empty")
    started = time.time()
    submitted = ModelsLabVideo().execute({**request, "submit_only": True})
    if not submitted.success:
        report = {
            "status": "blocked", "stage": "provider_submission",
            "job_created": False, "output_exists": False,
            "reason": submitted.error, "credential_persisted": False,
            "live_recovery_validated": False,
            "elapsed_seconds": round(time.time() - started, 2),
        }
        report_path = output.with_suffix(output.suffix + ".recovery-report.json")
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2
    request_id = str(submitted.data.get("request_id") or "")
    if not request_id:
        raise SystemExit("ModelsLab submission returned no request ID")

    # A new adapter instance simulates process/agent restart. The durable
    # sidecar must supply the provider handle; this call must not resubmit.
    recovered = ModelsLabVideo().execute(request)
    report = {
        "status": "pass" if recovered.success else "fail",
        "model_id": args.model_id,
        "operation": request["operation"],
        "submitted_request_id": request_id,
        "recovered_request_id": recovered.data.get("request_id"),
        "same_request": request_id == recovered.data.get("request_id"),
        "resumed": recovered.data.get("resumed"),
        "output_path": str(output),
        "job_state_path": recovered.data.get("job_state_path"),
        "output_exists": output.is_file() and output.stat().st_size > 0,
        "output_bytes": output.stat().st_size if output.is_file() else 0,
        "estimated_submission_cost_usd": submitted.cost_usd,
        "resume_cost_usd": recovered.cost_usd,
        "elapsed_seconds": round(time.time() - started, 2),
        "probe": {key: recovered.data.get(key) for key in (
            "duration_seconds", "video_width", "video_height", "video_codec", "file_size_bytes"
        )},
        "error": recovered.error,
    }
    report_path = output.with_suffix(output.suffix + ".recovery-report.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if all((report["status"] == "pass", report["same_request"],
                     report["resumed"], report["output_exists"])) else 1


if __name__ == "__main__":
    raise SystemExit(main())
