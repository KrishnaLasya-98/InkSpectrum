from typing import List
from .base import BaseEvaluator
from ..schemas import EvaluationResult, ModelResult, TestCase

SAMPLE_PDF_TEXT = """
Chapter 1: Food
Where does it come from?
1.1 Food Variety
Different states in India have different cuisines.
Pattol Bai from Kerala prepared sadya for a function.
1.2 Food Ingredients
Food comes from plants and animals.
Plants give us fruits, vegetables, grains, pulses.
Animals give us milk, eggs, meat, honey.
1.3 Animal Products
Dairy products come from cows, buffaloes, goats.
Eggs come from hens, ducks.
1.4 Plant Products
Rice, wheat, maize are grains.
Spinach, carrot, potato are vegetables.
Mango, banana, apple are fruits.
"""

EXTRACTION_PROMPT = f"""Extract the key educational concepts from this textbook chapter. List:
1. Main topic
2. 5 key subtopics
3. 3 learning objectives
4. Any diagrams or visual aids mentioned

Text:
{SAMPLE_PDF_TEXT}
"""


class ExtractionEvaluator(BaseEvaluator):
    def __init__(self):
        super().__init__("extraction")

    async def run(self, client, model: str, test_cases: List[TestCase]) -> EvaluationResult:
        results = []
        for tc in test_cases:
            result = await client.generate(model, EXTRACTION_PROMPT)
            results.append(result)

        score = 0.0
        keywords = []
        if results and results[0].success:
            response = results[0].response.lower()
            keywords = ["food", "plants", "animals", "ingredients", "crops"]
            matches = sum(1 for kw in keywords if kw in response)
            score = matches / len(keywords)

        return EvaluationResult(
            task=self.name,
            model=model,
            provider=results[0].provider if results else "unknown",
            score=score,
            details={"keywords_checked": keywords},
            results=results,
        )
