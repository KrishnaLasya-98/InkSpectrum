from typing import Dict, AsyncIterator
from .base import BaseLLMClient
from ..schemas import ModelResult
import time

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

class GroqClient(BaseLLMClient):
    def __init__(self, api_key: str):
        super().__init__(api_key, GROQ_URL)

    async def generate(self, model: str, prompt: str, **kwargs) -> ModelResult:
        start = time.time()
        try:
            response = await self.client.post(
                self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    **kwargs,
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            latency = (time.time() - start) * 1000
            return ModelResult(
                model=model,
                provider="groq",
                latency_ms=latency,
                tokens_used=usage.get("total_tokens", 0),
                success=True,
                response=content,
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            return ModelResult(
                model=model,
                provider="groq",
                latency_ms=latency,
                tokens_used=0,
                success=False,
                error=str(e),
            )

    async def stream(self, model: str, prompt: str, **kwargs) -> AsyncIterator[str]:
        response = await self.client.post(
            self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
                **kwargs,
            },
        )
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                yield line[6:]

    def get_rate_limits(self, model: str) -> Dict[str, int]:
        return {"rpm": 30, "rpd": 1000, "tpm": 8000}
