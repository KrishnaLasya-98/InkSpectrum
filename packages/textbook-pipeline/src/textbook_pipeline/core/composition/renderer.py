"""Phase 4: Video Composition.

Generates a final MP4 from Phase 2 script scenes + Phase 3 audio files.

Strategy:
1. Create visual slide images per scene using Pillow (text on colored background).
2. Use FFmpeg to assemble each scene's slides + audio into a video segment.
3. Concatenate all segments into the final chapter MP4.

Future: swap slide generator for Remotion/MoviePy renderer when available.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Color palette for visual variety
PALETTE = [
    "#1a1a2e", "#16213e", "#0f3460", "#533483",
    "#e94560", "#2c3333", "#3a4d39", "#4a4e69",
    "#22223b", "#4d4c7d", "#9a8c98", "#c9ada7",
]

FONT_PATHS = [
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/calibri.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _find_font(size: int) -> ImageFont.FreeTypeFont:
    for fp in FONT_PATHS:
        if Path(fp).exists():
            return ImageFont.truetype(fp, size)
    return ImageFont.load_default()


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    """Wrap text to fit within max_width pixels."""
    words = text.split()
    lines: List[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = font.getbbox(test)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def create_scene_slide(
    scene: Dict[str, Any],
    output_path: Path,
    width: int = 1280,
    height: int = 720,
) -> Path:
    """Create a visual slide image for a scene.

    Renders the scene title + first voiceover line on a colored background.
    """
    color_idx = hash(scene.get("id", "")) % len(PALETTE)
    bg_color = PALETTE[color_idx]
    text_color = "#ffffff"

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    title = scene.get("title", "Lesson")
    vo_lines = scene.get("voiceover_lines", [])
    first_vo = vo_lines[0].get("text", "") if vo_lines else ""

    # Title
    title_font = _find_font(56)
    title_lines = _wrap_text(title, title_font, width - 120)
    y = 80
    for line in title_lines:
        bbox = title_font.getbbox(line)
        tw = bbox[2] - bbox[0]
        draw.text(((width - tw) // 2, y), line, font=title_font, fill=text_color)
        y += 70

    # Separator
    y += 20
    draw.line([(120, y), (width - 120, y)], fill="#ffffff88", width=2)
    y += 30

    # First voiceover line
    if first_vo:
        vo_font = _find_font(32)
        vo_lines_wrapped = _wrap_text(first_vo[:300], vo_font, width - 120)
        for line in vo_lines_wrapped:
            bbox = vo_font.getbbox(line)
            tw = bbox[2] - bbox[0]
            draw.text(((width - tw) // 2, y), line, font=vo_font, fill="#dddddd")
            y += 45

    # Scene ID footer
    footer_font = _find_font(18)
    footer = scene.get("id", "")
    draw.text((20, height - 30), footer, font=footer_font, fill="#ffffff44")

    img.save(str(output_path), "PNG")
    return output_path


def get_audio_duration(audio_path: Path) -> float:
    """Get audio duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip())
    except Exception as exc:
        logger.warning("Could not get audio duration for %s: %s", audio_path, exc)
        return 5.0


def create_scene_video_segment(
    scene: Dict[str, Any],
    audio_files: List[Path],
    output_path: Path,
    temp_dir: Path,
    width: int = 1280,
    height: int = 720,
    fps: int = 24,
) -> Path:
    """Create a video segment for one scene from its audio files.

    Shows a slide image for the total audio duration.
    """
    if not audio_files:
        return output_path

    # Check for AI-generated assets first
    assets = scene.get("generated_assets", {})
    video_asset = assets.get("video")
    image_asset = assets.get("image")

    # Calculate total audio duration
    total_duration = sum(get_audio_duration(p) for p in audio_files)
    total_duration = max(total_duration, 2.0)  # Minimum 2s per scene

    # Use FFmpeg to create video from assets + audio
    if video_asset and Path(video_asset).exists():
        # Use AI-generated video clip, loop/extend to match audio duration
        video_input = str(video_asset)
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", video_input,
                "-i", str(audio_files[0]),
                "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-shortest",
                "-t", f"{total_duration:.3f}",
                str(output_path),
            ],
            capture_output=True, timeout=120,
        )
    elif image_asset and Path(image_asset).exists():
        # Use AI-generated image as slide
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-loop", "1", "-i", str(image_asset),
                "-i", str(audio_files[0]),
                "-c:v", "libx264", "-tune", "stillimage",
                "-c:a", "aac", "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-shortest",
                "-t", f"{total_duration:.3f}",
                "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
                str(output_path),
            ],
            capture_output=True, timeout=120,
        )
    else:
        # Fallback: create Pillow slide
        slide_path = temp_dir / f"{scene['id']}_slide.png"
        create_scene_slide(scene, slide_path, width, height)

        # If multiple audio files, concat them first
        if len(audio_files) == 1:
            audio_input = str(audio_files[0])
        else:
            concat_list = temp_dir / f"{scene['id']}_concat.txt"
            concat_list.write_text(
                "\n".join(f"file '{p.resolve()}'" for p in audio_files),
                encoding="utf-8",
            )
            audio_input = str(temp_dir / f"{scene['id']}_concat.mp3")
            subprocess.run(
                [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(concat_list),
                    "-c", "copy", audio_input,
                ],
                capture_output=True, timeout=60,
            )

        subprocess.run(
            [
                "ffmpeg", "-y",
                "-loop", "1", "-i", str(slide_path),
                "-i", audio_input,
                "-c:v", "libx264", "-tune", "stillimage",
                "-c:a", "aac", "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-shortest",
                "-t", f"{total_duration:.3f}",
                "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
                str(output_path),
            ],
            capture_output=True, timeout=120,
        )

    return output_path


def concat_videos(video_files: List[Path], output_path: Path) -> Path:
    """Concatenate multiple video files into one using FFmpeg."""
    if not video_files:
        raise ValueError("No video files to concatenate")

    if len(video_files) == 1:
        video_files[0].rename(output_path)
        return output_path

    concat_list = output_path.parent / "concat_list.txt"
    concat_list.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in video_files),
        encoding="utf-8",
    )

    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(output_path),
        ],
        capture_output=True, timeout=300,
    )

    # Remux to normalize container duration metadata: concatenating with
    # -c copy can write an inflated mvhd duration (~1-2s gap per segment).
    # A stream-copy remux recomputes container metadata without re-encoding.
    remux_path = output_path.with_suffix(".remux.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(output_path),
            "-c", "copy", "-movflags", "+faststart",
            str(remux_path),
        ],
        capture_output=True, timeout=300,
    )
    if remux_path.exists() and remux_path.stat().st_size > 0:
        remux_path.replace(output_path)
    else:
        logger.warning("Remux failed; keeping original concat output")

    return output_path


def render_chapter(
    scenes_json_path: Path,
    audio_dir: Path,
    output_video_path: Path,
    temp_dir: Optional[Path] = None,
) -> Path:
    """Render all scenes into a final chapter video.

    Args:
        scenes_json_path: Path to phase2_script_scenes_with_audio.json
        audio_dir: Directory containing generated audio files
        output_video_path: Final MP4 output path
        temp_dir: Temporary directory for intermediate files

    Returns:
        Path to the final video file
    """
    scenes = json.loads(scenes_json_path.read_text(encoding="utf-8"))
    logger.info("Rendering %d scenes into %s", len(scenes), output_video_path)

    temp_dir = temp_dir or Path(tempfile.mkdtemp(prefix="ink_render_"))
    temp_dir.mkdir(parents=True, exist_ok=True)

    output_video_path.parent.mkdir(parents=True, exist_ok=True)
    segments: List[Path] = []

    for idx, scene in enumerate(scenes):
        scene_id = scene.get("id", f"scene_{idx}")
        segment_path = temp_dir / f"{scene_id}_segment.mp4"

        # Collect audio files for this scene
        audio_files: List[Path] = []
        for vo in scene.get("voiceover_lines", []):
            ap = vo.get("audio_path")
            if ap:
                p = Path(ap)
                if p.exists():
                    audio_files.append(p)
                else:
                    # Try relative to audio_dir
                    candidate = audio_dir / p.name
                    if candidate.exists():
                        audio_files.append(candidate)

        if not audio_files:
            logger.warning("No audio for scene %s; creating silent placeholder", scene_id)
            # Create a silent audio segment
            silent = temp_dir / f"{scene_id}_silent.mp3"
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                 "-t", "3", str(silent)],
                capture_output=True, timeout=10,
            )
            audio_files = [silent]

        logger.info("Rendering scene %d/%d: %s (%d audio files)", idx + 1, len(scenes), scene_id, len(audio_files))
        create_scene_video_segment(scene, audio_files, segment_path, temp_dir)
        if segment_path.exists():
            segments.append(segment_path)

    if not segments:
        raise RuntimeError("No video segments were created")

    # Concatenate all segments
    logger.info("Concatenating %d segments...", len(segments))
    concat_videos(segments, output_video_path)
    logger.info("Final video: %s (%d bytes)", output_video_path, output_video_path.stat().st_size)

    return output_video_path
