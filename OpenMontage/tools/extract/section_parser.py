"""Markdown section parser for opendataloader output.

Converts extracted .md files into typed ContentBlock lists that feed the
educational content pipeline.

Block types
-----------
intro           lesson header, warm-up, overview
concept         definition, explanation, fact paragraphs
worked_example  step-by-step worked problem (Maths)
story_section   narrative reading passage (English)
qa_item         assessment blocks (Answer / Fill-blank / MCQ)
activity        drawing / hands-on activity pages
glossary        vocabulary definition lists
recall          "Let's Recall" summary bullets

CLI
---
    python -m tools.extract.section_parser --subject evs
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from enum import Enum
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
    ToolStatus,
    ToolTier,
)

# ---------------------------------------------------------------------------
# Paths — use env var OPENDATALOADER_OUTPUT_DIR if set, else default Windows path
# ---------------------------------------------------------------------------
_ODL_DIR = Path(
    os.environ.get(
        "OPENDATALOADER_OUTPUT_DIR",
        r"C:\Users\user\Downloads\opendataloader_output",
    )
)
_SUBJECT_MD: dict[str, str] = {
    "evs":
        "RPS - EVS - CLASS 1 - INDIVIDUAL - B (2026) PRINTFILE-pages-2.md",
    "english":
        "RPS - ENGLISH - CLASS 1 - INDIVIDUAL - A (2026) PRINTFILE (2)-pages-2.md",
    "maths":
        "RPS - MATHS - CLASS 1 - INDIVIDUAL - B (2026) PRINTFILE-pages-2.md",
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
class BlockType(str, Enum):
    INTRO          = "intro"
    CONCEPT        = "concept"
    WORKED_EXAMPLE = "worked_example"
    STORY_SECTION  = "story_section"
    QA_ITEM        = "qa_item"
    ACTIVITY       = "activity"
    GLOSSARY       = "glossary"
    RECALL         = "recall"


@dataclass
class QAPair:
    number: str
    question: str
    answer_hint: str = ""
    qa_format: str = "short_answer"  # short_answer | fill_blank | mcq | true_false


@dataclass
class ContentBlock:
    block_id: str
    block_type: BlockType
    heading: str
    body_text: str
    image_refs: list[str] = field(default_factory=list)
    equations: list[str] = field(default_factory=list)
    qa_pairs: list[QAPair] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["block_type"] = self.block_type.value
        return d


# ---------------------------------------------------------------------------
# Classifiers
# ---------------------------------------------------------------------------
_RECALL_RE   = re.compile(r"let.?s recall|summary", re.I)
_GLOSSARY_RE = re.compile(r"glossary|vocabulary|word\s+form", re.I)
_ACTIVITY_RE = re.compile(r"activity|draw|life\s+skills|self\s*assess|creative\s+abil", re.I)
_QA_RE       = re.compile(
    r"answer\s+the\s+following|fill\s+in\s+the\s+blank|choose\s+the\s+correct"
    r"|comprehend|speaking\s+abil|grammar|pronunciation|listening\s+abil"
    r"|true\s+or\s+false|tick\s+the",
    re.I,
)
_INTRO_RE    = re.compile(r"warm.?up|we learn|highlights|lesson\s*:?\s*\d|introduction", re.I)
_WORKED_RE   = re.compile(r"let\s+us\s+make|let\s+us\s+count|skip\s+count|place\s+value|tens|ones", re.I)
_STORY_RE    = re.compile(r"read\s+and\s+enjoy|story|let\s+us\s+read", re.I)

_MCQ_OPTS_RE = re.compile(r"\b[abc]\)\s*\S", re.I)
_BLANK_RE    = re.compile(r"_{3,}")
_IMG_RE      = re.compile(r"!\[.*?\]\((.*?)\)")
_EQ_RE       = re.compile(r"\d+\s*[\+\-×÷=]\s*\d+|\$[^$]+\$")
_Q_NUM_RE    = re.compile(r"^\s*[-–]?\s*(\d+)\s*[.)]\s+(.+)", re.M)


def _classify(heading: str, body: str, subject: str) -> BlockType:
    src = (heading + " " + body[:300]).lower()
    if _RECALL_RE.search(src):   return BlockType.RECALL
    if _GLOSSARY_RE.search(src): return BlockType.GLOSSARY
    if _ACTIVITY_RE.search(src): return BlockType.ACTIVITY
    if _QA_RE.search(src):       return BlockType.QA_ITEM
    if _INTRO_RE.search(src):    return BlockType.INTRO
    if subject == "maths" and _WORKED_RE.search(src): return BlockType.WORKED_EXAMPLE
    if subject == "english" and _STORY_RE.search(src): return BlockType.STORY_SECTION
    return BlockType.CONCEPT


def _extract_qa(body: str) -> list[QAPair]:
    pairs: list[QAPair] = []
    for m in _Q_NUM_RE.finditer(body):
        text = m.group(2).strip()
        if _MCQ_OPTS_RE.search(text):
            fmt  = "mcq"
            opts = re.findall(r"[abc]\)\s*([^abc\n]+)", text, re.I)
            hint = " | ".join(o.strip() for o in opts)
        elif _BLANK_RE.search(text):
            fmt, hint = "fill_blank", ""
        elif re.search(r"\btrue\b|\bfalse\b", text, re.I):
            fmt, hint = "true_false", ""
        else:
            fmt, hint = "short_answer", ""
        q = re.sub(r"\s+[abc]\).*$", "", text, flags=re.I).strip()
        pairs.append(QAPair(number=m.group(1), question=q, answer_hint=hint, qa_format=fmt))
    return pairs


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
class SectionParser(BaseTool):
    """Parse opendataloader markdown output into typed ContentBlocks."""

    name = "section_parser"
    version = "1.0.0"
    tier = ToolTier.SOURCE
    capability = "content_parsing"
    provider = "openmontage"
    stability = ToolStability.PRODUCTION
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies: list[str] = []
    install_instructions = "No external dependencies."
    agent_skills: list[str] = ["pdf-extraction"]
    capabilities = ["markdown_parsing", "block_classification", "qa_extraction"]

    input_schema = {
        "type": "object",
        "required": ["subject"],
        "properties": {
            "subject":    {"type": "string", "minLength": 1},
            "md_path":    {"type": "string"},
            "output_dir": {"type": "string"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "blocks":      {"type": "array"},
            "block_count": {"type": "integer"},
            "output_path": {"type": "string"},
        },
    }

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 0.5

    # --- public helpers -------------------------------------------------------

    def parse_file(self, md_path: Path, subject: str) -> list[ContentBlock]:
        if not md_path.exists():
            raise FileNotFoundError(f"Markdown not found: {md_path}")
        return self._parse(md_path.read_text(encoding="utf-8"), subject)

    def parse_text(self, markdown: str, subject: str) -> list[ContentBlock]:
        return self._parse(markdown, subject)

    # --- core -----------------------------------------------------------------

    def _parse(self, text: str, subject: str) -> list[ContentBlock]:
        parts = re.split(r"^(#{1,6}\s+.+)$", text, flags=re.M)
        blocks: list[ContentBlock] = []
        idx = 0

        # Text before first heading → intro
        if parts and not parts[0].startswith("#"):
            pre = parts[0].strip()
            if pre:
                blocks.append(self._make(idx, "Lesson Introduction", pre, subject))
                idx += 1

        i = 1
        while i < len(parts):
            heading = re.sub(r"^#+\s*", "", parts[i].strip())
            body    = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if heading or body:
                blocks.append(self._make(idx, heading, body, subject))
                idx += 1
            i += 2

        return blocks

    def _make(self, idx: int, heading: str, body: str, subject: str) -> ContentBlock:
        btype      = _classify(heading, body, subject)
        image_refs = _IMG_RE.findall(body)
        equations  = _EQ_RE.findall(body)
        qa_pairs   = _extract_qa(body) if btype in (
            BlockType.QA_ITEM, BlockType.GLOSSARY, BlockType.RECALL
        ) else []
        clean_body = _IMG_RE.sub("", body).strip()
        return ContentBlock(
            block_id   = f"{subject}_block_{idx:03d}",
            block_type = btype,
            heading    = heading,
            body_text  = clean_body,
            image_refs = image_refs,
            equations  = equations,
            qa_pairs   = qa_pairs,
        )

    # --- BaseTool interface ---------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        subject = inputs["subject"]
        if inputs.get("md_path"):
            md_path = Path(inputs["md_path"])
        elif subject in _SUBJECT_MD:
            md_path = _ODL_DIR / _SUBJECT_MD[subject]
        else:
            return ToolResult(
                success=False,
                error=(
                    f"No default markdown is registered for subject {subject!r}. "
                    "Provide md_path for chapter-agnostic ingestion."
                ),
            )
        out_dir = (
            Path(inputs["output_dir"]) if inputs.get("output_dir")
            else _ROOT / "projects" / subject / "artifacts"
        )

        try:
            blocks = self.parse_file(md_path, subject)
        except FileNotFoundError as exc:
            return ToolResult(success=False, error=str(exc))

        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "section_blocks.json"
        serialised = [b.to_dict() for b in blocks]
        out_path.write_text(
            json.dumps({"subject": subject, "blocks": serialised}, indent=2),
            encoding="utf-8",
        )

        return ToolResult(
            success=True,
            data={"blocks": serialised, "block_count": len(blocks),
                  "output_path": str(out_path)},
            artifacts=["extracted_content"],
            cost_usd=0.0,
        )

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {
            "tool": self.name,
            "estimated_cost_usd": 0.0,
            "estimated_runtime_seconds": 0.5,
            "status": self.get_status().value,
            "would_execute": True,
        }

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _cli() -> None:
    ap = argparse.ArgumentParser(description="Parse opendataloader markdown.")
    ap.add_argument(
        "--subject",
        required=True,
        help="Subject label. New subjects must also provide --md-path.",
    )
    ap.add_argument("--md-path", dest="md_path")
    ap.add_argument("--output-dir", dest="output_dir")
    args = ap.parse_args()

    inp: dict[str, Any] = {"subject": args.subject}
    if args.md_path:    inp["md_path"]    = args.md_path
    if args.output_dir: inp["output_dir"] = args.output_dir

    res = SectionParser().execute(inp)
    if res.success:
        print(f"✓ {res.data['block_count']} blocks → {res.data['output_path']}")
        for b in res.data["blocks"]:
            print(f"  [{b['block_type']:16s}] {b['heading'][:55]}"
                  f"  imgs={len(b['image_refs'])} qa={len(b['qa_pairs'])}")
    else:
        print(f"✗ {res.error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _cli()
