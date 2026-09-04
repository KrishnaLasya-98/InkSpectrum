import os
import httpx
from typing import List, Dict, Any, Optional
from .base import LLMProvider, RateLimits, ModelPricing


class DeepSeekProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            api_key=api_key or os.environ.get("DEEPSEEK_API_KEY", ""),
            base_url="https://api.deepseek.com/v1"
        )
        self.capabilities = ProviderCapabilities(
            supports_streaming=True,
            supports_function_calling=True,
            max_context_window=65536
        )
    
    async def complete(self, messages, model="deepseek-v4-flash", temperature=0.7, max_tokens=4096, **kwargs):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    **kwargs
                },
                timeout=120.0
            )
            response.raise_for_status()
            return response.json()
    
    def get_rate_limits(self, model):
        return RateLimits(rpm=100, rpd=None, tpm=100000)
    
    def get_pricing(self, model):
        return ModelPricing(input_per_1m=0.44, output_per_1m=0.22)
    
    def get_available_models(self):
        return ["deepseek-v4-flash"]
