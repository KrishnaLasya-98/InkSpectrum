"""ModelsLab video generation via v7 Video Fusion API.

Best for alternative cloud video generation with 40+ models including
Seedance, Wan, Veo, Sora, Kling, and Hailuo via a single API key.
"""

from __future__ import annotations

import os
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

from tools.video._modelslab_shared import (
    download_modelslab_output,
    estimate_modelslab_cost,
    estimate_modelslab_runtime,
    poll_modelslab,
    submit_modelslab,
    upload_modelslab_media,
)
from tools.video.modelslab_capabilities import (
    DEFAULT_MODELS_BY_OPERATION,
    resolve_modelslab_video_contract,
)


_RECOVERABLE_JOB_STATES = {"submitted", "processing", "timed_out", "poll_error"}


def _job_state_path(output_path: Path) -> Path:
    return output_path.with_suffix(output_path.suffix + ".modelslab-job.json")


def _request_fingerprint(model_id: str, operation: str, payload: dict[str, Any]) -> str:
    safe = {key: value for key, value in payload.items() if key != "key"}
    raw = json.dumps({"model_id": model_id, "operation": operation, "payload": safe},
                     sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _read_job_state(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _write_job_state(path: Path, state: dict[str, Any]) -> None:
    """Atomically persist a provider handle. Never store credentials."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _strip_audio_track(output_path: Path) -> None:
    """Make a downloaded educational clip physically silent.

    Provider flags are not a sufficient guarantee across model families.  The
    final local file is therefore remuxed with ``-an`` before it can enter an
    educational composition.
    """

    if not output_path.is_file():
        return
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError(
            "ffmpeg is required to enforce silent educational video outputs"
        )
    silent_path = output_path.with_name(f"{output_path.stem}.silent{output_path.suffix}")
    completed = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(output_path),
            "-map",
            "0:v:0",
            "-c:v",
            "copy",
            "-an",
            str(silent_path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if completed.returncode != 0 or not silent_path.is_file():
        silent_path.unlink(missing_ok=True)
        raise RuntimeError(
            "Could not remove generated audio from educational clip: "
            f"{completed.stderr[-500:]}"
        )
    silent_path.replace(output_path)


class ModelsLabVideo(BaseTool):
    name = "modelslab_video"
    version = "0.2.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "modelslab"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:MODELSLAB_API_KEY"]
    install_instructions = (
        "Set MODELSLAB_API_KEY to your ModelsLab API key.\n"
        "  Get one at https://modelslab.com"
    )
    agent_skills = ["modelslab-video-generation"]

    capabilities = [
        "text_to_video",
        "image_to_video",
        "reference_to_video",
        "video_to_video",
        "lip_sync",
    ]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_to_video": True,
        "video_to_video": True,
        "lip_sync": True,
        "aspect_ratio": True,
        "seed": True,
        "native_audio": True,
        "multi_shot": True,
        "camera_direction": True,
        "cinematic_quality": True,
    }
    best_for = [
        "ModelsLab video generation via v7 Video Fusion API",
        "alternative to fal.ai with 40+ models including Seedance, Wan, Veo, Sora, Kling, Hailuo",
        "text-to-video, image-to-video, video-to-video, lip-sync, and motion control",
        "direct API access with single API key for multiple model families",
    ]
    not_good_for = ["offline generation", "budget-constrained projects"]
    fallback_tools = ["seedance_video", "kling_video", "minimax_video", "heygen_video"]
    quality_score = 0.92

    input_schema = {
        "type": "object",
        "anyOf": [{"required": ["prompt"]}, {"required": ["resume_request_id"]}],
        "properties": {
            "prompt": {"type": "string"},
            "negative_prompt": {
                "type": "string",
                "description": "Visual and motion artifacts the provider should avoid",
            },
            "operation": {
                "type": "string",
                "enum": [
                    "text_to_video",
                    "image_to_video",
                    "reference_to_video",
                    "video_to_video",
                    "lip_sync",
                ],
                "default": "text_to_video",
            },
            "model_id": {
                "type": "string",
                "description": "ModelsLab model identifier (e.g., 'seedance', 'wan', 'veo')",
            },
            "model_variant": {
                "type": "string",
                "enum": ["standard", "fast"],
                "default": "standard",
                "description": "standard = highest quality, fast = lower latency and cost",
            },
            "duration": {
                "type": "string",
                "enum": [
                    "auto",
                    "4",
                    "5",
                    "6",
                    "7",
                    "8",
                    "9",
                    "10",
                    "11",
                    "12",
                    "13",
                    "14",
                    "15",
                    "16",
                    "17",
                    "18",
                    "19",
                    "20",
                    "21",
                    "22",
                    "23",
                    "24",
                    "25",
                    "26",
                    "27",
                    "28",
                    "29",
                    "30",
                ],
                "default": "5",
                "description": "Duration in seconds. 'auto' lets the model decide.",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["auto", "21:9", "16:9", "4:3", "1:1", "3:4", "9:16"],
                "default": "16:9",
            },
            "resolution": {
                "type": "string",
                "enum": ["480p", "720p", "768P", "1080p"],
                "default": "720p",
            },
            "fps": {
                "type": "integer",
                "minimum": 16,
                "maximum": 25,
                "description": "Output frame rate for models that expose FPS controls",
            },
            "num_frames": {
                "type": "integer",
                "minimum": 81,
                "maximum": 122,
                "description": "Frame count for ModelsLab Wan 2.2 variants",
            },
            "generate_audio": {
                "type": "boolean",
                "default": True,
                "description": "Generate synchronized audio",
            },
            "educational_mode": {
                "type": "boolean",
                "default": False,
                "description": (
                    "Force provider audio off and strip any audio track after "
                    "download; approved narration remains authoritative"
                ),
            },
            "image_url": {
                "type": "string",
                "description": "Start frame image URL for image_to_video",
            },
            "image_path": {
                "type": "string",
                "description": "Local start-frame path for image_to_video",
            },
            "end_image_url": {
                "type": "string",
                "description": "Optional end frame URL for image_to_video",
            },
            "reference_image_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Reference image URLs for reference_to_video",
            },
            "reference_image_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Local reference image paths for reference_to_video",
            },
            "reference_video_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Reference video clip URLs for reference_to_video",
            },
            "reference_audio_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Reference audio clip URLs for reference_to_video",
            },
            "video_url": {
                "type": "string",
                "description": "Source video URL for video_to_video",
            },
            "video_path": {
                "type": "string",
                "description": "Local source video path for video_to_video",
            },
            "audio_url": {
                "type": "string",
                "description": "Audio URL for lip_sync",
            },
            "audio_path": {
                "type": "string",
                "description": "Local audio path for lip_sync",
            },
            "width": {
                "type": "integer",
                "description": "Output width in pixels",
            },
            "height": {
                "type": "integer",
                "description": "Output height in pixels",
            },
            "seed": {
                "type": "integer",
                "description": "Optional seed for reproducibility",
            },
            "output_path": {"type": "string"},
            "submit_only": {
                "type": "boolean",
                "default": False,
                "description": "Return the provider request ID without waiting for completion",
            },
            "resume_request_id": {
                "type": "string",
                "description": "Poll/download an already submitted request without creating another paid job",
            },
            "poll_endpoint": {"type": "string"},
            "job_state_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2, retryable_errors=["rate_limit", "timeout"]
    )
    idempotency_key_fields = [
        "prompt",
        "model_id",
        "operation",
        "duration",
        "seed",
        "generate_audio",
        "educational_mode",
    ]
    side_effects = ["writes video file to output_path", "calls ModelsLab API"]
    user_visible_verification = [
        "Watch generated clip for motion coherence, audio sync, and visual quality"
    ]

    def _get_api_key(self) -> str | None:
        # Keep video generation consistent with the narration adapter: a
        # chapter run may be launched from any working directory, so load the
        # repository-scoped ignored environment file explicitly.
        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
        return os.environ.get("MODELSLAB_API_KEY")

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        model_id = inputs.get("model_id", "")
        duration = inputs.get("duration", 5)
        return estimate_modelslab_cost(model_id, duration)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        model_id = inputs.get("model_id", "")
        duration = inputs.get("duration", 5)
        return estimate_modelslab_runtime(model_id, duration)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="MODELSLAB_API_KEY not set. " + self.install_instructions,
            )

        start = time.time()
        if not inputs.get("prompt") and not inputs.get("resume_request_id"):
            return ToolResult(success=False, error="prompt or resume_request_id is required")
        operation = inputs.get("operation", "text_to_video")
        model_id = inputs.get("model_id") or DEFAULT_MODELS_BY_OPERATION.get(
            operation, "seedance-t2v"
        )
        try:
            contract = resolve_modelslab_video_contract(model_id, operation)
            url = contract.endpoint_for(operation)
        except ValueError as exc:
            return ToolResult(success=False, error=str(exc))

        profile = contract.parameter_profile
        is_h3_minimax = profile == "h3_minimax"
        is_wan22_t2v = profile == "wan22_t2v"
        is_wan22_i2v = profile == "wan22_i2v"
        is_wan22 = profile in {"wan22_t2v", "wan22_i2v"}
        educational_mode = bool(inputs.get("educational_mode", False))

        # Never accept a continuity constraint and silently drop its end frame.
        # Wan's documented contract is a single init_image. H3's public page
        # lists an image array but does not define start/end ordering; its name
        # alone is not evidence for a two-frame request contract.
        if (
            operation == "image_to_video"
            and inputs.get("end_image_url")
            and not inputs.get("resume_request_id")
            and (is_wan22_i2v or model_id == "h3-minimax-start-end-frame")
        ):
            return ToolResult(
                success=False,
                data={"production_state": "contract_blocked", "job_created": False},
                error=(
                    f"End-frame control is not verified for {model_id}; refusing "
                    "to discard end_image_url. Verify the provider's two-frame "
                    "contract before submitting a continuity-constrained shot."
                ),
            )

        payload: dict[str, Any] = {"key": api_key}

        if inputs.get("prompt"):
            payload["prompt"] = inputs["prompt"]
        if inputs.get("negative_prompt"):
            payload["negative_prompt"] = inputs["negative_prompt"]
        payload["model_id"] = model_id

        # h3-minimax models have strict param requirements per docs
        if is_wan22_t2v:
            payload["fps"] = max(16, min(25, int(inputs.get("fps", 24))))
            payload["num_frames"] = max(
                81, min(120, int(inputs.get("num_frames", 120)))
            )
            payload["portrait"] = False
            payload["output_type"] = "mp4"
        elif is_wan22_i2v:
            payload["fps"] = max(16, min(20, int(inputs.get("fps", 18))))
            payload["num_frames"] = max(
                82, min(120, int(inputs.get("num_frames", 90)))
            )
            payload["resolution"] = "480"
            payload["output_type"] = "mp4"
        elif is_h3_minimax:
            # duration: required, string, 5-15
            raw_duration = inputs.get("duration", 5)
            try:
                dur = int(raw_duration)
            except (TypeError, ValueError):
                dur = 5
            dur = max(5, min(15, dur))
            payload["duration"] = str(dur)

            # The current H3 v6 endpoint validates this as a numeric value.
            # The public model page still shows a JSON string in examples, but
            # the live API rejects "768P" with "must be a number".
            res = inputs.get("resolution", "768P")
            if res in ("768P", "768p", "768"):
                payload["resolution"] = 768
            elif res == 768:
                payload["resolution"] = 768

            # NO aspect_ratio for h3-minimax
            # H3 start/end image ordering is not defined by its public llms.txt.
        else:
            # v7 models use broader params
            if inputs.get("duration"):
                payload["duration"] = inputs["duration"]
            if inputs.get("aspect_ratio"):
                payload["aspect_ratio"] = inputs["aspect_ratio"]
            if inputs.get("resolution"):
                payload["resolution"] = inputs["resolution"]

        if contract.accepts_generate_audio:
            payload["generate_audio"] = (
                False if educational_mode else inputs.get("generate_audio", True)
            )
        if inputs.get("seed") is not None:
            payload["seed"] = inputs["seed"]

        if operation == "image_to_video":
            init_images = []
            if inputs.get("image_url"):
                init_images.append(inputs["image_url"])
            elif inputs.get("image_path"):
                init_images.append(upload_modelslab_media(inputs["image_path"], api_key))
            if inputs.get("end_image_url"):
                init_images.append(inputs["end_image_url"])
            if init_images:
                uses_base64 = any(str(image).startswith("data:") for image in init_images)
                if is_h3_minimax and uses_base64:
                    init_images = [
                        str(image).split(",", 1)[1]
                        if str(image).startswith("data:")
                        else image
                        for image in init_images
                    ]
                payload["init_image"] = init_images[0] if is_wan22_i2v else init_images
                if uses_base64:
                    payload["base64"] = True

        if operation == "reference_to_video":
            ref_image_urls = list(inputs.get("reference_image_urls") or [])
            for local_path in inputs.get("reference_image_paths") or []:
                ref_image_urls.append(upload_modelslab_media(local_path, api_key))
            if is_h3_minimax:
                if ref_image_urls:
                    uses_base64 = any(
                        str(image).startswith("data:") for image in ref_image_urls
                    )
                    if uses_base64:
                        ref_image_urls = [
                            str(image).split(",", 1)[1]
                            if str(image).startswith("data:")
                            else image
                            for image in ref_image_urls
                        ]
                    payload["init_image"] = ref_image_urls
                    if uses_base64:
                        payload["base64"] = True
                ref_video_urls = list(inputs.get("reference_video_urls") or [])
                payload["init_video"] = ref_video_urls
                ref_audio_urls = list(inputs.get("reference_audio_urls") or [])
                payload["init_audio"] = ref_audio_urls
            elif ref_image_urls:
                payload["reference_image_urls"] = ref_image_urls

        if operation == "video_to_video":
            init_videos = []
            if inputs.get("video_url"):
                init_videos.append(inputs["video_url"])
            elif inputs.get("video_path"):
                init_videos.append(inputs["video_path"])
            if init_videos:
                payload["init_video"] = init_videos

        if operation == "lip_sync":
            if inputs.get("video_url"):
                payload["init_video"] = inputs["video_url"]
            elif inputs.get("video_path"):
                payload["init_video"] = inputs["video_path"]
            if inputs.get("audio_url"):
                payload["init_audio"] = inputs["audio_url"]
            elif inputs.get("audio_path"):
                payload["init_audio"] = inputs["audio_path"]

        output_path = Path(inputs.get("output_path", "modelslab_output.mp4")).resolve()
        job_path = Path(inputs.get("job_state_path") or _job_state_path(output_path)).resolve()
        poll_endpoint = str(inputs.get("poll_endpoint") or contract.poll_endpoint)
        fingerprint = _request_fingerprint(model_id, operation, payload)
        existing = _read_job_state(job_path)
        request_id = str(inputs.get("resume_request_id") or "")
        resumed = bool(request_id)
        if not request_id and existing and existing.get("status") in _RECOVERABLE_JOB_STATES:
            if existing.get("request_fingerprint") != fingerprint:
                return ToolResult(
                    success=False,
                    data={"recoverable": True, "job_state_path": str(job_path),
                          "request_id": existing.get("request_id")},
                    error="A recoverable ModelsLab job exists for different content; reconcile or archive it before submitting paid work.",
                )
            request_id = str(existing.get("request_id") or "")
            poll_endpoint = str(existing.get("poll_endpoint") or poll_endpoint)
            resumed = bool(request_id)

        try:
            if not request_id:
                submit_resp = submit_modelslab(url, api_key, payload, timeout=30)
                request_id = str(submit_resp.get("id") or submit_resp.get("request_id") or "")
                if not request_id:
                    return ToolResult(
                        success=False,
                        error=f"ModelsLab did not return a request ID: {submit_resp}",
                    )
                _write_job_state(job_path, {
                    "version": "1.0", "provider": "modelslab", "status": "submitted",
                    "request_id": request_id, "request_fingerprint": fingerprint,
                    "poll_endpoint": poll_endpoint, "model_id": model_id,
                    "operation": operation, "output_path": str(output_path),
                    "estimated_runtime_seconds": self.estimate_runtime(inputs),
                    "submitted_at_unix": time.time(),
                })
            if inputs.get("submit_only"):
                return ToolResult(
                    success=True,
                    data={
                        "provider": "modelslab",
                        "model": model_id,
                        "operation": operation,
                        "status": "processing",
                        "request_id": str(request_id),
                        "poll_endpoint": poll_endpoint,
                        "provider_contract": contract.name,
                        "audio_policy": "silent" if educational_mode else "provider_default",
                        "output_path": str(inputs.get("output_path", "modelslab_output.mp4")),
                        "job_state_path": str(job_path),
                        "resumed": resumed,
                    },
                    cost_usd=0.0 if resumed else self.estimate_cost(inputs),
                    duration_seconds=round(time.time() - start, 2),
                    model=model_id,
                )
            state = _read_job_state(job_path) or {}
            _write_job_state(job_path, {**state, "status": "processing", "last_poll_at_unix": time.time()})
            result = poll_modelslab(request_id, api_key, endpoint=poll_endpoint)
            download_modelslab_output(result, output_path)
            if educational_mode:
                _strip_audio_track(output_path)
            state = _read_job_state(job_path) or {}
            _write_job_state(job_path, {**state, "status": "success",
                                       "completed_at_unix": time.time(),
                                       "output_path": str(output_path)})
        except TimeoutError as exc:
            state = _read_job_state(job_path) or {}
            _write_job_state(job_path, {**state, "status": "timed_out",
                                       "last_error": str(exc)[:500]})
            return ToolResult(success=False, data={"recoverable": True,
                "request_id": request_id, "poll_endpoint": poll_endpoint,
                "job_state_path": str(job_path), "output_path": str(output_path)},
                error=f"ModelsLab job timed out but remains resumable: {exc}",
                cost_usd=0.0 if resumed else self.estimate_cost(inputs), model=model_id)
        except Exception as e:
            if request_id:
                state = _read_job_state(job_path) or {}
                terminal = "generation failed:" in str(e).casefold()
                _write_job_state(job_path, {**state,
                    "status": "terminal_failed" if terminal else "poll_error",
                    "last_error": str(e)[:500]})
            return ToolResult(
                success=False,
                data={"recoverable": bool(request_id) and not terminal,
                      "request_id": request_id, "poll_endpoint": poll_endpoint,
                      "job_state_path": str(job_path), "output_path": str(output_path)},
                error=f"ModelsLab video generation failed: {e}",
                cost_usd=0.0 if resumed else self.estimate_cost(inputs), model=model_id,
            )

        from tools.video._shared import probe_output

        probed = probe_output(output_path)
        return ToolResult(
            success=True,
            data={
                "provider": "modelslab",
                "model": model_id,
                "operation": operation,
                "provider_contract": contract.name,
                "educational_mode": educational_mode,
                "audio_policy": "silent" if educational_mode else "provider_default",
                "prompt": inputs.get("prompt", ""),
                "aspect_ratio": inputs.get("aspect_ratio") if not (is_h3_minimax or is_wan22) else None,
                "resolution": inputs.get("resolution"),
                "generate_audio": (
                    False
                    if educational_mode
                    else inputs.get("generate_audio")
                    if contract.accepts_generate_audio
                    else None
                ),
                "seed": inputs.get("seed"),
                "output": str(output_path),
                "output_path": str(output_path),
                "request_id": request_id,
                "job_state_path": str(job_path),
                "resumed": resumed,
                "format": "mp4",
                **probed,
            },
            artifacts=[str(output_path)],
            cost_usd=0.0 if resumed else self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=model_id,
        )
