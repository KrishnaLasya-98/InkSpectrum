import os
import httpx
from typing import List, Dict, Any, Optional
from .base import LLMProvider, RateLimits, ModelPricing


class AnyAPIProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            api_key=api_key or os.environ.get("ANYAPI_API_KEY", ""),
            base_url="https://api.anyapi.ai/v1"
        )
        self.capabilities = ProviderCapabilities(
            supports_streaming=False,
            supports_function_calling=False,
            max_context_window=8192
        )
    
    async def complete(self, messages, model="qwen3-coder:free", temperature=0.7, max_tokens=4096, **kwargs):
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
        return RateLimits(rpm=60, rpd=None, tpm=100000)
    
    def get_pricing(self, model):
        if ":free" in model:
            return ModelPricing()
        return ModelPricing(input_per_1m=0.50, output_per_1m=1.50)
    
    def get_available_models(self):
        return [
            "qwen3-coder:free",
            "qwen3.8-27b",
            "nvidia/nemotron-nano-9b-v2:free",
            "google/gemma-4-26b-a4b-it:free",
            "nvidia/nemotron-3-ultra-550b-a55b:free",
        ]
