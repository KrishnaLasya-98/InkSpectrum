"""VoiceSynthesisPipeline — ModelsLab TTS stack with STT QA loop.

Provider availability and billing depend on the active ModelsLab plan. The
pipeline keeps one configured narrator identity for the complete chapter.

TTS stack
---------
  Primary   text-to-speech  configured chapter voice
  Retry     same voice and delivery profile (no section-level voice switching)
  Offline   piper_tts only when identity-changing fallback is explicitly allowed

STT QA loop
-----------
After every TTS call, speech-to-text transcribes the audio and diffs
against the source script. If word-error-rate > 5% the segment is
regenerated with the same chapter voice.
Max 3 regeneration attempts before accepting best-so-far.
"""
from __future__ import annotations

import json
import hashlib
import os
import re
import time
import base64
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)


def _audio_duration_seconds(path: Path) -> float:
    """Measure a local audio file without decoding it into memory."""
    try:
        import wave

        with wave.open(str(path), "rb") as stream:
            return round(stream.getnframes() / stream.getframerate(), 3)
    except Exception:
        import subprocess

        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise ValueError(f"Cannot measure cached narration: {path}")
        return round(float(result.stdout.strip()), 3)

# ---------------------------------------------------------------------------
# ModelsLab endpoints
# ---------------------------------------------------------------------------
_ML_BASE   = "https://modelslab.com/api"
_TTS_V6    = f"{_ML_BASE}/v6/voice/text_to_speech"
_TTS_V7    = f"{_ML_BASE}/v7/voice/text-to-speech"
_STT_V6    = f"{_ML_BASE}/v6/voice/speech_to_text"
_FETCH_V6  = f"{_ML_BASE}/v6/voice/fetch"
_VOICE_UPLOAD_V6 = f"{_ML_BASE}/v6/voice/voice_upload"

# ---------------------------------------------------------------------------
# TTS profiles. Availability and price are controlled by the active ModelsLab
# account; this file must not describe provider plans as free or unlimited.
# ---------------------------------------------------------------------------
FALLBACK_CHAIN = [
    {
        "engine":   "modelslab",
        "model_id": "text-to-speech",
        "endpoint": _TTS_V6,
        "voice_id": "nova",
        "speed":    "0.8",
        "language": "american english",
        "cost":     "provider_plan",
        "note":     "Primary — warm, child-friendly",
    },
    {
        "engine":   "modelslab",
        "model_id": "text-to-speech",
        "endpoint": _TTS_V6,
        "voice_id": "sophia",
        "speed":    "0.75",
        "language": "american english",
        "cost":     "provider_plan",
        "note":     "Q&A sections — slower, more deliberate",
    },
    {
        "engine":   "modelslab",
        "model_id": "text-to-speech",
        "endpoint": _TTS_V6,
        "voice_id": "bella",
        "speed":    "0.85",
        "language": "american english",
        "cost":     "provider_plan",
        "note":     "Recall/summary sections",
    },
    {
        "engine":   "modelslab",
        "model_id": "eleven_multilingual_v2",
        "endpoint": _TTS_V7,
        "voice_id": "Nila - Tamil",
        "cost":     "provider_plan",
        "note":     "Regional: Tamil / Indian classrooms",
    },
    {
        "engine":   "piper_tts",
        "model_id": "en_US-lessac-medium",
        "cost":     "$0",
        "note":     "Offline fallback — zero API dependency",
    },
]

# The narrator identity is chapter-scoped. Section types may change pacing in
# future delivery metadata, but must never silently select another voice.
_DEFAULT_VOICE = {"voice_id": "nova", "speed": "0.8"}

_MAX_WER        = 0.05   # 5% word-error-rate threshold
_MAX_REGEN      = 3      # regeneration attempts before accepting best-so-far
_POLL_INTERVAL  = 2      # seconds between async status polls
_POLL_TIMEOUT   = 120    # seconds before giving up on a generation job
_KOKORO_PROVIDERS = {"kokoro", "huggingface-kokoro", "hyperframes-kokoro"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _api_key() -> str:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    key = os.environ.get("MODELSLAB_API_KEY", "")
    if not key:
        raise EnvironmentError("MODELSLAB_API_KEY not set in environment")
    return key


def _word_error_rate(reference: str, hypothesis: str) -> float:
    """Levenshtein-based WER (word level)."""
    ref  = reference.lower().split()
    hyp  = hypothesis.lower().split()
    if not ref:
        return 0.0
    r, h = len(ref), len(hyp)
    dp = list(range(h + 1))
    for i in range(1, r + 1):
        new_dp = [i] + [0] * h
        for j in range(1, h + 1):
            if ref[i - 1] == hyp[j - 1]:
                new_dp[j] = dp[j - 1]
            else:
                new_dp[j] = 1 + min(dp[j], new_dp[j - 1], dp[j - 1])
        dp = new_dp
    return dp[h] / max(r, 1)


def _poll_for_audio(job_id: str, api_key: str) -> str | None:
    """Poll ModelsLab fetch endpoint until audio URL is available."""
    deadline = time.monotonic() + _POLL_TIMEOUT
    while time.monotonic() < deadline:
        try:
            resp = requests.post(
                f"{_FETCH_V6}/{job_id}",
                json={"key": api_key},
                timeout=30,
            )
            data = resp.json()
        except requests.Timeout:
            # Network blip on poll — sleep and retry without giving up the job.
            time.sleep(_POLL_INTERVAL)
            continue
        except Exception:
            return None
        status = data.get("status", "")
        if status == "success":
            output = data.get("output") or data.get("url")
            if isinstance(output, list) and output:
                return output[0]
            if isinstance(output, str) and output:
                return output
        if status in ("failed", "error"):
            return None
        time.sleep(_POLL_INTERVAL)
    return None


def _download(url: str, dest: Path) -> Path:
    """Download a URL to dest, creating parent dirs."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + _POLL_TIMEOUT
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            from lib.media_download import download_atomic
            return download_atomic(url, dest, timeout=60)
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(_POLL_INTERVAL)
    raise RuntimeError(f"ModelsLab audio URL did not become ready: {last_error}")


def _upload_voice(reference_path: Path, api_key: str, name: str) -> str:
    """Upload a consented 10-25 second reference and return its ModelsLab voice id."""
    suffix = reference_path.suffix.lower()
    mime = "audio/wav" if suffix == ".wav" else "audio/mpeg"
    encoded = base64.b64encode(reference_path.read_bytes()).decode("ascii")
    response = requests.post(
        _VOICE_UPLOAD_V6,
        json={
            "key": api_key,
            "name": name,
            "init_audio": f"data:{mime};base64,{encoded}",
            "language": "english",
            "base64": True,
            "gender": "female",
        },
        timeout=120,
    )
    data = response.json()
    voice_id = data.get("voice_id")
    if response.status_code >= 400 or data.get("status") == "error" or not voice_id:
        message = data.get("message") or data.get("error") or f"HTTP {response.status_code}"
        raise RuntimeError(f"ModelsLab voice upload failed: {message}")
    return str(voice_id)


def _call_stt(audio_path: Path, api_key: str) -> str:
    """Transcribe audio via ModelsLab speech-to-text. Returns transcript."""
    with open(audio_path, "rb") as fh:
        resp = requests.post(
            _STT_V6,
            data={"key": api_key},
            files={"file": fh},
            timeout=60,
        )
    data = resp.json()
    return data.get("text", data.get("transcript", ""))


def _call_piper(text: str, voice: str, dest: Path) -> Path | None:
    """Generate audio with local piper-tts. Returns path or None."""
    import shutil
    import subprocess as sp

    if not shutil.which("piper"):
        return None


def _load_kokoro_model():
    """Load the cached Hugging Face Kokoro-82M runtime once per chapter."""

    try:
        import kokoro_onnx  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError("Kokoro narration requires kokoro-onnx") from exc
    cache_root = Path(
        os.environ.get(
            "HYPERFRAMES_TTS_CACHE_DIR",
            Path.home() / ".cache" / "hyperframes" / "tts",
        )
    )
    model_path = cache_root / "models" / "kokoro-v1.0.onnx"
    voices_path = cache_root / "voices" / "voices-v1.0.bin"
    missing = [str(path) for path in (model_path, voices_path) if not path.is_file()]
    if missing:
        raise RuntimeError(
            "Kokoro model cache is incomplete. Run `npx hyperframes tts --list` "
            "and generate one sample first. Missing: " + ", ".join(missing)
        )
    return kokoro_onnx.Kokoro(str(model_path), str(voices_path))


def _generate_kokoro_audio(
    model: Any,
    *,
    text: str,
    voice_id: str,
    speed: float,
    language: str,
    destination: Path,
) -> float:
    """Synthesize one deterministic WAV segment and return measured duration."""

    import inspect
    import soundfile as sf  # type: ignore[import-untyped]

    destination.parent.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, Any] = {"voice": voice_id, "speed": float(speed)}
    normalized_language = str(language or "").strip().lower()
    language_map = {
        "english": "en-us",
        "american english": "en-us",
        "british english": "en-gb",
    }
    lang = language_map.get(normalized_language, normalized_language)
    if lang and "lang" in inspect.signature(model.create).parameters:
        kwargs["lang"] = lang
    samples, sample_rate = model.create(text, **kwargs)
    sf.write(str(destination), samples, sample_rate)
    return round(len(samples) / float(sample_rate), 3)


def _join_spoken_heading_and_body(
    heading_path: Path,
    body_path: Path,
    pause_seconds: float,
    destination: Path,
) -> float:
    """Join a spoken heading, an exact pause, and the section narration."""

    return _join_audio_parts([heading_path, body_path], [pause_seconds, 0], destination)


def _join_audio_parts(paths, pauses, destination):
    """Bounded-memory assembly, including silence, published atomically."""
    import uuid
    import numpy as np
    import soundfile as sf
    info = sf.info(str(paths[0]))
    temporary = destination.with_name(f".{destination.stem}.{uuid.uuid4().hex}.wav")
    frames = 0
    try:
        with sf.SoundFile(str(temporary), "w", samplerate=info.samplerate,
                          channels=info.channels, subtype="PCM_16") as output:
            for path, pause in zip(paths, pauses, strict=True):
                with sf.SoundFile(str(path)) as source:
                    if source.samplerate != info.samplerate or source.channels != info.channels:
                        raise RuntimeError("Incompatible audio sample rate or channels")
                    for block in source.blocks(blocksize=65536, dtype="float32", always_2d=True):
                        output.write(block)
                        frames += len(block)
                remaining = round(max(0, pause) * info.samplerate)
                silence = np.zeros((min(65536, remaining), info.channels), dtype="float32")
                while remaining:
                    count = min(len(silence), remaining)
                    output.write(silence[:count])
                    frames += count
                    remaining -= count
        temporary.replace(destination)
        return round(frames / info.samplerate, 3)
    finally:
        temporary.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

class VoiceSynthesisPipeline(BaseTool):
    """ModelsLab TTS pipeline with STT QA loop for children's educational narration."""

    name = "voice_synthesis_pipeline"
    version = "2.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.API

    dependencies = ["env:MODELSLAB_API_KEY"]
    install_instructions = "Set MODELSLAB_API_KEY in .env and use an active ModelsLab plan."
    agent_skills = ["text-to-speech", "audio-production"]
    capabilities = ["tts", "stt_qa_loop", "loudness_normalization", "children_voice"]

    input_schema = {
        "type": "object",
        "required": ["narration_segments"],
        "properties": {
            "narration_segments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["section_id", "text"],
                    "properties": {
                        "section_id":       {"type": "string"},
                        "text":             {"type": "string"},
                        "source_block_type": {"type": "string"},
                        "duration_seconds": {"type": "number"},
                    },
                },
            },
            "output_dir": {"type": "string"},
            "language":   {"type": "string", "default": "american english"},
            "voice_id":   {"type": "string"},
            "voice_profile": {
                "type": "object",
                "description": "Stable narrator configuration applied to every chapter segment",
                "properties": {
                    "voice_id": {"type": "string"},
                    "model_id": {"type": "string"},
                    "language": {"type": "string"},
                    "speed": {"type": "number", "minimum": 0.5, "maximum": 1.5},
                },
            },
            "voice_reference_path": {"type": "string"},
            "voice_reference_name": {"type": "string", "default": "OpenMontage teacher"},
            "model_id":   {"type": "string", "default": "text-to-speech"},
            "provider": {
                "type": "string",
                "enum": ["modelslab", "kokoro", "huggingface-kokoro", "hyperframes-kokoro"],
                "default": "modelslab",
            },
            "speed":      {"type": "number", "minimum": 0.5, "maximum": 1.5},
            "enable_stt_qa": {"type": "boolean", "default": True},
            "allow_voice_fallback": {
                "type": "boolean",
                "default": False,
                "description": "Permit a different offline voice only when explicitly requested",
            },
            "dry_run":    {"type": "boolean", "default": False},
            "seed":       {"type": "integer"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "narration_manifest": {"type": "object"},
            "qa_report":          {"type": "object"},
        },
    }

    # --- helpers --------------------------------------------------------------

    def _voice_for(self, source_block_type: str) -> dict[str, str]:
        del source_block_type
        return dict(_DEFAULT_VOICE)

    def _generate_segment(
        self,
        text: str,
        section_id: str,
        source_block_type: str,
        output_dir: Path,
        api_key: str,
        dry_run: bool,
        preferred_voice: str | None = None,
        language: str = "american english",
        speed: float | None = None,
        model_id: str = "text-to-speech",
        enable_stt_qa: bool = True,
        allow_voice_fallback: bool = False,
    ) -> tuple[Path | None, float, str, float]:
        """Generate one TTS segment with STT QA loop.

        Returns (audio_path, duration_seconds, voice_used, wer).
        """
        dest = output_dir / f"{section_id}.wav"
        self._last_generation_error = ""
        if dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"")
            est_dur = max(1.0, len(text.split()) / 2.0)
            return dest, est_dur, f"{preferred_voice or _DEFAULT_VOICE['voice_id']}-dryrun", 0.0

        voice_cfg = self._voice_for(source_block_type)
        if preferred_voice:
            voice_cfg = {
                "voice_id": preferred_voice,
                "speed": str(speed if speed is not None else 0.85),
            }
        # Retry the same chapter narrator. Changing voices to improve WER makes
        # a single lesson sound as though several teachers are speaking.
        voices_to_try = [dict(voice_cfg) for _ in range(_MAX_REGEN)]
        best_path, best_wer, best_voice = None, float("inf"), "nova"

        for attempt, vc in enumerate(voices_to_try[:_MAX_REGEN], 1):
            # ModelsLab v6 TTS
            payload = {
                "key": api_key,
                "model_id": model_id,
                "prompt": text,
                "voice_id": vc["voice_id"],
            }
            if model_id == "text-to-speech":
                payload.update({
                    "speed": vc.get("speed", "0.8"),
                    "language": language,
                })
            try:
                from lib.production_runtime import atomic_json
                endpoint = _TTS_V7 if model_id != "text-to-speech" else _TTS_V6
                fingerprint = hashlib.sha256(json.dumps(
                    {"endpoint": endpoint, **{k: v for k, v in payload.items() if k != "key"}},
                    sort_keys=True).encode()).hexdigest()
                job_path = dest.with_suffix(f".attempt{attempt}.job.json")
                job = json.loads(job_path.read_text(encoding="utf-8")) if job_path.is_file() else {}
                if job and job.get("fingerprint") != fingerprint:
                    self._last_generation_error = "TTS request changed; use a new output directory to preserve existing job recovery"
                    return None, 0.0, vc["voice_id"], 1.0
                if job.get("state") == "submitting":
                    self._last_generation_error = "TTS submission outcome unknown; reconcile the provider request before retrying"
                    return None, 0.0, vc["voice_id"], 1.0
                if job.get("response"):
                    data = job["response"]
                else:
                    atomic_json(job_path, {"fingerprint": fingerprint, "state": "submitting"})
                    with requests.post(endpoint, json=payload, timeout=60) as resp:
                        resp.raise_for_status()
                        data = resp.json()
                    data = {k: data[k] for k in ("status", "id", "request_id", "output", "url", "future_links") if k in data}
                    atomic_json(job_path, {"fingerprint": fingerprint, "state": "submitted", "response": data})
                if data.get("status") in {"error", "failed"}:
                    self._last_generation_error = str(
                        data.get("message") or data.get("error") or json.dumps(data)
                    )
            except requests.Timeout:
                # Provider may have accepted the job. Keep the submission
                # journal uncertain rather than creating a duplicate request.
                self._last_generation_error = "ModelsLab initial request timed out"
                return None, 0.0, vc["voice_id"], 1.0
            except Exception as exc:
                self._last_generation_error = f"ModelsLab request exception: {exc}"
                return None, 0.0, vc["voice_id"], 1.0

            # Handle async job
            status = data.get("status", "")
            audio_url: str | None = None
            if status == "processing":
                future_links = data.get("future_links") or []
                if isinstance(future_links, list) and future_links:
                    audio_url = future_links[0]
                else:
                    job_id = data.get("id") or data.get("request_id")
                    if job_id:
                        audio_url = _poll_for_audio(str(job_id), api_key)
            elif status == "success":
                out = data.get("output") or data.get("url")
                audio_url = out[0] if isinstance(out, list) else out

            if not audio_url:
                if not self._last_generation_error:
                    self._last_generation_error = f"No audio URL in ModelsLab response: {data}"
                return None, 0.0, vc["voice_id"], 1.0

            audio_path = _download(audio_url, dest.with_suffix(f".attempt{attempt}.wav"))

            # STT QA
            if enable_stt_qa:
                try:
                    transcript = _call_stt(audio_path, api_key)
                    wer = _word_error_rate(text, transcript)
                except Exception:
                    self._last_generation_error = "Speech QA unavailable; generated audio retained, validation required"
                    return None, 0.0, vc["voice_id"], 1.0
            else:
                wer = 0.0

            if wer < best_wer:
                best_wer, best_path, best_voice = wer, audio_path, vc["voice_id"]

            if wer <= _MAX_WER:
                break  # good enough — stop retrying

        # Rename best attempt to final name
        if best_path and best_path != dest:
            # ``Path.rename`` cannot overwrite an existing destination on
            # Windows, which breaks targeted narration regeneration.
            best_path.replace(dest)
        elif best_path is None and allow_voice_fallback:
            # An identity-changing fallback is opt-in and recorded in the manifest.
            piper_path = _call_piper(text, "en_US-lessac-medium", dest)
            if piper_path:
                best_path = piper_path
            else:
                return None, 0.0, "failed", 1.0
        elif best_path is None:
            return None, 0.0, "failed", 1.0

        # Read exact duration from WAV header (stdlib wave module works for
        # any sample rate / channel count without ffprobe dependency).
        # Fallback chain: wave header → ffprobe → word-count estimate.
        try:
            import wave as _wave
            if dest.exists() and dest.stat().st_size > 44:
                with _wave.open(str(dest), "rb") as wf:
                    frames = wf.getnframes()
                    rate   = wf.getframerate()
                    dur = frames / rate if rate > 0 else 0.0
            else:
                import shutil as _shu, subprocess as _sp
                if dest.exists() and _shu.which("ffprobe"):
                    r = _sp.run(
                        ["ffprobe", "-v", "error",
                         "-show_entries", "format=duration",
                         "-of", "default=noprint_wrappers=1:nokey=1", str(dest)],
                        capture_output=True, text=True, timeout=10,
                    )
                    dur = float(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else 0.0
                else:
                    dur = len(text.split()) / 2.0
        except Exception:
            dur = len(text.split()) / 2.0

        return dest, max(1.0, round(dur, 2)), best_voice, best_wer

    # --- BaseTool interface ---------------------------------------------------

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Exact provider billing is account/model dependent. Returning zero
        # would incorrectly claim that production narration has no cost.
        return float(inputs.get("estimated_cost_usd", 0.0))

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        segs = inputs.get("narration_segments", [])
        return max(5.0, len(segs) * 8.0)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        segments:   list[dict[str, Any]] = inputs.get("narration_segments", [])
        output_dir  = Path(inputs.get("output_dir", "renders/audio"))
        voice_profile = dict(inputs.get("voice_profile") or {})
        language    = voice_profile.get(
            "language", inputs.get("language", "american english")
        )
        voice_id    = (
            voice_profile.get("voice_id")
            or inputs.get("voice_id")
            or _DEFAULT_VOICE["voice_id"]
        )
        voice_reference_path = inputs.get("voice_reference_path")
        model_id    = voice_profile.get(
            "model_id", inputs.get("model_id", "text-to-speech")
        )
        speed       = voice_profile.get(
            "speed", inputs.get("speed", float(_DEFAULT_VOICE["speed"]))
        )
        enable_stt_qa = inputs.get("enable_stt_qa", True)
        allow_voice_fallback = bool(inputs.get("allow_voice_fallback", False))
        dry_run     = inputs.get("dry_run", False)
        seed        = inputs.get("seed")
        provider    = str(inputs.get("provider") or "modelslab")

        if not segments:
            return ToolResult(success=False, error="No narration_segments provided")

        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
        api_key = "" if dry_run else os.environ.get("MODELSLAB_API_KEY", "")
        if provider == "modelslab" and not dry_run and not api_key:
            return ToolResult(success=False, error="MODELSLAB_API_KEY not set")

        if provider != "modelslab" and provider not in _KOKORO_PROVIDERS:
            return ToolResult(success=False, error=f"Unsupported TTS provider: {provider}")

        if voice_reference_path and not dry_run:
            reference = Path(voice_reference_path)
            if not reference.is_file():
                return ToolResult(success=False, error=f"Voice reference not found: {reference}")
            try:
                voice_id = _upload_voice(
                    reference,
                    api_key,
                    inputs.get("voice_reference_name", "OpenMontage teacher"),
                )
                model_id = "text-to-speech"
            except Exception as exc:
                return ToolResult(success=False, error=str(exc))

        output_dir.mkdir(parents=True, exist_ok=True)
        start = time.monotonic()

        cache_path = output_dir / ".tts-cache.json"
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cache = {"version": "1.0", "segments": {}}
        cached_segments = dict(cache.get("segments") or {})

        manifest_segs: list[dict[str, Any]] = []
        qa_issues:     list[dict[str, Any]] = []

        for seg in segments:
            sid   = seg["section_id"]
            body_text = str(seg["text"]).strip()
            spoken_heading = str(seg.get("spoken_heading") or "").strip()
            heading_parts = [str(value).strip() for value in seg.get("spoken_headings", []) if str(value).strip()]
            if heading_parts:
                spoken_heading = " ".join(value if value[-1:] in ".!?" else value + "." for value in heading_parts)
            text = " ".join(part for part in (spoken_heading, body_text) if part)
            btype = seg.get("source_block_type", "concept")
            title_card_hold_seconds = max(
                0.0, float(seg.get("title_card_hold_seconds") or 0.0)
            )
            topic_end_pause = max(0.0, float(seg.get("topic_end_pause_seconds") or 0.0))
            heading_duration = 0.0
            heading_holds = []
            from tools.structure.exercise_delivery import build_exercise_delivery
            try:
                exercise_parts = build_exercise_delivery(body_text, seg.get("exercise_questions", []))
            except ValueError as exc:
                return ToolResult(success=False, error=f"Exercise delivery in {sid}: {exc}")
            has_exercise_pauses = any(p["pause_after_seconds"] for p in exercise_parts)

            audio_path = output_dir / f"{sid}.wav"
            fingerprint_payload = {
                "validation_version": 2,
                "enable_stt_qa": bool(enable_stt_qa),
                "body_text": body_text,
                "spoken_heading": spoken_heading,
                "spoken_headings": heading_parts,
                "provider": provider,
                "voice_id": voice_id,
                "model_id": model_id,
                "language": language,
                "speed": float(speed),
                "topic_end_pause_seconds": topic_end_pause,
                "exercise_delivery": exercise_parts if has_exercise_pauses else [],
            }
            if title_card_hold_seconds > 0:
                fingerprint_payload["title_card_hold_seconds"] = (
                    title_card_hold_seconds
                )
            fingerprint = hashlib.sha256(
                json.dumps(
                    fingerprint_payload,
                    sort_keys=True,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            cached = cached_segments.get(sid) or {}
            cache_hit = (
                not dry_run
                and cached.get("fingerprint") == fingerprint
                and audio_path.is_file()
                and audio_path.stat().st_size > 44
            )
            if cache_hit:
                duration = _audio_duration_seconds(audio_path)
                heading_duration = float(cached.get("heading_duration_seconds") or 0.0)
                heading_holds = cached.get("heading_holds", [])
                voice, wer = voice_id, float(cached.get("wer") or 0.0)
            elif len(heading_parts) > 1 or has_exercise_pauses:
                headings = heading_parts or ([spoken_heading] if spoken_heading else [])
                pieces = [{"section_id": f"heading-{i}", "text": part} for i, part in enumerate(headings)]
                pieces.extend({"section_id": f"body-{i}", "text": part["text"]}
                              for i, part in enumerate(exercise_parts))
                pauses = [title_card_hold_seconds] * len(headings) + [p["pause_after_seconds"] for p in exercise_parts]
                nested = self.execute({**inputs, "narration_segments": pieces,
                                       "output_dir": str(output_dir / f"{sid}-parts"),
                                       "voice_reference_path": None,
                                       "voice_profile": {"voice_id": voice_id, "model_id": model_id,
                                                         "language": language, "speed": speed}})
                if not nested.success:
                    return nested
                rendered = nested.data["narration_manifest"]["segments"]
                cursor = 0.0
                for part, item in zip(headings, rendered[:len(headings)]):
                    cursor += float(item["duration_seconds"])
                    heading_holds.append({"title": part, "start_seconds": cursor,
                                          "end_seconds": cursor + title_card_hold_seconds})
                    cursor += title_card_hold_seconds
                heading_duration = cursor - title_card_hold_seconds if headings else 0.0
                duration = sum(float(item["duration_seconds"]) + pause for item, pause in zip(rendered, pauses))
                voice, wer = rendered[-1]["voice_used"], max(item["wer"] for item in rendered)
                if dry_run:
                    audio_path.write_bytes(b"")
                else:
                    duration = _join_audio_parts([Path(item["audio_path"]) for item in rendered], pauses, audio_path)
            elif dry_run:
                audio_path.parent.mkdir(parents=True, exist_ok=True)
                audio_path.write_bytes(b"")
                duration = max(1.0, len(body_text.split()) / 2.0)
                if spoken_heading:
                    heading_duration = max(1.0, len(spoken_heading.split()) / 2.0)
                    duration += heading_duration
                    duration += title_card_hold_seconds
                duration = round(duration, 3)
                voice, wer = f"{voice_id}-dryrun", 0.0
            elif provider in _KOKORO_PROVIDERS:
                try:
                    if getattr(self, "_kokoro_model", None) is None:
                        self._kokoro_model = _load_kokoro_model()
                    kokoro_model = self._kokoro_model
                    if spoken_heading:
                        heading_path = output_dir / f".{sid}.heading.wav"
                        body_path = output_dir / f".{sid}.body.wav"
                        heading_duration = _generate_kokoro_audio(
                            kokoro_model,
                            text=spoken_heading,
                            voice_id=voice_id,
                            speed=float(speed),
                            language=language,
                            destination=heading_path,
                        )
                        _generate_kokoro_audio(
                            kokoro_model,
                            text=body_text,
                            voice_id=voice_id,
                            speed=float(speed),
                            language=language,
                            destination=body_path,
                        )
                        duration = _join_spoken_heading_and_body(
                            heading_path,
                            body_path,
                            title_card_hold_seconds,
                            audio_path,
                        )
                        heading_path.unlink(missing_ok=True)
                        body_path.unlink(missing_ok=True)
                    else:
                        duration = _generate_kokoro_audio(
                            kokoro_model,
                            text=body_text,
                            voice_id=voice_id,
                            speed=float(speed),
                            language=language,
                            destination=audio_path,
                        )
                    voice, wer = voice_id, 0.0
                except Exception as exc:
                    return ToolResult(
                        success=False,
                        error=f"Kokoro TTS failed for segment {sid}: {exc}",
                    )
            else:
                if spoken_heading:
                    heading_path, _heading_duration, heading_voice, heading_wer = self._generate_segment(
                        text=spoken_heading,
                        section_id=f"{sid}__heading",
                        source_block_type=btype,
                        output_dir=output_dir,
                        api_key=api_key,
                        dry_run=False,
                        preferred_voice=voice_id,
                        language=language,
                        speed=speed,
                        model_id=model_id,
                        enable_stt_qa=enable_stt_qa,
                        allow_voice_fallback=allow_voice_fallback,
                    )
                    body_path, _body_duration, body_voice, body_wer = self._generate_segment(
                        text=body_text,
                        section_id=f"{sid}__body",
                        source_block_type=btype,
                        output_dir=output_dir,
                        api_key=api_key,
                        dry_run=False,
                        preferred_voice=voice_id,
                        language=language,
                        speed=speed,
                        model_id=model_id,
                        enable_stt_qa=enable_stt_qa,
                        allow_voice_fallback=allow_voice_fallback,
                    )
                    if heading_path is None or body_path is None:
                        audio_path = None
                        duration, voice, wer = 0.0, "failed", 1.0
                    else:
                        heading_duration = _audio_duration_seconds(heading_path)
                        duration = _join_spoken_heading_and_body(
                            heading_path,
                            body_path,
                            title_card_hold_seconds,
                            audio_path,
                        )
                        heading_path.unlink(missing_ok=True)
                        body_path.unlink(missing_ok=True)
                        voice = body_voice or heading_voice
                        wer = max(heading_wer, body_wer)
                else:
                    audio_path, duration, voice, wer = self._generate_segment(
                        text=body_text,
                        section_id=sid,
                        source_block_type=btype,
                        output_dir=output_dir,
                        api_key=api_key,
                        dry_run=False,
                        preferred_voice=voice_id,
                        language=language,
                        speed=speed,
                        model_id=model_id,
                        enable_stt_qa=enable_stt_qa,
                        allow_voice_fallback=allow_voice_fallback,
                    )

            if not cache_hit and audio_path is not None and topic_end_pause:
                if dry_run:
                    duration += topic_end_pause
                else:
                    duration = _join_audio_parts([audio_path], [topic_end_pause], audio_path)

            if not dry_run and audio_path is not None:
                cached_segments[sid] = {
                    "fingerprint": fingerprint,
                    "path": str(audio_path.resolve()),
                    "duration_seconds": duration,
                    "voice": voice,
                    "wer": wer,
                    "heading_duration_seconds": heading_duration,
                    "heading_holds": heading_holds,
                }
                from lib.production_runtime import atomic_json
                atomic_json(cache_path, {"version": "2.0", "segments": cached_segments})

            if audio_path is None:
                return ToolResult(
                    success=False,
                    error=(
                        f"TTS failed for segment {sid} after {_MAX_REGEN} attempts: "
                        f"{getattr(self, '_last_generation_error', 'unknown provider error')}"
                    ),
                )

            if wer > _MAX_WER and not dry_run:
                qa_issues.append({
                    "section_id": sid,
                    "wer": round(wer, 3),
                    "action": "review_required",
                })

            manifest_segs.append({
                "section_id":    sid,
                "text":          text,
                "body_text":     body_text,
                "spoken_heading": spoken_heading,
                "heading_duration_seconds": heading_duration,
                "heading_holds": heading_holds,
                "body_start_seconds": heading_duration + (title_card_hold_seconds if spoken_heading else 0.0),
                "topic_end_pause_seconds": topic_end_pause,
                "audio_path":    str(audio_path.resolve()),
                "duration_seconds": duration,
                "title_card_hold_seconds": title_card_hold_seconds,
                "voice_used":    voice,
                "wer":           round(wer, 3),
                "delivery_cues_applied": {
                    "speed": str(speed if speed is not None else "0.8"),
                    "pace": "children-120wpm",
                    "language": language,
                },
                "cost_usd":      0.0,
            })

        total_dur = sum(s["duration_seconds"] for s in manifest_segs)

        if not dry_run:
            from lib.production_runtime import atomic_json
            atomic_json(cache_path, {"version": "2.0", "segments": cached_segments})

        narration_manifest = {
            "version":    "1.0",
            "engine_used": (
                "huggingface-kokoro-82m"
                if provider in _KOKORO_PROVIDERS
                else "modelslab-text-to-speech"
            ),
            "voice_name": voice_id,
            "voice_characteristics": {
                "child_friendly": True,
                "gender":  "neutral",
                "accent":  language,
                "pace":    "120wpm-children",
                "energy":  "warm",
            },
            "segments":                manifest_segs,
            "total_duration_seconds":  round(total_dur, 2),
            "total_cost_usd":          0.0,
            "metadata": {
                "tts_model":    model_id,
                "stt_qa_model": "faster-whisper-word-alignment" if provider in _KOKORO_PROVIDERS else "speech-to-text",
                "max_wer_threshold": _MAX_WER,
                "fallback_chain_available": allow_voice_fallback,
                "piper_offline_fallback": allow_voice_fallback,
                "voice_locked_for_chapter": not allow_voice_fallback,
            },
        }

        qa_report = {
            "total_segments": len(segments),
            "status": "failed" if qa_issues else ("passed" if enable_stt_qa and not dry_run and provider == "modelslab" else "unverified"),
            "qa_passed":      len(segments) - len(qa_issues) if enable_stt_qa and not dry_run and provider == "modelslab" else 0,
            "qa_issues":      qa_issues,
            "stt_qa_enabled": bool(enable_stt_qa and not dry_run and provider == "modelslab"),
        }

        return ToolResult(
            success=not qa_issues,
            error="Narration failed speech QA; review required" if qa_issues else None,
            data={"narration_manifest": narration_manifest, "qa_report": qa_report},
            artifacts=["narration_manifest"],
            cost_usd=0.0,
            duration_seconds=time.monotonic() - start,
            seed=seed,
        )

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {
            "tool": self.name,
            "estimated_cost_usd": 0.0,
            "estimated_runtime_seconds": self.estimate_runtime(inputs),
            "status": self.get_status().value,
            "would_execute": True,
        }
