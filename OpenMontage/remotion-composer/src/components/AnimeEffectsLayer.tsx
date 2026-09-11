import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type AnimeEffectType =
  | "speed-lines"
  | "particles-sparkles"
  | "particles-burst"
  | "particles-swirl"
  | "particles-stardust"
  | "reaction-pop"
  | "screen-shake";

export interface SpeedLineConfig {
  direction: "radial" | "horizontal" | "diagonal";
  lineCount: number;
  lengthPx: number;
  opacity: number;
  color: string;
}

export interface ParticleBurstConfig {
  count: number;
  color: string;
  sizeRange: [number, number];
  lifespanMs: number;
  gravity: number;
}

export interface ReactionPopConfig {
  emoji: string;
  scale: number;
  enterDurationMs: number;
  exitDurationMs: number;
  loop: boolean;
}

export interface AnimeEffectsLayerProps {
  type: "word" | "sentence" | "scene";
  effect: AnimeEffectType;
  frame: number;
  fps: number;
  durationInFrames: number;
  color?: string;
  speedLineConfig?: Partial<SpeedLineConfig>;
  particleConfig?: Partial<ParticleBurstConfig>;
  reactionConfig?: Partial<ReactionPopConfig>;
  bounds?: { x: number; y: number; width: number; height: number };
}

// ---------------------------------------------------------------------------
// Deterministic seeded random
// ---------------------------------------------------------------------------

function seededRandom(seed: number): number {
  const x = Math.sin(seed * 12.9898 + seed * 78.233) * 43758.5453;
  return x - Math.floor(x);
}

// ---------------------------------------------------------------------------
// Speed Lines
// ---------------------------------------------------------------------------

const SpeedLines: React.FC<{
  config: SpeedLineConfig;
  frame: number;
  fps: number;
  durationInFrames: number;
  bounds: { x: number; y: number; width: number; height: number };
}> = ({ config, frame, fps, durationInFrames, bounds }) => {
  const fadeIn = interpolate(frame, [0, Math.round(fps * 0.15)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(
    frame,
    [durationInFrames - Math.round(fps * 0.2), durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const progress = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const cx = bounds.x + bounds.width / 2;
  const cy = bounds.y + bounds.height / 2;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {Array.from({ length: config.lineCount }, (_, i) => {
        const angle = (i / config.lineCount) * 360 + progress * 15;
        const length = config.lengthPx * (0.6 + seededRandom(i * 7 + 1) * 0.4);
        const startR = 20 + seededRandom(i * 13 + 2) * 40;
        const lineOpacity = config.opacity * fadeIn * fadeOut;

        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: `calc(${cx}% + ${Math.cos((angle * Math.PI) / 180) * startR}px)`,
              top: `calc(${cy}% + ${Math.sin((angle * Math.PI) / 180) * startR}px)`,
              width: 2,
              height: length,
              backgroundColor: config.color,
              opacity: lineOpacity,
              transform: `rotate(${angle + 90}deg)`,
              transformOrigin: "top center",
              borderRadius: 1,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Particles: Sparkles (word-level)
// ---------------------------------------------------------------------------

const Sparkles: React.FC<{
  count: number;
  color: string;
  frame: number;
  fps: number;
  durationInFrames: number;
  bounds: { x: number; y: number; width: number; height: number };
}> = ({ count, color, frame, fps, durationInFrames, bounds }) => {
  const cx = bounds.x + bounds.width / 2;
  const cy = bounds.y + bounds.height / 2;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {Array.from({ length: count }, (_, i) => {
        const seed = i * 7 + 1;
        const angle = seededRandom(seed) * Math.PI * 2;
        const dist = 30 + seededRandom(seed + 1) * 60;
        const size = 3 + seededRandom(seed + 2) * 5;
        const speed = 0.5 + seededRandom(seed + 3) * 1.0;
        const delay = Math.round(seededRandom(seed + 4) * fps * 0.1);
        const t = (frame - delay) / fps;

        if (t < 0) return null;

        const x = cx + Math.cos(angle) * dist * Math.min(t * speed, 1);
        const y = cy + Math.sin(angle) * dist * Math.min(t * speed, 1) - t * 20;
        const alpha = Math.max(0, 1 - t / 0.6);
        const scale = Math.max(0.1, 1 - t / 0.6);

        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: `${x}%`,
              top: `${y}%`,
              width: size,
              height: size,
              backgroundColor: color,
              borderRadius: "50%",
              opacity: alpha * 0.9,
              transform: `scale(${scale})`,
              boxShadow: `0 0 ${size * 2}px ${color}`,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Particles: Burst (sentence-level)
// ---------------------------------------------------------------------------

const Burst: React.FC<{
  count: number;
  color: string;
  frame: number;
  fps: number;
  durationInFrames: number;
  bounds: { x: number; y: number; width: number; height: number };
}> = ({ count, color, frame, fps, durationInFrames, bounds }) => {
  const cx = bounds.x + bounds.width / 2;
  const cy = bounds.y + bounds.height / 2;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {Array.from({ length: count }, (_, i) => {
        const seed = i * 11 + 3;
        const angle = seededRandom(seed) * Math.PI * 2;
        const speed = 80 + seededRandom(seed + 1) * 120;
        const size = 2 + seededRandom(seed + 2) * 4;
        const t = frame / fps;

        const x = cx + Math.cos(angle) * speed * Math.min(t * 2, 1);
        const y = cy + Math.sin(angle) * speed * Math.min(t * 2, 1) + t * t * 40;
        const alpha = Math.max(0, 1 - t / 0.8);
        const scale = Math.max(0.1, 1 - t / 0.8);

        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: `${x}%`,
              top: `${y}%`,
              width: size,
              height: size,
              backgroundColor: color,
              borderRadius: "50%",
              opacity: alpha * 0.8,
              transform: `scale(${scale})`,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Particles: Swirl (scene-level transition)
// ---------------------------------------------------------------------------

const Swirl: React.FC<{
  count: number;
  color: string;
  frame: number;
  fps: number;
  durationInFrames: number;
}> = ({ count, color, frame, fps, durationInFrames }) => {
  const progress = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = Math.sin(progress * Math.PI) * 0.6;

  return (
    <AbsoluteFill style={{ pointerEvents: "none", opacity }}>
      {Array.from({ length: count }, (_, i) => {
        const seed = i * 17 + 5;
        const angle = progress * Math.PI * 4 + seededRandom(seed) * Math.PI * 2;
        const dist = 20 + progress * 40 + seededRandom(seed + 1) * 20;
        const x = 50 + Math.cos(angle) * dist;
        const y = 50 + Math.sin(angle) * dist;
        const size = 2 + seededRandom(seed + 2) * 3;

        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: `${x}%`,
              top: `${y}%`,
              width: size,
              height: size,
              backgroundColor: color,
              borderRadius: "50%",
              opacity: 0.7,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Particles: Stardust (character name)
// ---------------------------------------------------------------------------

const Stardust: React.FC<{
  count: number;
  color: string;
  frame: number;
  fps: number;
  durationInFrames: number;
  bounds: { x: number; y: number; width: number; height: number };
}> = ({ count, color, frame, fps, durationInFrames, bounds }) => {
  const cx = bounds.x + bounds.width / 2;
  const cy = bounds.y + bounds.height / 2;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {Array.from({ length: count }, (_, i) => {
        const seed = i * 13 + 7;
        const xOff = (seededRandom(seed) - 0.5) * bounds.width * 1.5;
        const speed = 0.3 + seededRandom(seed + 1) * 0.6;
        const t = (frame / fps) * speed;
        const x = cx + xOff;
        const y = cy - t * 30;
        const alpha = Math.max(0, 0.8 - t / 1.2);
        const twinkle = 0.5 + Math.sin(t * 5 + seed) * 0.5;
        const size = 2 + seededRandom(seed + 2) * 3;

        if (y < bounds.y - 10) return null;

        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: `${x}%`,
              top: `${y}%`,
              width: size,
              height: size,
              backgroundColor: color,
              borderRadius: "50%",
              opacity: alpha * twinkle,
              boxShadow: `0 0 ${size * 2}px ${color}`,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Reaction Pop (emoji / character)
// ---------------------------------------------------------------------------

const ReactionPop: React.FC<{
  config: ReactionPopConfig;
  frame: number;
  fps: number;
  durationInFrames: number;
}> = ({ config, frame, fps, durationInFrames }) => {
  const enterFrames = Math.round((config.enterDurationMs / 1000) * fps);
  const exitFrames = Math.round((config.exitDurationMs / 1000) * fps);
  const holdFrames = durationInFrames - enterFrames - exitFrames;

  let scale = 0;
  let opacity = 0;

  if (frame < enterFrames) {
    const p = frame / enterFrames;
    scale = p < 0.6 ? p / 0.6 : 1 + (1 - p) / 0.4 * 0.2;
    opacity = p;
  } else if (frame < enterFrames + holdFrames) {
    scale = config.loop
      ? 1 + Math.sin(((frame - enterFrames) / fps) * 3) * 0.05
      : 1;
    opacity = 1;
  } else {
    const p = (frame - enterFrames - holdFrames) / exitFrames;
    scale = 1 - p * 0.3;
    opacity = 1 - p;
  }

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        pointerEvents: "none",
      }}
    >
      <span
        style={{
          fontSize: 48 * config.scale,
          opacity,
          transform: `scale(${scale})`,
          display: "inline-block",
          filter: "drop-shadow(0 4px 8px rgba(0,0,0,0.3))",
        }}
      >
        {config.emoji}
      </span>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Screen Shake
// ---------------------------------------------------------------------------

export const ScreenShake: React.FC<{
  intensity: number;
  frame: number;
  fps: number;
  durationInFrames: number;
  children: React.ReactNode;
}> = ({ intensity, frame, fps, durationInFrames, children }) => {
  const decay = interpolate(frame, [0, durationInFrames], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const shakeX = (Math.sin(frame * 0.8) * 2 + Math.cos(frame * 1.3) * 2) * intensity * decay;
  const shakeY = (Math.cos(frame * 0.9) * 2 + Math.sin(frame * 1.1) * 2) * intensity * decay;

  return (
    <AbsoluteFill
      style={{
        transform: `translate(${shakeX}px, ${shakeY}px)`,
        willChange: "transform",
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Main dispatcher
// ---------------------------------------------------------------------------

export const AnimeEffectsLayer: React.FC<AnimeEffectsLayerProps> = ({
  type,
  effect,
  frame,
  fps,
  durationInFrames,
  color = "#FFD93D",
  speedLineConfig,
  particleConfig,
  reactionConfig,
  bounds = { x: 35, y: 30, width: 30, height: 20 },
}) => {
  const defaultSpeedLines: SpeedLineConfig = {
    direction: "radial",
    lineCount: 24,
    lengthPx: 120,
    opacity: 0.25,
    color: "#FFFFFF",
    ...speedLineConfig,
  };

  const defaultParticles: ParticleBurstConfig = {
    count: 10,
    color,
    sizeRange: [2, 6],
    lifespanMs: 600,
    gravity: 40,
    ...particleConfig,
  };

  const defaultReaction: ReactionPopConfig = {
    emoji: "✨",
    scale: 0.8,
    enterDurationMs: 200,
    exitDurationMs: 300,
    loop: type === "word",
    ...reactionConfig,
  };

  switch (effect) {
    case "speed-lines":
      return type === "word" || type === "sentence" ? (
        <SpeedLines
          config={defaultSpeedLines}
          frame={frame}
          fps={fps}
          durationInFrames={durationInFrames}
          bounds={bounds}
        />
      ) : null;

    case "particles-sparkles":
      return (
        <Sparkles
          count={defaultParticles.count}
          color={defaultParticles.color}
          frame={frame}
          fps={fps}
          durationInFrames={durationInFrames}
          bounds={bounds}
        />
      );

    case "particles-burst":
      return (
        <Burst
          count={defaultParticles.count}
          color={defaultParticles.color}
          frame={frame}
          fps={fps}
          durationInFrames={durationInFrames}
          bounds={bounds}
        />
      );

    case "particles-swirl":
      return (
        <Swirl
          count={defaultParticles.count}
          color={defaultParticles.color}
          frame={frame}
          fps={fps}
          durationInFrames={durationInFrames}
        />
      );

    case "particles-stardust":
      return (
        <Stardust
          count={defaultParticles.count}
          color={defaultParticles.color}
          frame={frame}
          fps={fps}
          durationInFrames={durationInFrames}
          bounds={bounds}
        />
      );

    case "reaction-pop":
      return (
        <ReactionPop
          config={defaultReaction}
          frame={frame}
          fps={fps}
          durationInFrames={durationInFrames}
        />
      );

    default:
      return null;
  }
};
