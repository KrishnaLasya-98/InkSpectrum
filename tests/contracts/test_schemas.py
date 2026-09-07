"""Schema validation tests using jsonschema + committed JSON Schema files."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _load_schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class TestBaseToolSchema:
    def test_validates_minimal_metadata(self):
        from jsonschema import validate
        schema = _load_schema(Path("schemas/tools/base_tool.schema.json"))
        instance = {
            "name": "test_tool",
            "version": "1.0.0",
            "tier": "core",
            "capability": "testing",
            "provider": "test",
            "runtime": "local",
            "stability": "production",
        }
        validate(instance=instance, schema=schema)

    def test_rejects_invalid_tier(self):
        from jsonschema import ValidationError, validate
        schema = _load_schema(Path("schemas/tools/base_tool.schema.json"))
        instance = {
            "name": "bad",
            "version": "1.0.0",
            "tier": "not_a_tier",
            "capability": "x",
            "provider": "x",
            "runtime": "local",
            "stability": "production",
        }
        with pytest.raises(ValidationError):
            validate(instance=instance, schema=schema)


class TestPipelineSchema:
    def test_validates_framework_smoke(self):
        import yaml
        from jsonschema import validate
        schema = _load_schema(Path("schemas/pipelines/pipeline.schema.json"))
        manifest = yaml.safe_load(Path("pipeline_defs/framework_smoke.yaml").read_text())
        validate(instance=manifest, schema=schema)

    def test_validates_english_classroom(self):
        import yaml
        from jsonschema import validate
        schema = _load_schema(Path("schemas/pipelines/pipeline.schema.json"))
        manifest = yaml.safe_load(Path("pipeline_defs/english_classroom.yaml").read_text())
        validate(instance=manifest, schema=schema)
