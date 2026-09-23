"""Shared helpers for ModelsLab provider tools.

Centralizes polling, upload, and cost utilities so each ModelsLab tool
file stays thin and consistent.
"""

from __future__ import annotations

import base64
import os
import mimetypes
import time
from pathlib import Path
from typing import Any

from tools.base_tool import ToolResult


def upload_modelslab_media(
    media_path: str | Path,
    api_key: str,
    *,
    timeout: int = 120,
) -> str:
    """Upload a local reference asset to ModelsLab and return its public URL."""
    path = Path(media_path).resolve()
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(f"ModelsLab upload source is missing or empty: {path}")

    import requests  # noqa: PLC0415

    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    with path.open("rb") as handle:
        response = requests.post(
            "https://modelslab.com/api/v6/realtime/upload",
            data={"key": api_key},
            files={"file": (path.name, handle, mime_type)},
            timeout=timeout,
        )
    response.raise_for_status()
    data = response.json()
    url = data.get("url") or data.get("output")
    if isinstance(url, list):
        url = url[0] if url else None
    if isinstance(url, str) and url:
        return url

    # ModelsLab's current SDK contract accepts base64 file inputs, while the
    # legacy realtime upload route may be disabled for non-enterprise keys.
    # Returning a data URI keeps local image-to-video generation self-contained.
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def poll_modelslab(
    request_id: str,
    api_key: str,
    *,
    endpoint: str = "video-fusion",
    timeout: int = 900,
    interval: float = 5.0,
) -> dict[str, Any]:
    """Poll a ModelsLab async request until completion or failure.

    Args:
        request_id: The request ID returned from the initial submission.
        api_key: ModelsLab API key.
        endpoint: API endpoint family ("video-fusion", "images", "voice", "video").
                   Use "video" for h3-minimax v6 endpoints.
        timeout: Maximum seconds to wait.
        interval: Initial poll interval in seconds; backs off up to 30s.

    Returns:
        The final result payload dict.

    Raises:
        RuntimeError: If the request fails or times out.
    """
    # h3-minimax models use /api/v6/video/fetch/{id}
    # v7 models use /api/v7/{endpoint}/fetch/{id}
    if endpoint == "video":
        base_url = f"https://modelslab.com/api/v6/video/fetch/{request_id}"
    else:
        base_url = f"https://modelslab.com/api/v7/{endpoint}/fetch/{request_id}"
    payload = {"key": api_key}
    deadline = time.time() + timeout
    current_interval = interval

    import requests  # noqa: PLC0415

    while time.time() < deadline:
        poll_err: Exception | None = None
        for _poll_retry in range(5):
            try:
                response = requests.post(base_url, json=payload, timeout=30)
                response.raise_for_status()
                data = response.json()
                poll_err = None
                break
            except Exception as exc:
                poll_err = exc
                remaining = max(0.0, deadline - time.time())
                if remaining <= 0:
                    break
                time.sleep(min(10.0, remaining))
        else:
            # All poll retries exhausted
            if poll_err is not None:
                raise RuntimeError(
                    f"ModelsLab poll failed after 5 consecutive errors: {poll_err}"
                ) from poll_err

        status = data.get("status", "")
        if status == "success":
            return data
        if status in ("failed", "error", "cancelled"):
            raise RuntimeError(
                f"ModelsLab generation failed: {data.get('message', status)}"
            )

        remaining = max(0.0, deadline - time.time())
        time.sleep(min(current_interval, remaining))
        current_interval = min(current_interval * 1.2, 30.0)

    raise TimeoutError(
        f"ModelsLab request {request_id} timed out after {timeout}s"
    )


def submit_modelslab(
    url: str,
    api_key: str,
    payload: dict[str, Any],
    *,
    timeout: int = 30,
) -> dict[str, Any]:
    """Submit a request to a ModelsLab endpoint and return the JSON response.

    Args:
        url: Full ModelsLab endpoint URL.
        api_key: ModelsLab API key.
        payload: Request body dict.
        timeout: HTTP timeout in seconds.

    Returns:
        Parsed JSON response.

    Raises:
        RuntimeError: If the HTTP request fails.
    """
    import requests  # noqa: PLC0415

    body = {"key": api_key, **payload}
    response = requests.post(url, json=body, timeout=timeout)
    response.raise_for_status()
    return response.json()


def download_modelslab_output(
    result: dict[str, Any],
    output_path: Path,
    *,
    timeout: int = 120,
) -> Path:
    """Download the primary output file from a ModelsLab result payload.

    Args:
        result: Parsed JSON response from a successful ModelsLab fetch.
        output_path: Destination path on disk.
        timeout: Download timeout in seconds.

    Returns:
        The resolved output_path.

    Raises:
        RuntimeError: If the result has no downloadable output.
    """
    output_url = (result.get("output") or [None])[0] or result.get("url")
    if not output_url:
        raise RuntimeError(f"No output URL in ModelsLab result: {result}")

    import requests  # noqa: PLC0415

    response = requests.get(output_url, timeout=timeout)
    response.raise_for_status()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(response.content)
    return output_path


def estimate_modelslab_cost(
    model_id: str,
    duration: int | str = 5,
) -> float:
    """Estimate cost in USD for a ModelsLab video generation call.

    Uses rough per-second rates by model family. Override with provider
    pricing pages when exact rates are known.

    Args:
        model_id: ModelsLab model identifier.
        duration: Duration in seconds, or "auto".

    Returns:
        Estimated cost in USD.
    """
    try:
        seconds = 5 if duration == "auto" else int(duration)
    except (TypeError, ValueError):
        seconds = 5

    model_lower = model_id.lower()
    if "seedance" in model_lower:
        rate = 0.30
    elif "wan" in model_lower:
        rate = 0.18
    elif "veo" in model_lower:
        rate = 0.25
    elif "sora" in model_lower:
        rate = 0.20
    elif "kling" in model_lower:
        rate = 0.15
    elif "hailuo" in model_lower or "minimax" in model_lower:
        rate = 0.19
    else:
        rate = 0.20

    return round(rate * seconds, 2)


def estimate_modelslab_runtime(
    model_id: str,
    duration: int | str = 5,
) -> float:
    """Estimate runtime in seconds for a ModelsLab generation call."""
    model_lower = model_id.lower()
    if "seedance" in model_lower:
        base = 150.0
    elif "wan" in model_lower:
        base = 120.0
    elif "veo" in model_lower:
        base = 180.0
    elif "sora" in model_lower:
        base = 160.0
    elif "kling" in model_lower:
        base = 100.0
    elif "hailuo" in model_lower or "minimax" in model_lower:
        base = 120.0
    else:
        base = 120.0

    try:
        seconds = 5 if duration == "auto" else int(duration)
    except (TypeError, ValueError):
        seconds = 5
    return base + seconds * 3.0
