"""Tests targeting coverage gaps identified in the coverage report.

Covers uncovered branches in:
- src/api_importer.py     (lines 25-50: response code fallbacks, request body variants)
- src/environment.py      (line 38-39: OSError in permission check)
- src/main_quickbooks_mcp.py (lines 79-88, 132, 140-142, 184-185, 244-247, 334-335)
- src/quickbooks_interaction.py (lines 51, 141, 173-191, 224-236)

Run with: pytest tests/test_coverage_gaps.py -v
"""

import json
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_qb_session():
    """Instantiate QuickBooksSession with a mocked successful token refresh."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"access_token": "tok", "refresh_token": "rt"}
    with patch("requests.post", return_value=mock_resp):
        from quickbooks_interaction import QuickBooksSession
        return QuickBooksSession()


def _schema(paths, components=None):
    """Minimal OpenAPI schema dict for api_importer tests."""
    return {
        "paths": paths,
        "components": {"schemas": components or {}},
    }


def _import_main_fresh(post_status=401):
    """Re-import main_quickbooks_mcp with a fresh module state."""
    for mod in list(sys.modules):
        if "main_quickbooks_mcp" in mod:
            del sys.modules[mod]
    mock_resp = MagicMock()
    mock_resp.status_code = post_status
    mock_resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}
    with patch("requests.post", return_value=mock_resp):
        import main_quickbooks_mcp
    return main_quickbooks_mcp


# ===========================================================================
# api_importer.py — response code fallbacks (lines 25-29)
# ===========================================================================

class TestApiImporterResponseCodes:
    """Fallback logic when '200' is absent from responses dict."""

    def test_2xx_fallback_uses_201(self):
        """Picks 201 when 200 is absent."""
        schema = _schema({"/invoices": {"post": {
            "summary": "Create invoice",
            "responses": {"201": {"description": "Created"}},
            "parameters": [],
        }}})
        with patch("builtins.open", mock_open(read_data=json.dumps(schema))):
            from api_importer import load_apis
            result = load_apis()
        assert result[0]["response_description"] == "Created"

    def test_3xx_fallback_when_no_2xx(self):
        """Falls back to 3xx when no 2xx code is present."""
        schema = _schema({"/redirect": {"get": {
            "summary": "Redirect",
            "responses": {"301": {"description": "Moved Permanently"}},
            "parameters": [],
        }}})
        with patch("builtins.open", mock_open(read_data=json.dumps(schema))):
            from api_importer import load_apis
            result = load_apis()
        assert result[0]["response_description"] == "Moved Permanently"


# ===========================================================================
# api_importer.py — request body variants (lines 35-50)
# ===========================================================================

class TestApiImporterRequestBody:
    """Request body parsing: properties dict, type+description, and $ref."""

    def test_request_body_with_properties(self):
        """Extracts field descriptions from a properties dict (lines 38-40)."""
        schema = _schema({"/account": {"post": {
            "summary": "Create account",
            "responses": {"200": {"description": "OK"}},
            "parameters": [],
            "requestBody": {"content": {"application/json": {"schema": {
                "properties": {
                    "Name": {"description": "Account name"},
                    "Type": {"description": "Account type"},
                }
            }}}},
        }}})
        with patch("builtins.open", mock_open(read_data=json.dumps(schema))):
            from api_importer import load_apis
            result = load_apis()
        assert result[0]["request_data"]["Name"] == "Account name"

    def test_request_body_type_and_description(self):
        """Handles schema with type+description and no properties (lines 42-43)."""
        schema = _schema({"/query": {"get": {
            "summary": "Query",
            "responses": {"200": {"description": "OK"}},
            "parameters": [],
            "requestBody": {"content": {"text/plain": {"schema": {
                "type": "string",
                "description": "SQL query string",
            }}}},
        }}})
        with patch("builtins.open", mock_open(read_data=json.dumps(schema))):
            from api_importer import load_apis
            result = load_apis()
        assert result[0]["request_data"]["string"] == "SQL query string"

    def test_request_body_with_ref(self):
        """Resolves $ref from components/schemas (lines 45-48)."""
        schema = _schema(
            paths={"/account": {"post": {
                "summary": "Create",
                "responses": {"200": {"description": "OK"}},
                "parameters": [],
                "requestBody": {"content": {"application/json": {"schema": {
                    "$ref": "#/components/schemas/Account"
                }}}},
            }}},
            components={"Account": {"properties": {
                "Name": {"description": "Account name"},
            }}},
        )
        with patch("builtins.open", mock_open(read_data=json.dumps(schema))):
            from api_importer import load_apis
            result = load_apis()
        assert "Name" in result[0]["request_data"]

    def test_request_body_unknown_key_raises(self):
        """Unknown schema key raises ValueError (line 50)."""
        schema = _schema({"/account": {"post": {
            "summary": "Create",
            "responses": {"200": {"description": "OK"}},
            "parameters": [],
            "requestBody": {"content": {"application/json": {"schema": {
                "unknownKey": "value"
            }}}},
        }}})
        with patch("builtins.open", mock_open(read_data=json.dumps(schema))):
            from api_importer import load_apis
            with pytest.raises((ValueError, Exception)):
                load_apis()


# ===========================================================================
# environment.py — OSError branch (lines 38-39)
# ===========================================================================

class TestEnvironmentOSError:
    """stat() raising OSError is caught silently (lines 38-39)."""

    def test_oserror_in_stat_does_not_raise(self, caplog):
        """OSError from stat() is caught and logged at DEBUG, no WARNING."""
        import environment
        environment._PERMISSIONS_CHECKED = False

        mock_env_path = MagicMock()
        mock_env_path.exists.return_value = True
        mock_env_path.stat.side_effect = OSError("Permission denied")

        with patch("environment.Path") as MockPath:
            MockPath.return_value.parent.__truediv__.return_value = mock_env_path
            with caplog.at_level(logging.DEBUG, logger="environment"):
                environment._check_env_permissions()

        env_warnings = [
            r for r in caplog.records
            if r.levelno >= logging.WARNING and r.name == "environment"
        ]
        assert len(env_warnings) == 0


# ===========================================================================
# main_quickbooks_mcp.py — get_quickbooks_entity_schema errors (lines 79-88)
# ===========================================================================

class TestGetEntitySchemaErrors:
    """Error branches in get_quickbooks_entity_schema."""

    def test_file_not_found_returns_friendly_message(self):
        """FileNotFoundError → user-friendly message (lines 79-82)."""
        main = _import_main_fresh()
        with patch("builtins.open", side_effect=FileNotFoundError):
            result = main.get_quickbooks_entity_schema("Account")
        assert "not found" in result.text.lower()

    def test_generic_exception_returns_error_message(self):
        """Unexpected exception → generic message without internal details (lines 84-88)."""
        main = _import_main_fresh()
        with patch("builtins.open", side_effect=PermissionError("no access")):
            result = main.get_quickbooks_entity_schema("Account")
        assert "error" in result.text.lower()
        assert "no access" not in result.text


# ===========================================================================
# main_quickbooks_mcp.py — query_quickbooks edge cases (lines 132, 140-142)
# ===========================================================================

class TestQueryQuickBooksEdgeCases:
    """Uncovered branches in query_quickbooks."""

    def test_query_when_session_is_none(self, monkeypatch):
        """Returns error message when quickbooks session is None (line 132)."""
        main = _import_main_fresh()
        monkeypatch.setattr(main, "quickbooks", None)
        result = main.query_quickbooks("SELECT * FROM Account")
        assert "session" in result.text.lower() or "initialised" in result.text.lower()

    def test_query_exception_returns_generic_message(self, monkeypatch):
        """Exception inside query() returns generic message, no leak (lines 140-142)."""
        main = _import_main_fresh()
        mock_session = MagicMock()
        mock_session.query.side_effect = RuntimeError("db connection lost")
        monkeypatch.setattr(main, "quickbooks", mock_session)
        result = main.query_quickbooks("SELECT * FROM Account")
        assert "error" in result.text.lower()
        assert "db connection lost" not in result.text


# ===========================================================================
# main_quickbooks_mcp.py — closure factory edge cases (lines 184-185, 244-247)
# ===========================================================================

class TestMakeApiToolEdgeCases:
    """Edge cases in the closure-factory handler."""

    def test_missing_path_parameter_returns_message(self):
        """KeyError from route.format() returns descriptive message (lines 184-185)."""
        from main_quickbooks_mcp import _make_api_tool
        from rate_limiter import RateLimiter

        mock_session = MagicMock()
        limiter = RateLimiter(requests_per_minute=100)
        # Route uses {id} but parameter name is accountId — mismatch causes KeyError
        config = {
            "route": "/account/{id}",
            "method": "get",
            "parameters": [
                {"name": "accountId", "location": "path", "required": True,
                 "type": "string", "description": "ID"},
            ],
            "docstring": "Get account.",
            "tool_name": "get_account",
        }
        handler = _make_api_tool(config, lambda: mock_session, limiter)
        result = handler(accountId="123")
        assert "missing" in result.text.lower() or "parameter" in result.text.lower()

    def test_handler_exception_returns_generic_message(self):
        """Unexpected exception in handler returns generic message (lines 244-247)."""
        from main_quickbooks_mcp import _make_api_tool
        from rate_limiter import RateLimiter

        mock_session = MagicMock()
        mock_session.call_route.side_effect = RuntimeError("unexpected failure")
        limiter = RateLimiter(requests_per_minute=100)
        config = {
            "route": "/test",
            "method": "get",
            "parameters": [],
            "docstring": "Test.",
            "tool_name": "get_test",
        }
        handler = _make_api_tool(config, lambda: mock_session, limiter)
        result = handler()
        assert "error" in result.text.lower()
        assert "unexpected failure" not in result.text


# ===========================================================================
# main_quickbooks_mcp.py — register_all_apis exception (lines 334-335)
# ===========================================================================

class TestRegisterAllApisException:
    """Exception in load_apis() is caught and logged (lines 334-335)."""

    def test_load_apis_failure_is_caught_and_warned(self, caplog):
        """Warning is emitted when schema loading fails; static tools still work."""
        for mod in list(sys.modules):
            if "main_quickbooks_mcp" in mod:
                del sys.modules[mod]

        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch("requests.post", return_value=mock_resp):
            with patch("api_importer.load_apis", side_effect=Exception("schema missing")):
                with caplog.at_level(logging.WARNING):
                    import main_quickbooks_mcp

        assert any(
            "schema missing" in r.message or "Failed to register" in r.message
            for r in caplog.records
        )
        assert hasattr(main_quickbooks_mcp, "query_quickbooks")


# ===========================================================================
# quickbooks_interaction.py — _get_headers with None token (line 51)
# ===========================================================================

class TestGetHeadersNoneToken:
    """_get_headers returns None when access_token is None (line 51)."""

    def test_returns_none_when_no_access_token(self):
        session = _make_qb_session()
        session.access_token = None
        assert session._get_headers() is None


# ===========================================================================
# quickbooks_interaction.py — route slash handling (line 141)
# ===========================================================================

class TestCallRouteSlashHandling:
    """Route without leading slash has '/' prepended (line 141)."""

    def test_route_without_slash_gets_prepended(self):
        session = _make_qb_session()
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {"ok": True}

        with patch("requests.get", return_value=mock_get_resp) as mock_get:
            session.call_route("get", "query")  # no leading slash

        called_url = mock_get.call_args[0][0]
        assert "/query" in called_url


# ===========================================================================
# quickbooks_interaction.py — 401 retry error branches (lines 173-191)
# ===========================================================================

class TestCallRoute401RetryErrors:
    """Network error and JSON decode error on the 401-retry path."""

    def test_network_error_on_401_retry_returns_error_dict(self):
        """ConnectionError on retry after 401 → error dict (lines 173-180)."""
        from requests.exceptions import ConnectionError as ReqConnectionError

        session = _make_qb_session()
        call_count = {"n": 0}

        def fake_send(method, url, params, body):
            call_count["n"] += 1
            if call_count["n"] == 1:
                r = MagicMock()
                r.status_code = 401
                return r
            raise ReqConnectionError("gone")

        mock_post = MagicMock()
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "new", "refresh_token": "rt"}

        with patch("requests.post", mock_post):
            session._send = fake_send
            result = session.call_route("get", "/query")

        assert "error" in result
        assert "Network error" in result["error"]

    def test_json_decode_error_on_401_retry_returns_error_dict(self):
        """ValueError from json() on retry → error dict (lines 184-191)."""
        session = _make_qb_session()
        call_count = {"n": 0}

        def fake_send(method, url, params, body):
            call_count["n"] += 1
            r = MagicMock()
            if call_count["n"] == 1:
                r.status_code = 401
            else:
                r.status_code = 200
                r.json.side_effect = ValueError("bad json")
            return r

        mock_post = MagicMock()
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "new", "refresh_token": "rt"}

        with patch("requests.post", mock_post):
            session._send = fake_send
            result = session.call_route("get", "/query")

        assert "error" in result
        assert "Invalid JSON" in result["error"]


# ===========================================================================
# quickbooks_interaction.py — convenience methods (lines 224-236)
# ===========================================================================

class TestConvenienceMethods:
    """Thin wrapper methods delegate to call_route correctly."""

    def test_get_account(self):
        session = _make_qb_session()
        session.call_route = MagicMock(return_value={"Account": {}})
        session.get_account("123")
        session.call_route.assert_called_once_with("get", "/account/123")

    def test_get_bill(self):
        session = _make_qb_session()
        session.call_route = MagicMock(return_value={"Bill": {}})
        session.get_bill("456")
        session.call_route.assert_called_once_with("get", "/bill/456")

    def test_get_customer(self):
        session = _make_qb_session()
        session.call_route = MagicMock(return_value={"Customer": {}})
        session.get_customer("789")
        session.call_route.assert_called_once_with("get", "/customer/789")

    def test_get_vendor(self):
        session = _make_qb_session()
        session.call_route = MagicMock(return_value={"Vendor": {}})
        session.get_vendor("abc")
        session.call_route.assert_called_once_with("get", "/vendor/abc")

    def test_get_invoice(self):
        session = _make_qb_session()
        session.call_route = MagicMock(return_value={"Invoice": {}})
        session.get_invoice("def")
        session.call_route.assert_called_once_with("get", "/invoice/def")
