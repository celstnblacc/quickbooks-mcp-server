"""Edge case and boundary condition tests."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# -----------------------------------------------------------------------
# Rate limiter boundary
# -----------------------------------------------------------------------
class TestRateLimiterBoundary:
    def test_exact_zero_then_one_refill(self):
        from rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=60)
        # Drain all 60 tokens
        for _ in range(60):
            assert limiter.is_allowed() is True
        assert limiter.is_allowed() is False

        # Advance exactly 1 second → 1 token (60/60 = 1 token/sec)
        limiter.last_refill -= 1.0
        assert limiter.is_allowed() is True
        assert limiter.is_allowed() is False  # only 1 token was refilled

    def test_tokens_never_exceed_capacity(self):
        from rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=5)
        # Simulate very long idle (10 minutes)
        limiter.last_refill -= 600
        limiter._refill()
        assert limiter.tokens == 5.0  # capped at capacity


# -----------------------------------------------------------------------
# .env edge cases for persistence
# -----------------------------------------------------------------------
class TestEnvPersistenceEdgeCases:
    def test_no_trailing_newline(self, tmp_path):
        """File with no trailing newline still works."""
        env_file = tmp_path / ".env"
        env_file.write_text("QUICKBOOKS_REFRESH_TOKEN=old")  # no \n

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}
        with patch("requests.post", return_value=mock_resp):
            from quickbooks_interaction import QuickBooksSession
            session = QuickBooksSession()

        session.refresh_token = "new_tok"

        # Patch __file__ in quickbooks_interaction module to point to test directory
        import quickbooks_interaction
        with patch.object(quickbooks_interaction, '__file__', str(env_file)):
            session._persist_refresh_token()

        content = env_file.read_text()
        assert "QUICKBOOKS_REFRESH_TOKEN=new_tok" in content


# -----------------------------------------------------------------------
# Closure factory edge cases
# -----------------------------------------------------------------------
class TestClosureFactoryEdgeCases:
    @pytest.fixture(autouse=True)
    def _import(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if mod in ("main_quickbooks_mcp", "quickbooks_interaction", "rate_limiter", "api_importer", "environment"):
                    del sys.modules[mod]
            from main_quickbooks_mcp import _make_api_tool
            self.factory = _make_api_tool

    def _limiter(self):
        m = MagicMock()
        m.is_allowed.return_value = True
        return m

    def test_no_parameters(self, mock_qb_session):
        """API with zero parameters should work."""
        config = {
            "route": "/companyinfo",
            "method": "get",
            "parameters": [],
            "docstring": "Get company info.",
            "tool_name": "get_companyinfo",
        }
        handler = self.factory(config, lambda: mock_qb_session, self._limiter())
        handler()
        mock_qb_session.call_route.assert_called_once_with(
            method_type="get",
            route="/companyinfo",
            params={},
            body=None,
        )

    def test_path_only_params(self, mock_qb_session):
        """Endpoint with only path params — no query or body."""
        config = {
            "route": "/account/{id}",
            "method": "get",
            "parameters": [
                {"name": "id", "location": "path", "required": True, "type": "string", "description": ""},
            ],
            "docstring": "Get account.",
            "tool_name": "get_account",
        }
        handler = self.factory(config, lambda: mock_qb_session, self._limiter())
        handler(id="55")
        call_kw = mock_qb_session.call_route.call_args.kwargs
        assert call_kw["route"] == "/account/55"
        assert call_kw["params"] == {}
        assert call_kw["body"] is None

    def test_mixed_params_post(self, mock_qb_session):
        """POST with path + query + body all at once."""
        config = {
            "route": "/entity/{entityId}",
            "method": "post",
            "parameters": [
                {"name": "entityId", "location": "path", "required": True, "type": "string", "description": ""},
                {"name": "minorversion", "location": "query", "required": False, "type": "string", "description": ""},
            ],
            "docstring": "Create entity.",
            "tool_name": "post_entity",
        }
        handler = self.factory(config, lambda: mock_qb_session, self._limiter())
        handler(entityId="10", minorversion="65", DisplayName="Test Corp")
        call_kw = mock_qb_session.call_route.call_args.kwargs
        assert call_kw["route"] == "/entity/10"
        assert call_kw["params"] == {"minorversion": "65"}
        assert call_kw["body"] == {"DisplayName": "Test Corp"}

    def test_kwargs_string_no_equals(self, mock_qb_session):
        """kwargs='noequals' should not crash."""
        config = {
            "route": "/test",
            "method": "get",
            "parameters": [],
            "docstring": "Test.",
            "tool_name": "get_test",
        }
        handler = self.factory(config, lambda: mock_qb_session, self._limiter())
        handler(kwargs="noequals")  # should not raise
        mock_qb_session.call_route.assert_called_once()


# -----------------------------------------------------------------------
# Very long query
# -----------------------------------------------------------------------
class TestVeryLongQuery:
    def test_10k_select_doesnt_crash(self):
        """A 10,000-char SELECT query should pass validation (server won't crash)."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if mod in ("main_quickbooks_mcp", "quickbooks_interaction", "rate_limiter", "api_importer", "environment"):
                    del sys.modules[mod]
            from main_quickbooks_mcp import query_quickbooks

        long_query = "SELECT " + "A" * 9993  # total ~10000 chars
        result = query_quickbooks(long_query)
        # Should either pass validation (session error) or handle gracefully
        assert result.text  # non-empty response, no crash


# -----------------------------------------------------------------------
# Concurrent-style rapid calls
# -----------------------------------------------------------------------
class TestRapidCalls:
    def test_sequential_rapid_calls_respect_limit(self):
        """Many rapid sequential calls should be correctly limited."""
        from rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=10)
        allowed = sum(1 for _ in range(20) if limiter.is_allowed())
        assert allowed == 10  # exactly 10 should pass, 10 should fail
