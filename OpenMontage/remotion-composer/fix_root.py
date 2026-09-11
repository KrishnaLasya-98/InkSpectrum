import re
with open(r'D:\InkSpectrum\OpenMontage\remotion-composer\src\Root.tsx', 'r') as f:
    content = f.read()
insert = """      <Composition
        id="EduVideoTopic"
        component={EduVideoTopicComposition}
        durationInFrames={30 * 480}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          scenePlan: null,
          theme: resolveTheme({ theme: "sunshine-classroom" }),
        }}
      />"""
content = content.replace('    </>', insert + '\n    </>')
with open(r'D:\InkSpectrum\OpenMontage\remotion-composer\src\Root.tsx', 'w') as f:
    f.write(content)
