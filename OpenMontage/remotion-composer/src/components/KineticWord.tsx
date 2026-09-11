import React, { useEffect, useRef } from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { AnimeEffectsLayer, type AnimeEffectType } from "./AnimeEffectsLayer";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type SentenceRole =
  | "statement"
  | "question"
  | "definition"
  | "example"
  | "character_name"
  | "emphasis";

export type WordState = "waiting" | "entering" | "speaking" | "exiting" | "exited";

export interface WordAlignment {
  word: string;
  start: number;
  end: number;
  index: number;
  isPlosive: boolean;
  isEmphasis: boolean;
  amplitude: number;
  pauseAfterMs: number;
}

export interface WordLayout {
  xPercent: number;
  yPercent: number;
  widthPercent: number;
  lineIndex: number;
  wordIndexInLine: number;
}

export interface WordAnimationConfig {
  enterDurationMs: number;
  exitDurationMs: number;
  highlightDurationMs: number;
  staggerDelayMs: number;
  amplitudeScaleRange: [number, number];
  consonantPopScale: number;
  consonantPopDurationMs: number;
  floatingDurationMs: number;
  breathingDurationMs: number;
  breathingScaleRange: [number, number];
  speedLineTrigger: AnimeEffectType;
  particleTrigger: AnimeEffectType;
  reactionTrigger: AnimeEffectType;
}

export interface KineticWordProps {
  word: WordAlignment;
  layout: WordLayout;
  frame: number;
  fps: number;
  amplitude: number;
  isActive: boolean;
  isHighlighted: boolean;
  sentenceRole: SentenceRole;
  animConfig: WordAnimationConfig;
  showEffects: boolean;
  onEnter?: (word: WordAlignment) => void;
  onSpeak?: (word: WordAlignment) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function classifySentenceRole(sentence: string): SentenceRole {
  const trimmed = sentence.trim();
  if (/^[\p{Emoji_Presentation}\p{Extended_Pictographic}]/u.test(trimmed)) return "character_name";
  if (trimmed.endsWith("?")) return "question";
  if (/^(Definition|Define|What is|A \w+ is)/i.test(trimmed)) return "definition";
  if (/^(For example|Example|e\.g\.|Like)/i.test(trimmed)) return "example";
  if (/^(Important|Key|Note|Remember|Watch)/i.test(trimmed)) return "emphasis";
  return "statement";
}

function detectPlosives(word: string): boolean {
  return /[ptkbdg]/i.test(word);
}

// ---------------------------------------------------------------------------
// State calculation
// ---------------------------------------------------------------------------

function getWordState(
  frame: number,
  word: WordAlignment,
  fps: number,
  enterDurationMs: number,
  exitDurationMs: number
): WordState {
  const enterStart = Math.round(word.start * fps);
  const enterEnd = enterStart + Math.round((enterDurationMs / 1000) * fps);
  const speakEnd = enterEnd + Math.round((100 / 1000) * fps);
  const exitEnd = Math.round(word.end * fps) + Math.round((exitDurationMs / 1000) * fps);

  if (frame < enterStart) return "waiting";
  if (frame < enterEnd) return "entering";
  if (frame < speakEnd) return "speaking";
  if (frame < exitEnd) return "exiting";
  return "exited";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const KineticWord: React.FC<KineticWordProps> = ({
  word,
  layout,
  frame,
  fps,
  amplitude,
  isActive,
  isHighlighted,
  sentenceRole,
  animConfig,
  showEffects,
  onEnter,
  onSpeak,
}) => {
  const state = getWordState(
    frame,
    word,
    fps,
    animConfig.enterDurationMs,
    animConfig.exitDurationMs
  );

  const enterStartFrame = Math.round(word.start * fps);
  const enterFrames = Math.round((animConfig.enterDurationMs / 1000) * fps);
  const speakFrames = Math.round((animConfig.highlightDurationMs / 1000) * fps);

  // Notify on enter start (once)
  useEffect(() => {
    if (frame === enterStartFrame && onEnter) onEnter(word);
  }, [frame, enterStartFrame, word, onEnter]);

  const hasSpoken = useRef(false);

  useEffect(() => {
    if (isActive && !hasSpoken.current && onSpeak) {
      hasSpoken.current = true;
      onSpeak(word);
    }
    if (!isActive) {
      hasSpoken.current = false;
    }
  }, [isActive, word, onSpeak]);

  // ---------- Animation values ----------

  const springEnter = spring({
    frame: frame - enterStartFrame,
    fps,
    config: { damping: 14, stiffness: 180 },
  });

  // Opacity
  const opacity =
    state === "waiting" || state === "exited"
      ? 0
      : state === "entering"
        ? springEnter
        : state === "exiting"
          ? interpolate(frame, [
              Math.round(word.end * fps),
              Math.round(word.end * fps) + Math.round((animConfig.exitDurationMs / 1000) * fps),
            ], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
          : 1;

  // Scale: base scale + amplitude + consonant pop
  let scale = 1;
  if (state === "entering") {
    scale = springEnter < 0.5 ? 0.8 + springEnter * 0.4 : 1 + (springEnter - 0.5) * 0.1;
  } else if (state === "speaking" || state === "exiting") {
    const ampBoost = amplitude * (animConfig.amplitudeScaleRange[1] - animConfig.amplitudeScaleRange[0]);
    scale = 1 + ampBoost;
    if (word.isPlosive && frame < Math.round(word.start * fps) + Math.round((animConfig.consonantPopDurationMs / 1000) * fps)) {
      scale += animConfig.consonantPopScale;
    }
  }

  // TranslateY
  const translateY =
    state === "entering"
      ? interpolate(springEnter, [0, 1], [20, 0])
      : state === "exiting"
        ? interpolate(frame, [
            Math.round(word.end * fps),
            Math.round(word.end * fps) + Math.round((animConfig.exitDurationMs / 1000) * fps),
          ], [0, -10], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
        : 0;

  // Breathing idle animation (only when speaking and held)
  const breathingProgress = (frame / fps) / (animConfig.breathingDurationMs / 1000);
  const breathingScale =
    state === "speaking" || state === "exiting"
      ? 1 + Math.sin(breathingProgress * Math.PI * 2) * (animConfig.breathingScaleRange[1] - 1)
      : 0;

  // Color
  let color = "#F5F0E8";
  let glow = "none";
  if (isActive || isHighlighted) {
    color = "#FFD93D";
    glow = "0 0 20px rgba(255, 217, 61, 0.6), 0 2px 8px rgba(0,0,0,0.4)";
  }

  // Special role styling
  if (sentenceRole === "question") color = "#A78BFA";
  if (sentenceRole === "definition") color = "#4ECDC4";
  if (sentenceRole === "character_name") color = "#FF6B9D";
  if (sentenceRole === "emphasis") color = "#FF8C42";

  const finalScale = scale + breathingScale;

  // Effect bounds (relative to word position)
  const bounds = {
    x: layout.xPercent,
    y: layout.yPercent,
    width: layout.widthPercent,
    height: 12,
  };

  // Determine which effect to show
  let effect: AnimeEffectType | null = null;
  if (showEffects) {
    if (sentenceRole === "emphasis" && isActive) effect = animConfig.speedLineTrigger;
    else if (word.isEmphasis && isActive) effect = animConfig.speedLineTrigger;
    else if (sentenceRole === "character_name" && state === "entering") effect = animConfig.particleTrigger;
    else if (sentenceRole === "definition" && state === "speaking") effect = "particles-burst";
    else if (word.isEmphasis && isHighlighted) effect = animConfig.reactionTrigger;
  }

  return (
    <AbsoluteFill
      style={{
        left: `${layout.xPercent}%`,
        top: `${layout.yPercent}%`,
        width: `${layout.widthPercent}%`,
        justifyContent: "flex-start",
        alignItems: "flex-start",
      }}
    >
      <span
        style={{
          fontSize: word.isEmphasis ? 52 : 40,
          fontWeight: word.isEmphasis ? 700 : 500,
          fontFamily: "'Noto Sans', 'Space Grotesk', system-ui, sans-serif",
          lineHeight: 1.3,
          opacity,
          transform: `scale(${finalScale}) translateY(${translateY}px)`,
          color,
          textShadow: glow,
          whiteSpace: "nowrap",
          willChange: "transform, opacity",
          display: "inline-block",
          position: "relative",
        }}
      >
        {word.word}
        {effect && (
          <AnimeEffectsLayer
            type="word"
            effect={effect}
            frame={frame}
            fps={fps}
            durationInFrames={Math.round(fps * 0.6)}
            bounds={bounds}
            color={color}
          />
        )}
      </span>
    </AbsoluteFill>
  );
};
