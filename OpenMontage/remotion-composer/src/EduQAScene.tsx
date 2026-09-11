import {
  AbsoluteFill,
  Img,
  Sequence,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export type QAFormat = "short_answer" | "fill_blank" | "mcq" | "true_false";

export interface QACard {
  card_id: string;
  format: QAFormat;
  question: string;
  /** fill_blank: the answer tokens. mcq: not used. */
  blanks?: string[];
  /** mcq: option strings e.g. ["a) water", "b) land", "c) sky"] */
  choices?: string[];
  /** mcq: 0-based index of correct choice */
  correct_index?: number;
  /** short_answer / true_false */
  answer_text?: string;
  /** seconds before answer reveals (default 2.5) */
  reveal_delay_seconds?: number;
  /** optional image beside the question */
  support_image?: string;
}

export interface EduQASceneProps {
  cards: QACard[];
  /** seconds per card (default 8) */
  seconds_per_card?: number;
  theme?: "sunshine" | "dark";
}

// ---------------------------------------------------------------------------
// Sunshine Classroom tokens
// ---------------------------------------------------------------------------
const SC = {
  BG:        "#FFFDF0",
  PRIMARY:   "#FF8C42",
  SECONDARY: "#4ECDC4",
  ACCENT:    "#FFD93D",
  QA_REVEAL: "#FF6B9D",
  TEXT:      "#2D2D2D",
  MUTED:     "#9CA3AF",
  CORRECT:   "#6BCB77",
  WRONG:     "#D1D5DB",
  CARD_BG:   "#FFFFFF",
  FONT:      "Nunito, 'Segoe UI', Arial, sans-serif",
} as const;

// ---------------------------------------------------------------------------
// Sparky mascot — simple inline SVG star (no external asset dependency)
// ---------------------------------------------------------------------------
const Sparky: React.FC<{ scale: number }> = ({ scale }) => (
  <svg
    width={80 * scale}
    height={80 * scale}
    viewBox="0 0 80 80"
    style={{ display: "block" }}
  >
    <polygon
      points="40,5 49,30 76,30 54,48 63,74 40,57 17,74 26,48 4,30 31,30"
      fill={SC.ACCENT}
      stroke={SC.PRIMARY}
      strokeWidth={3}
    />
    <circle cx="34" cy="36" r="4" fill={SC.TEXT} />
    <circle cx="46" cy="36" r="4" fill={SC.TEXT} />
    <path d="M33,47 Q40,54 47,47" stroke={SC.TEXT} strokeWidth={3}
          fill="none" strokeLinecap="round" />
  </svg>
);

// ---------------------------------------------------------------------------
// Shared card wrapper
// ---------------------------------------------------------------------------
const CardShell: React.FC<{
  children: React.ReactNode;
  opacity: number;
  translateY: number;
}> = ({ children, opacity, translateY }) => (
  <div
    style={{
      position: "absolute",
      inset: 0,
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      padding: "60px 80px",
      background: SC.BG,
      opacity,
      transform: `translateY(${translateY}px)`,
    }}
  >
    {children}
  </div>
);

const QBox: React.FC<{ text: string }> = ({ text }) => (
  <div
    style={{
      background: SC.CARD_BG,
      borderRadius: 24,
      padding: "36px 48px",
      width: "100%",
      maxWidth: 1400,
      boxShadow: "0 4px 24px rgba(0,0,0,0.08)",
      fontFamily: SC.FONT,
      fontSize: 52,
      fontWeight: 700,
      color: SC.TEXT,
      lineHeight: 1.4,
      textAlign: "center" as const,
    }}
  >
    {text}
  </div>
);

// ---------------------------------------------------------------------------
// Short answer card
// ---------------------------------------------------------------------------
const ShortAnswerCard: React.FC<{ card: QACard; fps: number }> = ({ card, fps }) => {
  const frame = useCurrentFrame();
  const revealDelay = (card.reveal_delay_seconds ?? 2.5) * fps;

  const cardOpacity = spring({ frame, fps, config: { damping: 20, stiffness: 80 } });
  const cardSlide   = interpolate(spring({ frame, fps }), [0, 1], [40, 0]);

  const answerOpacity = spring({ frame: frame - revealDelay, fps, config: { damping: 18 } });
  const answerScale   = spring({ frame: frame - revealDelay, fps,
                                  config: { damping: 10, stiffness: 200 }, from: 0.7, to: 1 });
  const sparkyScale   = spring({ frame: frame - revealDelay - 3, fps,
                                  config: { damping: 8, stiffness: 300 }, from: 0, to: 1 });

  return (
    <CardShell opacity={cardOpacity} translateY={cardSlide}>
      {card.support_image && (
        <Img
          src={card.support_image}
          style={{ width: 260, height: 180, objectFit: "contain", marginBottom: 24, borderRadius: 16 }}
        />
      )}
      <QBox text={card.question} />
      <div
        style={{
          marginTop: 32,
          fontFamily: SC.FONT,
          fontSize: 60,
          fontWeight: 800,
          color: SC.QA_REVEAL,
          opacity: answerOpacity,
          transform: `scale(${answerScale})`,
          textAlign: "center" as const,
          textShadow: `0 0 20px ${SC.QA_REVEAL}44`,
        }}
      >
        {card.answer_text ?? ""}
      </div>
      {/* Sparky celebrates */}
      <div
        style={{
          position: "absolute",
          bottom: 80,
          right: 120,
          opacity: sparkyScale > 0.1 ? answerOpacity : 0,
          transform: `scale(${sparkyScale})`,
        }}
      >
        <Sparky scale={sparkyScale} />
      </div>
    </CardShell>
  );
};

// ---------------------------------------------------------------------------
// Fill-blank card
// ---------------------------------------------------------------------------
const FillBlankCard: React.FC<{ card: QACard; fps: number }> = ({ card, fps }) => {
  const frame = useCurrentFrame();
  const revealDelay = (card.reveal_delay_seconds ?? 2.5) * fps;

  const cardOpacity = spring({ frame, fps, config: { damping: 20 } });
  const cardSlide   = interpolate(spring({ frame, fps }), [0, 1], [40, 0]);

  // Each blank reveals one at a time after revealDelay
  const blanks = card.blanks ?? [];

  return (
    <CardShell opacity={cardOpacity} translateY={cardSlide}>
      {card.support_image && (
        <Img
          src={card.support_image}
          style={{ width: 260, height: 180, objectFit: "contain", marginBottom: 24, borderRadius: 16 }}
        />
      )}
      <QBox text={card.question} />
      <div
        style={{
          marginTop: 40,
          display: "flex",
          gap: 24,
          flexWrap: "wrap" as const,
          justifyContent: "center",
        }}
      >
        {blanks.map((answer, i) => {
          const blankDelay = revealDelay + i * fps * 0.5;
          const blankOpacity = spring({ frame: frame - blankDelay, fps, config: { damping: 18 } });
          const blankScale   = spring({ frame: frame - blankDelay, fps,
                                         config: { damping: 10, stiffness: 220 }, from: 0.6, to: 1 });
          return (
            <div
              key={i}
              style={{
                background: `${SC.QA_REVEAL}22`,
                border: `3px solid ${SC.QA_REVEAL}`,
                borderRadius: 16,
                padding: "16px 32px",
                fontFamily: SC.FONT,
                fontSize: 52,
                fontWeight: 800,
                color: SC.QA_REVEAL,
                opacity: blankOpacity,
                transform: `scale(${blankScale})`,
                minWidth: 160,
                textAlign: "center" as const,
                boxShadow: `0 0 16px ${SC.QA_REVEAL}33`,
              }}
            >
              {answer}
            </div>
          );
        })}
      </div>
    </CardShell>
  );
};

// ---------------------------------------------------------------------------
// MCQ card
// ---------------------------------------------------------------------------
const MCQCard: React.FC<{ card: QACard; fps: number }> = ({ card, fps }) => {
  const frame = useCurrentFrame();
  const revealDelay = (card.reveal_delay_seconds ?? 2.5) * fps;
  const choices = card.choices ?? [];
  const correctIdx = card.correct_index ?? 0;

  const cardOpacity = spring({ frame, fps, config: { damping: 20 } });
  const cardSlide   = interpolate(spring({ frame, fps }), [0, 1], [40, 0]);
  const revealed    = frame >= revealDelay;

  return (
    <CardShell opacity={cardOpacity} translateY={cardSlide}>
      <QBox text={card.question} />
      <div
        style={{
          marginTop: 40,
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 28,
          width: "100%",
          maxWidth: 1300,
        }}
      >
        {choices.map((choice, i) => {
          const choiceDelay  = i * 6;
          const choiceSpring = spring({ frame: frame - choiceDelay, fps, config: { damping: 18 } });
          const isCorrect    = i === correctIdx;
          const revealScale  = revealed && isCorrect
            ? spring({ frame: frame - revealDelay, fps, config: { damping: 8, stiffness: 260 }, from: 0.9, to: 1.08 })
            : 1;

          let bg    = `${SC.SECONDARY}18`;
          let border = SC.SECONDARY;
          let textColor = SC.TEXT;
          if (revealed && isCorrect) {
            bg     = `${SC.CORRECT}33`;
            border = SC.CORRECT;
            textColor = SC.CORRECT;
          } else if (revealed && !isCorrect) {
            bg     = SC.WRONG;
            border = SC.WRONG;
            textColor = SC.MUTED;
          }

          return (
            <div
              key={i}
              style={{
                background: bg,
                border: `3px solid ${border}`,
                borderRadius: 20,
                padding: "24px 32px",
                fontFamily: SC.FONT,
                fontSize: 44,
                fontWeight: revealed && isCorrect ? 800 : 600,
                color: textColor,
                opacity: choiceSpring,
                transform: `scale(${revealed && isCorrect ? revealScale : 1})`,
                textAlign: "center" as const,
                transition: "background 0.3s, border 0.3s",
              }}
            >
              {choice}
              {revealed && isCorrect && (
                <span style={{ marginLeft: 12, fontSize: 40 }}>✓</span>
              )}
            </div>
          );
        })}
      </div>
      {/* Sparky on correct reveal */}
      {revealed && (
        <div style={{ position: "absolute", bottom: 60, right: 100 }}>
          <Sparky
            scale={spring({ frame: frame - revealDelay - 2, fps,
                             config: { damping: 8, stiffness: 300 }, from: 0, to: 1 })}
          />
        </div>
      )}
    </CardShell>
  );
};

// ---------------------------------------------------------------------------
// True/False card (reuses ShortAnswerCard layout)
// ---------------------------------------------------------------------------
const TrueFalseCard: React.FC<{ card: QACard; fps: number }> = ({ card, fps }) => (
  <ShortAnswerCard card={card} fps={fps} />
);

// ---------------------------------------------------------------------------
// Main composition
// ---------------------------------------------------------------------------
export const EduQAScene: React.FC<EduQASceneProps> = ({
  cards,
  seconds_per_card = 8,
  theme = "sunshine",
}) => {
  const { fps } = useVideoConfig();
  const framesPerCard = seconds_per_card * fps;

  return (
    <AbsoluteFill style={{ background: SC.BG }}>
      {cards.map((card, i) => (
        <Sequence
          key={card.card_id}
          from={i * framesPerCard}
          durationInFrames={framesPerCard}
        >
          {card.format === "short_answer" && (
            <ShortAnswerCard card={card} fps={fps} />
          )}
          {card.format === "fill_blank" && (
            <FillBlankCard card={card} fps={fps} />
          )}
          {card.format === "mcq" && (
            <MCQCard card={card} fps={fps} />
          )}
          {card.format === "true_false" && (
            <TrueFalseCard card={card} fps={fps} />
          )}
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
