"""Simple token-bucket rate limiter for MCP tool invocations."""

import time
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token-bucket rate limiter.

    Allows a configurable number of requests per minute with burst capacity
    equal to the per-minute limit.
    """

    def __init__(self, requests_per_minute: int = 60):
        self.capacity = requests_per_minute
        self.tokens = float(requests_per_minute)
        self.refill_rate = requests_per_minute / 60.0  # tokens per second
        self.last_refill = time.monotonic()

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.last_refill
        # Handle negative elapsed time (clock jumped backward)
        if elapsed >= 0:
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        # Always update last_refill to current time
        self.last_refill = now

    def is_allowed(self) -> bool:
        """Return True if the request is within rate limits, False otherwise."""
        self._refill()
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        logger.warning("Rate limit exceeded (%d req/min)", self.capacity)
        return False
