"""Retry utilities with exponential backoff and jitter."""

from __future__ import annotations

import random
import time
from functools import wraps
from typing import Any, Callable, TypeVar

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
)

T = TypeVar("T")


def retry_on_llm_error(
    max_attempts: int = 3,
    min_wait: float = 2.0,
    max_wait: float = 30.0,
):
    """Decorator for LLM calls with exponential backoff and jitter.

    Retries on common transient errors: rate limits, timeouts, server errors.
    """
    return retry(
        retry=retry_if_exception_type((TimeoutError, ConnectionError, OSError)),
        wait=wait_exponential_jitter(initial=min_wait, max=max_wait),
        stop=stop_after_attempt(max_attempts),
        reraise=True,
    )


def retry_with_backoff(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
):
    """Generic retry decorator with exponential backoff."""
    return retry(
        retry=retry_if_exception_type(exceptions),
        wait=wait_exponential_jitter(initial=min_wait, max=max_wait),
        stop=stop_after_attempt(max_attempts),
        reraise=True,
    )


class RateLimiter:
    """Simple token bucket rate limiter."""

    def __init__(self, rate: float, capacity: int = 1):
        self.rate = rate  # tokens per second
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()

    def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens. Returns True if successful."""
        now = time.monotonic()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def wait(self, tokens: int = 1) -> None:
        """Block until tokens are available."""
        while not self.acquire(tokens):
            time.sleep(0.1)
