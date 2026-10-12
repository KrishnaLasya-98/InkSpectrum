"""Compile reviewed questions into spoken parts and explicit silent pauses."""
import math


def build_exercise_delivery(text, questions):
    text = " ".join(str(text).split())
    parts, cursor = [], 0
    for question in questions:
        prompt = " ".join(str(question.get("question", "")).split())
        pause = float(question.get("thinking_pause_seconds", 0))
        if not math.isfinite(pause) or not 0 <= pause <= 60:
            raise ValueError("Thinking pause must be between 0 and 60 seconds")
        index = text.find(prompt, cursor) if prompt else -1
        if index < 0:
            raise ValueError("Exercise question is absent from ordered narration")
        end = index + len(prompt)
        # Do not accept an accidental substring inside a different word.
        if (index and text[index-1].isalnum()) or (end < len(text) and text[end].isalnum()):
            raise ValueError("Exercise question does not match a complete narration phrase")
        part = text[cursor:end].strip()
        if part:
            parts.append({"text": part, "pause_after_seconds": pause})
        cursor = end
    tail = text[cursor:].strip()
    if tail:
        parts.append({"text": tail, "pause_after_seconds": 0})
    return parts
