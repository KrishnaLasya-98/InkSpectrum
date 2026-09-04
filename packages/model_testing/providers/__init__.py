from .base import LLMProvider, RateLimits, ModelPricing, ProviderCapabilities
from .groq import GroqProvider
from .anyapi import AnyAPIProvider
from .together import TogetherProvider
from .deepseek import DeepSeekProvider


PROVIDER_REGISTRY = {
    "groq": GroqProvider,
    "anyapi": AnyAPIProvider,
    "together": TogetherProvider,
    "deepseek": DeepSeekProvider,
}


def get_provider(name: str, api_key: Optional[str] = None) -> LLMProvider:
    provider_class = PROVIDER_REGISTRY.get(name)
    if not provider_class:
        raise ValueError(f"Unknown provider: {name}")
    return provider_class(api_key=api_key)
