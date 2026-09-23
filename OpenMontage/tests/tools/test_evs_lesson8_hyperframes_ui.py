"""Regression checks for the dynamic EVS Lesson 8 HyperFrames contract."""
from __future__ import annotations

import json
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2] / "projects" / "evs-lesson-8"
BASELINE_HTML = PROJECT / "one-minute-preview" / "hyperframes" / "index.html"
FULL_HTML = PROJECT / "full-hyperframes" / "index.html"
CONTRACT = PROJECT / "artifacts" / "hyperframes_ui_contract.json"


def _css_rules(html: str) -> dict[str, dict[str, str]]:
    style = re.search(r"<style>(.*?)</style>", html, flags=re.DOTALL)
    assert style
    rules: dict[str, dict[str, str]] = {}
    for selector_text, body in re.findall(r"([^{}]+)\{([^{}]*)\}", style.group(1)):
        declarations = {}
        for declaration in body.split(";"):
            if ":" in declaration:
                name, value = declaration.split(":", 1)
                declarations[name.strip()] = re.sub(r"\s+", " ", value.strip())
        for selector in selector_text.split(","):
            rules[selector.strip()] = declarations
    return rules


def _resolve(value: str | None, rules: dict[str, dict[str, str]]) -> str | None:
    if value is None:
        return None
    for _ in range(4):
        match = re.search(r"var\((--[\w-]+)\)", value)
        if not match:
            break
        value = value.replace(match.group(0), rules[":root"][match.group(1)])
    return value


def _timeline() -> dict:
    raw = (PROJECT / "full-hyperframes" / "timeline-data.js").read_text(encoding="utf-8")
    return json.loads(raw.split("=", 1)[1].strip().rstrip(";"))


def test_full_hyperframes_matches_approved_ui_contract():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    baseline = _css_rules(BASELINE_HTML.read_text(encoding="utf-8"))
    full_html = FULL_HTML.read_text(encoding="utf-8")
    full = _css_rules(full_html)
    for selector, expected in contract["shared_selectors"].items():
        assert selector in baseline and selector in full
        for property_name, expected_value in expected.items():
            expected_value = _resolve(expected_value, baseline)
            assert _resolve(baseline[selector].get(property_name), baseline) == expected_value
            assert _resolve(full[selector].get(property_name), full) == expected_value
    for selector in ("#animal-lion", "#animal-elephant", "#animal-tiger"):
        assert selector in baseline and selector in full
    for class_name in ("title-card", "title-card-inner", "section-label", "highlights-box", "caption-card", "caption-phrase", "topic-card", "animal-name", "footer-card", "footer-inner", "motion", "wash", "graphics-bg", "corner"):
        assert f".{class_name}" in baseline and f".{class_name}" in full
    assert 'data-media-policy="graphics-only"' in full_html
    assert "progressive_word_reveal" in FULL_HTML.read_text(encoding="utf-8") or "visible_word_indices" in full_html


def test_full_metadata_uses_dynamic_duration_and_canonical_contract():
    metadata = json.loads((PROJECT / "full-hyperframes" / "hyperframes.json").read_text(encoding="utf-8"))
    timeline = _timeline()
    assert metadata["duration"] == timeline["duration"] == 402.404
    assert metadata["width"] == 1920 and metadata["height"] == 1080 and metadata["fps"] == 30
    assert metadata["baseline"]["style_lock"] == "one-minute-approved-ui"


def test_full_timeline_has_source_provenance_progressive_captions_and_slogan():
    data = _timeline()
    assert len(data["sections"]) == 16
    assert len(data["exercises"]) == 13
    assert all(section["title_source_line_ids"] and section["subtitle_source_line_ids"] for section in data["sections"])
    assert all(section["title_card"]["media_policy"] == "graphics_only" for section in data["sections"])
    assert all(phrase["steps"] and phrase["steps"][0]["visible_word_indices"] for section in data["sections"] for phrase in section["caption_phrases"])
    assert data["slogan"] == ["Animals also have feelings. Do not hurt animals. They will be friendly to us. Protect animals."]
