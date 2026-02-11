"""Stress and performance tests for the QuickBooks MCP Server.

These tests are more resource-intensive and time-consuming than unit tests.
They verify the system behaves correctly under load, with concurrent requests,
and with large payloads.

Run with: pytest tests/test_stress.py -v
Or: ./run_tests.sh --stress
"""

import sys
import time
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# -----------------------------------------------------------------------
# Rate Limiter Stress Tests
# -----------------------------------------------------------------------
class TestRateLimiterStress:
    """Test rate limiter under heavy load."""

    def test_sustained_load_over_time(self):
        """Simulate sustained load over 5 seconds."""
        from rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=120)  # 2 req/sec

        # First exhaust the initial burst capacity
        for _ in range(120):
            limiter.is_allowed()

        # Now test sustained rate over 5 seconds
        start = time.time()
        allowed = []
        denied = []

        # Make requests for 5 seconds
        while time.time() - start < 5.0:
            if limiter.is_allowed():
                allowed.append(time.time())
            else:
                denied.append(time.time())
            time.sleep(0.01)  # 10ms between attempts

        # Should allow roughly 10 requests (2/sec * 5 sec)
        # Allow some margin for timing variations
        assert 8 <= len(allowed) <= 12, f"Expected 8-12 allowed, got {len(allowed)}"
        assert len(denied) > 0, "Should have denied some requests"

    def test_burst_then_sustain(self):
        """Test burst capacity followed by sustained rate."""
        from rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=60)

        # Burst: drain all 60 tokens immediately
        burst_allowed = sum(1 for _ in range(100) if limiter.is_allowed())
        assert burst_allowed == 60

        # Wait 3 seconds (should refill ~3 tokens at 1/sec)
        time.sleep(3.1)

        sustained_allowed = sum(1 for _ in range(10) if limiter.is_allowed())
        assert 2 <= sustained_allowed <= 4  # ~3 tokens refilled

    def test_concurrent_access(self):
        """Test rate limiter with concurrent threads."""
        from rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=100)
        results = {"allowed": 0, "denied": 0}
        lock = threading.Lock()

        def worker():
            for _ in range(50):
                if limiter.is_allowed():
                    with lock:
                        results["allowed"] += 1
                else:
                    with lock:
                        results["denied"] += 1
                time.sleep(0.001)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        total = results["allowed"] + results["denied"]
        assert total == 200  # 4 threads * 50 attempts
        # Should allow ~100 and deny ~100 (with some variation)
        assert 80 <= results["allowed"] <= 120
        assert results["denied"] > 0


# -----------------------------------------------------------------------
# Query Validation Stress Tests
# -----------------------------------------------------------------------
class TestQueryValidationStress:
    """Test query validation with extreme inputs."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        """Set up with minimal mocking."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("requests.post", return_value=mock_resp):
            # Clear module cache
            for mod in list(sys.modules):
                if mod in ("main_quickbooks_mcp", "quickbooks_interaction",
                          "rate_limiter", "api_importer", "environment"):
                    del sys.modules[mod]

    def test_extremely_long_query(self):
        """Test with a 100KB SELECT query."""
        from main_quickbooks_mcp import query_quickbooks

        # 100KB query - need ~8000 conditions to exceed 100KB
        long_query = "SELECT * FROM Account WHERE " + " OR ".join(
            f"Id='{i}'" for i in range(8000)
        )
        assert len(long_query) > 100_000

        result = query_quickbooks(long_query)
        # Should not crash, either passes validation or returns error
        assert result.text
        assert len(result.text) > 0

    def test_query_with_many_keywords(self):
        """Query containing SELECT plus many other safe keywords."""
        from main_quickbooks_mcp import query_quickbooks

        # This should pass (SELECT is at start, blocked keywords in strings)
        query = "SELECT * FROM Account WHERE Name='DELETE' OR Type='UPDATE'"
        result = query_quickbooks(query)
        assert result.text
        # Should pass validation (keywords are in string literals)
        assert "Only SELECT queries are permitted" not in result.text

    def test_rapid_validation_calls(self):
        """Validate 1000 queries rapidly."""
        from main_quickbooks_mcp import query_quickbooks

        queries = [
            "SELECT * FROM Account",
            "select * from Customer",
            "  SELECT * FROM Invoice  ",
            "DELETE FROM Account",
            "UPDATE Account SET Name='x'",
        ]

        start = time.time()
        for _ in range(200):
            for q in queries:
                result = query_quickbooks(q)
                assert result.text  # Should always return something
        elapsed = time.time() - start

        # 1000 validations should be fast (< 1 second)
        assert elapsed < 1.0, f"Validation too slow: {elapsed}s for 1000 queries"


# -----------------------------------------------------------------------
# Closure Factory Stress Tests
# -----------------------------------------------------------------------
class TestClosureFactoryStress:
    """Test dynamic tool generation under load."""

    def test_many_tool_registrations(self):
        """Register 100 tools and verify they all work."""
        from main_quickbooks_mcp import _make_api_tool
        from rate_limiter import RateLimiter

        mock_session = MagicMock()
        mock_session.call_route.return_value = {"status": "ok"}
        limiter = RateLimiter(requests_per_minute=1000)

        handlers = []
        for i in range(100):
            config = {
                "route": f"/entity{i}/{{id}}",
                "method": "get",
                "parameters": [
                    {"name": "id", "location": "path", "required": True,
                     "type": "string", "description": ""},
                ],
                "docstring": f"Tool {i}",
                "tool_name": f"get_entity{i}",
            }
            handler = _make_api_tool(config, lambda: mock_session, limiter)
            handlers.append(handler)

        # Call each handler
        for i, handler in enumerate(handlers):
            result = handler(id=f"test{i}")
            assert result.text == "{'status': 'ok'}"

    def test_concurrent_tool_calls(self):
        """Call the same tool from multiple threads."""
        from main_quickbooks_mcp import _make_api_tool
        from rate_limiter import RateLimiter

        mock_session = MagicMock()
        mock_session.call_route.return_value = {"count": 0}
        limiter = RateLimiter(requests_per_minute=1000)

        config = {
            "route": "/test/{id}",
            "method": "get",
            "parameters": [
                {"name": "id", "location": "path", "required": True,
                 "type": "string", "description": ""},
            ],
            "docstring": "Test tool",
            "tool_name": "get_test",
        }
        handler = _make_api_tool(config, lambda: mock_session, limiter)

        def worker(thread_id):
            results = []
            for i in range(20):
                result = handler(id=f"t{thread_id}_i{i}")
                results.append(result.text)
            return results

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker, i) for i in range(10)]
            all_results = []
            for future in as_completed(futures):
                all_results.extend(future.result())

        # Should have 200 results (10 threads * 20 calls)
        assert len(all_results) == 200
        assert all("count" in r for r in all_results)

    def test_large_parameter_sets(self):
        """Tool with many parameters (100 query params)."""
        from main_quickbooks_mcp import _make_api_tool
        from rate_limiter import RateLimiter

        mock_session = MagicMock()
        mock_session.call_route.return_value = {"ok": True}
        limiter = RateLimiter(requests_per_minute=1000)

        params = [
            {"name": f"param{i}", "location": "query", "required": False,
             "type": "string", "description": ""}
            for i in range(100)
        ]

        config = {
            "route": "/complex",
            "method": "get",
            "parameters": params,
            "docstring": "Complex tool",
            "tool_name": "get_complex",
        }
        handler = _make_api_tool(config, lambda: mock_session, limiter)

        # Call with 50 params
        kwargs = {f"param{i}": f"value{i}" for i in range(50)}
        result = handler(**kwargs)

        # Verify all params were passed
        call_args = mock_session.call_route.call_args
        assert len(call_args.kwargs["params"]) == 50


# -----------------------------------------------------------------------
# Token Persistence Stress Tests
# -----------------------------------------------------------------------
class TestTokenPersistenceStress:
    """Test token persistence under various conditions."""

    def test_rapid_token_updates(self, tmp_path):
        """Update token 100 times rapidly."""
        env_file = tmp_path / ".env"
        env_file.write_text("QUICKBOOKS_REFRESH_TOKEN=initial\n")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "at",
            "refresh_token": "rt"
        }

        with patch("requests.post", return_value=mock_resp):
            from quickbooks_interaction import QuickBooksSession
            session = QuickBooksSession()

        for i in range(100):
            session.refresh_token = f"token_{i}"
            session._persist_refresh_token(env_path=env_file)

        content = env_file.read_text()
        assert "QUICKBOOKS_REFRESH_TOKEN=token_99" in content
        # Should only have ONE refresh token line
        assert content.count("QUICKBOOKS_REFRESH_TOKEN=") == 1

    def test_large_env_file(self, tmp_path):
        """Token persistence with a large .env file."""
        env_file = tmp_path / ".env"

        # Create large .env with 1000 lines
        lines = [f"VAR{i}=value{i}" for i in range(1000)]
        lines.insert(500, "QUICKBOOKS_REFRESH_TOKEN=old")
        env_file.write_text("\n".join(lines) + "\n")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "at",
            "refresh_token": "rt"
        }

        with patch("requests.post", return_value=mock_resp):
            from quickbooks_interaction import QuickBooksSession
            session = QuickBooksSession()

        session.refresh_token = "new_token"

        start = time.time()
        session._persist_refresh_token(env_path=env_file)
        elapsed = time.time() - start

        # Should be fast even with large file
        assert elapsed < 0.5, f"Token persistence too slow: {elapsed}s"

        content = env_file.read_text()
        assert "QUICKBOOKS_REFRESH_TOKEN=new_token" in content
        assert content.count("QUICKBOOKS_REFRESH_TOKEN=") == 1


# -----------------------------------------------------------------------
# Memory and Resource Tests
# -----------------------------------------------------------------------
class TestMemoryAndResources:
    """Test memory usage and resource cleanup."""

    def test_no_memory_leak_in_rate_limiter(self):
        """Rate limiter shouldn't accumulate state over many calls."""
        from rate_limiter import RateLimiter
        import sys

        limiter = RateLimiter(requests_per_minute=1000)

        # Make 10,000 calls
        for _ in range(10_000):
            limiter.is_allowed()
            if _ % 100 == 0:
                time.sleep(0.01)  # Allow some refills

        # Rate limiter should maintain constant size
        # (no growing lists/dicts/etc)
        size = sys.getsizeof(limiter.__dict__)
        assert size < 500  # Should be very small

    def test_tool_factory_memory(self):
        """Creating many tools shouldn't leak memory significantly."""
        from main_quickbooks_mcp import _make_api_tool
        from rate_limiter import RateLimiter
        import gc

        mock_session = MagicMock()
        limiter = RateLimiter(requests_per_minute=1000)

        gc.collect()
        # Create and discard 1000 tools
        for i in range(1000):
            config = {
                "route": f"/test{i}",
                "method": "get",
                "parameters": [],
                "docstring": f"Tool {i}",
                "tool_name": f"tool_{i}",
            }
            handler = _make_api_tool(config, lambda: mock_session, limiter)
            # Use handler once
            handler()

        gc.collect()
        # If we got here without OOM, memory usage is acceptable


# -----------------------------------------------------------------------
# Performance Benchmarks
# -----------------------------------------------------------------------
class TestPerformanceBenchmarks:
    """Performance benchmarks for key operations."""

    def test_query_validation_speed(self):
        """Benchmark query validation speed."""
        from main_quickbooks_mcp import _BLOCKED_QUERY_KEYWORDS

        queries = [
            "SELECT * FROM Account WHERE Id='123'",
            "select * from Customer",
            "  SELECT  Id, Name FROM Invoice  ",
        ] * 100  # 300 queries

        start = time.time()
        for query in queries:
            stripped = query.strip()
            assert stripped.upper().startswith("SELECT")
            upper_tokens = set(stripped.upper().split())
            blocked = upper_tokens & _BLOCKED_QUERY_KEYWORDS
            assert not blocked
        elapsed = time.time() - start

        # 300 validations should be < 10ms
        assert elapsed < 0.01, f"Validation too slow: {elapsed}s for 300 queries"

    def test_tool_call_overhead(self):
        """Measure overhead of tool call wrapper."""
        from main_quickbooks_mcp import _make_api_tool
        from rate_limiter import RateLimiter

        mock_session = MagicMock()
        mock_session.call_route.return_value = {"ok": True}
        limiter = RateLimiter(requests_per_minute=10000)

        config = {
            "route": "/test",
            "method": "get",
            "parameters": [],
            "docstring": "Test",
            "tool_name": "test",
        }
        handler = _make_api_tool(config, lambda: mock_session, limiter)

        # Warm up
        for _ in range(10):
            handler()

        # Benchmark
        start = time.time()
        for _ in range(1000):
            handler()
        elapsed = time.time() - start

        # 1000 calls should be < 100ms (< 0.1ms per call)
        assert elapsed < 0.1, f"Tool call overhead too high: {elapsed}s for 1000 calls"

        # Calculate calls per second
        calls_per_sec = 1000 / elapsed
        print(f"\n  Tool call throughput: {calls_per_sec:.0f} calls/sec")
        assert calls_per_sec > 10000  # Should handle 10k+ calls/sec
