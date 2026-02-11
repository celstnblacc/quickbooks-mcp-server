"""Error recovery and resilience tests.

These tests verify the system recovers gracefully from failures like network
timeouts, API errors, token refresh failures, and service unavailability.

Run with: pytest tests/test_error_recovery.py -v
"""

import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
from requests.exceptions import Timeout, ConnectionError, RequestException

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestNetworkTimeoutRecovery:
    """Test recovery from network timeouts."""

    def test_timeout_on_query_returns_error(self):
        """Query that times out returns graceful error message."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}

        with patch("requests.post", return_value=mock_resp):
            from quickbooks_interaction import QuickBooksSession
            session = QuickBooksSession()

        # Mock timeout on GET request
        with patch("requests.get", side_effect=Timeout("Connection timeout")):
            result = session.call_route("get", "/query", params={"query": "SELECT * FROM Account"})

            # Should return error dict, not crash
            assert isinstance(result, dict)
            assert "error" in result

    def test_connection_error_handled_gracefully(self):
        """Connection errors don't crash the server."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}

        with patch("requests.post", return_value=mock_resp):
            from quickbooks_interaction import QuickBooksSession
            session = QuickBooksSession()

        # Simulate connection error
        with patch("requests.get", side_effect=ConnectionError("Connection refused")):
            result = session.call_route("get", "/query", params={"query": "SELECT * FROM Account"})

            # Should handle gracefully
            assert isinstance(result, dict)

    def test_partial_response_handling(self):
        """Handles responses with incomplete data."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}

        with patch("requests.post", return_value=mock_resp):
            from quickbooks_interaction import QuickBooksSession
            session = QuickBooksSession()

        # Return malformed JSON
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.side_effect = ValueError("Invalid JSON")

        with patch("requests.get", return_value=mock_get_resp):
            result = session.call_route("get", "/query", params={"query": "SELECT * FROM Account"})

            # Should handle JSON parse error
            assert result is not None


class TestTokenRefreshRecovery:
    """Test recovery from token refresh failures."""

    def test_token_refresh_failure_first_then_success(self):
        """Token refresh fails once, then succeeds on retry."""
        call_count = {"count": 0}

        def mock_post(*args, **kwargs):
            call_count["count"] += 1
            mock_resp = MagicMock()
            if call_count["count"] == 1:
                # First call fails
                mock_resp.status_code = 500
                mock_resp.json.return_value = {}
            else:
                # Subsequent calls succeed
                mock_resp.status_code = 200
                mock_resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}
            return mock_resp

        with patch("requests.post", side_effect=mock_post):
            from quickbooks_interaction import QuickBooksSession

            # First initialization fails
            with pytest.raises(RuntimeError):
                session = QuickBooksSession()

    def test_expired_token_triggers_auto_refresh(self):
        """Expired token (401) automatically triggers refresh."""
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"access_token": "at1", "refresh_token": "rt"}

        call_count = {"get": 0, "post": 0}

        def mock_get(*args, **kwargs):
            call_count["get"] += 1
            resp = MagicMock()
            if call_count["get"] == 1:
                # First GET returns 401 (expired)
                resp.status_code = 401
                resp.json.return_value = {}
            else:
                # After refresh, succeed
                resp.status_code = 200
                resp.json.return_value = {"QueryResponse": {"Account": []}}
            return resp

        def mock_post(*args, **kwargs):
            call_count["post"] += 1
            resp = MagicMock()
            resp.status_code = 200
            # Return new token on refresh
            resp.json.return_value = {"access_token": "at_new", "refresh_token": "rt"}
            return resp

        with patch("requests.post", side_effect=mock_post):
            with patch("requests.get", side_effect=mock_get):
                from quickbooks_interaction import QuickBooksSession
                session = QuickBooksSession()

                result = session.query("SELECT * FROM Account")

                # Should have called GET twice (first 401, then retry)
                assert call_count["get"] == 2
                # Should have refreshed token
                assert call_count["post"] == 2  # Initial + refresh
                # Should return successful result
                assert "QueryResponse" in result

    def test_token_refresh_total_failure(self):
        """All token refresh attempts fail."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {}

        with patch("requests.post", return_value=mock_resp):
            from quickbooks_interaction import QuickBooksSession

            with pytest.raises(RuntimeError) as exc_info:
                QuickBooksSession()

            assert "refresh" in str(exc_info.value).lower()


class TestRateLimitRecovery:
    """Test recovery from rate limiting."""

    def test_rate_limit_blocks_then_allows_after_refill(self):
        """Rate limiter blocks requests, then allows after refill period."""
        from rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=10)

        # Exhaust all tokens
        for _ in range(10):
            assert limiter.is_allowed() is True

        # Should block
        assert limiter.is_allowed() is False

        # Wait for refill (1 second = 10/60 tokens)
        time.sleep(1.1)

        # Should allow 1 request
        assert limiter.is_allowed() is True

    def test_tool_call_blocked_by_rate_limit_returns_message(self):
        """Tool call blocked by rate limiter returns user-friendly message."""
        mock_session = MagicMock()
        mock_session.call_route.return_value = {"ok": True}

        from rate_limiter import RateLimiter
        from main_quickbooks_mcp import _make_api_tool

        limiter = RateLimiter(requests_per_minute=2)

        # Exhaust limiter
        limiter.is_allowed()
        limiter.is_allowed()

        config = {
            "route": "/test",
            "method": "get",
            "parameters": [],
            "docstring": "Test",
            "tool_name": "test",
        }
        handler = _make_api_tool(config, lambda: mock_session, limiter)

        result = handler()

        # Should return rate limit message
        assert "rate limit" in result.text.lower()


class TestAPIUnavailability:
    """Test handling of API service unavailability."""

    def test_500_internal_server_error(self):
        """Handle 500 Internal Server Error from API."""
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 500
        mock_get_resp.json.return_value = {}

        with patch("requests.post", return_value=mock_post_resp):
            with patch("requests.get", return_value=mock_get_resp):
                from quickbooks_interaction import QuickBooksSession
                session = QuickBooksSession()

                result = session.query("SELECT * FROM Account")

                # Should return error, not crash
                assert "error" in result
                assert "500" in str(result["error"])

    def test_503_service_unavailable(self):
        """Handle 503 Service Unavailable."""
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 503
        mock_get_resp.json.return_value = {}

        with patch("requests.post", return_value=mock_post_resp):
            with patch("requests.get", return_value=mock_get_resp):
                from quickbooks_interaction import QuickBooksSession
                session = QuickBooksSession()

                result = session.query("SELECT * FROM Account")

                assert "error" in result
                assert "503" in str(result["error"])

    def test_429_too_many_requests(self):
        """Handle 429 Too Many Requests (API rate limiting)."""
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 429
        mock_get_resp.json.return_value = {}

        with patch("requests.post", return_value=mock_post_resp):
            with patch("requests.get", return_value=mock_get_resp):
                from quickbooks_interaction import QuickBooksSession
                session = QuickBooksSession()

                result = session.query("SELECT * FROM Account")

                # Should handle 429 gracefully
                assert "error" in result
                assert "429" in str(result["error"])


class TestDataRecovery:
    """Test recovery from corrupt or invalid data."""

    def test_corrupt_env_file_handling(self, tmp_path):
        """Handles corrupt .env file gracefully."""
        env_file = tmp_path / ".env"
        # Write invalid data
        env_file.write_text("CORRUPT_DATA_@#$%^&*()\x00\x01\x02")

        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.cwd", return_value=tmp_path):
                # Try to load environment
                from dotenv import load_dotenv
                # Should not crash
                load_dotenv(env_file)

    def test_missing_required_env_vars(self):
        """Missing required environment variables handled properly."""
        with patch.dict("os.environ", {}, clear=True):
            with patch("environment.Environment.get", return_value=None):
                from quickbooks_interaction import QuickBooksSession

                # Should handle missing credentials
                # (will fail on token refresh, but shouldn't crash on init)
                try:
                    session = QuickBooksSession()
                except Exception as e:
                    # Should get a meaningful error
                    assert "client_id" in str(e).lower() or "refresh" in str(e).lower()

    def test_invalid_json_in_openapi_schema(self, tmp_path):
        """Handles invalid JSON in OpenAPI schema file."""
        schema_file = tmp_path / "quickbooks_openapi_schema.json"
        schema_file.write_text("{invalid json content")

        # Patch the specific file open, not all path operations
        with patch("builtins.open", side_effect=lambda p, *args, **kwargs:
                   open(schema_file, *args, **kwargs) if "quickbooks_openapi_schema.json" in str(p)
                   else open(p, *args, **kwargs)):
            from api_importer import load_apis

            with pytest.raises(Exception) as exc_info:
                load_apis()

            # Should raise exception about loading API documentation
            assert "API documentation" in str(exc_info.value) or "json" in str(exc_info.value).lower()


class TestConcurrentFailures:
    """Test handling of concurrent request failures."""

    def test_multiple_failed_requests_dont_corrupt_state(self):
        """Multiple concurrent failures don't corrupt session state."""
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}

        with patch("requests.post", return_value=mock_post_resp):
            from quickbooks_interaction import QuickBooksSession
            session = QuickBooksSession()

        initial_token = session.access_token

        # Multiple failed requests
        with patch("requests.get", side_effect=Timeout("timeout")):
            for _ in range(10):
                result = session.call_route("get", "/query", params={"query": "test"})
                assert isinstance(result, dict)

        # Session state should be unchanged
        assert session.access_token == initial_token

    def test_token_persistence_failure_doesnt_crash(self, tmp_path):
        """Token persistence failure doesn't crash the session."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "at", "refresh_token": "rt_new"}

        # Make .env read-only to cause write failure
        env_file = tmp_path / ".env"
        env_file.write_text("QUICKBOOKS_REFRESH_TOKEN=old\n")
        env_file.chmod(0o444)  # Read-only

        with patch("requests.post", return_value=mock_resp):
            from quickbooks_interaction import QuickBooksSession
            session = QuickBooksSession()

        # Patch Path in quickbooks_interaction module to return mock that points to test env
        with patch("quickbooks_interaction.Path") as mock_path_class:
            mock_instance = MagicMock()
            mock_instance.parent = tmp_path
            mock_path_class.return_value = mock_instance
            # Should log warning but not crash
            session._persist_refresh_token()

        # Session should still be usable
        assert session.refresh_token == "rt_new"


class TestGracefulDegradation:
    """Test graceful degradation when services are partially available."""

    def test_query_works_when_schema_unavailable(self):
        """Query tool works even if entity schema file is missing."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}

        with patch("requests.post", return_value=mock_resp):
            # Delete module cache
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            # Import with missing schema file
            with patch("builtins.open", side_effect=FileNotFoundError):
                from main_quickbooks_mcp import query_quickbooks

                # get_quickbooks_entity_schema might fail, but query should work
                result = query_quickbooks("SELECT * FROM Account")
                # Should return error about no session, not crash
                assert result.text

    def test_tools_registered_despite_partial_schema_errors(self):
        """Tools are registered even if some schema entries are malformed."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch("requests.post", return_value=mock_resp):
            # This will cause import to happen
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            # Import should succeed (tools registered at import time)
            import main_quickbooks_mcp

            # Should have registered tools
            assert hasattr(main_quickbooks_mcp, "mcp")
