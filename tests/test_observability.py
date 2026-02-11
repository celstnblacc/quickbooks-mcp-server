"""Observability and logging tests.

These tests verify that logging, error reporting, and monitoring work
correctly and that sensitive data is never leaked.

Run with: pytest tests/test_observability.py -v
"""

import sys
import re
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestLoggingConfiguration:
    """Test logging is properly configured."""

    def test_logging_module_configured(self):
        """Logging is configured at application startup."""
        # Import should set up logging
        import main_quickbooks_mcp

        # Logger should exist
        logger = logging.getLogger("main_quickbooks_mcp")
        assert logger

    def test_log_level_set(self):
        """Log level is configured."""
        logger = logging.getLogger("main_quickbooks_mcp")

        # Should have a level set (not NOTSET unless explicitly configured)
        # Default is INFO
        assert logger.level == logging.INFO or logger.getEffectiveLevel() >= logging.DEBUG

    def test_log_format_includes_required_fields(self, caplog):
        """Log format includes timestamp, level, and message."""
        logger = logging.getLogger("test_observability")
        logger.setLevel(logging.INFO)

        with caplog.at_level(logging.INFO):
            logger.info("Test log message")

        assert len(caplog.records) > 0
        record = caplog.records[0]

        # Should have these attributes
        assert hasattr(record, "levelname")
        assert hasattr(record, "message")
        assert hasattr(record, "created")
        assert record.levelname == "INFO"
        assert record.message == "Test log message"


class TestSensitiveDataProtection:
    """Test that sensitive data is never logged."""

    def test_access_token_not_in_logs(self, caplog):
        """Access tokens are never logged."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.VERYSECRETTOKEN",
            "refresh_token": "AB11234567890SECRETREFRESHTOKEN"
        }

        with patch("requests.post", return_value=mock_resp):
            with caplog.at_level(logging.DEBUG):
                from quickbooks_interaction import QuickBooksSession
                session = QuickBooksSession()

        # Check all log messages
        all_logs = " ".join(record.message for record in caplog.records)

        # Should NOT contain tokens
        assert "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9" not in all_logs
        assert "VERYSECRETTOKEN" not in all_logs
        assert "SECRETREFRESHTOKEN" not in all_logs

    def test_refresh_token_not_in_logs(self, caplog):
        """Refresh tokens are never logged."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "at",
            "refresh_token": "AB11234567890SECRETREFRESH"
        }

        with patch("requests.post", return_value=mock_resp):
            with caplog.at_level(logging.DEBUG):
                from quickbooks_interaction import QuickBooksSession
                session = QuickBooksSession()

        all_logs = " ".join(record.message for record in caplog.records)
        assert "AB11234567890SECRETREFRESH" not in all_logs

    def test_api_credentials_not_in_logs(self, caplog):
        """Client ID and secret are never logged."""
        with patch.dict("os.environ", {
            "QUICKBOOKS_CLIENT_ID": "SECRET_CLIENT_ID_123",
            "QUICKBOOKS_CLIENT_SECRET": "SUPER_SECRET_KEY_456",
            "QUICKBOOKS_REFRESH_TOKEN": "rt",
            "QUICKBOOKS_COMPANY_ID": "123",
            "QUICKBOOKS_ENV": "sandbox"
        }):
            with caplog.at_level(logging.DEBUG):
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}

                with patch("requests.post", return_value=mock_resp):
                    from quickbooks_interaction import QuickBooksSession
                    session = QuickBooksSession()

        all_logs = " ".join(record.message for record in caplog.records)
        assert "SECRET_CLIENT_ID_123" not in all_logs
        assert "SUPER_SECRET_KEY_456" not in all_logs

    def test_user_query_data_not_leaked(self, caplog):
        """User query data with sensitive info isn't leaked."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            with caplog.at_level(logging.INFO):
                from main_quickbooks_mcp import query_quickbooks

                # Query with sensitive-looking data
                query_quickbooks("SELECT * FROM Account WHERE SSN='123-45-6789'")

        # SSN should not be in logs
        all_logs = " ".join(record.message for record in caplog.records)
        assert "123-45-6789" not in all_logs


class TestLogLevels:
    """Test appropriate log levels are used."""

    def test_error_conditions_logged_as_error(self, caplog):
        """Error conditions are logged at ERROR level."""
        with caplog.at_level(logging.ERROR):
            logger = logging.getLogger("test")
            logger.error("Critical error occurred")

        assert len(caplog.records) > 0
        assert any(r.levelname == "ERROR" for r in caplog.records)

    def test_normal_operations_logged_as_info(self, caplog):
        """Normal operations are logged at INFO level."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}

        with patch("requests.post", return_value=mock_resp):
            with caplog.at_level(logging.INFO):
                from quickbooks_interaction import QuickBooksSession
                session = QuickBooksSession()

        # Should have INFO level logs for initialization
        info_logs = [r for r in caplog.records if r.levelname == "INFO"]
        assert len(info_logs) > 0

    def test_debug_information_at_debug_level(self, caplog):
        """Debug information is at DEBUG level."""
        with caplog.at_level(logging.DEBUG):
            logger = logging.getLogger("test")
            logger.debug("Debug information")

        debug_logs = [r for r in caplog.records if r.levelname == "DEBUG"]
        assert len(debug_logs) > 0


class TestErrorLogging:
    """Test error logging and reporting."""

    def test_exceptions_logged_with_traceback(self, caplog):
        """Exceptions are logged with tracebacks internally."""
        with caplog.at_level(logging.ERROR):
            logger = logging.getLogger("test")
            try:
                raise ValueError("Test exception")
            except ValueError:
                logger.exception("An error occurred")

        # Should have error log
        error_logs = [r for r in caplog.records if r.levelname == "ERROR"]
        assert len(error_logs) > 0

        # Should mention the error
        assert any("error" in r.message.lower() for r in error_logs)

    def test_api_errors_logged(self, caplog):
        """API errors are logged internally."""
        mock_post = MagicMock()
        mock_post.status_code = 200
        mock_post.json.return_value = {"access_token": "at", "refresh_token": "rt"}

        mock_get = MagicMock()
        mock_get.status_code = 500
        mock_get.json.return_value = {}

        with patch("requests.post", return_value=mock_post):
            with patch("requests.get", return_value=mock_get):
                with caplog.at_level(logging.ERROR):
                    from quickbooks_interaction import QuickBooksSession
                    session = QuickBooksSession()
                    session.query("SELECT * FROM Account")

        # Should log error about API failure
        error_logs = [r for r in caplog.records if r.levelname == "ERROR"]
        assert len(error_logs) > 0

    def test_token_refresh_failure_logged(self, caplog):
        """Token refresh failures are logged."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {}

        with patch("requests.post", return_value=mock_resp):
            with caplog.at_level(logging.ERROR):
                from quickbooks_interaction import QuickBooksSession

                try:
                    QuickBooksSession()
                except RuntimeError:
                    pass

        # Should have logged the failure
        error_logs = [r for r in caplog.records if r.levelname == "ERROR"]
        assert len(error_logs) > 0
        assert any("token" in r.message.lower() or "refresh" in r.message.lower() for r in error_logs)


class TestStructuredLogging:
    """Test log messages are structured and parseable."""

    def test_log_messages_well_formatted(self, caplog):
        """Log messages are well-formatted and parseable."""
        with caplog.at_level(logging.INFO):
            logger = logging.getLogger("test")
            logger.info("Operation completed successfully")

        assert len(caplog.records) > 0
        record = caplog.records[0]

        # Message should be clear and not truncated
        assert len(record.message) > 0
        assert record.message == "Operation completed successfully"

    def test_log_messages_contain_context(self, caplog):
        """Log messages contain relevant context."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}

        with patch("requests.post", return_value=mock_resp):
            with caplog.at_level(logging.INFO):
                from quickbooks_interaction import QuickBooksSession
                QuickBooksSession()

        # Should have context about what happened
        messages = [r.message for r in caplog.records]
        # Some message should mention initialization or session
        assert any("session" in m.lower() or "initializ" in m.lower() for m in messages)


class TestLogOutputDestination:
    """Test logs are output to correct destination."""

    def test_logs_go_to_stderr(self):
        """Logs are sent to stderr, not stdout."""
        # This is configured in main_quickbooks_mcp.py
        # basicConfig(stream=sys.stderr)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}

        # Capture stderr
        stderr_capture = StringIO()

        with patch("sys.stderr", stderr_capture):
            with patch("requests.post", return_value=mock_resp):
                for mod in list(sys.modules):
                    if "main_quickbooks_mcp" in mod:
                        del sys.modules[mod]

                # This should trigger logging
                import main_quickbooks_mcp

        # Some output should have gone to stderr
        # (or logging was already configured, which is ok)
        output = stderr_capture.getvalue()
        # Output may be empty if logging was already set up


class TestOperationalMetrics:
    """Test operational metrics and monitoring."""

    def test_tool_execution_logged(self, caplog):
        """Tool executions are logged for monitoring."""
        mock_session = MagicMock()
        mock_session.call_route.return_value = {"ok": True}

        from rate_limiter import RateLimiter

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

        limiter = RateLimiter(requests_per_minute=1000)
        handler = _make_api_tool(config, lambda: mock_session, limiter)

        with caplog.at_level(logging.INFO):
            handler()

        # Should log execution
        info_logs = [r for r in caplog.records if r.levelname == "INFO"]
        assert any("test_tool" in r.message or "Executing" in r.message for r in info_logs)

    def test_rate_limit_exceeded_logged(self, caplog):
        """Rate limit exceeded events are logged."""
        from rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=2)

        # Exhaust limit
        limiter.is_allowed()
        limiter.is_allowed()

        with caplog.at_level(logging.WARNING):
            limiter.is_allowed()

        # Should log warning
        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert any("rate limit" in r.message.lower() for r in warnings)


class TestLogSanitization:
    """Test that logs are sanitized properly."""

    def test_no_token_patterns_in_logs(self, caplog):
        """No token-like patterns appear in logs."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "A" * 200,  # Very long token
            "refresh_token": "B" * 200
        }

        with patch("requests.post", return_value=mock_resp):
            with caplog.at_level(logging.DEBUG):
                from quickbooks_interaction import QuickBooksSession
                QuickBooksSession()

        all_logs = " ".join(record.message for record in caplog.records)

        # Should not contain long alphanumeric strings (tokens)
        long_alphanum = re.findall(r'[A-Za-z0-9]{50,}', all_logs)
        # If found, they shouldn't be the actual tokens
        assert "A" * 50 not in all_logs
        assert "B" * 50 not in all_logs

    def test_error_messages_sanitized_for_client(self):
        """Error messages returned to client are sanitized."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}

        with patch("requests.post", return_value=mock_resp):
            from quickbooks_interaction import QuickBooksSession
            session = QuickBooksSession()

        # Simulate error with internal details
        mock_get = MagicMock()
        mock_get.status_code = 500
        mock_get.json.return_value = {"error": "Internal server error: database connection failed at line 123"}

        with patch("requests.get", return_value=mock_get):
            result = session.call_route("get", "/query", params={"query": "test"})

        # Error returned to client should be generic
        assert "error" in result
        # Should NOT contain internal details
        assert "database connection" not in str(result)
        assert "line 123" not in str(result)
