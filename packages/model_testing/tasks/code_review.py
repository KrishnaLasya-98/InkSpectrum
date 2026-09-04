from typing import List, Dict, Any, Optional


class CodeReviewTask:
    name = "code_review"
    description = "Review a Python scene renderer for bugs and improvements"
    
    SAMPLE_CODE = """
import manim as mn

class SceneRenderer(mn.Scene):
    def construct(self):
        title = mn.Text("Hello World")
        self.play(mn.Create(title))
        self.wait(2)
"""
    
    def get_messages(self, code: Optional[str] = None) -> List[Dict[str, str]]:
        target_code = code or self.SAMPLE_CODE
        return [
            {
                "role": "system",
                "content": "You are an expert Python code reviewer specializing in Manim animations. Review code for bugs, performance issues, and best practices."
            },
            {
                "role": "user",
                "content": f"Review this Manim scene renderer code. Identify bugs, performance issues, and suggest improvements:\n\n```python\n{target_code}\n```"
            }
        ]
    
    def score(self, output: str) -> float:
        score = 0.0
        if "bug" in output.lower() or "issue" in output.lower() or "fix" in output.lower():
            score += 1.5
        if "performance" in output.lower() or "optimize" in output.lower():
            score += 1.0
        if "best practice" in output.lower() or "recommendation" in output.lower():
            score += 1.0
        if "manim" in output.lower():
            score += 0.5
        if len(output.split()) > 100:
            score += 1.0
        return min(score, 5.0)
