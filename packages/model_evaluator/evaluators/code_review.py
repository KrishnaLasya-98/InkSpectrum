from typing import List
from .base import BaseEvaluator
from ..schemas import EvaluationResult, ModelResult, TestCase

CODE_SNIPPET = """
def render_scene(scene):
    # TODO: implement
    pass
"""

CODE_REVIEW_PROMPT = f"""Review this Python code for a Manim scene renderer. Identify:
1. 3 bugs or issues
2. 2 improvements
3. Overall quality score (1-5)

Code:
{CODE_SNIPPET}
"""


class CodeReviewEvaluator(BaseEvaluator):
    def __init__(self):
        super().__init__("code_review")

    async def run(self, client, model: str, test_cases: List[TestCase]) -> EvaluationResult:
        results = []
        for tc in test_cases:
            result = await client.generate(model, CODE_REVIEW_PROMPT)
            results.append(result)

        score = 0.0
        criteria = []
        if results and results[0].success:
            response = results[0].response.lower()
            criteria = ["bug", "improvement", "score"]
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
