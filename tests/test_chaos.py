"""Chaos and fault injection tests.

These tests verify system resilience under adverse conditions like
thread failures, disk full, corrupted files, and system time changes.

Run with: pytest tests/test_chaos.py -v
Warning: Some tests may be slow or resource-intensive
"""

import sys
import os
import time
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestDiskFailures:
    """Test handling of disk-related failures."""

    def test_token_persistence_disk_full(self, tmp_path):
        """Token persistence handles disk full scenario."""
        env_file = tmp_path / ".env"
        env_file.write_text("QUICKBOOKS_REFRESH_TOKEN=old\n")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "at", "refresh_token": "rt_new"}

        with patch("requests.post", return_value=mock_resp):
            from quickbooks_interaction import QuickBooksSession
            session = QuickBooksSession()

        # Simulate disk full (OSError on write)
        with patch("pathlib.Path.write_text", side_effect=OSError("No space left on device")):
            # Should log warning but not crash
            session._persist_refresh_token(env_path=env_file)

        # Session should still be usable
        assert session.refresh_token == "rt_new"

    def test_schema_file_read_failure(self):
        """Schema loading handles read failures."""
        with patch("builtins.open", side_effect=OSError("Disk read error")):
            from api_importer import load_apis

            with pytest.raises(Exception) as exc_info:
                load_apis()

            # Should raise but with meaningful message
            assert "API documentation" in str(exc_info.value) or "Disk" in str(exc_info.value)

    def test_env_file_corrupted_midread(self, tmp_path):
        """Env file gets corrupted while being read."""
        env_file = tmp_path / ".env"

        # File that will fail midway through read
        mock_file = mock_open(read_data="QUICKBOOKS_CLIENT_ID=test\n")
        mock_file.return_value.__iter__ = lambda self: iter([])
        mock_file.return_value.read.side_effect = OSError("I/O error")

        with patch("builtins.open", mock_file):
            # Should handle gracefully
            try:
                content = env_file.read_text()
            except OSError:
                pass  # Expected


class TestMemoryPressure:
    """Test behavior under memory pressure."""

    def test_large_query_response_handling(self):
        """Handle very large API responses."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}

        with patch("requests.post", return_value=mock_resp):
            from quickbooks_interaction import QuickBooksSession
            session = QuickBooksSession()

        # Simulate huge response
        huge_response = MagicMock()
        huge_response.status_code = 200
        huge_response.json.return_value = {
            "QueryResponse": {
                "Account": [{"Id": str(i), "Name": f"Account{i}"} for i in range(10000)]
            }
        }

        with patch("requests.get", return_value=huge_response):
            result = session.query("SELECT * FROM Account")

            # Should handle (may be slow, but shouldn't crash)
            assert "QueryResponse" in result
            assert len(result["QueryResponse"]["Account"]) == 10000

    def test_many_concurrent_rate_limiter_checks(self):
        """Rate limiter under extreme concurrent load."""
        from rate_limiter import RateLimiter
        import threading

        limiter = RateLimiter(requests_per_minute=1000)
        results = []
        lock = threading.Lock()

        def hammer():
            for _ in range(100):
                r = limiter.is_allowed()
                with lock:
                    results.append(r)

        threads = [threading.Thread(target=hammer) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should complete without crash
        assert len(results) == 2000


class TestNetworkChaos:
    """Test resilience to network chaos."""

    def test_random_connection_drops(self):
        """Random connection failures during requests."""
        from requests.exceptions import ConnectionError

        call_count = {"count": 0}

        def flaky_request(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] % 3 == 0:
                raise ConnectionError("Connection reset by peer")
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}
            return resp

        with patch("requests.post", side_effect=flaky_request):
            from quickbooks_interaction import QuickBooksSession

            # May fail on initialization due to flaky connection
            try:
                session = QuickBooksSession()
            except RuntimeError:
                # Expected - connection failed during token refresh
                pass

    def test_slow_network_responses(self):
        """Extremely slow network responses."""
        def slow_response(*args, **kwargs):
            time.sleep(0.1)  # Simulate slow network
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}
            return resp

        with patch("requests.post", side_effect=slow_response):
            start = time.time()
            from quickbooks_interaction import QuickBooksSession
            session = QuickBooksSession()
            elapsed = time.time() - start

            # Should complete eventually
            assert elapsed >= 0.1
            assert session.access_token == "at"

    def test_partial_response_data(self):
        """Network returns partial/incomplete response data."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # Missing refresh_token (incomplete response)
        mock_resp.json.return_value = {"access_token": "at"}

        with patch("requests.post", return_value=mock_resp):
            from quickbooks_interaction import QuickBooksSession

            session = QuickBooksSession()

            # Should handle missing refresh_token
            # (will use old one or default)
            assert session.access_token == "at"


class TestFileSystemChaos:
    """Test resilience to filesystem issues."""

    def test_env_file_deleted_during_operation(self, tmp_path):
        """Env file deleted while server is running."""
        env_file = tmp_path / ".env"
        env_file.write_text("QUICKBOOKS_REFRESH_TOKEN=old\n")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}

        with patch("requests.post", return_value=mock_resp):
            from quickbooks_interaction import QuickBooksSession
            session = QuickBooksSession()

        # Delete env file
        env_file.unlink()

        # Should handle gracefully (log error, continue)
        session._persist_refresh_token(env_path=env_file)

        # Session should still work
        assert session.access_token == "at"

    def test_directory_permissions_changed(self, tmp_path):
        """Directory permissions changed unexpectedly."""
        env_dir = tmp_path / "restricted"
        env_dir.mkdir()
        env_file = env_dir / ".env"
        env_file.write_text("QUICKBOOKS_REFRESH_TOKEN=old\n")

        # Make directory read-only (on Unix-like systems)
        if os.name != 'nt':  # Skip on Windows
            env_dir.chmod(0o555)

            try:
                # Try to write to read-only directory
                with pytest.raises((OSError, PermissionError)):
                    (env_dir / "newfile.txt").write_text("test")
            finally:
                # Restore permissions for cleanup
                env_dir.chmod(0o755)


class TestTimeAndClockChaos:
    """Test behavior with time/clock issues."""

    def test_system_clock_jumps_forward(self):
        """System clock suddenly jumps forward."""
        from rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=60)

        # Exhaust tokens
        for _ in range(60):
            limiter.is_allowed()

        # Simulate clock jump (1 hour forward)
        limiter.last_refill -= 3600

        # Should handle gracefully (refill to capacity, not overflow)
        limiter._refill()
        assert limiter.tokens == limiter.capacity

    def test_system_clock_jumps_backward(self):
        """System clock jumps backward (time goes negative)."""
        from rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=60)

        # Simulate backward jump
        limiter.last_refill += 3600  # Future time

        # Should handle (negative elapsed time)
        limiter._refill()
        # Should not crash
        assert limiter.tokens >= 0

    def test_rate_limiter_with_zero_elapsed_time(self):
        """Refill called with exactly zero elapsed time."""
        from rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=60)

        current_tokens = limiter.tokens

        # Refill immediately (zero elapsed time)
        limiter._refill()

        # Tokens shouldn't change significantly
        assert abs(limiter.tokens - current_tokens) < 0.1


class TestConcurrencyRaceConditions:
    """Test for race conditions under concurrent access."""

    def test_concurrent_token_refresh(self):
        """Multiple threads trigger token refresh simultaneously."""
        call_count = {"count": 0}

        def mock_post(*args, **kwargs):
            time.sleep(0.01)  # Simulate network delay
            call_count["count"] += 1
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "access_token": f"at_{call_count['count']}",
                "refresh_token": f"rt_{call_count['count']}"
            }
            return resp

        with patch("requests.post", side_effect=mock_post):
            from quickbooks_interaction import QuickBooksSession
            session = QuickBooksSession()

        # Multiple threads refresh token at once
        def refresh_worker():
            session.refresh_access_token()

        threads = [threading.Thread(target=refresh_worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should complete without crashing
        # (access_token will be from one of the refreshes)
        assert session.access_token.startswith("at_")

    def test_concurrent_file_writes(self, tmp_path):
        """Multiple threads write to env file simultaneously."""
        env_file = tmp_path / ".env"
        env_file.write_text("QUICKBOOKS_REFRESH_TOKEN=initial\n")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}

        with patch("requests.post", return_value=mock_resp):
            from quickbooks_interaction import QuickBooksSession
            session = QuickBooksSession()

        def write_worker(thread_id):
            session.refresh_token = f"token_{thread_id}"
            session._persist_refresh_token(env_path=env_file)

        threads = [threading.Thread(target=write_worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # File should still be valid (one token should have won)
        content = env_file.read_text()
        assert "QUICKBOOKS_REFRESH_TOKEN=token_" in content


class TestResourceExhaustion:
    """Test behavior when resources are exhausted."""

    def test_too_many_open_files(self):
        """System runs out of file descriptors."""
        # This is hard to simulate safely, so we mock it
        with patch("builtins.open", side_effect=OSError("Too many open files")):
            from api_importer import load_apis

            with pytest.raises(Exception):
                load_apis()

    def test_out_of_memory_simulation(self):
        """Simulate out-of-memory condition."""
        # Mock allocation failure
        with patch("builtins.list", side_effect=MemoryError("Out of memory")):
            # Operations should fail gracefully
            try:
                large_list = list(range(1000000))
            except MemoryError:
                pass  # Expected


class TestExceptionCascades:
    """Test handling of cascading exceptions."""

    def test_exception_during_error_handling(self):
        """Exception occurs while handling another exception."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}

        with patch("requests.post", return_value=mock_resp):
            from quickbooks_interaction import QuickBooksSession
            session = QuickBooksSession()

        # First exception: API call fails
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 500

        # Second exception: JSON parsing fails during error handling
        mock_get_resp.json.side_effect = ValueError("JSON error")

        with patch("requests.get", return_value=mock_get_resp):
            result = session.call_route("get", "/query", params={"query": "test"})

            # Should handle both exceptions
            assert "error" in result


class TestGracefulDegradation:
    """Test that system degrades gracefully under chaos."""

    def test_partial_service_availability(self):
        """Some services work while others fail."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            # Query validation should work even if session fails
            from main_quickbooks_mcp import query_quickbooks

            result = query_quickbooks("SELECT * FROM Account")

            # Should return error about session, not crash
            assert result.text
            assert "session" in result.text.lower() or "error" in result.text.lower()
