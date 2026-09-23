"""ModelsLab video generation via v7 Video Fusion API.

Best for alternative cloud video generation with 40+ models including
Seedance, Wan, Veo, Sora, Kling, and Hailuo via a single API key.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

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


class ModelsLabVideo(BaseTool):
    name = "modelslab_video"
    version = "0.1.0"
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
        "required": ["prompt"],
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
    ]
    side_effects = ["writes video file to output_path", "calls ModelsLab API"]
    user_visible_verification = [
        "Watch generated clip for motion coherence, audio sync, and visual quality"
    ]

    def _get_api_key(self) -> str | None:
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
        operation = inputs.get("operation", "text_to_video")
        model_id = inputs.get("model_id") or {
            "image_to_video": "seedance-i2v",
            "video_to_video": "wan2.1",
            "lip_sync": "lipsync-2",
        }.get(operation, "seedance-t2v")

        # h3-minimax models require v6 endpoint and strict params
        is_h3_minimax = model_id in (
            "h3-minimax-t2v",
            "h3-minimax-start-end-frame",
            "h3-minimax-r2v",
        )
        is_wan22_t2v = model_id in {"wan2.2", "wan-2.2-t2v"}
        is_wan22_i2v = model_id == "wan-2.2-i2v"
        is_wan22 = is_wan22_t2v or is_wan22_i2v
        if is_wan22_t2v:
            if operation != "text_to_video":
                return ToolResult(
                    success=False,
                    error=(
                        f"ModelsLab {model_id} supports text_to_video through "
                        "the verified v6 adapter route"
                    ),
                )
            url = "https://modelslab.com/api/v6/video/text2video_ultra"
        elif is_wan22_i2v:
            if operation != "image_to_video":
                return ToolResult(
                    success=False,
                    error=(
                        "ModelsLab wan-2.2-i2v requires operation=image_to_video"
                    ),
                )
            url = "https://modelslab.com/api/v6/video/img2video_ultra"
        elif is_h3_minimax:
            if operation == "text_to_video":
                url = "https://modelslab.com/api/v6/video/text2video"
            elif operation == "image_to_video":
                url = "https://modelslab.com/api/v6/video/img2video"
            elif operation == "reference_to_video":
                url = "https://modelslab.com/api/v6/video/img2video"
            elif operation == "video_to_video":
                url = "https://modelslab.com/api/v6/video/img2video"
            elif operation == "lip_sync":
                url = "https://modelslab.com/api/v6/video/img2video"
            else:
                return ToolResult(success=False, error=f"Unsupported operation for {model_id}: {operation}")
        else:
            if operation == "text_to_video":
                url = "https://modelslab.com/api/v7/video-fusion/text-to-video"
            elif operation == "image_to_video":
                url = "https://modelslab.com/api/v7/video-fusion/image-to-video"
            elif operation == "reference_to_video":
                url = "https://modelslab.com/api/v7/video-fusion/text-to-video"
            elif operation == "video_to_video":
                url = "https://modelslab.com/api/v7/video-fusion/video-to-video"
            elif operation == "lip_sync":
                url = "https://modelslab.com/api/v7/video-fusion/lip-sync"
            else:
                return ToolResult(
                    success=False,
                    error=f"Unsupported operation: {operation}",
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
                82, min(122, int(inputs.get("num_frames", 90)))
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
            # NO end_image for h3-minimax-start-end-frame
        else:
            # v7 models use broader params
            if inputs.get("duration"):
                payload["duration"] = inputs["duration"]
            if inputs.get("aspect_ratio"):
                payload["aspect_ratio"] = inputs["aspect_ratio"]
            if inputs.get("resolution"):
                payload["resolution"] = inputs["resolution"]

        if "generate_audio" in inputs and not is_h3_minimax and not is_wan22:
            payload["generate_audio"] = inputs["generate_audio"]
        if inputs.get("seed") is not None:
            payload["seed"] = inputs["seed"]

        if operation == "image_to_video":
            init_images = []
            if inputs.get("image_url"):
                init_images.append(inputs["image_url"])
            elif inputs.get("image_path"):
                init_images.append(upload_modelslab_media(inputs["image_path"], api_key))
            # h3-minimax-start-end-frame does NOT support end_image
            if inputs.get("end_image_url") and model_id != "h3-minimax-start-end-frame":
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

        try:
            submit_resp = submit_modelslab(url, api_key, payload, timeout=30)
            request_id = submit_resp.get("id") or submit_resp.get("request_id")
            if not request_id:
                return ToolResult(
                    success=False,
                    error=f"ModelsLab did not return a request ID: {submit_resp}",
                )

            # Use correct poll endpoint based on model family
            poll_endpoint = "video" if (is_h3_minimax or is_wan22) else "video-fusion"
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
                        "output_path": str(inputs.get("output_path", "modelslab_output.mp4")),
                    },
                    cost_usd=self.estimate_cost(inputs),
                    duration_seconds=round(time.time() - start, 2),
                    model=model_id,
                )
            result = poll_modelslab(request_id, api_key, endpoint=poll_endpoint)

            output_path = Path(inputs.get("output_path", "modelslab_output.mp4"))
            download_modelslab_output(result, output_path)

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"ModelsLab video generation failed: {e}",
            )

        from tools.video._shared import probe_output

        probed = probe_output(output_path)
        return ToolResult(
            success=True,
            data={
                "provider": "modelslab",
                "model": model_id,
                "operation": operation,
                "prompt": inputs.get("prompt", ""),
                "aspect_ratio": inputs.get("aspect_ratio") if not (is_h3_minimax or is_wan22) else None,
                "resolution": inputs.get("resolution"),
                "generate_audio": inputs.get("generate_audio") if not is_h3_minimax else None,
                "seed": inputs.get("seed"),
                "output": str(output_path),
                "output_path": str(output_path),
                "format": "mp4",
                **probed,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=model_id,
        )
