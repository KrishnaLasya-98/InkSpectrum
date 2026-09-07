"""Platform-specific render profiles."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MediaProfile:
    name: str
    width: int
    height: int
    fps: int
    aspect: str
    notes: str = ""


PROFILES: dict[str, MediaProfile] = {
    "youtube_landscape": MediaProfile(1920, 1080, 30, "16:9", "Standard YouTube"),
    "youtube_4k": MediaProfile(3840, 2160, 30, "16:9", "4K YouTube"),
    "youtube_shorts": MediaProfile(1080, 1920, 30, "9:16", "YouTube Shorts"),
    "tiktok": MediaProfile(1080, 1920, 30, "9:16", "TikTok"),
    "classroom_720p": MediaProfile(1280, 720, 24, "16:9", "Classroom projection"),
    "classroom_1080p": MediaProfile(1920, 1080, 24, "16:9", "Classroom HD"),
}


def get_profile(name: str) -> MediaProfile:
    if name not in PROFILES:
        raise KeyError(f"Unknown media profile: {name}. Known: {list(PROFILES)}")
    return PROFILES[name]
