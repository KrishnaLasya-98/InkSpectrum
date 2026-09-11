import {
  AbsoluteFill,
  interpolate,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { KineticWord, type KineticWordProps, type WordAlignment, type WordLayout, type SentenceRole, type WordAnimationConfig } from "./KineticWord";
import { AnimeEffectsLayer, type AnimeEffectType } from "./AnimeEffectsLayer";

// ---------------------------------------------------------------------------
// Pillar 1 data contracts
// ---------------------------------------------------------------------------

export interface TranscriptData {
  word_timestamps: Array<{ word: string; start: number; end: number }>;
  sentences: Array<{ text: string; start: number; end: number; role?: string }>;
  audio_metadata?: {
    sample_rate?: number;
    duration_seconds: number;
    rms_amplitude: Array<{ time: number; rms: number }>;
  };
}

export interface RMSFrame {
  time: number;
  rms: number;
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

export interface KineticTypographyConfig {
  maxWordsPerLine: number;
  maxLines: number;
  wordEnterDurationMs: number;
  wordExitDurationMs: number;
  highlightDurationMs: number;
  staggerDelayMs: number;
  overlapRatio: number;
  amplitudeScaleRange: [number, number];
  consonantPopScale: number;
  consonantPopDurationMs: number;
  floatingDurationMs: number;
  breathingDurationMs: number;
  breathingScaleRange: [number, number];
  speedLineTrigger: AnimeEffectType;
  particleTrigger: AnimeEffectType;
  reactionTrigger: AnimeEffectType;
  textColor: string;
  highlightColor: string;
  fontFamily: string;
  backgroundColor: string;
}

const DEFAULT_CONFIG: KineticTypographyConfig = {
  maxWordsPerLine: 7,
  maxLines: 2,
  wordEnterDurationMs: 150,
  wordExitDurationMs: 200,
  highlightDurationMs: 100,
  staggerDelayMs: 50,
  overlapRatio: 0.3,
  amplitudeScaleRange: [0, 0.15],
  consonantPopScale: 0.20,
  consonantPopDurationMs: 50,
  floatingDurationMs: 500,
  breathingDurationMs: 1200,
  breathingScaleRange: [1.0, 1.03],
  speedLineTrigger: "speed-lines",
  particleTrigger: "particles-sparkles",
  reactionTrigger: "reaction-pop",
  textColor: "#F5F0E8",
  highlightColor: "#FFD93D",
  fontFamily: "'Noto Sans', 'Space Grotesk', system-ui, sans-serif",
  backgroundColor: "#0A0A1A",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function detectPlosives(word: string): boolean {
  return /[ptkbdg]/i.test(word);
}

function classifySentenceRole(sentence: string): SentenceRole {
  const trimmed = sentence.trim();
  if (/^[\p{Emoji_Presentation}\p{Extended_Pictographic}]/u.test(trimmed)) return "character_name";
  if (trimmed.endsWith("?")) return "question";
  if (/^(Definition|Define|What is|A \w+ is)/i.test(trimmed)) return "definition";
  if (/^(For example|Example|e\.g\.|Like)/i.test(trimmed)) return "example";
  if (/^(Important|Key|Note|Remember|Watch)/i.test(trimmed)) return "emphasis";
  return "statement";
}

function buildWordAlignments(transcript: TranscriptData): WordAlignment[] {
  const words: WordAlignment[] = [];
  let idx = 0;

  for (const wt of transcript.word_timestamps) {
    const start = wt.start;
    const end = wt.end;
    const next = transcript.word_timestamps[idx + 1];
    const pauseAfterMs = next ? (next.start - end) * 1000 : 0;

    words.push({
      word: wt.word,
      start,
      end,
      index: idx,
      isPlosive: detectPlosives(wt.word),
      isEmphasis: /^(Important|Key|Note|Remember|Watch)/i.test(wt.word),
      amplitude: 0,
      pauseAfterMs,
    });

    idx++;
  }

  return words;
}

function getRMSAtTime(envelope: RMSFrame[], time: number): number {
  if (!envelope.length) return 0;
  let closest = envelope[0];
  let minDist = Math.abs(time - closest.time);
  for (const frame of envelope) {
    const dist = Math.abs(time - frame.time);
    if (dist < minDist) {
      minDist = dist;
      closest = frame;
    }
  }
  return closest.rms;
}

function wrapWordsToLines(words: string[], maxWordsPerLine: number): string[][] {
  const lines: string[][] = [];
  let currentLine: string[] = [];

  for (const word of words) {
    if (currentLine.length >= maxWordsPerLine) {
      lines.push(currentLine);
      currentLine = [];
    }
    currentLine.push(word);
  }

  if (currentLine.length > 0) lines.push(currentLine);

  return lines;
}

function computeLayout(
  words: WordAlignment[],
  maxWordsPerLine: number,
  maxLines: number
): Array<{ word: WordAlignment; layout: WordLayout }> {
  const rawLines = wrapWordsToLines(words.map(w => w.word), maxWordsPerLine);
  const lines = rawLines.slice(0, maxLines);

  const result: Array<{ word: WordAlignment; layout: WordLayout }> = [];
  let wordPointer = 0;

  for (let lineIdx = 0; lineIdx < lines.length; lineIdx++) {
    const line = lines[lineIdx];
    const lineWordCount = line.length;

    for (let wordIdxInLine = 0; wordIdxInLine < lineWordCount; wordIdxInLine++) {
      if (wordPointer >= words.length) break;
      const word = words[wordPointer];
      const widthPercent = 100 / lineWordCount;

      result.push({
        word,
        layout: {
          xPercent: wordIdxInLine * widthPercent,
          yPercent: lineIdx * 14,
          widthPercent,
          lineIndex: lineIdx,
          wordIndexInLine: wordIdxInLine,
        },
      });

      wordPointer++;
    }
  }

  return result;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export interface KineticTypographyProps {
  transcript: TranscriptData;
  currentTime: number;
  config?: Partial<KineticTypographyConfig>;
  children?: React.ReactNode;
  onWordEnter?: (word: WordAlignment) => void;
  onWordSpeak?: (word: WordAlignment) => void;
}

export const KineticTypography: React.FC<KineticTypographyProps> = ({
  transcript,
  currentTime,
  config: userConfig,
  children,
  onWordEnter,
  onWordSpeak,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const config = { ...DEFAULT_CONFIG, ...userConfig };

  const words = buildWordAlignments(transcript);
  const layoutItems = computeLayout(words, config.maxWordsPerLine, config.maxLines);

  // Map word index to sentence role by scanning transcript sentences
  const wordRoleMap = new Map<number, SentenceRole>();
  let globalWordIdx = 0;

  for (const sentence of transcript.sentences) {
    const role = (sentence.role as SentenceRole) || classifySentenceRole(sentence.text);
    const sentenceWordCount = sentence.text.split(/\s+/).length;

    for (let i = 0; i < sentenceWordCount; i++) {
      if (globalWordIdx < words.length) {
        wordRoleMap.set(words[globalWordIdx].index, role);
      }
      globalWordIdx++;
    }
  }

  // Update amplitudes from envelope
  const enrichedWords = words.map(w => ({
    ...w,
    amplitude: getRMSAtTime(transcript.audio_metadata?.rms_amplitude ?? [], w.start),
  }));

  // Find active word
  const activeWordIndex = enrichedWords.findIndex(w => currentTime >= w.start && currentTime <= w.end);
  const highlightedWordIndex = activeWordIndex >= 0 ? activeWordIndex - 1 : -1;

  // Determine active sentence role
  const activeSentence = transcript.sentences.find(s => currentTime >= s.start && currentTime <= s.end);
  const activeRole = activeSentence ? classifySentenceRole(activeSentence.text) : "statement";

  const animConfig: WordAnimationConfig = {
    enterDurationMs: config.wordEnterDurationMs,
    exitDurationMs: config.wordExitDurationMs,
    highlightDurationMs: config.highlightDurationMs,
    staggerDelayMs: config.staggerDelayMs,
    amplitudeScaleRange: config.amplitudeScaleRange,
    consonantPopScale: config.consonantPopScale,
    consonantPopDurationMs: config.consonantPopDurationMs,
    floatingDurationMs: config.floatingDurationMs,
    breathingDurationMs: config.breathingDurationMs,
    breathingScaleRange: config.breathingScaleRange,
    speedLineTrigger: config.speedLineTrigger,
    particleTrigger: config.particleTrigger,
    reactionTrigger: config.reactionTrigger,
  };

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background: config.backgroundColor,
        overflow: "hidden",
      }}
    >
      {layoutItems.map(({ word, layout }) => {
        const wordIdx = enrichedWords.findIndex(w => w.index === word.index);
        const amplitude = enrichedWords[wordIdx]?.amplitude ?? 0;
        const role = wordRoleMap.get(word.index) ?? activeRole;
        const isActive = wordIdx === activeWordIndex;
        const isHighlighted = wordIdx === highlightedWordIndex;
        const showEffects = isActive || isHighlighted;

        return (
          <KineticWord
            key={word.index}
            word={enrichedWords[wordIdx] ?? word}
            layout={layout}
            frame={frame}
            fps={fps}
            amplitude={amplitude}
            isActive={isActive}
            isHighlighted={isHighlighted}
            sentenceRole={role}
            animConfig={animConfig}
            showEffects={showEffects}
            onEnter={onWordEnter}
            onSpeak={onWordSpeak}
          />
        );
      })}

      {/* Scene-level effects */}
      {(activeRole === "emphasis" || activeRole === "question") && (
        <AnimeEffectsLayer
          type="scene"
          effect={activeRole === "emphasis" ? config.speedLineTrigger : "reaction-pop"}
          frame={frame}
          fps={fps}
          durationInFrames={durationInFrames}
          bounds={{ x: 20, y: 20, width: 60, height: 60 }}
        />
      )}

      {children}
    </AbsoluteFill>
  );
};
