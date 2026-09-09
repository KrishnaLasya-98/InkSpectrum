import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  Audio,
  staticFile,
  Sequence,
} from "remotion";

interface SceneProps {
  scene: {
    id: string;
    title: string;
    voiceover_lines: Array<{
      text: string;
      duration_seconds: number;
      pause_after: number;
    }>;
    scene_steps: Array<{
      type: string;
      text: string;
      at: number;
      duration?: number;
    }>;
    duration_seconds: number;
    storyboard?: Array<{
      time: number;
      duration: number;
      visual: string;
      on_screen_text: string;
      camera_motion: string;
      animation_type: string;
      transition_in: string;
      transition_out: string;
      asset_requirements: string[];
    }>;
  };
  audioPath?: string;
  assets?: Record<string, string>;
}

export const SceneComposition: React.FC<SceneProps> = ({
  scene,
  audioPath,
  assets = {},
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTime = frame / fps;

  // Get current storyboard shot
  const storyboard = scene.storyboard || [];
  const currentShot = storyboard.find(
    (shot) =>
      currentTime >= shot.time &&
      currentTime < shot.time + shot.duration
  );

  // Calculate opacity for transitions
  const getTransitionOpacity = (shot: any): number => {
    if (!shot) return 1;
    const fadeInDuration = 0.5; // 0.5 seconds
    const fadeOutDuration = 0.5;
    const shotStart = shot.time;
    const shotEnd = shot.time + shot.duration;

    let opacity = 1;
    if (currentTime - shotStart < fadeInDuration) {
      opacity = (currentTime - shotStart) / fadeInDuration;
    } else if (shotEnd - currentTime < fadeOutDuration) {
      opacity = (shotEnd - currentTime) / fadeOutDuration;
    }
    return Math.max(0, Math.min(1, opacity));
  };

  // Render based on storyboard or fallback to scene_steps
  const renderContent = () => {
    if (currentShot) {
      return (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "center",
            padding: 40,
            opacity: getTransitionOpacity(currentShot),
          }}
        >
          {/* Background */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              backgroundColor: "#1a1a2e",
            }}
          />

          {/* Title */}
          <h1
            style={{
              color: "#ffffff",
              fontSize: 64,
              fontWeight: "bold",
              textAlign: "center",
              marginBottom: 20,
              zIndex: 1,
            }}
          >
            {scene.title}
          </h1>

          {/* On-screen text from storyboard */}
          {currentShot.on_screen_text && (
            <p
              style={{
                color: "#dddddd",
                fontSize: 32,
                textAlign: "center",
                maxWidth: 1000,
                lineHeight: 1.4,
                zIndex: 1,
              }}
            >
              {currentShot.on_screen_text}
            </p>
          )}

          {/* Animation indicator */}
          <div
            style={{
              position: "absolute",
              bottom: 40,
              left: 40,
              color: "#888888",
              fontSize: 16,
            }}
          >
            {currentShot.animation_type} | {currentShot.camera_motion}
          </div>
        </div>
      );
    }

    // Fallback: render scene_steps
    const activeStep = scene.scene_steps.find((step) => {
      const stepStart = step.at;
      const stepEnd = stepStart + (step.duration || 3);
      return currentTime >= stepStart && currentTime < stepEnd;
    });

    if (!activeStep) {
      return (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            backgroundColor: "#1a1a2e",
          }}
        >
          <p style={{ color: "#ffffff", fontSize: 48 }}>{scene.title}</p>
        </div>
      );
    }

    return (
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          padding: 40,
        }}
      >
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundColor: "#1a1a2e",
          }}
        />

        {activeStep.text && (
          <p
            style={{
              color: "#ffffff",
              fontSize: 36,
              textAlign: "center",
              maxWidth: 1000,
              lineHeight: 1.4,
              zIndex: 1,
            }}
          >
            {activeStep.text}
          </p>
        )}
      </div>
    );
  };

  return (
    <AbsoluteFill>
      {renderContent()}
      {audioPath && <Audio src={audioPath} />}
    </AbsoluteFill>
  );
};
