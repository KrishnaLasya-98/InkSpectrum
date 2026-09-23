import React from "react";
import { Audio, Composition, registerRoot } from "remotion";
import { EvsUiPreview } from "./EvsUiPreview";

const Root: React.FC = () => (
  <>
    <Composition
      id="EvsUiPreview"
      component={EvsUiPreview}
      durationInFrames={30 * 30}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={{}}
    />
  </>
);

registerRoot(Root);
