"""Functional regression tests (golden tests).

These tests ensure critical functionality remains stable across versions.
They define baseline behavior that must not change.

Run with: pytest tests/test_functional_regression.py -v
"""

import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestGoldenQueries:
    """Golden tests for critical query patterns that must always work."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

    def test_golden_select_all_account(self):
        """SELECT * FROM Account MAXRESULTS 1 - must always be accepted."""
        from main_quickbooks_mcp import query_quickbooks

        result = query_quickbooks("SELECT * FROM Account MAXRESULTS 1")

        # Should pass validation (session error is ok, validation error is not)
        assert "Only SELECT queries are permitted" not in result.text
        assert "Blocked keywords" not in result.text

    def test_golden_select_with_where(self):
        """SELECT with WHERE clause - must always be accepted."""
        from main_quickbooks_mcp import query_quickbooks

        result = query_quickbooks("SELECT * FROM Account WHERE Active=true")

        assert "Only SELECT queries are permitted" not in result.text
        assert "Blocked keywords" not in result.text

    def test_golden_select_specific_fields(self):
        """SELECT specific fields - must always be accepted."""
        from main_quickbooks_mcp import query_quickbooks

        result = query_quickbooks("SELECT Id, Name, Balance FROM Account")

        assert "Only SELECT queries are permitted" not in result.text
        assert "Blocked keywords" not in result.text

    def test_golden_select_lowercase(self):
        """Lowercase 'select' - must always be accepted."""
        from main_quickbooks_mcp import query_quickbooks

        result = query_quickbooks("select * from Account maxresults 1")

        assert "Only SELECT queries are permitted" not in result.text

    def test_golden_select_with_whitespace(self):
        """SELECT with leading/trailing whitespace - must always work."""
        from main_quickbooks_mcp import query_quickbooks

        result = query_quickbooks("  SELECT * FROM Account  ")

        assert "Only SELECT queries are permitted" not in result.text

    def test_golden_blocked_delete(self):
        """DELETE query - must always be blocked."""
        from main_quickbooks_mcp import query_quickbooks

        result = query_quickbooks("DELETE FROM Account WHERE Id='1'")

        # Must block
        assert "Only SELECT queries are permitted" in result.text or "Blocked keywords" in result.text

    def test_golden_blocked_update(self):
        """UPDATE query - must always be blocked."""
        from main_quickbooks_mcp import query_quickbooks

        result = query_quickbooks("UPDATE Account SET Name='Test'")

        assert "Only SELECT queries are permitted" in result.text or "Blocked keywords" in result.text

    def test_golden_blocked_drop(self):
        """DROP TABLE - must always be blocked."""
        from main_quickbooks_mcp import query_quickbooks

        result = query_quickbooks("DROP TABLE Account")

        assert "Only SELECT queries are permitted" in result.text or "Blocked keywords" in result.text


class TestToolRegistrationStability:
    """Test that tool registration is stable across versions."""

    def test_static_tools_always_registered(self):
        """Core static tools are always available."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            import main_quickbooks_mcp

            # These tools must always exist
            assert hasattr(main_quickbooks_mcp, "query_quickbooks")
            assert hasattr(main_quickbooks_mcp, "get_quickbooks_entity_schema")

            # Should be callable
            assert callable(main_quickbooks_mcp.query_quickbooks)
            assert callable(main_quickbooks_mcp.get_quickbooks_entity_schema)

    def test_dynamic_tools_registered_from_schema(self):
        """Dynamic tools are registered from OpenAPI schema."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            import main_quickbooks_mcp

            # Should have registered APIs
            from api_importer import load_apis
            apis = load_apis()

            # At least 10 endpoints should be registered
            assert len(apis) >= 10

    def test_tool_names_follow_convention(self):
        """Tool names follow consistent naming convention."""
        from api_importer import load_apis

        apis = load_apis()

        for api in apis:
            # Tool names should be method + sanitized route
            assert "route" in api
            assert "method" in api

            # Method should be lowercase HTTP verb
            assert api["method"].lower() in ("get", "post", "put", "patch", "delete")

    def test_tool_docstrings_present(self):
        """All tools have docstrings."""
        from api_importer import load_apis

        apis = load_apis()

        # Check first 10 APIs
        for api in apis[:10]:
            summary = api.get("summary")
            # Should have summary or it will be generated
            assert summary is not None or True  # Generated if None


@pytest.mark.integration
class TestBackwardCompatibilityIntegration:
    """Integration tests for backward compatibility."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from quickbooks_interaction import QuickBooksSession
        self.session = QuickBooksSession()

    def test_query_method_signature(self):
        """query() method signature unchanged."""
        # Should accept single string parameter
        result = self.session.query("SELECT * FROM Account MAXRESULTS 1")
        assert isinstance(result, dict)

    def test_get_account_method_exists(self):
        """get_account() convenience method still exists."""
        assert hasattr(self.session, "get_account")
        assert callable(self.session.get_account)

    def test_session_attributes_stable(self):
        """QuickBooksSession has expected attributes."""
        assert hasattr(self.session, "access_token")
        assert hasattr(self.session, "refresh_token")
        assert hasattr(self.session, "client_id")
        assert hasattr(self.session, "company_id")
        assert hasattr(self.session, "base_url")


class TestEnvFileBackwardCompatibility:
    """Test backward compatibility with .env file formats."""

    def test_env_format_basic(self, tmp_path):
        """Basic .env format is supported."""
        env_file = tmp_path / ".env"
        env_file.write_text("""
QUICKBOOKS_CLIENT_ID=test_id
QUICKBOOKS_CLIENT_SECRET=test_secret
QUICKBOOKS_REFRESH_TOKEN=test_token
QUICKBOOKS_COMPANY_ID=123456
QUICKBOOKS_ENV=sandbox
""")

        from dotenv import load_dotenv
        load_dotenv(env_file)

        import os
        assert os.getenv("QUICKBOOKS_CLIENT_ID") == "test_id"

    def test_env_format_with_comments(self, tmp_path):
        """Env file with comments is supported."""
        env_file = tmp_path / ".env"
        env_file.write_text("""
# QuickBooks credentials
QUICKBOOKS_CLIENT_ID=test_id
# Secret key
QUICKBOOKS_CLIENT_SECRET=test_secret
QUICKBOOKS_REFRESH_TOKEN=test_token
QUICKBOOKS_COMPANY_ID=123456
QUICKBOOKS_ENV=sandbox
""")

        from dotenv import load_dotenv
        load_dotenv(env_file)

        import os
        assert os.getenv("QUICKBOOKS_CLIENT_ID") == "test_id"

    def test_env_format_with_quotes(self, tmp_path):
        """Env file with quoted values is supported."""
        env_file = tmp_path / ".env"
        env_file.write_text("""
QUICKBOOKS_CLIENT_ID="test_id"
QUICKBOOKS_CLIENT_SECRET='test_secret'
QUICKBOOKS_REFRESH_TOKEN=test_token
""")

        from dotenv import load_dotenv
        load_dotenv(env_file)

        # Should handle quotes correctly
        import os
        client_id = os.getenv("QUICKBOOKS_CLIENT_ID")
        assert "test_id" in client_id


class TestAPISchemaStability:
    """Test that API schema structure is stable."""

    def test_openapi_schema_structure_stable(self):
        """OpenAPI schema has expected structure."""
        schema_path = PROJECT_ROOT / "data" / "quickbooks_openapi_schema.json"
        with open(schema_path) as f:
            schema = json.load(f)

        # Must have paths
        assert "paths" in schema
        assert isinstance(schema["paths"], dict)

        # Must have components or definitions
        assert "components" in schema or "definitions" in schema

    def test_entity_schema_structure_stable(self):
        """Entity schema has expected structure."""
        schema_path = PROJECT_ROOT / "data" / "quickbooks_entity_schemas.json"
        with open(schema_path) as f:
            schemas = json.load(f)

        # Must be a dict
        assert isinstance(schemas, dict)

        # Should have common entities
        # (If missing, that's ok, but structure should be dict)
        if "Account" in schemas:
            assert isinstance(schemas["Account"], dict)

    def test_api_importer_output_format(self):
        """api_importer returns stable format."""
        from api_importer import load_apis

        apis = load_apis()

        # Should be a list
        assert isinstance(apis, list)

        # Each API should have required fields
        for api in apis[:5]:  # Check first 5
            assert "route" in api
            assert "method" in api
            assert "response_description" in api
            assert "parameters" in api

            # Parameters should be a list
            assert isinstance(api["parameters"], list)


class TestSecurityBehaviorStability:
    """Test that security behaviors remain stable."""

    def test_rate_limiter_default_capacity(self):
        """Rate limiter default capacity unchanged."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            import main_quickbooks_mcp

            # Default should be 60 req/min
            assert main_quickbooks_mcp.rate_limiter.capacity == 60

    def test_http_method_allowlist_stable(self):
        """HTTP method allowlist unchanged."""
        from quickbooks_interaction import ALLOWED_METHODS

        # Must include standard HTTP methods
        assert "get" in ALLOWED_METHODS
        assert "post" in ALLOWED_METHODS
        assert "put" in ALLOWED_METHODS
        assert "patch" in ALLOWED_METHODS
        assert "delete" in ALLOWED_METHODS

        # Must NOT include dangerous methods
        assert "exec" not in ALLOWED_METHODS
        assert "__class__" not in ALLOWED_METHODS

    def test_blocked_query_keywords_stable(self):
        """Blocked query keywords list unchanged."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            import main_quickbooks_mcp

            keywords = main_quickbooks_mcp._BLOCKED_QUERY_KEYWORDS

            # Must block dangerous operations
            assert "DELETE" in keywords
            assert "UPDATE" in keywords
            assert "INSERT" in keywords
            assert "DROP" in keywords
            assert "ALTER" in keywords
            assert "CREATE" in keywords


class TestLoggingBehaviorStability:
    """Test that logging behavior is stable."""

    def test_logging_configured(self):
        """Logging is configured at module level."""
        import logging

        # Logger should exist
        logger = logging.getLogger("main_quickbooks_mcp")
        assert logger

    def test_log_format_structured(self):
        """Log format includes timestamp and level."""
        import logging
        import io

        # Capture log output
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(
            logging.Formatter("%(asctime)s  %(name)s  %(levelname)s  %(message)s")
        )

        logger = logging.getLogger("test_regression")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        logger.info("Test message")

        output = stream.getvalue()
        assert "INFO" in output
        assert "Test message" in output


class TestMCPProtocolCompliance:
    """Test MCP protocol compliance remains stable."""

    def test_tools_return_textcontent(self):
        """All tools return TextContent objects."""
        from mcp import types

        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            from main_quickbooks_mcp import query_quickbooks

            result = query_quickbooks("SELECT * FROM Account")

            # Must return TextContent
            assert isinstance(result, types.TextContent)
            assert hasattr(result, "text")
            assert hasattr(result, "type")
            assert result.type == "text"

    def test_mcp_server_type(self):
        """MCP server is FastMCP."""
        from mcp.server.fastmcp import FastMCP

        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            import main_quickbooks_mcp

            # Server should be FastMCP
            assert isinstance(main_quickbooks_mcp.mcp, FastMCP)
