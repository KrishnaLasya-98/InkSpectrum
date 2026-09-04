import { Composition, Sequence, Audio, staticFile, Img, Video, useCurrentFrame, interpolate } from "remotion";
import React from "react";
import manifest from "./manifest.json";

export const Root = () => {
  let totalFrames = 300;
  try {
    let totalSec = 0;
    for (const scene of manifest) {
      for (const line of scene.audio_lines) {
        totalSec += (line.duration_seconds || 3.0) + (line.pause_after || 0.5);
      }
    }
    totalFrames = Math.max(300, Math.ceil(totalSec * 30));
  } catch (e) {
    console.error("Error calculating duration:", e);
  }

  return (
    <Composition
      id="FullChapterLecture"
      component={ChapterLecture}
      durationInFrames={totalFrames}
      fps={30}
      width={1920}
      height={1080}
    />
  );
};

const detectSceneType = (scene) => {
  const title = (scene.title || "").toLowerCase();
  const sceneId = (scene.scene_id || "").toLowerCase();

  if (title.includes("welcome") || sceneId.includes("intro")) return "INTRO";
  if (title.includes("true") || title.includes("false")) return "TRUE_FALSE";
  if (title.includes("answer") && (title.includes("reveal") || title.includes("a") || title.includes("b") || title.includes("c"))) return "ANSWER";
  if (title.includes("question") || title.includes("mcq") || title.includes("greeting")) return "QUESTION";
  if (title.includes("comprehending") || title.includes("discuss") || title.includes("work")) return "EXERCISE";
  if (title.includes("worked step")) return "WORKED_STEP";
  if (title.includes("story") || title.includes("beach") || title.includes("lesson")) return "STORY";
  return "GENERIC";
};

const ChapterLecture = () => {
  let accumulatedFrames = 0;

  return (
    <div style={{ flex: 1, backgroundColor: "#0f172a", color: "white", fontFamily: "sans-serif", position: "relative" }}>
      {manifest.map((scene, sIdx) => {
        let sceneSec = 0;
        for (const line of scene.audio_lines) {
          sceneSec += (line.duration_seconds || 3.0) + (line.pause_after || 0.5);
        }
        if (sceneSec === 0) sceneSec = 5.0;
        const sceneFrames = Math.ceil(sceneSec * 30);
        const fromFrame = accumulatedFrames;
        accumulatedFrames += sceneFrames;

        return (
          <Sequence key={scene.scene_id || sIdx} from={fromFrame} durationInFrames={sceneFrames}>
            <SceneView scene={scene} sceneType={detectSceneType(scene)} />
          </Sequence>
        );
      })}
    </div>
  );
};

const SceneView = ({ scene, sceneType }) => {
  // Resolve background asset path -> use static file in public/
  const bgAsset = scene.background_asset || "";
  const bgFilename = bgAsset ? bgAsset.split("\\").pop().split("/").pop() : null;
  const isVideo = bgFilename && bgFilename.endsWith(".mp4");
  const bgStaticPath = bgFilename ? staticFile(`visuals/${bgFilename}`) : null;

  // Choose layout based on scene type
  const layout = getLayoutForType(sceneType);

  return (
    <div style={{ flex: 1, width: "100%", height: "100%", position: "relative", overflow: "hidden", backgroundColor: layout.bgColor }}>
      {/* Layer 1: Background image or video */}
      {bgStaticPath && !isVideo && (
        <Img
          src={bgStaticPath}
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            objectFit: "cover",
            opacity: layout.bgOpacity,
            filter: layout.bgFilter,
          }}
        />
      )}
      {bgStaticPath && isVideo && (
        <Video
          src={bgStaticPath}
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            objectFit: "cover",
            opacity: layout.bgOpacity,
          }}
          muted
        />
      )}

      {/* Layer 2: Gradient overlay for text readability */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          background: layout.overlay,
        }}
      />

      {/* Layer 3: Header */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          padding: "40px 60px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          zIndex: 10,
        }}
      >
        <h2 style={{ fontSize: "32px", color: "#38bdf8", margin: 0, textShadow: "0 2px 8px rgba(0,0,0,0.8)" }}>
          Grade 1 English • Lesson 1
        </h2>
        <span
          style={{
            fontSize: "24px",
            color: "#94a3b8",
            backgroundColor: "rgba(15, 23, 42, 0.85)",
            padding: "8px 20px",
            borderRadius: "12px",
            border: "1px solid #475569",
            backdropFilter: "blur(8px)",
          }}
        >
          {sceneType === "INTRO" ? "🌊 Introduction" :
           sceneType === "STORY" ? "📖 Story" :
           sceneType === "QUESTION" ? "❓ Question" :
           sceneType === "ANSWER" ? "✅ Answer" :
           sceneType === "TRUE_FALSE" ? "✔️ True / False" :
           sceneType === "WORKED_STEP" ? "🪜 Step" :
           sceneType === "EXERCISE" ? "📝 Exercise" : "🎬 Scene"}
        </span>
      </div>

      {/* Layer 4: Main content area (steps) */}
      <div
        style={{
          position: "absolute",
          top: "120px",
          left: layout.contentArea.left,
          right: layout.contentArea.right,
          bottom: layout.contentArea.bottom,
          display: "flex",
          flexDirection: "column",
          justifyContent: layout.contentArea.justify || "center",
          alignItems: layout.contentArea.align || "center",
          gap: "16px",
          padding: "20px",
          zIndex: 5,
        }}
      >
        {scene.scene_steps && scene.scene_steps.slice(0, 6).map((step, idx) => (
          <div
            key={idx}
            style={{
              fontSize: step.size === "xl" ? "64px" : step.size === "lg" ? "48px" : "36px",
              fontWeight: "bold",
              textAlign: "center",
              color: layout.textColor,
              textShadow: "0 4px 12px rgba(0,0,0,0.9)",
              maxWidth: "90%",
              lineHeight: 1.3,
            }}
          >
            {step.text || step.latex || ""}
          </div>
        ))}
      </div>

      {/* Layer 5: Audio + Subtitle overlay */}
      <AudioAndSubtitles scene={scene} layout={layout} />
    </div>
  );
};

const getLayoutForType = (type) => {
  switch (type) {
    case "INTRO":
      return {
        bgColor: "#0c4a6e",
        bgOpacity: 1.0,
        bgFilter: "brightness(0.9)",
        overlay: "linear-gradient(135deg, rgba(15, 23, 42, 0.4) 0%, rgba(12, 74, 110, 0.6) 100%)",
        textColor: "#fef3c7",
        subtitleBg: "rgba(15, 23, 42, 0.92)",
        subtitleColor: "#fef3c7",
        contentArea: { left: "60px", right: "60px", bottom: "200px", justify: "center", align: "center" },
      };
    case "STORY":
      return {
        bgColor: "#0c4a6e",
        bgOpacity: 0.9,
        bgFilter: "brightness(0.85) saturate(1.1)",
        overlay: "linear-gradient(to right, rgba(0,0,0,0.5) 0%, rgba(0,0,0,0.2) 100%)",
        textColor: "#ffffff",
        subtitleBg: "rgba(15, 23, 42, 0.95)",
        subtitleColor: "#ffffff",
        contentArea: { left: "60px", right: "60px", bottom: "180px", justify: "center", align: "flex-start" },
      };
    case "QUESTION":
      return {
        bgColor: "#1e293b",
        bgOpacity: 0.7,
        bgFilter: "blur(2px) brightness(0.7)",
        overlay: "linear-gradient(135deg, rgba(30, 41, 59, 0.85) 0%, rgba(15, 23, 42, 0.7) 100%)",
        textColor: "#fde68a",
        subtitleBg: "rgba(251, 191, 36, 0.95)",
        subtitleColor: "#1e293b",
        contentArea: { left: "100px", right: "100px", bottom: "200px", justify: "center", align: "center" },
      };
    case "ANSWER":
      return {
        bgColor: "#14532d",
        bgOpacity: 0.6,
        bgFilter: "brightness(0.75) saturate(1.2)",
        overlay: "linear-gradient(135deg, rgba(20, 83, 45, 0.7) 0%, rgba(15, 23, 42, 0.6) 100%)",
        textColor: "#bbf7d0",
        subtitleBg: "rgba(20, 83, 45, 0.95)",
        subtitleColor: "#bbf7d0",
        contentArea: { left: "100px", right: "100px", bottom: "200px", justify: "center", align: "center" },
      };
    case "TRUE_FALSE":
      return {
        bgColor: "#1e293b",
        bgOpacity: 0.65,
        bgFilter: "blur(1px) brightness(0.7)",
        overlay: "linear-gradient(135deg, rgba(30, 41, 59, 0.85) 0%, rgba(15, 23, 42, 0.7) 100%)",
        textColor: "#fca5a5",
        subtitleBg: "rgba(220, 38, 38, 0.95)",
        subtitleColor: "#ffffff",
        contentArea: { left: "100px", right: "100px", bottom: "200px", justify: "center", align: "center" },
      };
    case "WORKED_STEP":
      return {
        bgColor: "#1e293b",
        bgOpacity: 0.5,
        bgFilter: "brightness(0.6) saturate(1.1)",
        overlay: "linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.65) 100%)",
        textColor: "#fde68a",
        subtitleBg: "rgba(15, 23, 42, 0.95)",
        subtitleColor: "#fde68a",
        contentArea: { left: "80px", right: "80px", bottom: "200px", justify: "center", align: "center" },
      };
    case "EXERCISE":
      return {
        bgColor: "#1e293b",
        bgOpacity: 0.6,
        bgFilter: "blur(2px) brightness(0.7)",
        overlay: "linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.7) 100%)",
        textColor: "#e0e7ff",
        subtitleBg: "rgba(15, 23, 42, 0.95)",
        subtitleColor: "#e0e7ff",
        contentArea: { left: "100px", right: "100px", bottom: "200px", justify: "center", align: "center" },
      };
    default:
      return {
        bgColor: "#0f172a",
        bgOpacity: 0.8,
        bgFilter: "brightness(0.8)",
        overlay: "linear-gradient(135deg, rgba(15, 23, 42, 0.7) 0%, rgba(15, 23, 42, 0.5) 100%)",
        textColor: "#ffffff",
        subtitleBg: "rgba(15, 23, 42, 0.95)",
        subtitleColor: "#ffffff",
        contentArea: { left: "60px", right: "60px", bottom: "200px", justify: "center", align: "center" },
      };
  }
};

const AudioAndSubtitles = ({ scene, layout }) => {
  let lineAccumulatedFrames = 0;
  const frame = useCurrentFrame();

  return (
    <>
      {scene.audio_lines && scene.audio_lines.map((line, lIdx) => {
        const lineFrames = Math.ceil(((line.duration_seconds || 3.0) + (line.pause_after || 0.5)) * 30);
        const start = lineAccumulatedFrames;
        lineAccumulatedFrames += lineFrames;

        const filename = line.audio_file ? line.audio_file.split("\\").pop().split("/").pop() : null;
        const audioSrc = filename ? staticFile(`audio/${filename}`) : null;

        // Calculate progress within this line
        const relativeFrame = frame - start;
        const opacity = interpolate(relativeFrame, [0, 10, lineFrames - 20, lineFrames], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

        return (
          <Sequence key={lIdx} from={start} durationInFrames={lineFrames}>
            {audioSrc && <Audio src={audioSrc} />}
            <div
              style={{
                position: "absolute",
                bottom: "50px",
                left: "100px",
                right: "100px",
                textAlign: "center",
                backgroundColor: layout.subtitleBg,
                color: layout.subtitleColor,
                padding: "28px 36px",
                borderRadius: "20px",
                fontSize: "32px",
                fontWeight: "500",
                lineHeight: 1.4,
                boxShadow: "0 10px 40px rgba(0,0,0,0.5)",
                border: "2px solid rgba(255,255,255,0.15)",
                zIndex: 20,
                opacity: opacity,
              }}
            >
              {line.text}
            </div>
          </Sequence>
        );
      })}
    </>
  );
};
