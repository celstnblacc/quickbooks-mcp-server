"""Tests for HTTP method allowlist in QuickBooksSession — F-02."""

import pytest
from unittest.mock import patch, MagicMock

from quickbooks_interaction import QuickBooksSession, ALLOWED_METHODS


@pytest.fixture
def session():
    """Create a QuickBooksSession without hitting the real token endpoint."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "access_token": "fake_at",
        "refresh_token": "fake_rt",
    }
    with patch("requests.post", return_value=mock_resp):
        s = QuickBooksSession()
    return s


# -----------------------------------------------------------------------
# Valid methods
# -----------------------------------------------------------------------
class TestValidMethods:
    @pytest.mark.parametrize("method", ["get", "post", "put", "patch", "delete"])
    def test_allowed_lowercase(self, session, method):
        """All five standard HTTP methods should be accepted."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True}
        with patch(f"requests.{method}", return_value=mock_resp):
            result = session.call_route(method, "/test")
        assert result == {"ok": True}

    @pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE"])
    def test_allowed_uppercase(self, session, method):
        """Uppercase variants should be normalised and accepted."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True}
        with patch(f"requests.{method.lower()}", return_value=mock_resp):
            result = session.call_route(method, "/test")
        assert result == {"ok": True}


# -----------------------------------------------------------------------
# Invalid methods
# -----------------------------------------------------------------------
class TestInvalidMethods:
    @pytest.mark.parametrize(
        "method",
        ["Session", "__class__", "__init__", "request", "options", "head", ""],
    )
    def test_rejected(self, session, method):
        """Methods outside the allowlist must raise ValueError."""
        with pytest.raises(ValueError, match="Invalid HTTP method"):
            session.call_route(method, "/test")


class TestAllowlistContents:
    def test_exactly_five_methods(self):
        assert ALLOWED_METHODS == frozenset({"get", "post", "put", "patch", "delete"})
