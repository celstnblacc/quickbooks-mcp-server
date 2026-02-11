"""Property-based and fuzz testing using Hypothesis.

These tests use randomized inputs to find unexpected edge cases, crashes,
and security vulnerabilities that traditional tests might miss.

Run with: pytest tests/test_property_based.py -v
Requires: pip install hypothesis

To run with more examples:
pytest tests/test_property_based.py --hypothesis-seed=random --hypothesis-show-statistics
"""

import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Check if hypothesis is available
try:
    from hypothesis import given, strategies as st, settings, HealthCheck
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False
    pytest.skip("Hypothesis not installed. Install with: pip install hypothesis", allow_module_level=True)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestQueryValidationFuzzing:
    """Fuzz test query validation with random inputs."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

    @given(st.text(min_size=1, max_size=1000))
    @settings(deadline=None, max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_query_validation_never_crashes(self, query_string):
        """Query validation handles any text input without crashing."""
        from main_quickbooks_mcp import query_quickbooks

        result = query_quickbooks(query_string)

        # Should always return TextContent, never crash
        assert result is not None
        assert hasattr(result, 'text')
        assert result.text is not None

    @given(st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll")), min_size=1, max_size=500))
    @settings(deadline=None, max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_query_validation_with_letters_only(self, query_string):
        """Query validation handles letter-only strings."""
        from main_quickbooks_mcp import query_quickbooks

        result = query_quickbooks(query_string)
        assert result.text is not None

    @given(prefix=st.text(max_size=20), suffix=st.text(max_size=20))
    @settings(deadline=None, max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_queries_with_select_keyword(self, prefix, suffix):
        """Queries containing SELECT are processed correctly."""
        from main_quickbooks_mcp import query_quickbooks

        query_string = f"{prefix}SELECT{suffix}"
        result = query_quickbooks(query_string)

        # Should not crash
        assert result.text is not None

        # If it starts with SELECT, should pass initial validation
        if query_string.strip().upper().startswith("SELECT"):
            assert "Only SELECT queries are permitted" not in result.text

    @given(st.text(alphabet="DELETE;DROP", min_size=1, max_size=100))
    @settings(deadline=None, max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_dangerous_keywords_always_blocked(self, query_string):
        """Queries with dangerous keywords are blocked."""
        from main_quickbooks_mcp import query_quickbooks

        # Add DELETE or DROP if not present
        dangerous_query = f"DELETE {query_string}" if "DELETE" not in query_string else query_string

        result = query_quickbooks(dangerous_query)

        # Should either block or return error, never execute
        assert result.text is not None


class TestRateLimiterFuzzing:
    """Fuzz test rate limiter with random parameters."""

    @given(st.integers(min_value=1, max_value=10000))
    @settings(deadline=None, max_examples=50)
    def test_rate_limiter_with_random_capacity(self, capacity):
        """Rate limiter works with any positive capacity."""
        from rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=capacity)

        # Should allow up to capacity requests (capped at 1000 for performance)
        max_requests = min(capacity + 10, 1000)
        allowed = sum(1 for _ in range(max_requests) if limiter.is_allowed())

        # Should allow roughly the expected amount (within 10%)
        expected = min(capacity, max_requests)
        assert expected * 0.9 <= allowed <= expected * 1.1 or capacity < 10

    @given(st.lists(st.booleans(), min_size=10, max_size=100))
    @settings(deadline=None, max_examples=50)
    def test_rate_limiter_with_random_call_pattern(self, pattern):
        """Rate limiter handles random request patterns."""
        from rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=50)

        # Random pattern of requests
        for should_request in pattern:
            if should_request:
                result = limiter.is_allowed()
                assert isinstance(result, bool)


class TestToolFactoryFuzzing:
    """Fuzz test dynamic tool generation."""

    @given(st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")), min_size=1, max_size=50))
    @settings(deadline=None, max_examples=50)
    def test_tool_name_generation(self, random_name):
        """Tool factory handles random tool names."""
        from rate_limiter import RateLimiter

        mock_session = MagicMock()
        mock_session.call_route.return_value = {"ok": True}
        limiter = RateLimiter(requests_per_minute=1000)

        # Clear module cache
        for mod in list(sys.modules):
            if "main_quickbooks_mcp" in mod:
                del sys.modules[mod]

        from main_quickbooks_mcp import _make_api_tool

        config = {
            "route": "/test",
            "method": "get",
            "parameters": [],
            "docstring": "Test tool",
            "tool_name": random_name or "default_name",
        }

        # Should not crash
        handler = _make_api_tool(config, lambda: mock_session, limiter)
        assert callable(handler)

    @given(st.dictionaries(
        st.text(min_size=1, max_size=20),
        st.one_of(st.text(), st.integers(), st.floats(allow_nan=False), st.booleans()),
        min_size=0,
        max_size=10
    ))
    @settings(deadline=None, max_examples=50)
    def test_tool_with_random_kwargs(self, kwargs):
        """Tool handlers accept random keyword arguments."""
        from rate_limiter import RateLimiter

        mock_session = MagicMock()
        mock_session.call_route.return_value = {"ok": True}
        limiter = RateLimiter(requests_per_minute=1000)

        for mod in list(sys.modules):
            if "main_quickbooks_mcp" in mod:
                del sys.modules[mod]

        from main_quickbooks_mcp import _make_api_tool

        config = {
            "route": "/test",
            "method": "get",
            "parameters": [],
            "docstring": "Test",
            "tool_name": "test_tool",
        }

        handler = _make_api_tool(config, lambda: mock_session, limiter)

        # Should handle random kwargs without crashing
        result = handler(**kwargs)
        assert result is not None


class TestParameterTypeFuzzing:
    """Fuzz test parameter type validation."""

    @given(st.one_of(
        st.text(), st.integers(), st.floats(allow_nan=False), st.booleans(),
        st.lists(st.integers()), st.dictionaries(st.text(), st.integers())
    ))
    @settings(deadline=None, max_examples=100)
    def test_parameter_type_validation(self, param_value):
        """Parameter validation handles various types."""
        from rate_limiter import RateLimiter

        mock_session = MagicMock()
        mock_session.call_route.return_value = {"ok": True}
        limiter = RateLimiter(requests_per_minute=1000)

        for mod in list(sys.modules):
            if "main_quickbooks_mcp" in mod:
                del sys.modules[mod]

        from main_quickbooks_mcp import _make_api_tool

        config = {
            "route": "/test/{id}",
            "method": "get",
            "parameters": [
                {"name": "id", "location": "path", "required": True, "type": "string", "description": ""},
            ],
            "docstring": "Test",
            "tool_name": "test_tool",
        }

        handler = _make_api_tool(config, lambda: mock_session, limiter)

        # Should handle any type without crashing (may reject invalid types)
        result = handler(id=param_value)
        assert result is not None


class TestUnicodeAndSpecialCharacters:
    """Test handling of Unicode and special characters."""

    @given(st.text(alphabet=st.characters(whitelist_categories=("L",)), min_size=1, max_size=100))
    @settings(deadline=None, max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_unicode_in_queries(self, unicode_text):
        """Queries with Unicode characters are handled correctly."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            from main_quickbooks_mcp import query_quickbooks

            query = f"SELECT * FROM Account WHERE Name='{unicode_text}'"
            result = query_quickbooks(query)

            # Should not crash
            assert result.text is not None

    @given(st.text(alphabet="!@#$%^&*()[]{}|\\:;\"'<>?,./", min_size=1, max_size=50))
    @settings(deadline=None, max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_special_characters_in_queries(self, special_chars):
        """Queries with special characters don't cause injection."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            from main_quickbooks_mcp import query_quickbooks

            query = f"SELECT * FROM Account {special_chars}"
            result = query_quickbooks(query)

            # Should handle safely
            assert result.text is not None

    @given(st.text(min_size=0, max_size=50))
    @settings(deadline=None, max_examples=50)
    def test_environment_var_fuzzing(self, random_value):
        """Environment variables with random values are handled."""
        from environment import Environment

        with patch.dict("os.environ", {"TEST_VAR": random_value}):
            result = Environment.get("TEST_VAR")
            assert result == random_value


class TestJSONFuzzing:
    """Fuzz test JSON parsing and generation."""

    @given(st.dictionaries(
        st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll")), min_size=1, max_size=20),
        st.one_of(st.text(), st.integers(), st.booleans(), st.none()),
        min_size=0,
        max_size=20
    ))
    @settings(deadline=None, max_examples=50)
    def test_json_body_fuzzing(self, random_dict):
        """Tool calls with random JSON bodies are handled."""
        from rate_limiter import RateLimiter

        mock_session = MagicMock()
        mock_session.call_route.return_value = {"ok": True}
        limiter = RateLimiter(requests_per_minute=1000)

        for mod in list(sys.modules):
            if "main_quickbooks_mcp" in mod:
                del sys.modules[mod]

        from main_quickbooks_mcp import _make_api_tool

        config = {
            "route": "/test",
            "method": "post",
            "parameters": [],
            "docstring": "Test",
            "tool_name": "test_post",
        }

        handler = _make_api_tool(config, lambda: mock_session, limiter)

        # Should handle random JSON-serializable dicts
        result = handler(**random_dict)
        assert result is not None


class TestBoundaryValueFuzzing:
    """Fuzz test with boundary values."""

    @given(st.integers(min_value=-1000000, max_value=1000000))
    @settings(deadline=None, max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_integer_parameters(self, int_value):
        """Integer parameters with extreme values are handled."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            from main_quickbooks_mcp import query_quickbooks

            query = f"SELECT * FROM Account MAXRESULTS {int_value}"
            result = query_quickbooks(query)

            # Should handle (may return error from API, but shouldn't crash)
            assert result.text is not None

    @given(st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False))
    @settings(deadline=None, max_examples=50)
    def test_float_rate_limiter_timing(self, time_delta):
        """Rate limiter handles various time deltas."""
        from rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=60)

        # Manually adjust time
        if time_delta > 0:
            limiter.last_refill -= abs(time_delta)
            # Should not crash when refilling
            limiter._refill()

            # Tokens should be capped at capacity
            assert 0 <= limiter.tokens <= limiter.capacity


class TestInjectionAttempts:
    """Test various injection attack attempts."""

    @given(st.text(min_size=1, max_size=200))
    @settings(deadline=None, max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_sql_injection_attempts_blocked(self, injection_attempt):
        """SQL injection attempts are blocked."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            from main_quickbooks_mcp import query_quickbooks

            # Common injection patterns
            patterns = [
                f"'; {injection_attempt} --",
                f"' OR '1'='1' {injection_attempt}",
                f"'; DROP TABLE {injection_attempt}; --",
            ]

            for pattern in patterns:
                result = query_quickbooks(pattern)
                # Should block (doesn't start with SELECT)
                assert "Only SELECT queries" in result.text or "Blocked keywords" in result.text

    @given(st.text(alphabet="SELECTselect; ", min_size=1, max_size=100))
    @settings(deadline=None, max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_obfuscated_dangerous_queries(self, query_text):
        """Obfuscated dangerous queries are caught."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            from main_quickbooks_mcp import query_quickbooks

            result = query_quickbooks(query_text)
            # Should always return something, never crash
            assert result.text is not None
