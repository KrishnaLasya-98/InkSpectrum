"""NarrationTextSyncer — word-level text/audio alignment for EduStream Pro.

Solves two problems the current pipeline has:

  1. TEXT-AUDIO SYNC: Subtitles and on-screen text are timed to the narration
     audio using word-level timestamps. Every word appears exactly when it is
     spoken, not when the section starts.

  2. FORMATTED DISPLAY: Text is broken into displayable chunks with proper
     line-wrapping, punctuation-aware phrasing, and font/size rules — not
     raw dumps of the narration_script string.

How it works
------------
  Step 1 — Forced alignment via WhisperX (if available) or CTC-forced alignment
           Produces word-level timestamps: [{word, start_ms, end_ms}, ...]

  Step 2 — Fallback linear interpolation: if alignment is unavailable,
           distribute word timings proportionally across the audio duration

  Step 3 — Phrase chunking: group words into 4–7 word display phrases
           respecting sentence boundaries, commas, and natural prosody

  Step 4 — Format spec generation: each phrase gets font_size, colour, and
           position based on the section's render_mode and content type

  Step 5 — Output: writes word_captions.json (Remotion CaptionOverlay format),
           formatted_srt.srt (properly phrased for subtitle burn), and
           props for EduQAScene card reveals

Output files (per project/subject/artifacts/)
---------------------------------------------
  narration_aligned.json       word-level timestamps for all segments
  word_captions.json           Remotion WordCaption[] ready for CaptionOverlay
  formatted_srt.srt            Properly phrased SRT with line-break rules
  qa_card_props.json           EduQAScene card props with reveal timing
"""
from __future__ import annotations

import json
import re
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.base_tool import (  # noqa: E402
    BaseTool,
    Determinism,
    ExecutionMode,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum words per subtitle line (SRT) — 7 words fits a 55-char display line
_MAX_WORDS_PER_LINE = 7
# Maximum lines per subtitle block — 2 lines per card keeps it readable
_MAX_LINES_PER_BLOCK = 2
# Minimum gap between subtitle blocks (ms) — prevents flicker
_MIN_GAP_MS = 80

# Children's font sizes by context
_FONT_SIZES = {
    "concept":        64,
    "qa_item":        52,
    "fill_blank":     56,
    "mcq":            44,
    "glossary":       52,
    "recall":         48,
    "worked_example": 60,
    "story_section":  56,
    "intro":          72,
    "activity":       52,
}

# Sunshine Classroom highlight colour by section type
_HIGHLIGHT_COLOURS = {
    "qa_item":     "#FF6B9D",   # coral pink — answer reveals
    "mcq":         "#6BCB77",   # green — correct choice
    "glossary":    "#FFD93D",   # yellow — vocabulary highlight
    "recall":      "#4ECDC4",   # teal — summary key terms
    "default":     "#FF8C42",   # orange — standard primary highlight
}

_FASTER_WHISPER_MODEL: Any | None = None


# ---------------------------------------------------------------------------
# Step 1 & 2: Word-level timestamp extraction
# ---------------------------------------------------------------------------

def _align_with_whisperx(audio_path: Path) -> list[dict[str, Any]] | None:
    """Try WhisperX forced alignment. Returns word list or None if unavailable."""
    try:
        import whisperx  # type: ignore[import-untyped]
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model  = whisperx.load_model("base", device)
        audio  = whisperx.load_audio(str(audio_path))
        result = model.transcribe(audio)

        # Forced alignment
        align_model, metadata = whisperx.load_align_model(
            language_code=result["language"], device=device
        )
        aligned = whisperx.align(
            result["segments"], align_model, metadata, audio, device
        )
        words = []
        for seg in aligned.get("word_segments", []):
            words.append({
                "word":     seg.get("word", ""),
                "start_ms": int(round(seg.get("start", 0) * 1000)),
                "end_ms":   int(round(seg.get("end",   0) * 1000)),
            })
        return words if words else None
    except Exception:
        return None


def _normalise_word(value: str) -> str:
    return re.sub(r"[^a-z0-9']+", "", value.lower())


def _align_with_faster_whisper(
    audio_path: Path,
    reference_text: str,
) -> list[dict[str, Any]] | None:
    """Transcribe real speech and project timestamps onto the exact script words."""
    global _FASTER_WHISPER_MODEL
    try:
        from faster_whisper import WhisperModel

        if _FASTER_WHISPER_MODEL is None:
            _FASTER_WHISPER_MODEL = WhisperModel(
                "small.en", device="cpu", compute_type="int8"
            )
        segments, _ = _FASTER_WHISPER_MODEL.transcribe(
            str(audio_path), language="en", beam_size=5, vad_filter=False,
            word_timestamps=True, condition_on_previous_text=False,
        )
        heard = [
            {
                "word": item.word.strip(),
                "token": _normalise_word(item.word),
                "start_ms": int(round(item.start * 1000)),
                "end_ms": int(round(item.end * 1000)),
            }
            for segment in segments
            for item in (segment.words or [])
            if _normalise_word(item.word)
        ]
        reference = reference_text.split()
        if not heard or not reference:
            return None
        output = [{"word": word} for word in reference]
        matcher = SequenceMatcher(
            None,
            [_normalise_word(word) for word in reference],
            [word["token"] for word in heard],
            autojunk=False,
        )
        for block in matcher.get_matching_blocks():
            for offset in range(block.size):
                source = heard[block.b + offset]
                output[block.a + offset].update(
                    start_ms=source["start_ms"], end_ms=source["end_ms"]
                )
        known = [index for index, word in enumerate(output) if "start_ms" in word]
        anchors = [(-1, 0)] + [(i, output[i]["start_ms"]) for i in known]
        final_end = heard[-1]["end_ms"]
        anchors.append((len(output), final_end))
        for (left_i, left_t), (right_i, right_t) in zip(anchors, anchors[1:]):
            missing = right_i - left_i - 1
            if missing <= 0:
                continue
            step = max(60, (right_t - left_t) / (missing + 1))
            for offset in range(1, missing + 1):
                index = left_i + offset
                start = int(round(left_t + step * offset))
                output[index].update(start_ms=start, end_ms=int(round(start + step * .86)))
        for index, word in enumerate(output):
            next_start = output[index + 1]["start_ms"] if index + 1 < len(output) else final_end
            word["end_ms"] = max(word["start_ms"] + 60, min(word["end_ms"], next_start))
        return output
    except Exception:
        return None


def _align_linear(
    text: str,
    duration_ms: float,
    start_offset_ms: float = 0.0,
) -> list[dict[str, Any]]:
    """Proportional word-timing fallback (no external dependency).

    Distributes word durations proportionally based on character length —
    longer words get proportionally more display time. This produces plausible
    karaoke-style timing without any forced alignment model.
    """
    words = text.split()
    if not words:
        return []

    # Weight each word by character length (longer = more time)
    lengths  = [max(len(w), 1) for w in words]
    total_ch = sum(lengths)
    cursor   = start_offset_ms

    result: list[dict[str, Any]] = []
    for word, length in zip(words, lengths):
        word_dur_ms = (length / total_ch) * duration_ms
        result.append({
            "word":     word,
            "start_ms": int(round(cursor)),
            "end_ms":   int(round(cursor + word_dur_ms)),
        })
        cursor += word_dur_ms

    return result


def _get_word_timestamps(
    audio_path: Path,
    text: str,
    duration_ms: float,
    start_offset_ms: float = 0.0,
) -> tuple[list[dict[str, Any]], str]:
    """Get speech-derived word timestamps before permitting interpolation."""
    if audio_path.exists() and audio_path.stat().st_size > 0:
        aligned = _align_with_whisperx(audio_path)
        if aligned:
            # Offset all timestamps by the section's start position in the video
            return ([
                {
                    "word":     w["word"],
                    "start_ms": w["start_ms"] + int(start_offset_ms),
                    "end_ms":   w["end_ms"]   + int(start_offset_ms),
                }
                for w in aligned
            ], "whisperx")
        aligned = _align_with_faster_whisper(audio_path, text)
        if aligned:
            return ([
                {
                    "word": w["word"],
                    "start_ms": w["start_ms"] + int(start_offset_ms),
                    "end_ms": w["end_ms"] + int(start_offset_ms),
                }
                for w in aligned
            ], "faster_whisper")
    return _align_linear(text, duration_ms, start_offset_ms), "linear_interpolation"


# ---------------------------------------------------------------------------
# Step 3: Phrase chunking — smart line breaks
# ---------------------------------------------------------------------------

# Sentence-ending punctuation — always break after these
_SENTENCE_END = re.compile(r"[.!?]$")
# Clause breaks — prefer breaking after these when approaching max width
_CLAUSE_BREAK = re.compile(r"[,;:]$")


def _chunk_into_phrases(
    words: list[dict[str, Any]],
    max_words: int = _MAX_WORDS_PER_LINE,
) -> list[list[dict[str, Any]]]:
    """Group words into display phrases of max_words, respecting punctuation."""
    phrases: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []

    for w in words:
        current.append(w)
        text = w["word"].rstrip()

        # Force break at sentence end
        if _SENTENCE_END.search(text):
            phrases.append(current)
            current = []
        # Prefer break at clause boundary when reaching half max_words
        elif _CLAUSE_BREAK.search(text) and len(current) >= max_words // 2:
            phrases.append(current)
            current = []
        # Hard break at max_words
        elif len(current) >= max_words:
            phrases.append(current)
            current = []

    if current:
        phrases.append(current)

    return phrases


# ---------------------------------------------------------------------------
# Step 4: Format spec
# ---------------------------------------------------------------------------

def _format_spec(
    source_block_type: str,
    text: str,
) -> dict[str, Any]:
    """Return display formatting parameters for a text segment."""
    btype = source_block_type or "concept"
    font_size = _FONT_SIZES.get(btype, 56)
    highlight = _HIGHLIGHT_COLOURS.get(btype, _HIGHLIGHT_COLOURS["default"])

    # Detect key terms for highlight: ALL_CAPS, quoted, or bolded (**) terms
    key_term_re = re.compile(r"\b[A-Z]{2,}\b|\"[^\"]+\"|\'[^\']+\'|\*\*[^*]+\*\*")
    key_terms = key_term_re.findall(text)
    clean_terms = [
        t.strip('"\'*').lower() for t in key_terms
    ]

    return {
        "font_size":    font_size,
        "highlight_color": highlight,
        "background_color": "rgba(255,253,240,0.90)",  # cream with high opacity
        "font_family":  "Nunito, 'Segoe UI', Arial, sans-serif",
        "font_weight":  "700",
        "text_shadow":  "0 2px 8px rgba(0,0,0,0.25)",
        "key_terms":    clean_terms,
        "words_per_page": min(6, _MAX_WORDS_PER_LINE),
    }


# ---------------------------------------------------------------------------
# Step 5: Output builders
# ---------------------------------------------------------------------------

def _build_word_captions(
    aligned_segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build Remotion WordCaption[] array from all aligned segments."""
    captions: list[dict[str, Any]] = []
    for seg in aligned_segments:
        for w in seg.get("words", []):
            captions.append({
                "word":           w["word"],
                "startMs":        w["start_ms"],
                "endMs":          w["end_ms"],
                "pageBreakAfter": bool(_SENTENCE_END.search(w["word"].rstrip())),
            })
    return captions


def _ts(ms: int) -> str:
    """Format ms as SRT timestamp HH:MM:SS,mmm."""
    h, r = divmod(ms, 3_600_000)
    m, r = divmod(r, 60_000)
    s, ms_r = divmod(r, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms_r:03d}"


def _build_formatted_srt(
    aligned_segments: list[dict[str, Any]],
) -> str:
    """Build properly-phrased SRT with line breaks that match natural speech."""
    blocks: list[tuple[int, int, str]] = []

    for seg in aligned_segments:
        words = seg.get("words", [])
        if not words:
            continue
        phrases = _chunk_into_phrases(words)
        for phrase in phrases:
            if not phrase:
                continue
            start_ms = phrase[0]["start_ms"]
            end_ms   = phrase[-1]["end_ms"]
            # Ensure minimum display duration of 400ms
            end_ms = max(end_ms, start_ms + 400)
            text = " ".join(w["word"] for w in phrase)
            blocks.append((start_ms, end_ms, text))

    # Enforce minimum gap between blocks
    result: list[str] = []
    for i, (start, end, text) in enumerate(blocks):
        if i > 0:
            prev_end = blocks[i - 1][1]
            if start - prev_end < _MIN_GAP_MS:
                start = prev_end + _MIN_GAP_MS

        result.append(str(i + 1))
        result.append(f"{_ts(start)} --> {_ts(end)}")
        # Wrap into max 2 lines for readability
        words_in_block = text.split()
        if len(words_in_block) > _MAX_WORDS_PER_LINE:
            mid = len(words_in_block) // 2
            line1 = " ".join(words_in_block[:mid])
            line2 = " ".join(words_in_block[mid:])
            result.append(f"{line1}\n{line2}")
        else:
            result.append(text)
        result.append("")

    return "\n".join(result)


def _build_qa_card_props(
    aligned_segments: list[dict[str, Any]],
    qa_pairs: list[dict[str, Any]],
    section_start_ms: float,
) -> list[dict[str, Any]]:
    """Build EduQAScene QACard props with reveal timing derived from narration audio.

    The reveal_delay_seconds is calculated as:
      time from section start → first word of the answer in narration
    rather than a hardcoded 2.5s — so the answer appears exactly when spoken.
    """
    cards: list[dict[str, Any]] = []
    if not qa_pairs or not aligned_segments:
        return cards

    # Build a flat word list with timestamps
    all_words = []
    for seg in aligned_segments:
        all_words.extend(seg.get("words", []))

    for i, pair in enumerate(qa_pairs):
        question = pair.get("question", "")
        answer   = pair.get("answer_hint", "") or pair.get("answer_text", "")
        fmt      = pair.get("qa_format", "short_answer")

        # Find the word in the aligned transcript that best matches
        # the beginning of the answer text
        answer_first_word = answer.split()[0].lower().rstrip(".,?!") if answer else ""
        reveal_ms = section_start_ms + 2500  # default 2.5s

        if answer_first_word:
            for w in all_words:
                if w["word"].lower().rstrip(".,?!") == answer_first_word:
                    reveal_ms = w["start_ms"]
                    break

        reveal_delay_s = max(1.0, (reveal_ms - section_start_ms) / 1000)

        card: dict[str, Any] = {
            "card_id":              f"qa_{i}_{pair.get('number', i)}",
            "format":               fmt,
            "question":             question,
            "reveal_delay_seconds": round(reveal_delay_s, 2),
        }

        if fmt == "mcq":
            card["choices"]       = pair.get("choices", [])
            card["correct_index"] = pair.get("correct_index", 0)
        elif fmt == "fill_blank":
            card["blanks"] = answer.split() if answer else []
        else:
            card["answer_text"] = answer

        cards.append(card)

    return cards


# ---------------------------------------------------------------------------
# NarrationTextSyncer tool
# ---------------------------------------------------------------------------

class NarrationTextSyncer(BaseTool):
    """Word-level text/audio alignment + formatted display for EduStream Pro."""

    name = "narration_text_syncer"
    version = "1.0.0"
    tier = ToolTier.CORE
    capability = "text_sync"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL

    dependencies: list[str] = []
    install_instructions = (
        "Optional for high-accuracy alignment: pip install whisperx torch\n"
        "Without it, proportional linear alignment is used (still well-timed)."
    )
    agent_skills = ["subtitle-sync", "whisperx"]
    capabilities = [
        "word_level_alignment",
        "phrase_chunking",
        "formatted_srt",
        "qa_card_timing",
        "remotion_caption_props",
    ]

    input_schema = {
        "type": "object",
        "required": ["narration_manifest", "educational_plan"],
        "properties": {
            "narration_manifest": {"type": "object"},
            "educational_plan":   {"type": "object"},
            "output_dir":         {"type": "string"},
            "title_offset_seconds": {"type": "number", "default": 0.0},
            "dry_run":            {"type": "boolean", "default": False},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "word_captions":    {"type": "array"},
            "formatted_srt":    {"type": "string"},
            "qa_card_props":    {"type": "object"},
            "narration_aligned": {"type": "array"},
            "alignment_method": {"type": "string"},
        },
    }

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        segs = len(inputs.get("narration_manifest", {}).get("segments", []))
        return max(5.0, segs * 3.0)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        manifest     = inputs.get("narration_manifest", {})
        plan         = inputs.get("educational_plan", {})
        out_dir      = Path(inputs.get("output_dir", "artifacts"))
        title_offset = float(inputs.get("title_offset_seconds", 0.0))
        dry_run      = inputs.get("dry_run", False)
        start_t      = time.monotonic()

        segments   = manifest.get("segments", [])
        sections   = {s["section_id"]: s for s in plan.get("sections", [])}
        out_dir.mkdir(parents=True, exist_ok=True)

        aligned_segments: list[dict[str, Any]] = []
        alignment_methods: set[str] = set()
        qa_card_map: dict[str, list[dict[str, Any]]] = {}

        for seg in segments:
            sid        = seg["section_id"]
            text       = seg.get("text", "")
            duration_s = float(seg.get("duration_seconds", len(text.split()) / 2))
            start_s    = float(seg.get("start_seconds", 0.0)) + title_offset
            audio_rel  = seg.get("audio_path", "")
            audio_path = (
                Path(audio_rel) if Path(audio_rel).is_absolute()
                else _ROOT / audio_rel
            )

            start_ms  = start_s * 1000
            dur_ms    = duration_s * 1000

            if dry_run:
                words = _align_linear(text, dur_ms, start_ms)
            else:
                words, method = _get_word_timestamps(audio_path, text, dur_ms, start_ms)
                alignment_methods.add(method)

            section_data = sections.get(sid, {})
            btype = section_data.get("source_block_type", "concept")
            fmt_spec = _format_spec(btype, text)

            aligned_seg = {
                "section_id":        sid,
                "text":              text,
                "start_ms":          int(start_ms),
                "end_ms":            int(start_ms + dur_ms),
                "words":             words,
                "format_spec":       fmt_spec,
                "source_block_type": btype,
            }
            aligned_segments.append(aligned_seg)

            # Build QA card props for any section that has qa_pairs,
            # regardless of block type (qa_item, fill_blank, mcq, recall all apply).
            qa_pairs = section_data.get("qa_pairs", [])
            if qa_pairs:
                qa_card_map[sid] = _build_qa_card_props(
                    [aligned_seg], qa_pairs, start_ms
                )

        # Build outputs
        word_captions  = _build_word_captions(aligned_segments)
        formatted_srt  = _build_formatted_srt(aligned_segments)
        alignment_method = (
            next(iter(alignment_methods))
            if len(alignment_methods) == 1
            else "+".join(sorted(alignment_methods)) or "linear_interpolation"
        )

        # Write artifacts
        (out_dir / "narration_aligned.json").write_text(
            json.dumps({"segments": aligned_segments, "method": alignment_method},
                       indent=2), encoding="utf-8"
        )
        (out_dir / "word_captions.json").write_text(
            json.dumps(word_captions, indent=2), encoding="utf-8"
        )
        srt_path = out_dir / "formatted_subtitles.srt"
        # If out_dir is artifacts/, put the SRT alongside it in renders/.
        # But if a caller passes an explicit output_dir that is already a
        # renders/ dir, write there directly.  Avoid the fragile .parent
        # traversal that breaks when out_dir depth changes.
        renders_srt = out_dir.parent / "renders" / "formatted_subtitles.srt"
        if (out_dir.parent / "renders").exists():
            srt_path = renders_srt
        srt_path.parent.mkdir(parents=True, exist_ok=True)
        srt_path.write_text(formatted_srt, encoding="utf-8")

        (out_dir / "qa_card_props.json").write_text(
            json.dumps(qa_card_map, indent=2), encoding="utf-8"
        )

        print(f"  ✓ Text sync: {len(word_captions)} words aligned "
              f"via {alignment_method}")
        print(f"    formatted_srt → {srt_path}")
        print(f"    word_captions → {out_dir / 'word_captions.json'}")
        if qa_card_map:
            total_cards = sum(len(v) for v in qa_card_map.values())
            print(f"    qa_card_props → {total_cards} cards with audio-derived reveal timings")

        return ToolResult(
            success=True,
            data={
                "word_captions":     word_captions,
                "formatted_srt":     formatted_srt,
                "formatted_srt_path": str(srt_path),
                "qa_card_props":     qa_card_map,
                "narration_aligned": aligned_segments,
                "alignment_method":  alignment_method,
            },
            artifacts=["narration_manifest"],
            cost_usd=0.0,
            duration_seconds=time.monotonic() - start_t,
        )

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {
            "tool": self.name,
            "estimated_cost_usd": 0.0,
            "estimated_runtime_seconds": self.estimate_runtime(inputs),
            "status": self.get_status().value,
            "would_execute": True,
        }
