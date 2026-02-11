"""Tests for refresh token persistence — F-06."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from quickbooks_interaction import QuickBooksSession


def _make_session():
    """Return a session with mocked init (no real network calls)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "access_token": "at_123",
        "refresh_token": "original_rt",
    }
    with patch("requests.post", return_value=mock_resp):
        s = QuickBooksSession()
    return s


class TestUpdatesExistingLine:
    def test_replaces_token_in_env(self, tmp_env_file):
        session = _make_session()
        session.refresh_token = "brand_new_token"

        # Patch __file__ in quickbooks_interaction module to point to test directory
        import quickbooks_interaction
        with patch.object(quickbooks_interaction, '__file__', str(tmp_env_file)):
            session._persist_refresh_token()

        content = tmp_env_file.read_text()
        assert "QUICKBOOKS_REFRESH_TOKEN=brand_new_token" in content
        assert "old_token" not in content


class TestAppendsIfMissing:
    def test_appends_line_if_no_token_key(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("QUICKBOOKS_CLIENT_ID=id\nQUICKBOOKS_ENV=sandbox\n")

        session = _make_session()
        session.refresh_token = "appended_token"

        # Patch __file__ in quickbooks_interaction module to point to test directory
        import quickbooks_interaction
        with patch.object(quickbooks_interaction, '__file__', str(env_file)):
            session._persist_refresh_token()

        content = env_file.read_text()
        assert "QUICKBOOKS_REFRESH_TOKEN=appended_token" in content
        assert "QUICKBOOKS_CLIENT_ID=id" in content


class TestNoCrashMissingFile:
    def test_no_error_when_env_absent(self, tmp_path):
        env_file = tmp_path / ".env"  # does not exist

        session = _make_session()
        session.refresh_token = "whatever"

        # Patch __file__ in quickbooks_interaction module to point to test directory
        import quickbooks_interaction
        with patch.object(quickbooks_interaction, '__file__', str(env_file)):
            session._persist_refresh_token()  # should not raise


class TestOtherLinesPreserved:
    def test_does_not_modify_other_vars(self, tmp_env_file):
        session = _make_session()
        session.refresh_token = "updated"

        # Patch __file__ in quickbooks_interaction module to point to test directory
        import quickbooks_interaction
        with patch.object(quickbooks_interaction, '__file__', str(tmp_env_file)):
            session._persist_refresh_token()

        content = tmp_env_file.read_text()
        assert "QUICKBOOKS_CLIENT_ID=id123" in content
        assert "QUICKBOOKS_CLIENT_SECRET=secret456" in content
        assert "QUICKBOOKS_COMPANY_ID=company789" in content
        assert "QUICKBOOKS_ENV=sandbox" in content


class TestNoDuplicateLines:
    def test_persist_twice_no_duplication(self, tmp_env_file):
        session = _make_session()

        # Patch __file__ in quickbooks_interaction module to point to test directory
        import quickbooks_interaction
        with patch.object(quickbooks_interaction, '__file__', str(tmp_env_file)):
            session.refresh_token = "first_update"
            session._persist_refresh_token()
            session.refresh_token = "second_update"
            session._persist_refresh_token()

        content = tmp_env_file.read_text()
        count = content.count("QUICKBOOKS_REFRESH_TOKEN=")
        assert count == 1
        assert "QUICKBOOKS_REFRESH_TOKEN=second_update" in content
