"""Tests for _make_api_tool closure factory — F-01."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import _make_api_tool — we need to handle the module-level init
_make_api_tool = None


@pytest.fixture(autouse=True)
def import_factory():
    global _make_api_tool
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    with patch("requests.post", return_value=mock_resp):
        for mod in list(sys.modules):
            if mod in ("main_quickbooks_mcp", "quickbooks_interaction", "rate_limiter", "api_importer", "environment"):
                del sys.modules[mod]
        from main_quickbooks_mcp import _make_api_tool as factory
        _make_api_tool = factory


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------
def _always_allowed():
    """A rate limiter that always allows."""
    limiter = MagicMock()
    limiter.is_allowed.return_value = True
    return limiter


def _always_blocked():
    """A rate limiter that always blocks."""
    limiter = MagicMock()
    limiter.is_allowed.return_value = False
    return limiter


# -----------------------------------------------------------------------
# Path parameter formatting
# -----------------------------------------------------------------------
class TestPathParams:
    def test_path_param_formatted(self, sample_api_config, mock_qb_session):
        handler = _make_api_tool(
            sample_api_config, lambda: mock_qb_session, _always_allowed()
        )
        handler(accountId="123")
        mock_qb_session.call_route.assert_called_once()
        call_kwargs = mock_qb_session.call_route.call_args
        assert call_kwargs.kwargs["route"] == "/account/123"

    def test_missing_path_param_returns_error(self, sample_api_config, mock_qb_session):
        handler = _make_api_tool(
            sample_api_config, lambda: mock_qb_session, _always_allowed()
        )
        # Call without the required path param — route.format() will fail
        # but we pass a different kwarg that won't match
        config = sample_api_config.copy()
        config["route"] = "/account/{accountId}"
        config["parameters"] = [
            {"name": "accountId", "location": "path", "required": True, "type": "string", "description": ""}
        ]
        handler2 = _make_api_tool(config, lambda: mock_qb_session, _always_allowed())
        result = handler2(wrong_param="abc")
        # The route has {accountId} but no path_params were collected
        # call_route is called with the un-formatted route
        # Actually: path_params is empty so route.format(**{}) won't raise
        # but the QuickBooks API will reject it. Let's test the KeyError case:
        config2 = config.copy()
        config2["route"] = "/account/{accountId}/{subId}"
        config2["parameters"] = [
            {"name": "accountId", "location": "path", "required": True, "type": "string", "description": ""},
            {"name": "subId", "location": "path", "required": True, "type": "string", "description": ""},
        ]
        handler3 = _make_api_tool(config2, lambda: mock_qb_session, _always_allowed())
        result = handler3(accountId="123")  # missing subId
        assert "Missing required path parameter" in result.text


# -----------------------------------------------------------------------
# Query parameter routing
# -----------------------------------------------------------------------
class TestQueryParams:
    def test_query_params_routed(self, mock_qb_session):
        config = {
            "route": "/query",
            "method": "get",
            "parameters": [
                {"name": "query", "location": "query", "required": True, "type": "string", "description": ""},
            ],
            "docstring": "Run a query.",
            "tool_name": "get_query",
        }
        handler = _make_api_tool(config, lambda: mock_qb_session, _always_allowed())
        handler(query="SELECT * FROM Account")
        call_kwargs = mock_qb_session.call_route.call_args
        assert call_kwargs.kwargs["params"] == {"query": "SELECT * FROM Account"}


# -----------------------------------------------------------------------
# Body parameters for POST
# -----------------------------------------------------------------------
class TestBodyParams:
    def test_body_for_post(self, post_api_config, mock_qb_session):
        handler = _make_api_tool(
            post_api_config, lambda: mock_qb_session, _always_allowed()
        )
        handler(minorversion="65", Line=[{"Amount": 100}])
        call_kwargs = mock_qb_session.call_route.call_args
        assert call_kwargs.kwargs["params"] == {"minorversion": "65"}
        assert call_kwargs.kwargs["body"] == {"Line": [{"Amount": 100}]}

    def test_no_body_for_get(self, sample_api_config, mock_qb_session):
        handler = _make_api_tool(
            sample_api_config, lambda: mock_qb_session, _always_allowed()
        )
        handler(accountId="1", extra_field="should_be_ignored")
        call_kwargs = mock_qb_session.call_route.call_args
        # GET → body should be None (extra kwargs are NOT put in body)
        assert call_kwargs.kwargs["body"] is None


# -----------------------------------------------------------------------
# Session and rate limiter checks
# -----------------------------------------------------------------------
class TestSessionNone:
    def test_returns_error_when_session_none(self, sample_api_config):
        handler = _make_api_tool(
            sample_api_config, lambda: None, _always_allowed()
        )
        result = handler(accountId="1")
        assert "not initialised" in result.text.lower()


class TestRateLimiting:
    def test_blocked_when_rate_limited(self, sample_api_config, mock_qb_session):
        handler = _make_api_tool(
            sample_api_config, lambda: mock_qb_session, _always_blocked()
        )
        result = handler(accountId="1")
        assert "Rate limit" in result.text


# -----------------------------------------------------------------------
# Invalid kwarg types — F-03
# -----------------------------------------------------------------------
class TestInvalidKwargTypes:
    def test_rejects_non_serializable_type(self, sample_api_config, mock_qb_session):
        handler = _make_api_tool(
            sample_api_config, lambda: mock_qb_session, _always_allowed()
        )
        result = handler(accountId=object())
        assert "Invalid type" in result.text


# -----------------------------------------------------------------------
# kwargs string workaround
# -----------------------------------------------------------------------
class TestKwargsStringWorkaround:
    def test_parses_key_equals_value(self, mock_qb_session):
        config = {
            "route": "/account/{accountId}",
            "method": "get",
            "parameters": [
                {"name": "accountId", "location": "path", "required": True, "type": "string", "description": ""},
            ],
            "docstring": "Get account.",
            "tool_name": "get_account",
        }
        handler = _make_api_tool(config, lambda: mock_qb_session, _always_allowed())
        handler(kwargs="accountId=42")
        call_kwargs = mock_qb_session.call_route.call_args
        assert call_kwargs.kwargs["route"] == "/account/42"

    def test_no_equals_leaves_unchanged(self, sample_api_config, mock_qb_session):
        handler = _make_api_tool(
            sample_api_config, lambda: mock_qb_session, _always_allowed()
        )
        # "kwargs" with no '=' should not be parsed
        result = handler(kwargs="noequals")
        # It will try to use "noequals" as the kwargs key — won't match any param
        mock_qb_session.call_route.assert_called_once()


# -----------------------------------------------------------------------
# Handler metadata
# -----------------------------------------------------------------------
class TestHandlerMetadata:
    def test_name_and_doc_set(self, sample_api_config, mock_qb_session):
        handler = _make_api_tool(
            sample_api_config, lambda: mock_qb_session, _always_allowed()
        )
        assert handler.__name__ == "get_account_accountId"
        assert "Get an account by ID." in handler.__doc__
