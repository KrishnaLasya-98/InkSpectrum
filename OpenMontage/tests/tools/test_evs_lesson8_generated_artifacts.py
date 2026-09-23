"""Generated-plan, coverage, asset, and baseline regression checks."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2] / "projects" / "evs-lesson-8"


def _load_validator(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, PROJECT / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _timeline() -> dict:
    raw = (PROJECT / "full-hyperframes" / "timeline-data.js").read_text(encoding="utf-8")
    return json.loads(raw.split("=", 1)[1].strip().rstrip(";"))


def test_generated_validator_and_baseline_comparator_pass():
    validator = _load_validator("evs_generated_validator", "validate_hyperframes.py")
    comparator = _load_validator("evs_baseline_comparator", "compare_hyperframes_baseline.py")
    assert validator.validate()["valid"]
    assert comparator.compare()["valid"]


def test_coverage_audit_has_exact_source_lines_and_manual_boundary_checks():
    data = _timeline()
    audit = data["coverage_audit"]
    assert audit["source_line_count"] == 79
    assert audit["covered_source_line_count"] == 79
    assert audit["uncovered_source_lines"] == []
    assert len(audit["image_references"]) == 27
    assert len(audit["manual_frame_checks"]) >= 16


def test_asset_report_records_observed_matches_candidates_and_uncertainty():
    report = _timeline()["coverage_audit"]["asset_report"]
    assert report["matches"]
    assert report["stock_candidates"]
    assert report["mismatches"]
    assert all(item["observed_frame_checked"] for item in report["matches"])
