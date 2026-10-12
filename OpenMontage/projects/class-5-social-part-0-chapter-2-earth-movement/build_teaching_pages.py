"""Derive draft source-faithful teaching-card pages from measured word timing.

This emits a review artifact only. Every page is a contiguous slice of exact
textbook panel copy; unmatched spoken anchors are explicitly reported.
"""

from __future__ import annotations

import json
import re
import argparse
from pathlib import Path

from tools.video.educational_hyperframes_composer import _panel_content


PROJECT = Path(__file__).resolve().parent


def _tokens(value: str) -> list[str]:
    return [token for word in value.split() if (token := re.sub(r"[^a-z0-9]", "", word.casefold()))]


def _page_text(value: str, limit: int = 185) -> list[str]:
    # Keep the textbook wording byte-for-byte except for whitespace joins.
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", " ".join(value.split()))
    pieces: list[str] = []
    for sentence in sentences:
        if len(sentence) <= limit:
            pieces.append(sentence)
            continue
        current = ""
        for word in sentence.split():
            if current and len(current) + len(word) + 1 > limit:
                pieces.append(current)
                current = ""
            current = f"{current} {word}".strip()
        if current:
            pieces.append(current)
    pages: list[str] = []
    for piece in pieces:
        if pages and len(pages[-1]) + len(piece) + 1 <= limit:
            pages[-1] += " " + piece
        else:
            pages.append(piece)
    return pages


def _word_anchor(words: list[dict], page: str, previous: int) -> tuple[int, float] | None:
    # The source card remains verbatim. Only its speech-search anchor expands
    # symbols/dates to match the intentionally natural spoken narration.
    spoken_anchor = page.replace("It takes 365¼ days", "It takes three hundred and sixty-five and one quarter days")
    spoken_anchor = spoken_anchor.replace("On 22 December", "On the twenty-second of December")
    spoken_anchor = spoken_anchor.replace("On 21 June", "On the twenty-first of June")
    wanted = _tokens(spoken_anchor)[:3]
    if not wanted:
        return None
    observed = [
        (index, parts[0])
        for index, word in enumerate(words)
        if (parts := _tokens(str(word["word"])))
    ]
    for offset in range(len(observed) - len(wanted) + 1):
        index = observed[offset][0]
        if index > previous and [token for _, token in observed[offset:offset + len(wanted)]] == wanted:
            return index, float(words[index]["startMs"]) / 1000
    return None


def build(sync_path: Path | None = None, captions_path: Path | None = None,
          output_path: Path | None = None) -> dict:
    plan = json.loads((PROJECT / "artifacts/educational_plan.json").read_text(encoding="utf-8"))
    sync = json.loads((sync_path or PROJECT / "artifacts/multimedia-sync-draft-v1.json").read_text(encoding="utf-8"))
    captions = json.loads((captions_path or PROJECT / "artifacts/alignment-v1/word_captions.json").read_text(encoding="utf-8"))
    by_id = {str(item["section_id"]): item for item in plan["sections"]}
    result: dict[str, object] = {"status": "draft_requires_visual_review", "sections": {}, "unmatched_anchors": []}
    for timing in sync["timeline"]:
        section_id = str(timing["section_id"])
        section = by_id[section_id]
        _, body, items = _panel_content(section, plan)
        text = " ".join([body, *items]).strip()
        if len(text) <= 220:
            continue
        pages = _page_text(text)
        if " ".join(" ".join(pages).split()) != " ".join(text.split()):
            raise ValueError(f"Source text changed while paging {section_id}")
        start = float(timing["start_seconds"])
        end = float(timing["end_seconds"])
        section_words = [word for word in captions if start * 1000 <= float(word["startMs"]) < end * 1000]
        starts = [0.0]
        previous = -1
        for page_index, page in enumerate(pages[1:], 1):
            match = _word_anchor(section_words, page, previous)
            if match is None:
                result["unmatched_anchors"].append({"section_id": section_id, "page_index": page_index, "text": page[:80]})
                # A placeholder makes the review artifact inspectable, not approved.
                offset = round((end - start) * page_index / len(pages), 3)
            else:
                previous, absolute = match
                offset = round(absolute - start, 3)
            starts.append(offset)
        duration = round(end - start, 3)
        starts.append(duration)
        if any(b <= a for a, b in zip(starts, starts[1:])):
            raise ValueError(f"Non-monotonic teaching-page timing for {section_id}: {starts}")
        result["sections"][section_id] = [
            {"text": page, "start_offset_seconds": starts[index], "end_offset_seconds": starts[index + 1]}
            for index, page in enumerate(pages)
        ]
    target = output_path or PROJECT / "artifacts/teaching-pages-draft-v1.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"path": str(target), "paged_sections": len(result["sections"]), "unmatched_anchors": result["unmatched_anchors"]}, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sync", type=Path)
    parser.add_argument("--captions", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    build(args.sync, args.captions, args.output)


if __name__ == "__main__":
    main()
