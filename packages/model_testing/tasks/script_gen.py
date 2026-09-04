from typing import List, Dict, Any


class ScriptGenTask:
    name = "script_generation"
    description = "Generate a 2-minute educational script from textbook content"
    
    def get_messages(self, content: str) -> List[Dict[str, str]]:
        return [
            {
                "role": "system",
                "content": "You are an expert educational scriptwriter. Create engaging, clear narration scripts for educational videos."
            },
            {
                "role": "user",
                "content": f"Based on this textbook content, write a 2-minute narration script (approximately 300 words) for an educational video. Include: opening hook, 3 key points, and a closing summary.\n\nContent:\n{content[:3000]}"
            }
        ]
    
    def score(self, output: str) -> float:
        score = 0.0
        word_count = len(output.split())
        if 200 <= word_count <= 400:
            score += 2.0
        elif 150 <= word_count <= 500:
            score += 1.0
        if "hook" in output.lower() or "introduction" in output.lower() or "start" in output.lower():
            score += 1.0
        if any(marker in output.lower() for marker in ["first", "second", "third", "1.", "2.", "3."]):
            score += 1.0
        if "summary" in output.lower() or "conclusion" in output.lower() or "recap" in output.lower():
            score += 1.0
        return min(score, 5.0)
