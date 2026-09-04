import os
import httpx
from typing import List, Dict, Any, Optional
from .base import LLMProvider, RateLimits, ModelPricing


class GroqProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            api_key=api_key or os.environ.get("GROQ_API_KEY", ""),
            base_url="https://api.groq.com/openai/v1"
        )
        self.capabilities = ProviderCapabilities(
            supports_streaming=True,
            supports_function_calling=True,
            max_context_window=8192
        )
    
    async def complete(self, messages, model="openai/gpt-oss-120b", temperature=0.7, max_tokens=4096, **kwargs):
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
        return RateLimits(rpm=30, rpd=1000, tpm=8000)
    
    def get_pricing(self, model):
        pricing = {
            "openai/gpt-oss-120b": ModelPricing(input_per_1m=0.15, output_per_1m=0.60),
            "openai/gpt-oss-20b": ModelPricing(input_per_1m=0.15, output_per_1m=0.60),
            "qwen3-32b": ModelPricing(input_per_1m=0.29, output_per_1m=0.59),
            "qwen3-8b": ModelPricing(input_per_1m=0.15, output_per_1m=0.47),
        }
        return pricing.get(model, ModelPricing())
    
    def get_available_models(self):
        return [
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "qwen3-32b",
            "qwen3-8b",
        ]
