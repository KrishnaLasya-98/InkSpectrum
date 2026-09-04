from typing import List
from .base import BaseEvaluator
from ..schemas import EvaluationResult, ModelResult, TestCase

SCRIPT_PROMPT = """Generate a 60-second educational video script for Class 4 EVS on the topic "Food Sources".
Format:
[Scene 1: Hook]
Narration: ...
Visual: ...

[Scene 2: Main Content]
Narration: ...
Visual: ...

Requirements:
- Simple language for 9-10 year olds
- 3 scenes max
- Include 1 question to engage students
"""


class ScriptGenEvaluator(BaseEvaluator):
    def __init__(self):
        super().__init__("script_generation")

    async def run(self, client, model: str, test_cases: List[TestCase]) -> EvaluationResult:
        results = []
        for tc in test_cases:
            result = await client.generate(model, SCRIPT_PROMPT)
            results.append(result)

        score = 0.0
        criteria = []
        if results and results[0].success:
            response = results[0].response.lower()
            criteria = ["scene", "narration", "visual", "question"]
            matches = sum(1 for c in criteria if c in response)
            score = matches / len(criteria)

        return EvaluationResult(
            task=self.name,
            model=model,
            provider=results[0].provider if results else "unknown",
            score=score,
            details={"criteria_checked": criteria},
            results=results,
        )
