"""Inventory authored HyperFrames compositions without executing their scripts.

Reads whole HTML files, including inline scripts, and records media references
and template vocabulary. Counts describe authored files, not verified pixels
in historic MP4s; JavaScript-created elements are explicitly reported separately.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re


class CompositionParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = Counter()
        self.classes = Counter()
        self.modes = Counter()
        self.media = []
        self.compositions = []
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        self.tags[tag] += 1
        if tag == "script" and data.get("src"):
            self.scripts.append(data["src"])
        self.classes.update((data.get("class") or "").split())
        for key in ("data-mode", "data-section-type", "data-template-id"):
            if data.get(key):
                self.modes[data[key]] += 1
        if data.get("data-composition-id"):
            self.compositions.append({key: data[key] for key in data if key in {
                "data-composition-id", "data-duration", "data-width", "data-height",
                "data-template-id", "data-template-version",
            }})
        if tag in {"video", "audio", "img"}:
            self.media.append({
                "tag": tag, "src": data.get("src", ""),
                "start": data.get("data-start"), "duration": data.get("data-duration"),
                "muted": "muted" in data, "loop": "loop" in data,
            })


def inspect_composition(path: Path, root: Path) -> dict:
    source = path.read_text(encoding="utf-8-sig")
    parser = CompositionParser()
    parser.feed(source)
    scripts = []
    combined_source = source
    for reference in parser.scripts:
        if re.match(r"^(https?:|data:)", reference):
            continue
        script_path = (path.parent / reference.split("?", 1)[0]).resolve()
        if not script_path.is_relative_to(root.resolve()) or not script_path.is_file():
            continue
        script = script_path.read_text(encoding="utf-8-sig")
        scripts.append({"path": script_path.relative_to(root.resolve()).as_posix(),
                        "sha256": hashlib.sha256(script.encode()).hexdigest(),
                        "lines": len(script.splitlines())})
        combined_source += "\n" + script
    refs = sorted(set(re.findall(
        r'''(?:[\w./-]+\.(?:mp4|webm|wav|mp3|png|jpg|jpeg|svg|webp))''', source,
        re.IGNORECASE,
    )))
    missing = []
    for item in parser.media:
        ref = item["src"]
        if ref and not re.match(r"^(https?:|data:|blob:)", ref):
            if not (path.parent / ref.split("?", 1)[0]).is_file():
                missing.append(ref)
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(source.encode()).hexdigest(),
        "lines": len(source.splitlines()), "compositions": parser.compositions,
        "static_media_counts": dict(Counter(item["tag"] for item in parser.media)),
        "static_media": parser.media, "missing_static_media": sorted(set(missing)),
        "all_literal_media_references": refs,
        "classes": dict(sorted(parser.classes.items())), "modes": dict(parser.modes),
        "local_scripts_read": scripts,
        "dynamic_dom": any(token in combined_source for token in ("innerHTML", "createElement", "insertAdjacentHTML")),
        "gsap_timeline": "gsap.timeline" in source,
        "word_highlight_indicators": [token for token in
            ("caption-word", "word.start", "word.end", "word.start_seconds", "active-word", "capStart")
            if token in source],
        "unmuted_video_count": sum(item["tag"] == "video" and not item["muted"] for item in parser.media),
        "looped_video_count": sum(item["tag"] == "video" and item["loop"] for item in parser.media),
    }


def inventory(root: Path) -> dict:
    paths = sorted(path for path in root.rglob("*.html") if
        "node_modules" not in path.parts and
        any("hyperframes" in part.lower() for part in path.relative_to(root).parts))
    results, errors = [], []
    for path in paths:
        try:
            results.append(inspect_composition(path, root))
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append({"path": str(path), "error": str(exc)})
    return {
        "version": "1.0", "scope": "all project HyperFrames HTML files excluding node_modules",
        "limitation": "Authored-source inventory; historical render-to-source identity and encoded appearance require separate verification.",
        "compositions": results, "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("projects", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = inventory(args.projects.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"files": len(report["compositions"]), "errors": report["errors"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
