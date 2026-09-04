from abc import ABC, abstractmethod
from typing import List
from ..schemas import EvaluationResult, ModelResult, TestCase

class BaseEvaluator(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def run(self, client, model: str, test_cases: List[TestCase]) -> EvaluationResult:
        pass
