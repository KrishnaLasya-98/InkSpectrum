from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

class ModelResult(BaseModel):
    model: str
    provider: str
    latency_ms: float
    tokens_used: int
    success: bool
    error: Optional[str] = None
    response: Optional[str] = None
    timestamp: datetime = datetime.now()

class EvaluationResult(BaseModel):
    task: str
    model: str
    provider: str
    score: float
    details: Dict[str, Any]
    results: List[ModelResult]
    timestamp: datetime = datetime.now()

class TestCase(BaseModel):
    name: str
    prompt: str
    expected_criteria: Dict[str, Any]
