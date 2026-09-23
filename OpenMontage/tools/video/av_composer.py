"""Audio-video composition tool — production-grade assembly.

Fixes applied vs v1.0.0:
  1. Never reads and writes the same file — uses explicit tmp files at every step
  2. Audio filter graph is complete: adelay per segment + amix with output label
  3. Subtitle burn is integrated (no separate step needed)
  4. concat_list.txt uses forward-slash absolute paths (Windows-safe)
  5. All ffmpeg calls use check=False + explicit error propagation
  6. Loudnorm uses a tmp file, not in-place overwrite
  7. Subtitle path escaping matches _compose2.py's proven formula
"""
from __future__ import annotations

import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

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
# Helpers
# ---------------------------------------------------------------------------

def _sh(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    """Run a command; raise RuntimeError on non-zero exit."""
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (exit {r.returncode}):\n"
            f"  cmd: {' '.join(cmd[:6])} …\n"
            f"  stderr: {r.stderr[-600:]}"
        )
    return r


def _probe_duration(path: Path) -> float:
    """Return video/audio duration via ffprobe. Returns 0.0 on failure."""
    if not shutil.which("ffprobe"):
        return 0.0
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error",
             "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=15,
        )
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def _probe_ok(path: Path, min_s: float = 0.5) -> bool:
    return path.exists() and _probe_duration(path) >= min_s


def _posix_path(p: Path) -> str:
    """Absolute POSIX path — forward slashes even on Windows."""
    return p.resolve().as_posix()


def _escape_sub_path(path: Path) -> str:
    """Escape path for ffmpeg -vf subtitles= on Windows.

    Drive colon must be escaped as \\:  e.g.  C\\:/Users/foo/bar.srt
    Spaces escaped as \\ (space).
    """
    p = _posix_path(path)
    p = re.sub(r"^([A-Za-z]):/", r"\1\\:/", p)
    p = p.replace(" ", "\\ ")
    return p


def _duration_to_srt_ts(secs: float) -> str:
    ms = int(round(secs * 1000))
    h, r = divmod(ms, 3_600_000)
    m, r = divmod(r, 60_000)
    s, ms = divmod(r, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ---------------------------------------------------------------------------
# AVComposer
# ---------------------------------------------------------------------------

class AVComposer(BaseTool):
    """Assemble clip segments + narration audio into a final chapter video.

    Pipeline
    --------
    1. Concat video segments → video_track.mp4          (copy codec)
    2. Build positioned audio mix → mix_raw.wav          (adelay per segment)
    3. Loudnorm mix → mix_norm.wav                       (separate tmp file)
    4. Mux video + normalised audio → nosub.mp4
    5. Build SRT from narration manifest timing
    6. Burn subtitles → final output (re-encode video stream)
    """

    name = "av_composer"
    version = "2.0.0"
    tier = ToolTier.CORE
    capability = "av_composition"
    provider = "openmontage"
    stability = ToolStability.PRODUCTION
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["cmd:ffmpeg", "cmd:ffprobe"]
    install_instructions = (
        "Install FFmpeg: winget install FFmpeg  (Windows)\n"
        "macOS: brew install ffmpeg\n"
        "Linux: sudo apt install ffmpeg"
    )
    agent_skills = ["ffmpeg", "audio-mixing", "loudness-normalization"]
    capabilities = [
        "video_merge",
        "positioned_audio_mix",
        "loudness_normalization",
        "subtitle_burn",
        "ducking",
    ]

    input_schema = {
        "type": "object",
        "required": ["video_segments"],
        "properties": {
            "video_segments":     {"type": "array", "items": {"type": "string"},
                                   "description": "Ordered list of clip paths"},
            "narration_manifest": {"type": "object",
                                   "description": "narration_manifest.json with segments[] "
                                                  "containing audio_path + start_seconds"},
            "background_music":   {"type": "string"},
            "output_path":        {"type": "string", "default": "renders/final_render.mp4"},
            "subtitle_style":     {"type": "string",
                                   "default": "FontName=Nunito,FontSize=22,"
                                              "PrimaryColour=&H00FFFFFF,"
                                              "OutlineColour=&H00000000,"
                                              "Outline=2,Alignment=2,MarginV=36"},
            "target_lufs":        {"type": "number", "default": -14.0},
            "duck_amount":        {"type": "number", "default": 0.3},
            "burn_subtitles":     {"type": "boolean", "default": True},
            "formatted_srt_path": {"type": "string",
                                   "description": "Pre-built word-timed SRT from NarrationTextSyncer. "
                                                  "When provided, used instead of auto-generated SRT."},
            "title_offset_seconds": {"type": "number", "default": 0.0,
                                     "description": "Seconds to add to every subtitle start time. "
                                                    "Use when calling AVComposer standalone without "
                                                    "runner-injected start_seconds. Leave 0.0 when "
                                                    "using SubjectPipelineRunner (offset already baked in)."},
            "dry_run":            {"type": "boolean", "default": False},
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "final_render":      {"type": "string"},
            "duration_seconds":  {"type": "number"},
            "subtitle_path":     {"type": "string"},
        },
    }

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return max(30.0, len(inputs.get("video_segments", [])) * 8.0)

    # ── Step 1: Video track concatenation ─────────────────────────────────────

    def _concat_video(
        self, segments: list[str], tmp_dir: Path
    ) -> Path:
        """Concatenate video clips using the concat demuxer (stream-copy, lossless)."""
        # Write concat list with absolute POSIX paths
        lst = tmp_dir / "concat_list.txt"
        lines = [f"file '{_posix_path(Path(s))}'" for s in segments]
        lst.write_text("\n".join(lines), encoding="utf-8")

        out = tmp_dir / "video_track.mp4"
        _sh([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(lst),
            "-c", "copy", str(out),
        ])
        if not _probe_ok(out):
            raise RuntimeError(f"Video track empty or missing after concat: {out}")
        return out

    # ── Step 2: Positioned audio mix ──────────────────────────────────────────

    def _build_audio_mix(
        self,
        total_duration: float,
        narration_manifest: dict[str, Any],
        background_music: str | None,
        duck_amount: float,
        tmp_dir: Path,
    ) -> Path:
        """Build a mixed WAV with each narration segment positioned at its start_seconds.

        Filter graph:
            [0:a]                     — silent base track (total_duration seconds)
            [1:a] adelay={ms} [nar1]  — segment 1 positioned
            [2:a] adelay={ms} [nar2]  — segment 2 positioned
            ...
            [0:a][nar1][nar2]...amix=inputs=N+1:normalize=0 [mixed]

        If background_music is provided:
            [mixed] is treated as the narration layer
            [bgm] is ducked by duck_amount
            Final mix = narration + ducked bgm
        """
        segments = narration_manifest.get("segments", [])

        # Silent base track (ensures the mix is exactly total_duration long)
        base = tmp_dir / "base.wav"
        _sh([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-t", str(total_duration), str(base),
        ])

        cmd: list[str] = ["ffmpeg", "-y", "-i", str(base)]
        filters: list[str] = []
        n_nar = 0   # tracks only segments that were actually added as ffmpeg inputs

        for idx, seg in enumerate(segments, 1):
            audio_file = Path(seg.get("audio_path", ""))
            if not audio_file.is_absolute():
                # Resolve relative paths from project root
                from pathlib import Path as P
                root = P(__file__).resolve().parents[2]
                audio_file = root / audio_file

            if not audio_file.exists():
                # Skip missing segments — non-fatal, leaves silence in that window
                continue

            n_nar += 1
            delay_ms = int(round(float(seg.get("start_seconds", 0)) * 1000))
            cmd.extend(["-i", str(audio_file)])
            filters.append(
                f"[{n_nar}:a]"
                f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                f"adelay={delay_ms}|{delay_ms},"
                f"volume=1.0"
                f"[nar{n_nar}]"
            )

        if n_nar == 0:
            # No narration — return silence
            return base

        total_inputs = n_nar + 1
        nar_labels   = "".join(f"[nar{i}]" for i in range(1, n_nar + 1))
        filters.append(
            f"[0:a]{nar_labels}"
            f"amix=inputs={total_inputs}:normalize=0:dropout_transition=0"
            f"[mixed]"
        )

        mix_raw = tmp_dir / "mix_raw.wav"
        cmd += [
            "-filter_complex", ";".join(filters),
            "-map", "[mixed]",
            "-ac", "2", "-ar", "48000",
            "-c:a", "pcm_s16le", str(mix_raw),
        ]
        _sh(cmd)

        if not background_music or not Path(background_music).exists():
            return mix_raw

        # Duck background music under narration
        bgm_mix = tmp_dir / "mix_with_bgm.wav"
        _sh([
            "ffmpeg", "-y",
            "-i", str(mix_raw), "-i", str(background_music),
            "-filter_complex",
            f"[1:a]volume={duck_amount},aloop=loop=-1:size=2e+09[bgm];"
            f"[0:a][bgm]amix=inputs=2:duration=first:normalize=0[out]",
            "-map", "[out]",
            "-ac", "2", "-ar", "48000",
            "-c:a", "pcm_s16le", str(bgm_mix),
        ])
        return bgm_mix

    # ── Step 3: Loudness normalisation ────────────────────────────────────────

    def _loudnorm(self, mix: Path, target_lufs: float, tmp_dir: Path) -> Path:
        """Loudnorm into a separate output file — never in-place."""
        norm = tmp_dir / "mix_norm.wav"
        _sh([
            "ffmpeg", "-y", "-i", str(mix),
            "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
            "-ar", "48000", "-ac", "2",
            "-c:a", "pcm_s16le", str(norm),
        ])
        return norm

    # ── Step 4: Mux video + audio ─────────────────────────────────────────────

    def _mux(self, video: Path, audio: Path, tmp_dir: Path) -> Path:
        """Mux video stream + audio stream into a new file (never overwrites input)."""
        out = tmp_dir / "muxed.mp4"
        _sh([
            "ffmpeg", "-y",
            "-i", str(video), "-i", str(audio),
            "-map", "0:v", "-map", "1:a",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(out),
        ])
        return out

    # ── Step 5: SRT subtitle generation ──────────────────────────────────────

    def _build_srt(
        self, narration_manifest: dict[str, Any], tmp_dir: Path,
        title_offset_seconds: float = 0.0,
    ) -> Path:
        """Build SRT file from narration manifest timing.

        title_offset_seconds is added to every segment's start_seconds.
        When called from SubjectPipelineRunner the manifest already has
        title_offset baked in (via NarrationTextSyncer), so the default 0.0
        is correct.  When called standalone without runner injection, pass
        the actual title clip duration here.
        """
        srt = tmp_dir / "subtitles.srt"
        lines: list[str] = []
        for i, seg in enumerate(narration_manifest.get("segments", []), 1):
            t0 = float(seg.get("start_seconds", 0)) + title_offset_seconds
            t1 = t0 + float(seg.get("duration_seconds", 5))
            lines.append(str(i))
            lines.append(f"{_duration_to_srt_ts(t0)} --> {_duration_to_srt_ts(t1)}")
            lines.append(seg.get("text", ""))
            lines.append("")
        srt.write_text("\n".join(lines), encoding="utf-8")
        return srt

    # ── Step 6: Subtitle burn ─────────────────────────────────────────────────

    def _burn_subtitles(
        self,
        muxed: Path,
        srt: Path,
        output: Path,
        subtitle_style: str,
    ) -> Path:
        """Re-encode video with subtitle burn. Input and output are different files.

        NOTE: On Windows subprocess does NOT use a shell, so single-quotes in
        the -vf argument are passed literally to ffmpeg as part of the filter
        string (not stripped by the shell).  We must omit them — ffmpeg accepts
        force_style= without surrounding quotes when passed as a single argv token.
        """
        sub_esc = _escape_sub_path(srt)
        # No single-quotes around force_style value — subprocess, not shell
        _sh([
            "ffmpeg", "-y", "-i", str(muxed),
            "-vf", f"subtitles={sub_esc}:force_style={subtitle_style}",
            "-c:v", "libx264", "-crf", "18", "-preset", "medium",
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            str(output),
        ])
        return output

    # ── BaseTool interface ────────────────────────────────────────────────────

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        video_segments     = inputs.get("video_segments", [])
        narration_manifest = inputs.get("narration_manifest", {})
        background_music   = inputs.get("background_music")
        output_path        = Path(inputs.get("output_path", "renders/final_render.mp4"))
        subtitle_style     = inputs.get("subtitle_style",
                                        "FontName=Arial,FontSize=22,"
                                        "PrimaryColour=&H00FFFFFF,"
                                        "OutlineColour=&H00000000,"
                                        "Outline=2,Alignment=2,MarginV=36")
        target_lufs        = inputs.get("target_lufs", -14.0)
        duck_amount        = inputs.get("duck_amount", 0.3)
        burn_subs          = inputs.get("burn_subtitles", True)
        formatted_srt_path = inputs.get("formatted_srt_path")
        title_offset_secs  = float(inputs.get("title_offset_seconds", 0.0))
        dry_run            = inputs.get("dry_run", False)
        start              = time.monotonic()

        if not video_segments:
            return ToolResult(success=False, error="No video_segments provided")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_dir = output_path.parent / "_compose_tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        if dry_run:
            output_path.write_bytes(b"")
            srt = tmp_dir / "subtitles.srt"
            srt.write_text("", encoding="utf-8")
            return ToolResult(
                success=True,
                data={"final_render": str(output_path),
                      "duration_seconds": 0.0,
                      "subtitle_path": str(srt)},
                artifacts=["final_review", "render_report"],
                cost_usd=0.0,
            )

        # Validate all input clips exist before starting
        missing = [s for s in video_segments if not Path(s).exists()]
        if missing:
            return ToolResult(
                success=False,
                error=f"{len(missing)} clip(s) not found: {missing[:3]}"
            )

        try:
            # Step 1: concat video
            video_track = self._concat_video(video_segments, tmp_dir)

            # Step 2: positioned audio mix
            total_dur = _probe_duration(video_track)
            audio_mix = self._build_audio_mix(
                total_duration=total_dur,
                narration_manifest=narration_manifest,
                background_music=background_music,
                duck_amount=duck_amount,
                tmp_dir=tmp_dir,
            )

            # Step 3: loudnorm
            norm_mix = self._loudnorm(audio_mix, target_lufs, tmp_dir)

            # Step 4: mux
            muxed = self._mux(video_track, norm_mix, tmp_dir)

            # Step 5: SRT — prefer word-timed formatted SRT from NarrationTextSyncer
            # if available; fall back to auto-generated section-level SRT.
            if formatted_srt_path and Path(formatted_srt_path).exists():
                srt = Path(formatted_srt_path)
            else:
                srt = self._build_srt(narration_manifest, tmp_dir, title_offset_secs)

            # Step 6: subtitle burn or straight copy
            if burn_subs and narration_manifest.get("segments"):
                final = self._burn_subtitles(muxed, srt, output_path, subtitle_style)
            else:
                import shutil as _sh2
                _sh2.copy2(str(muxed), str(output_path))
                final = output_path

        except RuntimeError as exc:
            return ToolResult(success=False, error=str(exc))
        except Exception as exc:
            return ToolResult(success=False, error=f"Unexpected error: {exc}")

        duration = _probe_duration(final)
        return ToolResult(
            success=True,
            data={
                "final_render":     str(final),
                "duration_seconds": duration,
                "subtitle_path":    str(srt),
            },
            artifacts=["final_review", "render_report"],
            cost_usd=0.0,
            duration_seconds=time.monotonic() - start,
        )

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {
            "tool": self.name,
            "estimated_cost_usd": 0.0,
            "estimated_runtime_seconds": self.estimate_runtime(inputs),
            "status": self.get_status().value,
            "would_execute": True,
        }
