import os
import httpx
from typing import List, Dict, Any, Optional
from .base import LLMProvider, RateLimits, ModelPricing


class TogetherProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            api_key=api_key or os.environ.get("TOGETHER_API_KEY", ""),
            base_url="https://api.together.xyz/v1"
        )
        self.capabilities = ProviderCapabilities(
            supports_streaming=True,
            supports_function_calling=True,
            max_context_window=8192
        )
    
    async def complete(self, messages, model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free", temperature=0.7, max_tokens=4096, **kwargs):
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
        return RateLimits(rpm=60, rpd=None, tpm=60000)
    
    def get_pricing(self, model):
        if "Free" in model:
            return ModelPricing()
        return ModelPricing(input_per_1m=0.14, output_per_1m=0.28)
    
    def get_available_models(self):
        return [
            "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
            "deepseek-ai/DeepSeek-V4-Flash-0731",
        ]
