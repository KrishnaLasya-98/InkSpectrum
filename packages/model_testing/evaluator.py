import time
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from .providers import get_provider, LLMProvider
from .models import get_model_config, ModelConfig


class TestStatus(Enum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class TestResult:
    model_id: str
    task_name: str
    status: TestStatus
    score: float = 0.0
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    output: str = ""
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ModelEvaluator:
    def __init__(self):
        self.results: List[TestResult] = []
    
    async def run_single_test(
        self,
        provider: LLMProvider,
        model_config: ModelConfig,
        task_name: str,
        messages: List[Dict[str, str]],
        scorer_func=None,
        timeout: float = 120.0
    ) -> TestResult:
        start_time = time.time()
        try:
            response = await asyncio.wait_for(
                provider.complete(messages=messages, model=model_config.model_id),
                timeout=timeout
            )
            latency_ms = (time.time() - start_time) * 1000
            
            output_text = ""
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0
            
            if "choices" in response and response["choices"]:
                output_text = response["choices"][0]["message"]["content"]
            if "usage" in response:
                usage = response["usage"]
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", 0)
            
            score = 0.0
            if scorer_func:
                score = scorer_func(output_text)
            
            cost = (
                (prompt_tokens / 1_000_000) * model_config.input_cost_per_1m +
                (completion_tokens / 1_000_000) * model_config.output_cost_per_1m
            )
            
            return TestResult(
                model_id=model_config.model_id,
                task_name=task_name,
                status=TestStatus.PASS,
                score=score,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=cost,
                output=output_text[:5000],
            )
        except asyncio.TimeoutError:
            return TestResult(
                model_id=model_config.model_id,
                task_name=task_name,
                status=TestStatus.TIMEOUT,
                latency_ms=(time.time() - start_time) * 1000,
                error=f"Request timed out after {timeout}s"
            )
        except Exception as e:
            return TestResult(
                model_id=model_config.model_id,
                task_name=task_name,
                status=TestStatus.ERROR,
                latency_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )
    
    async def run_benchmark(
        self,
        provider_name: str,
        model_ids: List[str],
        task_name: str,
        messages: List[Dict[str, str]],
        scorer_func=None
    ) -> List[TestResult]:
        provider = get_provider(provider_name)
        results = []
        for model_id in model_ids:
            config = get_model_config(model_id)
            result = await self.run_single_test(
                provider=provider,
                model_config=config,
                task_name=task_name,
                messages=messages,
                scorer_func=scorer_func
            )
            results.append(result)
            self.results.append(result)
        return results
