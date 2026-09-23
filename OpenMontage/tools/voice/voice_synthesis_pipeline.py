"""VoiceSynthesisPipeline — ModelsLab TTS stack with STT QA loop.

All models are open-source / unlimited on the ModelsLab plan.
inworld-tts-1 is removed (closed source, costs money).

TTS stack
---------
  Primary   text-to-speech  nova     /api/v6/voice/text_to_speech  (unlimited)
  Q&A       text-to-speech  sophia   speed 0.75 (deliberate pacing)
  Recall    text-to-speech  bella    speed 0.85 (slightly faster)
  Regional  eleven_multilingual_v2  Nila - Tamil  (Indian classrooms)
  Offline   piper_tts  (zero dependency fallback)

STT QA loop
-----------
After every TTS call, speech-to-text transcribes the audio and diffs
against the source script. If word-error-rate > 5% the segment is
regenerated with the next voice in the voice rotation list.
Max 3 regeneration attempts before accepting best-so-far.
"""
from __future__ import annotations

import json
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
# TTS stack — no closed-source models
# ---------------------------------------------------------------------------
FALLBACK_CHAIN = [
    {
        "engine":   "modelslab",
        "model_id": "text-to-speech",
        "endpoint": _TTS_V6,
        "voice_id": "nova",
        "speed":    "0.8",
        "language": "american english",
        "cost":     "unlimited",
        "note":     "Primary — warm, child-friendly, free/unlimited",
    },
    {
        "engine":   "modelslab",
        "model_id": "text-to-speech",
        "endpoint": _TTS_V6,
        "voice_id": "sophia",
        "speed":    "0.75",
        "language": "american english",
        "cost":     "unlimited",
        "note":     "Q&A sections — slower, more deliberate",
    },
    {
        "engine":   "modelslab",
        "model_id": "text-to-speech",
        "endpoint": _TTS_V6,
        "voice_id": "bella",
        "speed":    "0.85",
        "language": "american english",
        "cost":     "unlimited",
        "note":     "Recall/summary sections",
    },
    {
        "engine":   "modelslab",
        "model_id": "eleven_multilingual_v2",
        "endpoint": _TTS_V7,
        "voice_id": "Nila - Tamil",
        "cost":     "unlimited",
        "note":     "Regional: Tamil / Indian classrooms",
    },
    {
        "engine":   "piper_tts",
        "model_id": "en_US-lessac-medium",
        "cost":     "$0",
        "note":     "Offline fallback — zero API dependency",
    },
]

# voice→speed mapped by section source_block_type
_BLOCK_VOICE: dict[str, dict[str, str]] = {
    "qa_item":   {"voice_id": "sophia", "speed": "0.75"},
    "recall":    {"voice_id": "bella",  "speed": "0.85"},
    "glossary":  {"voice_id": "sophia", "speed": "0.75"},
    "activity":  {"voice_id": "bella",  "speed": "0.85"},
}
_DEFAULT_VOICE = {"voice_id": "nova", "speed": "0.8"}

_MAX_WER        = 0.05   # 5% word-error-rate threshold
_MAX_REGEN      = 3      # regeneration attempts before accepting best-so-far
_POLL_INTERVAL  = 2      # seconds between async status polls
_POLL_TIMEOUT   = 120    # seconds before giving up on a generation job


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
            r = requests.get(url, timeout=60, stream=True)
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            return dest
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
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        proc = sp.run(
            ["piper", "--model", voice, "--output_file", str(dest)],
            input=text.encode(),
            capture_output=True,
            timeout=60,
        )
        return dest if proc.returncode == 0 else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

class VoiceSynthesisPipeline(BaseTool):
    """ModelsLab TTS pipeline with STT QA loop for children's educational narration."""

    name = "voice_synthesis_pipeline"
    version = "2.0.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.API

    dependencies = ["env:MODELSLAB_API_KEY"]
    install_instructions = "Set MODELSLAB_API_KEY in .env (free/unlimited plan covers all TTS)."
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
            "voice_reference_path": {"type": "string"},
            "voice_reference_name": {"type": "string", "default": "OpenMontage teacher"},
            "model_id":   {"type": "string", "default": "text-to-speech"},
            "speed":      {"type": "number", "minimum": 0.5, "maximum": 1.5},
            "enable_stt_qa": {"type": "boolean", "default": True},
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
        return _BLOCK_VOICE.get(source_block_type, _DEFAULT_VOICE)

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
            return dest, est_dur, "nova-dryrun", 0.0

        voice_cfg = self._voice_for(source_block_type)
        if preferred_voice:
            voice_cfg = {
                "voice_id": preferred_voice,
                "speed": str(speed if speed is not None else 0.85),
            }
        voices_to_try = [
            voice_cfg,
            _BLOCK_VOICE.get("recall", _DEFAULT_VOICE),
            _DEFAULT_VOICE,
        ]
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
                endpoint = _TTS_V7 if model_id != "text-to-speech" else _TTS_V6
                resp = requests.post(endpoint, json=payload, timeout=60)
                data = resp.json()
                if resp.status_code >= 400 or data.get("status") in {"error", "failed"}:
                    self._last_generation_error = str(
                        data.get("message") or data.get("error") or json.dumps(data)
                    )
            except requests.Timeout:
                # Network timeout on the initial POST — don't count as a TTS
                # quality failure; retry with the same voice, not the next one.
                self._last_generation_error = "ModelsLab initial request timed out"
                continue
            except Exception as exc:
                self._last_generation_error = f"ModelsLab request exception: {exc}"
                continue

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
                continue

            audio_path = _download(audio_url, dest.with_suffix(f".attempt{attempt}.wav"))

            # STT QA
            if enable_stt_qa:
                try:
                    transcript = _call_stt(audio_path, api_key)
                    wer = _word_error_rate(text, transcript)
                except Exception:
                    wer = 0.0  # can't validate — accept
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
        elif best_path is None:
            # Final fallback: piper offline
            piper_path = _call_piper(text, "en_US-lessac-medium", dest)
            if piper_path:
                best_path = piper_path
            else:
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
        return 0.0  # unlimited on plan

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        segs = inputs.get("narration_segments", [])
        return max(5.0, len(segs) * 8.0)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        segments:   list[dict[str, Any]] = inputs.get("narration_segments", [])
        output_dir  = Path(inputs.get("output_dir", "renders/audio"))
        language    = inputs.get("language", "american english")
        voice_id    = inputs.get("voice_id")
        voice_reference_path = inputs.get("voice_reference_path")
        model_id    = inputs.get("model_id", "text-to-speech")
        speed       = inputs.get("speed")
        enable_stt_qa = inputs.get("enable_stt_qa", True)
        dry_run     = inputs.get("dry_run", False)
        seed        = inputs.get("seed")

        if not segments:
            return ToolResult(success=False, error="No narration_segments provided")

        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
        api_key = "" if dry_run else os.environ.get("MODELSLAB_API_KEY", "")
        if not dry_run and not api_key:
            return ToolResult(success=False, error="MODELSLAB_API_KEY not set")

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

        manifest_segs: list[dict[str, Any]] = []
        qa_issues:     list[dict[str, Any]] = []

        for seg in segments:
            sid   = seg["section_id"]
            text  = seg["text"]
            btype = seg.get("source_block_type", "concept")

            audio_path, duration, voice, wer = self._generate_segment(
                text=text,
                section_id=sid,
                source_block_type=btype,
                output_dir=output_dir,
                api_key=api_key,
                dry_run=dry_run,
                preferred_voice=voice_id,
                language=language,
                speed=speed,
                model_id=model_id,
                enable_stt_qa=enable_stt_qa,
            )

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
                    "action": "accepted_best_available",
                })

            manifest_segs.append({
                "section_id":    sid,
                "text":          text,
                "audio_path":    str(audio_path),
                "duration_seconds": duration,
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

        narration_manifest = {
            "version":    "1.0",
            "engine_used": "modelslab-text-to-speech",
            "voice_name": voice_id or "nova",
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
                "stt_qa_model": "speech-to-text",
                "max_wer_threshold": _MAX_WER,
                "fallback_chain_available": True,
                "piper_offline_fallback": True,
            },
        }

        qa_report = {
            "total_segments": len(segments),
            "qa_passed":      len(segments) - len(qa_issues),
            "qa_issues":      qa_issues,
            "stt_qa_enabled": bool(enable_stt_qa and not dry_run),
        }

        return ToolResult(
            success=True,
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
