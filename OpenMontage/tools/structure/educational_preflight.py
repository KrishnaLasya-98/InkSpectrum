"""Fail-fast environment and provider validation for educational production."""
from __future__ import annotations

import os
import importlib.util
import shutil
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]


def run_educational_preflight(
    config: dict[str, Any],
    *,
    workspace: str | Path,
    dry_run: bool,
) -> dict[str, Any]:
    # Match the ModelsLab audio/video adapters: production can be launched from
    # any working directory while the ignored repository .env remains the
    # single local credential source.
    load_dotenv(ROOT / ".env", override=False)
    checks: list[dict[str, Any]] = []

    def record(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    providers = config.get("providers") or {}
    audio = providers.get("audio") or {}
    video = providers.get("video") or {}
    if isinstance(audio, str):
        audio = {"provider": audio}
    if isinstance(video, str):
        video = {"provider": video}

    audio_provider = str(audio.get("provider", "modelslab"))
    supported_audio = {
        "modelslab", "kokoro", "huggingface-kokoro", "hyperframes-kokoro",
    }
    record("audio_provider", audio_provider in supported_audio, audio_provider)
    record(
        "video_provider",
        video.get("provider", "modelslab") == "modelslab",
        str(video.get("provider", "modelslab")),
    )
    audio_model = str(audio.get("model_id", "text-to-speech")).strip()
    voice_id = str(audio.get("voice_id", "nova")).strip()
    try:
        audio_speed = float(audio.get("speed", 0.82))
    except (TypeError, ValueError):
        audio_speed = -1.0
    record(
        "audio_contract",
        bool(audio_model and voice_id and 0.5 <= audio_speed <= 1.5),
        (
            f"model={audio_model or 'missing'}, voice={voice_id or 'missing'}, "
            f"speed={audio_speed}"
        ),
    )
    render_policy = config.get("render_policy") or {}
    workers = int(render_policy.get("workers", 1))
    low_memory = bool(render_policy.get("low_memory_mode", True))
    record(
        "safe_hyperframes_render",
        workers == 1 and low_memory,
        f"workers={workers}, low_memory_mode={low_memory}",
    )
    key_present = bool(os.environ.get("MODELSLAB_API_KEY"))
    record(
        "modelslab_credentials",
        dry_run or key_present,
        "not required for dry-run" if dry_run else "configured" if key_present else "missing",
    )
    if audio_provider != "modelslab":
        kokoro_available = (
            importlib.util.find_spec("kokoro_onnx") is not None
            and importlib.util.find_spec("soundfile") is not None
        )
        record(
            "kokoro_runtime",
            dry_run or kokoro_available,
            "not required for dry-run" if dry_run else "available" if kokoro_available else "missing",
        )

    from tools.video.modelslab_capabilities import resolve_modelslab_video_contract

    model_contracts = (
        (str(video.get("model_id", "wan2.2")), "text_to_video"),
        (str(video.get("image_model_id", "wan-2.2-i2v")), "image_to_video"),
        (str(video.get("reference_model_id", "h3-minimax-r2v")), "reference_to_video"),
        (str(video.get("fallback_model_id", "h3-minimax-t2v")), "text_to_video"),
    )
    for model_id, operation in model_contracts:
        try:
            contract = resolve_modelslab_video_contract(model_id, operation)
            record(
                f"model_contract:{operation}", True,
                f"{model_id} -> {contract.name}",
            )
        except Exception as exc:
            record(f"model_contract:{operation}", False, str(exc))

    if not dry_run:
        for command in ("ffmpeg", "ffprobe", "npx"):
            record(
                f"command:{command}",
                shutil.which(command) is not None,
                "available" if shutil.which(command) else "missing",
            )
        if str(config.get("subject_type") or "") == "mathematics":
            configured_manim_python = os.environ.get("OPENMONTAGE_MANIM_PYTHON")
            manim_available = importlib.util.find_spec("manim") is not None or bool(
                configured_manim_python and Path(configured_manim_python).is_file()
            )
            record(
                "precision_renderer:manim",
                manim_available,
                "available" if manim_available else "missing Python package 'manim' or OPENMONTAGE_MANIM_PYTHON",
            )

        semantic_required = bool(
            (video.get("semantic_qa") or {}).get("required")
            or (config.get("qa_policy") or {}).get("require_semantic_av_match")
        )
        if semantic_required:
            from tools.analysis.video_understand import VideoUnderstand
            from tools.base_tool import ToolStatus

            status = VideoUnderstand().get_status()
            record(
                "semantic_visual_qa",
                status == ToolStatus.AVAILABLE,
                status.value,
            )

        free_gb = shutil.disk_usage(Path(workspace).resolve().anchor).free / (1024 ** 3)
        minimum_gb = float(
            (config.get("render_policy") or {}).get("minimum_free_disk_gb", 8.0)
        )
        record(
            "render_disk_space",
            free_gb >= minimum_gb,
            f"{free_gb:.1f} GiB free; {minimum_gb:.1f} GiB required",
        )

    failures = [check for check in checks if not check["passed"]]
    return {
        "status": "pass" if not failures else "fail",
        "dry_run": dry_run,
        "checks": checks,
        "failure_count": len(failures),
        "failures": failures,
    }
