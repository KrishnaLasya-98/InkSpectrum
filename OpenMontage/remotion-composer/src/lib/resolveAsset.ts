import { staticFile } from "remotion";

const ASSET_SERVER_BASE = "http://localhost:18940/";

const VIDEO_AUDIO_EXTENSIONS = [".mp4", ".webm", ".ogg", ".wav", ".mp3", ".m4a"];

const isVideoAudio = (src: string): boolean =>
  VIDEO_AUDIO_EXTENSIONS.some((ext) => src.toLowerCase().endsWith(ext));

const isRemoteAsset = (src: string): boolean =>
  src.startsWith("http://") ||
  src.startsWith("https://") ||
  src.startsWith("data:");

const isWindowsAbsolutePath = (src: string): boolean =>
  /^[A-Za-z]:[\\/]/.test(src);

export function resolveAsset(src: string): string {
  if (isRemoteAsset(src)) {
    return src;
  }

  const withoutScheme = src.replace(/^file:\/\//i, "");
  const clean = /^\/[A-Za-z]:[\\/]/.test(withoutScheme)
    ? withoutScheme.slice(1)
    : withoutScheme;

  if (isVideoAudio(clean)) {
    const posix = clean.replace(/\\/g, "/").replace(/^[.\/]+/, "");
    return `${ASSET_SERVER_BASE}${posix}`;
  }

  if (clean.startsWith("/") || isWindowsAbsolutePath(clean)) {
    const posix = clean.replace(/\\/g, "/");
    return posix.startsWith("/") ? `file://${posix}` : `file:///${posix}`;
  }

  return staticFile(clean);
}
