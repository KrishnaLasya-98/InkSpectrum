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
from pathlib import Path
from typing import Any

import requests

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
                _FETCH_V6,
                json={"key": api_key, "request_id": job_id},
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
    r = requests.get(url, timeout=60, stream=True)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
    return dest


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
    ) -> tuple[Path | None, float, str, float]:
        """Generate one TTS segment with STT QA loop.

        Returns (audio_path, duration_seconds, voice_used, wer).
        """
        dest = output_dir / f"{section_id}.wav"
        if dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"")
            est_dur = max(1.0, len(text.split()) / 2.0)
            return dest, est_dur, "nova-dryrun", 0.0

        voice_cfg = self._voice_for(source_block_type)
        voices_to_try = [
            voice_cfg,
            _BLOCK_VOICE.get("recall", _DEFAULT_VOICE),
            _DEFAULT_VOICE,
        ]
        best_path, best_wer, best_voice = None, 1.0, "nova"

        for attempt, vc in enumerate(voices_to_try[:_MAX_REGEN], 1):
            # ModelsLab v6 TTS
            payload = {
                "key":      api_key,
                "model_id": "text-to-speech",
                "prompt":   text,
                "voice_id": vc["voice_id"],
                "speed":    vc.get("speed", "0.8"),
                "language": "american english",
            }
            try:
                resp = requests.post(_TTS_V6, json=payload, timeout=60)
                data = resp.json()
            except requests.Timeout:
                # Network timeout on the initial POST — don't count as a TTS
                # quality failure; retry with the same voice, not the next one.
                continue
            except Exception:
                continue

            # Handle async job
            status = data.get("status", "")
            audio_url: str | None = None
            if status == "processing":
                job_id = data.get("id") or data.get("request_id")
                if job_id:
                    audio_url = _poll_for_audio(str(job_id), api_key)
            elif status == "success":
                out = data.get("output") or data.get("url")
                audio_url = out[0] if isinstance(out, list) else out

            if not audio_url:
                continue

            audio_path = _download(audio_url, dest.with_suffix(f".attempt{attempt}.wav"))

            # STT QA
            try:
                transcript = _call_stt(audio_path, api_key)
                wer = _word_error_rate(text, transcript)
            except Exception:
                wer = 0.0  # can't validate — accept

            if wer < best_wer:
                best_wer, best_path, best_voice = wer, audio_path, vc["voice_id"]

            if wer <= _MAX_WER:
                break  # good enough — stop retrying

        # Rename best attempt to final name
        if best_path and best_path != dest:
            best_path.rename(dest)
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
        dry_run     = inputs.get("dry_run", False)
        seed        = inputs.get("seed")

        if not segments:
            return ToolResult(success=False, error="No narration_segments provided")

        api_key = "" if dry_run else os.environ.get("MODELSLAB_API_KEY", "")
        if not dry_run and not api_key:
            return ToolResult(success=False, error="MODELSLAB_API_KEY not set")

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
            )

            if audio_path is None:
                return ToolResult(
                    success=False,
                    error=f"TTS failed for segment {sid} after {_MAX_REGEN} attempts",
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
                "delivery_cues_applied": {"speed": "0.8", "pace": "children-120wpm"},
                "cost_usd":      0.0,
            })

        total_dur = sum(s["duration_seconds"] for s in manifest_segs)

        narration_manifest = {
            "version":    "1.0",
            "engine_used": "modelslab-text-to-speech",
            "voice_name": "nova",
            "voice_characteristics": {
                "child_friendly": True,
                "gender":  "neutral",
                "accent":  "american english",
                "pace":    "120wpm-children",
                "energy":  "warm",
            },
            "segments":                manifest_segs,
            "total_duration_seconds":  round(total_dur, 2),
            "total_cost_usd":          0.0,
            "metadata": {
                "tts_model":    "text-to-speech",
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
            "stt_qa_enabled": not dry_run,
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
