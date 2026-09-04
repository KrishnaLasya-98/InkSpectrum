from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, Dict
import httpx
from ..schemas import ModelResult

class BaseLLMClient(ABC):
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=60.0)

    @abstractmethod
    async def generate(self, model: str, prompt: str, **kwargs) -> ModelResult:
        pass

    @abstractmethod
    async def stream(self, model: str, prompt: str, **kwargs) -> AsyncIterator[str]:
        pass

    @abstractmethod
    def get_rate_limits(self, model: str) -> Dict[str, int]:
        pass

    async def close(self):
        await self.client.aclose()
