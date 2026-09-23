import React from "react";
import {
  AbsoluteFill,
  OffthreadVideo,
  Sequence,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { TransitionSeries, springTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { AnimeEffectsLayer } from "./components/AnimeEffectsLayer";
import { AnimeScene, type CameraMotion } from "./components/AnimeScene";
import { EduQAScene } from "./EduQAScene";
import { KineticTypography, type TranscriptData } from "./components/KineticTypography";
import { resolveTheme, type ThemeConfig } from "./Root";
import { resolveAsset } from "./lib/resolveAsset";

export interface SceneData {
  id: string;
  type: string;
  description: string;
  start_seconds: number;
  end_seconds: number;
  start_frame: number;
  duration_frames: number;
  loop_required?: boolean;
  particle_effect?: string;
  lighting_from?: string;
  lighting_to?: string;
  camera_motion?: CameraMotion;
  narration_url?: string;
  word_alignment_data?: any;
  video_clip?: string;
  assessment_type?: string;
  glossary_terms?: Array<{ term: string; definition: string; start: number; end: number }>;
  activity_prompts?: string[];
}

export interface ScenePlanData {
  version: string;
  style_playbook?: string;
  scenes: SceneData[];
  total_frames?: number;
  fps?: number;
  resolution?: { width: number; height: number };
}

export interface EduVideoTopicCompositionProps {
  scenePlan: ScenePlanData;
  theme: ThemeConfig;
}

const FONT = "'Nunito', system-ui, sans-serif";

function topicKey(scene: SceneData): string {
  return scene.id.replace(/\d+.*$/, "") || scene.type;
}

function loadTranscript(input?: any): TranscriptData {
  if (!input) {
    return { word_timestamps: [], sentences: [], audio_metadata: { duration_seconds: 0, rms_amplitude: [] } };
  }
  if (typeof input === "object" && Array.isArray((input as any).word_timestamps)) {
    return input as TranscriptData;
  }
  return { word_timestamps: [], sentences: [], audio_metadata: { duration_seconds: 0, rms_amplitude: [] } };
}

const CameraMotion: React.FC<{ motion: CameraMotion; children: React.ReactNode }> = ({
  motion,
  children,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const p = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  let s = 1,
    x = 0,
    y = 0;
  switch (motion) {
    case "zoom-in":
      s = 1 + p * 0.15;
      break;
    case "zoom-out":
      s = 1.15 - p * 0.15;
      break;
    case "pan-left":
      x = interpolate(p, [0, 1], [35, -35]);
      s = 1.12;
      break;
    case "pan-right":
      x = interpolate(p, [0, 1], [-35, 35]);
      s = 1.12;
      break;
    case "ken-burns":
      s = 1 + p * 0.18;
      x = interpolate(p, [0, 1], [0, -22]);
      y = interpolate(p, [0, 1], [0, -14]);
      break;
    case "drift-up":
      y = interpolate(p, [0, 1], [22, -22]);
      s = 1.1;
      break;
    case "drift-down":
      y = interpolate(p, [0, 1], [-22, 22]);
      s = 1.1;
      break;
    case "parallax":
      y = interpolate(p, [0, 1], [14, -14]);
      x = interpolate(p, [0, 1], [6, -6]);
      s = 1.12;
      break;
    default:
      s = 1.02;
      break;
  }
  return (
    <AbsoluteFill style={{ transform: `scale(${s}) translate(${x}px, ${y}px)` }}>
      {children}
    </AbsoluteFill>
  );
};

const SceneLayer: React.FC<{ scene: SceneData; theme: ThemeConfig }> = ({
  scene,
  theme,
}) => {
  const { fps, durationInFrames } = useVideoConfig();
  const frame = useCurrentFrame();

  const isReview = /^s12/.test(scene.id);
  const isGlossary = /^s13/.test(scene.id);
  const isAssessment = /^s1[45]/.test(scene.id);
  const isActivity = /^s16/.test(scene.id);

  if (isAssessment || isActivity || isReview) {
    const cards = isAssessment || isReview
      ? [
          {
            card_id: `${scene.id}_q`,
            format: (scene.assessment_type || (isReview ? "fill_blank" : "mcq")) as any,
            question: scene.description || "Question",
            choices: isAssessment ? ["A", "B", "C", "D"] : undefined,
            blanks: isReview ? ["Answer 1", "Answer 2"] : undefined,
            correct_index: isAssessment ? 0 : undefined,
            reveal_delay_seconds: 2.5,
          },
        ]
      : (scene.activity_prompts || ["Complete the activity"]).map((p, i) => ({
          card_id: `${scene.id}_act_${i}`,
          format: "short_answer" as const,
          question: p,
          answer_text: "Your response",
          reveal_delay_seconds: 2,
        }));
    return (
      <AbsoluteFill style={{ background: theme.backgroundColor }}>
        <EduQAScene cards={cards} seconds_per_card={8} theme="sunshine" />
      </AbsoluteFill>
    );
  }

  if (isGlossary && scene.glossary_terms) {
    return (
      <AbsoluteFill style={{ background: theme.backgroundColor, fontFamily: FONT }}>
        {scene.glossary_terms.map((term, i) => {
          const start = Math.floor(term.start * fps);
          const dur = Math.floor((term.end - term.start) * fps);
          if (dur <= 0) return null;
          return (
            <Sequence key={i} from={start} durationInFrames={dur}>
              <AbsoluteFill
                style={{ justifyContent: "center", alignItems: "center", padding: 80 }}
              >
                <div
                  style={{
                    background: theme.surfaceColor,
                    borderRadius: 24,
                    padding: "48px 64px",
                    maxWidth: 1200,
                    boxShadow: `0 8px 32px ${theme.primaryColor}22`,
                  }}
                >
                  <div
                    style={{
                      fontSize: 72,
                      fontWeight: 800,
                      color: theme.primaryColor,
                      marginBottom: 16,
                    }}
                  >
                    {term.term}
                  </div>
                  <div style={{ fontSize: 40, color: theme.textColor, lineHeight: 1.5 }}>
                    {term.definition}
                  </div>
                </div>
              </AbsoluteFill>
            </Sequence>
          );
        })}
      </AbsoluteFill>
    );
  }

  const camera = scene.camera_motion || "ken-burns";
  return (
    <AbsoluteFill style={{ background: theme.backgroundColor }}>
      {scene.video_clip ? (
        <Sequence from={0} durationInFrames={durationInFrames}>
          <CameraMotion motion={camera}>
            <OffthreadVideo
              src={resolveAsset(scene.video_clip)}
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          </CameraMotion>
        </Sequence>
      ) : (
        <AnimeScene
          images={[]}
          animation={camera}
          backgroundColor={theme.backgroundColor}
          lightingFrom={scene.lighting_from}
          lightingTo={scene.lighting_to}
          sceneDurationSeconds={scene.duration_frames / fps}
        />
      )}
      {scene.particle_effect && (
        <AnimeEffectsLayer
          type="scene"
          effect={scene.particle_effect as any}
          frame={frame}
          fps={fps}
          durationInFrames={durationInFrames}
        />
      )}
      {scene.narration_url && (
        <Sequence from={0} durationInFrames={durationInFrames}>
          <KineticTypography
            transcript={loadTranscript(scene.word_alignment_data)}
            currentTime={frame / fps}
            config={{
              textColor: theme.textColor,
              highlightColor: theme.captionHighlightColor,
              fontFamily: theme.bodyFont,
              backgroundColor: theme.backgroundColor,
            }}
          />
        </Sequence>
      )}
    </AbsoluteFill>
  );
};

export const EduVideoTopicComposition: React.FC<EduVideoTopicCompositionProps> = ({
  scenePlan,
  theme,
}) => {
  const scenes = scenePlan?.scenes || [];

  const topics: Array<{
    key: string;
    scenes: SceneData[];
    startFrame: number;
    durationFrames: number;
  }> = [];
  let cur: (typeof topics)[0] | null = null;

  for (const s of scenes) {
    const key = topicKey(s);
    if (!cur || cur.key !== key) {
      cur = { key, scenes: [s], startFrame: s.start_frame, durationFrames: s.duration_frames };
      topics.push(cur);
    } else {
      cur.scenes.push(s);
      cur.durationFrames = s.start_frame + s.duration_frames - cur.startFrame;
    }
  }

  return (
    <AbsoluteFill style={{ background: theme.backgroundColor }}>
      <TransitionSeries>
        {topics.flatMap((t, i) => {
          const seq = (
            <TransitionSeries.Sequence
              key={t.key}
              durationInFrames={t.durationFrames}
              offset={t.startFrame}
            >
              {t.scenes.map((s) => (
                <Sequence
                  key={s.id}
                  from={s.start_frame - t.startFrame}
                  durationInFrames={s.duration_frames}
                >
                  <SceneLayer scene={s} theme={theme} />
                </Sequence>
              ))}
            </TransitionSeries.Sequence>
          );
          const trans =
            i < topics.length - 1 ? (
              <TransitionSeries.Transition
                key={`t-${t.key}`}
                timing={springTiming({ config: { damping: 20, stiffness: 80 } })}
                presentation={fade()}
              />
            ) : null;
          return trans ? [seq, trans] : [seq];
        })}
      </TransitionSeries>
    </AbsoluteFill>
  );
};
