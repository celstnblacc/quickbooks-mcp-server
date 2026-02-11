"""Tests for query validation in query_quickbooks() — F-03."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# We test query_quickbooks in isolation by importing the function directly
# and mocking the quickbooks session / rate limiter at module level.

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def query_fn(monkeypatch):
    """Return query_quickbooks with the session set to None (no network)."""
    # We need to import after env is set (autouse fixture handles that)
    # Patch requests.post to prevent real HTTP during module import
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "unauthorized"
    with patch("requests.post", return_value=mock_response):
        # Force reimport
        for mod_name in list(sys.modules):
            if mod_name in (
                "main_quickbooks_mcp",
                "quickbooks_interaction",
                "rate_limiter",
                "api_importer",
                "environment",
            ):
                del sys.modules[mod_name]

        from main_quickbooks_mcp import query_quickbooks

    return query_quickbooks


# -----------------------------------------------------------------------
# SELECT queries — should pass validation
# -----------------------------------------------------------------------
class TestSelectAllowed:
    def test_basic_select(self, query_fn):
        result = query_fn("SELECT * FROM Account")
        # Passes validation but session is None → session error
        assert "not initialised" in result.text.lower() or "session" in result.text.lower()

    def test_lowercase_select(self, query_fn):
        result = query_fn("select * from Account")
        assert "Only SELECT" not in result.text

    def test_mixed_case_select(self, query_fn):
        result = query_fn("SeLeCt * FROM Account")
        assert "Only SELECT" not in result.text

    def test_leading_whitespace(self, query_fn):
        result = query_fn("   SELECT * FROM Account")
        assert "Only SELECT" not in result.text

    def test_leading_tab(self, query_fn):
        result = query_fn("\tSELECT * FROM Account")
        assert "Only SELECT" not in result.text


# -----------------------------------------------------------------------
# Blocked queries — should be rejected before touching the network
# -----------------------------------------------------------------------
class TestBlockedQueries:
    def test_delete_blocked(self, query_fn):
        result = query_fn("DELETE FROM Account WHERE Id='1'")
        assert "Only SELECT" in result.text

    def test_update_blocked(self, query_fn):
        result = query_fn("UPDATE Account SET Name='x'")
        assert "Only SELECT" in result.text

    def test_insert_blocked(self, query_fn):
        result = query_fn("INSERT INTO Account VALUES ('x')")
        assert "Only SELECT" in result.text

    def test_drop_blocked(self, query_fn):
        result = query_fn("DROP TABLE Account")
        assert "Only SELECT" in result.text

    def test_alter_blocked(self, query_fn):
        result = query_fn("ALTER TABLE Account ADD Col INT")
        assert "Only SELECT" in result.text

    def test_create_blocked(self, query_fn):
        result = query_fn("CREATE TABLE Foo (id INT)")
        assert "Only SELECT" in result.text


# -----------------------------------------------------------------------
# Injection patterns
# -----------------------------------------------------------------------
class TestInjectionPatterns:
    def test_semicolon_drop(self, query_fn):
        """SELECT followed by DROP via semicolon."""
        result = query_fn("SELECT * FROM Account; DROP TABLE Account")
        assert "Blocked" in result.text or "DROP" in result.text

    def test_empty_query(self, query_fn):
        result = query_fn("")
        assert "Only SELECT" in result.text

    def test_whitespace_only(self, query_fn):
        result = query_fn("   ")
        assert "Only SELECT" in result.text
