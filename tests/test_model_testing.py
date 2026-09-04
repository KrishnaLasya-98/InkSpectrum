import pytest
from packages.model_testing.models.config import ModelConfig, MODEL_CATALOG
from packages.model_testing.models.registry import get_model_config, list_models
from packages.model_testing.providers import PROVIDER_REGISTRY, get_provider
from packages.model_testing.tasks import TASK_REGISTRY


def test_model_config_creation():
    config = ModelConfig(
        model_id="test-model",
        provider="groq",
        display_name="Test Model",
        context_window=8192,
        rpm_limit=30,
        input_cost_per_1m=0.1,
        output_cost_per_1m=0.2,
    )
    assert config.model_id == "test-model"
    assert config.provider == "groq"
    assert config.rpm_limit == 30


def test_model_catalog_has_entries():
    assert len(MODEL_CATALOG) > 0
    assert "qwen3-coder:free" in MODEL_CATALOG
    assert "openai/gpt-oss-120b" in MODEL_CATALOG


def test_get_model_config():
    config = get_model_config("qwen3-coder:free")
    assert config.provider == "anyapi"
    assert config.supports_free_tier is True


def test_list_models_free_only():
    models = list_models(free_only=True)
    assert all(m.supports_free_tier for m in models)
    assert len(models) > 0


def test_provider_registry():
    assert "groq" in PROVIDER_REGISTRY
    assert "anyapi" in PROVIDER_REGISTRY
    assert "together" in PROVIDER_REGISTRY
    assert "deepseek" in PROVIDER_REGISTRY


def test_get_provider():
    provider = get_provider("groq")
    assert provider is not None
    assert provider.base_url == "https://api.groq.com/openai/v1"


def test_task_registry():
    assert "extraction" in TASK_REGISTRY
    assert "script_gen" in TASK_REGISTRY
    assert "code_review" in TASK_REGISTRY


def test_extraction_task():
    task_cls = TASK_REGISTRY["extraction"]
    task = task_cls()
    messages = task.get_messages("Test PDF content about science.")
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


def test_script_gen_task():
    task_cls = TASK_REGISTRY["script_gen"]
    task = task_cls()
    messages = task.get_messages("Content about math.")
    assert len(messages) == 2
    assert "script" in messages[1]["content"].lower() or "narration" in messages[1]["content"].lower()


def test_code_review_task():
    task_cls = TASK_REGISTRY["code_review"]
    task = task_cls()
    messages = task.get_messages()
    assert len(messages) == 2
    assert "review" in messages[1]["content"].lower()


def test_scoring_functions():
    extraction = TASK_REGISTRY["extraction"]()
    script = TASK_REGISTRY["script_gen"]()
    code_review = TASK_REGISTRY["code_review"]()
    
    assert extraction.score("This covers key concepts and definitions for learning objectives.") > 0
    assert script.score("Introduction hook. First point. Second point. Third point. Summary.") > 0
    assert code_review.score("There is a bug in the code. Performance can be improved. Best practice: use proper naming.") > 0
