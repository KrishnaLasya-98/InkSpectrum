"""Contract tests for lib.pipeline_loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from lib.pipeline_loader import load_manifest, PipelineManifest, StageSpec


class TestPipelineLoader:
    def test_loads_framework_smoke(self):
        path = Path("pipeline_defs/framework_smoke.yaml")
        if not path.exists():
            pytest.skip(f"Manifest not found: {path}")
        manifest = load_manifest(path)
        assert isinstance(manifest, PipelineManifest)
        assert manifest.name == "framework_smoke"
        assert len(manifest.stages) >= 2
        assert manifest.budget_default_usd == 0.10

    def test_loads_english_classroom(self):
        path = Path("pipeline_defs/english_classroom.yaml")
        if not path.exists():
            pytest.skip(f"Manifest not found: {path}")
        manifest = load_manifest(path)
        assert manifest.name == "english_classroom"
        stage_names = [s.name for s in manifest.stages]
        assert "research" in stage_names
        assert "script" in stage_names
        assert "assets" in stage_names
        assert "compose" in stage_names

    def test_stage_lookup(self):
        path = Path("pipeline_defs/framework_smoke.yaml")
        if not path.exists():
            pytest.skip(f"Manifest not found: {path}")
        manifest = load_manifest(path)
        s = manifest.stage("research")
        assert isinstance(s, StageSpec)
        assert s.name == "research"
        with pytest.raises(KeyError):
            manifest.stage("nonexistent")

    def test_invalid_yaml_raises(self, tmp_path: Path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("name: test\nstages: 'not a list'\n", encoding="utf-8")
        with pytest.raises(Exception):
            load_manifest(bad)
