from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


@dataclass
class RateLimits:
    rpm: Optional[int] = None
    rpd: Optional[int] = None
    tpm: Optional[int] = None


@dataclass
class ModelPricing:
    input_per_1m: float = 0.0
    output_per_1m: float = 0.0


@dataclass
class ProviderCapabilities:
    supports_streaming: bool = False
    supports_function_calling: bool = False
    max_context_window: int = 8192


class LLMProvider(ABC):
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url
        self.capabilities = ProviderCapabilities()
    
    @abstractmethod
    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def get_rate_limits(self, model: str) -> RateLimits:
        pass
    
    @abstractmethod
    def get_pricing(self, model: str) -> ModelPricing:
        pass
    
    @abstractmethod
    def get_available_models(self) -> List[str]:
        pass
