"""Shared fixtures for the quickbooks-mcp-server test suite."""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Dummy environment — prevents real QuickBooks connections during unit tests
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _set_dummy_env(monkeypatch):
    """Inject dummy credentials so modules can be imported safely."""
    monkeypatch.setenv("QUICKBOOKS_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("QUICKBOOKS_CLIENT_SECRET", "test_client_secret")
    monkeypatch.setenv("QUICKBOOKS_REFRESH_TOKEN", "test_refresh_token")
    monkeypatch.setenv("QUICKBOOKS_COMPANY_ID", "test_company_id")
    monkeypatch.setenv("QUICKBOOKS_ENV", "sandbox")


# ---------------------------------------------------------------------------
# Mock QuickBooks session that never hits the network
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_qb_session():
    """Return a MagicMock that behaves like QuickBooksSession."""
    session = MagicMock()
    session.access_token = "fake_access_token"
    session.refresh_token = "fake_refresh_token"
    session.base_url = "https://sandbox-quickbooks.api.intuit.com"
    session.company_id = "test_company_id"
    session.call_route.return_value = {"QueryResponse": {"Account": []}}
    return session


# ---------------------------------------------------------------------------
# Rate limiter helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def fresh_limiter():
    """Return a new RateLimiter with a small capacity for fast tests."""
    from rate_limiter import RateLimiter
    return RateLimiter(requests_per_minute=5)


# ---------------------------------------------------------------------------
# Temporary .env file
# ---------------------------------------------------------------------------
@pytest.fixture
def tmp_env_file(tmp_path):
    """Create a temporary .env file and return its Path."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "QUICKBOOKS_CLIENT_ID=id123\n"
        "QUICKBOOKS_CLIENT_SECRET=secret456\n"
        "QUICKBOOKS_REFRESH_TOKEN=old_token\n"
        "QUICKBOOKS_COMPANY_ID=company789\n"
        "QUICKBOOKS_ENV=sandbox\n"
    )
    return env_file


# ---------------------------------------------------------------------------
# API config fixture for closure factory tests
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_api_config():
    """Return a minimal API config dict for _make_api_tool tests."""
    return {
        "route": "/account/{accountId}",
        "method": "get",
        "parameters": [
            {
                "name": "accountId",
                "location": "path",
                "required": True,
                "type": "string",
                "description": "The account ID",
            }
        ],
        "docstring": "Get an account by ID.",
        "tool_name": "get_account_accountId",
    }


@pytest.fixture
def post_api_config():
    """API config for a POST endpoint with query + body params."""
    return {
        "route": "/invoice",
        "method": "post",
        "parameters": [
            {
                "name": "minorversion",
                "location": "query",
                "required": False,
                "type": "string",
                "description": "Minor version",
            }
        ],
        "docstring": "Create an invoice.",
        "tool_name": "post_invoice",
    }
