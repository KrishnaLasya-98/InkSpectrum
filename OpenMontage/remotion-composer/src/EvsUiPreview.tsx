import React from "react";
import {
  AbsoluteFill,
  Audio,
  OffthreadVideo,
  Sequence,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const PROJECT_ASSET_BASE = "http://localhost:18940/";

const clips = [
  "assets/video/scenes/s01/s01-0.mp4",
  "assets/video/scenes/s01/s01-1.mp4",
  "assets/video/scenes/s01/s01-2.mp4",
];

const asset = (path: string) => `${PROJECT_ASSET_BASE}${path}`;

const Panel: React.FC<{
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({ children, style }) => (
  <div
    style={{
      backgroundColor: "rgba(255, 253, 240, 0.94)",
      borderRadius: 28,
      boxShadow: "0 14px 36px rgba(40, 58, 72, 0.18)",
      color: "#174B59",
      fontFamily: "Arial, sans-serif",
      ...style,
    }}
  >
    {children}
  </div>
);

const Reveal: React.FC<{
  from: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({ from, children, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const progress = spring({
    frame: Math.max(0, frame - from),
    fps,
    config: { damping: 18, stiffness: 120, mass: 0.8 },
  });
  return (
    <div
      style={{
        opacity: interpolate(progress, [0, 1], [0, 1]),
        transform: `translateY(${interpolate(progress, [0, 1], [22, 0])}px) scale(${interpolate(progress, [0, 1], [0.96, 1])})`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

export const EvsUiPreview: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const titleOpacity = interpolate(frame, [0, 18], [0, 1], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ backgroundColor: "#FFF8E8", overflow: "hidden" }}>
      <Audio src={asset("renders/audio/s01.norm.wav")} volume={0.95} />

      <AbsoluteFill style={{ backgroundColor: "#FFF8E8" }}>
        <div
          style={{
            position: "absolute",
            inset: 0,
            background:
              "radial-gradient(circle at 8% 8%, rgba(245,200,75,.72), transparent 28%), radial-gradient(circle at 94% 10%, rgba(247,199,184,.68), transparent 24%)",
          }}
        />
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: 330,
            height: 180,
            backgroundColor: "rgba(245, 200, 75, .52)",
            borderBottomRightRadius: 180,
          }}
        />
      </AbsoluteFill>

      {clips.map((clip, index) => (
        <Sequence key={clip} from={index * 10 * fps} durationInFrames={10 * fps}>
          <OffthreadVideo
            src={asset(clip)}
            muted
            style={{
              position: "absolute",
              inset: 0,
              width: "100%",
              height: "100%",
              objectFit: "cover",
              filter: "saturate(.9) brightness(.86)",
            }}
          />
        </Sequence>
      ))}

      <AbsoluteFill style={{ backgroundColor: "rgba(255, 248, 232, .12)" }} />

      <Reveal from={0} style={{ position: "absolute", top: 64, left: 100 }}>
        <div
          style={{
            color: "#C9473F",
            fontFamily: "Arial, sans-serif",
            fontSize: 56,
            fontWeight: 800,
            letterSpacing: 1,
            opacity: titleOpacity,
          }}
        >
          ANIMAL LIFE
        </div>
      </Reveal>

      <Reveal from={12} style={{ position: "absolute", left: 92, bottom: 108 }}>
        <Panel style={{ width: 980, padding: "28px 36px 30px" }}>
          <div style={{ fontSize: 34, fontWeight: 700, lineHeight: 1.25 }}>
            Hello students! Today we will learn all about animals.
          </div>
          <div style={{ color: "#C9473F", fontSize: 25, fontWeight: 700, marginTop: 14 }}>
            Do you have a pet animal?
          </div>
        </Panel>
      </Reveal>

      <Reveal from={18} style={{ position: "absolute", right: 96, top: 236 }}>
        <Panel style={{ width: 540, padding: "26px 30px 30px" }}>
          <div
            style={{
              display: "inline-block",
              backgroundColor: "#1EA6A8",
              borderRadius: 24,
              color: "white",
              fontSize: 24,
              fontWeight: 800,
              padding: "9px 20px",
              marginBottom: 18,
            }}
          >
            LESSON HIGHLIGHTS
          </div>
          {["Animals around us", "Land Animals", "Water Animals", "Birds", "Insects", "Animal Homes"].map(
            (item, index) => (
              <div
                key={item}
                style={{
                  color: index % 2 === 0 ? "#174B59" : "#3C6570",
                  fontSize: 27,
                  fontWeight: 700,
                  lineHeight: 1.35,
                }}
              >
                <span style={{ color: "#C9473F", marginRight: 10 }}>•</span>
                {item}
              </div>
            ),
          )}
        </Panel>
      </Reveal>

      <div
        style={{
          position: "absolute",
          right: 42,
          bottom: 28,
          color: "rgba(23, 75, 89, .82)",
          fontFamily: "Arial, sans-serif",
          fontSize: 22,
          fontWeight: 700,
        }}
      >
        Explore • Learn • Protect
      </div>
    </AbsoluteFill>
  );
};
