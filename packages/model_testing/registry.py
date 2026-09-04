from typing import Dict, List, Optional
from .providers import PROVIDER_REGISTRY, get_provider
from .models import get_model_config, list_models, MODEL_CATALOG
from .tasks import TASK_REGISTRY


class ModelRegistry:
    def __init__(self):
        self.providers = PROVIDER_REGISTRY
        self.models = MODEL_CATALOG
        self.tasks = TASK_REGISTRY
    
    def get_provider(self, name: str, api_key: Optional[str] = None):
        return get_provider(name, api_key)
    
    def get_model(self, model_id: str):
        return get_model_config(model_id)
    
    def list_providers(self) -> List[str]:
        return list(self.providers.keys())
    
    def list_models(self, provider: Optional[str] = None, free_only: bool = False) -> List:
        return list_models(provider=provider, free_only=free_only)
    
    def list_tasks(self) -> List[str]:
        return list(self.tasks.keys())
    
    def get_task(self, name: str):
        return self.tasks[name]


registry = ModelRegistry()
