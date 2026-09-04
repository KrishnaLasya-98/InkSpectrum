from .config import MODEL_CATALOG, ModelConfig


def get_model_config(model_id: str) -> ModelConfig:
    if model_id not in MODEL_CATALOG:
        raise ValueError(f"Unknown model: {model_id}")
    return MODEL_CATALOG[model_id]


def list_models(provider: Optional[str] = None, free_only: bool = False) -> List[ModelConfig]:
    models = list(MODEL_CATALOG.values())
    if provider:
        models = [m for m in models if m.provider == provider]
    if free_only:
        models = [m for m in models if m.supports_free_tier]
    return models
