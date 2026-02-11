"""Tests for rate_limiter.py — token-bucket rate limiter."""

import time
from unittest.mock import patch

import pytest

from rate_limiter import RateLimiter


class TestAllowsRequestsWithinLimit:
    def test_allows_up_to_capacity(self, fresh_limiter):
        """All requests up to the capacity should be allowed."""
        for _ in range(fresh_limiter.capacity):
            assert fresh_limiter.is_allowed() is True

    def test_blocks_when_exhausted(self, fresh_limiter):
        """After exhausting tokens the next request is blocked."""
        for _ in range(fresh_limiter.capacity):
            fresh_limiter.is_allowed()
        assert fresh_limiter.is_allowed() is False


class TestRefill:
    def test_refills_over_time(self):
        """After exhausting tokens, advancing the clock restores them."""
        limiter = RateLimiter(requests_per_minute=60)
        # Drain all tokens
        for _ in range(60):
            limiter.is_allowed()
        assert limiter.is_allowed() is False

        # Advance 60 seconds — full refill
        limiter.last_refill -= 60
        assert limiter.is_allowed() is True

    def test_partial_refill(self):
        """Advancing half the period gives roughly half the tokens."""
        limiter = RateLimiter(requests_per_minute=60)
        for _ in range(60):
            limiter.is_allowed()

        # Advance 30 seconds — ~30 tokens back
        limiter.last_refill -= 30
        count = 0
        while limiter.is_allowed():
            count += 1
        assert 28 <= count <= 32  # allow minor float imprecision


class TestBurstCapacity:
    def test_full_burst_after_idle(self):
        """After a long idle, burst up to full capacity should work."""
        limiter = RateLimiter(requests_per_minute=10)
        # Simulate long idle
        limiter.last_refill -= 600
        for _ in range(10):
            assert limiter.is_allowed() is True
        # 11th should fail (capacity is 10)
        assert limiter.is_allowed() is False


class TestCustomCapacity:
    def test_custom_limit(self):
        """A non-default capacity is respected."""
        limiter = RateLimiter(requests_per_minute=3)
        assert limiter.capacity == 3
        for _ in range(3):
            assert limiter.is_allowed() is True
        assert limiter.is_allowed() is False
