import React from "react";
import { registerRoot, Composition } from "remotion";
import { EduVideoTopicComposition, type ScenePlanData } from "./EduVideoTopicComposition";
import { resolveTheme, type ThemeConfig } from "./Root";
import scenePlanData from "../../projects/evs-lesson-8/artifacts/scene_plan_render_fixed.json";

const scenePlan = (scenePlanData as unknown) as ScenePlanData;
const theme: ThemeConfig = resolveTheme({ theme: "sunshine-classroom" });

const RenderRoot: React.FC = () => {
  return (
    <Composition
      id="EduVideoTopic"
      component={EduVideoTopicComposition as any}
      durationInFrames={scenePlan.total_frames || 30 * 480}
      fps={scenePlan.fps || 30}
      width={scenePlan.resolution?.width || 1920}
      height={scenePlan.resolution?.height || 1080}
      defaultProps={{
        scenePlan,
        theme,
      }}
    />
  );
};

registerRoot(RenderRoot);
