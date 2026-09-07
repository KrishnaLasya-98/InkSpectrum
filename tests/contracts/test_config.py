"""Contract tests for lib.config_model.InkSpectrumConfig."""

from __future__ import annotations

from pathlib import Path

import pytest

from lib.config_model import InkSpectrumConfig, LLMConfig, BudgetConfig


class TestInkSpectrumConfig:
    def test_defaults_load(self):
        cfg = InkSpectrumConfig.load(config_path=Path("/nonexistent.yaml"))
        assert cfg.llm.provider == "groq"
        assert cfg.llm.model == "openai/gpt-oss-120b"
        assert cfg.budget.default_per_pipeline_usd == 2.00
        assert cfg.checkpoint.auto_resume is True

    def test_sub_models_validate(self):
        llm = LLMConfig(api_key_env="MY_KEY")
        assert llm.api_key_env == "MY_KEY"
        assert llm.temperature == 0.3

        b = BudgetConfig(default_per_pipeline_usd=5.0, enforce_hard_cap=False)
        assert b.default_per_pipeline_usd == 5.0
        assert b.enforce_hard_cap is False

    def test_loads_yaml_when_present(self, tmp_path: Path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            "llm:\n  model: custom-model\nbudget:\n  default_per_pipeline_usd: 1.5\n",
            encoding="utf-8",
        )
        cfg = InkSpectrumConfig.load(config_path=cfg_file)
        assert cfg.llm.model == "custom-model"
        assert cfg.budget.default_per_pipeline_usd == 1.5
