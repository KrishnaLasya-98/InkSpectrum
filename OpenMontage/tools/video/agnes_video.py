"""Agnes Video V2.0 and 2.5 generation through the Agnes API Hub.

The adapter keeps Agnes behind OpenMontage's normal ``video_generation``
capability, so ``video_selector`` discovers it automatically. Modern 2.5
supports text, first-frame, keyframe, and multi-reference generation.
"""
from __future__ import annotations

import base64
import mimetypes
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


class AgnesVideo(BaseTool):
    name = "agnes_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "agnes"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:AGNES_API_KEY"]
    install_instructions = (
        "Set AGNES_API_KEY (or AGNES_API_TOKEN / APIHUB_AGNES_API_KEY). "
        "Create a key through https://agnes-ai.com"
    )
    agent_skills: list[str] = []

    capabilities = ["text_to_video", "image_to_video", "reference_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_to_video": True,
        "keyframes": True,
        "multiple_reference_images": True,
        "reference_image": True,
        "reference_video": True,
        "reference_audio": True,
        "aspect_ratio": True,
        "seed": True,
        "character_consistency": True,
    }
    best_for = [
        "budget-conscious 720p video prototypes",
        "first/last-frame animation",
        "reference-conditioned character and style continuity",
        "provider comparison against ModelsLab before full production",
    ]
    not_good_for = [
        "offline generation",
        "production use before an Agnes smoke test establishes current quota and output quality",
    ]
    fallback_tools = ["modelslab_video", "seedance_video", "kling_video"]
    quality_score = 0.90

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "negative_prompt": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video", "reference_to_video"],
                "default": "text_to_video",
            },
            "model_id": {
                "type": "string",
                "enum": ["agnes-video-v2.0", "agnes-video-2.5-flash", "agnes-video-2.5"],
                "default": "agnes-video-2.5-flash",
            },
            "duration": {
                "type": "string",
                "enum": [str(value) for value in range(4, 13)],
                "default": "5",
            },
            "resolution": {
                "type": "string",
                "enum": ["720P", "1080P", "1K", "2K"],
                "default": "720P",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"],
                "default": "16:9",
            },
            "seed": {"type": "integer"},
            "image_url": {"type": "string"},
            "image_path": {"type": "string"},
            "end_image_url": {"type": "string"},
            "end_image_path": {"type": "string"},
            "reference_image_urls": {"type": "array", "items": {"type": "string"}},
            "reference_video_urls": {"type": "array", "items": {"type": "string"}},
            "reference_audio_urls": {"type": "array", "items": {"type": "string"}},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2, retryable_errors=["rate_limit", "timeout"]
    )
    idempotency_key_fields = ["prompt", "model_id", "operation", "duration", "seed"]
    side_effects = ["writes video file to output_path", "calls Agnes API"]
    user_visible_verification = [
        "Review identity, anatomy, motion continuity, embedded text, and output duration"
    ]

    @staticmethod
    def _api_key() -> str | None:
        return (
            os.environ.get("AGNES_API_KEY")
            or os.environ.get("AGNES_API_TOKEN")
            or os.environ.get("APIHUB_AGNES_API_KEY")
        )

    @staticmethod
    def _base_url() -> str:
        return os.environ.get("AGNES_API_BASE", "https://apihub.agnes-ai.com").rstrip("/")

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._api_key() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        """Use an override because Agnes quota/pricing can change independently."""
        try:
            per_second = float(os.environ.get("AGNES_VIDEO_COST_PER_SECOND", "0"))
            seconds = int(inputs.get("duration", "5"))
        except (TypeError, ValueError):
            return 0.0
        return round(per_second * seconds, 2)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        try:
            return 90.0 + int(inputs.get("duration", "5")) * 3.0
        except (TypeError, ValueError):
            return 105.0

    @staticmethod
    def _local_image_data(path_value: str) -> str:
        path = Path(path_value)
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._api_key()
        if not api_key:
            return ToolResult(success=False, error=self.install_instructions)

        import requests

        start = time.time()
        model_id = inputs.get("model_id", "agnes-video-2.5-flash")
        operation = inputs.get("operation", "text_to_video")
        resolution = inputs.get("resolution", "720P")

        prompt = str(inputs["prompt"])
        if inputs.get("negative_prompt"):
            prompt = f"{prompt}\nAvoid: {inputs['negative_prompt']}"

        is_v25 = model_id in {"agnes-video-2.5-flash", "agnes-video-2.5"}
        if model_id == "agnes-video-2.5-flash" and resolution != "720P":
            return ToolResult(success=False, error="agnes-video-2.5-flash supports 720P only")

        dimensions = {
            "720P": (1280, 720),
            "1080P": (1920, 1080),
            "1K": (1920, 1080),
            "2K": (2560, 1440),
        }
        width, height = dimensions.get(resolution, dimensions["720P"])
        seconds = max(4, min(12, int(inputs.get("duration", "5"))))
        if is_v25:
            payload: dict[str, Any] = {
                "model": model_id,
                "prompt": prompt,
                "seconds": str(seconds),
                "size": resolution,
                "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
                "n": 1,
            }
        else:
            payload = {
                "model": model_id,
                "prompt": prompt,
                "width": width,
                "height": height,
                "num_frames": min(441, seconds * 24 + 1),
                "frame_rate": 24,
            }
        if inputs.get("seed") is not None:
            payload["seed"] = inputs["seed"]

        if operation == "text_to_video":
            payload["mode"] = "text" if is_v25 else "ti2vid"
        elif operation == "image_to_video":
            first_frame = inputs.get("image_url")
            if not first_frame and inputs.get("image_path"):
                first_frame = self._local_image_data(inputs["image_path"])
            if not first_frame:
                return ToolResult(success=False, error="image_to_video requires image_url or image_path")
            last_frame = inputs.get("end_image_url")
            if not last_frame and inputs.get("end_image_path"):
                last_frame = self._local_image_data(inputs["end_image_path"])
            if is_v25:
                payload["mode"] = "keyframe"
                payload["first_frame"] = first_frame
                if last_frame:
                    payload["last_frame"] = last_frame
            else:
                payload["mode"] = "keyframes" if last_frame else "img2video"
                payload["image"] = first_frame
            if last_frame and not is_v25:
                payload["extra_body"] = {
                    "image": [first_frame, last_frame],
                    "mode": "keyframes",
                }
        elif operation == "reference_to_video":
            if not is_v25:
                return ToolResult(success=False, error="reference_to_video requires an Agnes 2.5 model")
            images = list(inputs.get("reference_image_urls") or [])
            audios = list(inputs.get("reference_audio_urls") or [])
            videos = list(inputs.get("reference_video_urls") or [])
            if not (images or audios or videos):
                return ToolResult(success=False, error="reference_to_video requires reference media")
            if len(images) > 5 or len(audios) > 3:
                return ToolResult(success=False, error="Agnes reference limits are 5 images and 3 audio clips")
            if model_id.endswith("flash") and videos:
                return ToolResult(
                    success=False,
                    error="Agnes 2.5 Flash does not support reference videos; use the non-Flash model",
                )
            payload.update({"mode": "reference", "images": images, "audios": audios})
            if videos:
                payload["videos"] = videos
        else:
            return ToolResult(success=False, error=f"Unsupported Agnes operation: {operation}")

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        def request_with_backoff(method: str, url: str, **kwargs: Any):
            """Retry Agnes throttling without abandoning an accepted generation job."""
            response = None
            retryable_statuses = {429, 502, 503, 504}
            for attempt in range(8):
                response = requests.request(method, url, **kwargs)
                if response.status_code not in retryable_statuses:
                    return response
                retry_after = response.headers.get("Retry-After")
                try:
                    delay = max(5.0, float(retry_after)) if retry_after else min(60.0, 5.0 * (2**attempt))
                except ValueError:
                    delay = min(60.0, 5.0 * (2**attempt))
                time.sleep(delay)
            return response

        try:
            submit = request_with_backoff(
                "POST",
                f"{self._base_url()}/v1/videos",
                headers=headers,
                json=payload,
                timeout=30,
            )
            submit.raise_for_status()
            submitted = submit.json()
            video_id = submitted.get("video_id") or submitted.get("id") or submitted.get("task_id")
            if not video_id:
                raise RuntimeError(f"Agnes returned no video id: {submitted}")

            deadline = time.time() + 900
            result: dict[str, Any] = {}
            while time.time() < deadline:
                response = request_with_backoff(
                    "GET",
                    f"{self._base_url()}/agnesapi",
                    headers=headers,
                    params={"video_id": video_id, "model_name": model_id},
                    timeout=30,
                )
                response.raise_for_status()
                result = response.json()
                status = str(result.get("status", "")).lower()
                if status in {"completed", "success"}:
                    break
                if status in {"failed", "error", "cancelled"}:
                    raise RuntimeError(result.get("error") or result.get("message") or status)
                time.sleep(5)
            else:
                raise TimeoutError(f"Agnes video {video_id} timed out after 900 seconds")

            video_url = (
                (result.get("metadata") or {}).get("url")
                or result.get("url")
                or (result.get("output") or [None])[0]
            )
            if not video_url:
                raise RuntimeError(f"Agnes completed without an output URL: {result}")
            download = request_with_backoff("GET", video_url, timeout=120)
            download.raise_for_status()
            output_path = Path(inputs.get("output_path", "agnes_output.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(download.content)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(success=False, error=f"Agnes video generation failed: {exc}")

        from tools.video._shared import probe_output

        probed = probe_output(output_path)
        return ToolResult(
            success=True,
            data={
                "provider": "agnes",
                "model": model_id,
                "operation": operation,
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
