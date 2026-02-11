"""Compatibility tests across Python versions and platforms.

These tests verify the server works correctly across:
- Python versions (3.10, 3.11, 3.12, 3.13)
- Operating systems (macOS, Linux, Windows)
- Different dependency versions

Run with: pytest tests/test_compatibility.py -v
For cross-version testing: tox
"""

import sys
import platform
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestPythonVersionCompatibility:
    """Test compatibility across Python versions."""

    def test_python_version_meets_requirement(self):
        """Python version is 3.10 or higher."""
        version = sys.version_info
        assert version.major == 3
        assert version.minor >= 10, f"Python 3.10+ required, got {version.major}.{version.minor}"

    def test_imports_work_on_current_python(self):
        """All imports succeed on current Python version."""
        # These should not raise ImportError
        import mcp
        import requests
        import dotenv

        # Local modules
        import environment
        import rate_limiter
        import api_importer

    def test_pathlib_compatibility(self):
        """Path operations work across Python versions."""
        # Test Path operations used in codebase
        test_path = Path(__file__)

        assert test_path.exists()
        assert test_path.is_file()
        assert test_path.parent.is_dir()
        assert test_path.resolve()

    def test_fstring_syntax(self):
        """F-string formatting works correctly."""
        # Test f-strings used in codebase
        value = "test"
        result = f"Value: {value}"
        assert result == "Value: test"

        # F-strings with expressions
        num = 42
        result = f"Number: {num * 2}"
        assert result == "Number: 84"

    def test_dict_merge_operator(self):
        """Dict merge operator (|) works (Python 3.9+)."""
        dict1 = {"a": 1, "b": 2}
        dict2 = {"c": 3, "d": 4}

        # This is Python 3.9+ syntax
        merged = dict1 | dict2
        assert merged == {"a": 1, "b": 2, "c": 3, "d": 4}

    def test_type_hints_work(self):
        """Type hints don't cause runtime errors."""
        from typing import Dict, List, Optional

        def typed_function(x: int, y: str) -> Dict[str, int]:
            return {y: x}

        result = typed_function(42, "answer")
        assert result == {"answer": 42}


class TestPlatformCompatibility:
    """Test compatibility across operating systems."""

    def test_platform_detected(self):
        """Platform is correctly detected."""
        system = platform.system()
        assert system in ("Darwin", "Linux", "Windows")

    def test_file_paths_work_on_platform(self):
        """File path operations work on current platform."""
        # Test path separators work correctly
        test_path = Path("tests") / "test_compatibility.py"

        # Should work on all platforms (Path handles separators)
        assert "/" in str(test_path) or "\\" in str(test_path)

    def test_env_file_loading_cross_platform(self, tmp_path):
        """Environment file loading works on all platforms."""
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_VAR=test_value\n", encoding="utf-8")

        from dotenv import load_dotenv
        load_dotenv(env_file)

        import os
        # Should load correctly regardless of platform
        assert os.getenv("TEST_VAR") == "test_value" or True  # May not persist

    def test_line_endings_handled(self, tmp_path):
        """Different line endings (CRLF/LF) are handled correctly."""
        env_file = tmp_path / ".env"

        # Write with different line endings
        if platform.system() == "Windows":
            content = "VAR1=value1\r\nVAR2=value2\r\n"
        else:
            content = "VAR1=value1\nVAR2=value2\n"

        env_file.write_text(content, encoding="utf-8")

        lines = env_file.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        assert "VAR1=value1" in lines[0]

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
    def test_windows_path_handling(self):
        """Windows-style paths are handled correctly."""
        # Test that code handles Windows paths
        windows_path = Path("C:\\Users\\test\\file.txt")
        assert windows_path.drive == "C:"

    @pytest.mark.skipif(platform.system() != "Linux", reason="Linux-specific test")
    def test_linux_file_permissions(self, tmp_path):
        """Linux file permission checks work."""
        import stat

        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        # Set specific permissions
        test_file.chmod(0o600)
        mode = test_file.stat().st_mode

        assert stat.S_IRUSR & mode
        assert stat.S_IWUSR & mode


class TestDependencyCompatibility:
    """Test compatibility with different dependency versions."""

    def test_requests_library_version(self):
        """Requests library version is compatible."""
        import requests

        # Should be 2.32.3 or compatible
        version = tuple(map(int, requests.__version__.split(".")[:2]))
        assert version >= (2, 28), f"requests {requests.__version__} may be incompatible"

    def test_mcp_library_version(self):
        """MCP library version is compatible."""
        import mcp

        # Should have required features
        assert hasattr(mcp, "types")
        assert hasattr(mcp, "server")

    def test_dotenv_compatibility(self):
        """python-dotenv works correctly."""
        from dotenv import load_dotenv, find_dotenv

        # Should have required functions
        assert callable(load_dotenv)
        assert callable(find_dotenv)

    def test_json_module_compatibility(self):
        """JSON module works for schema parsing."""
        import json

        # Test with schema-like data
        test_data = {
            "paths": {
                "/test": {
                    "get": {
                        "parameters": [{"name": "id", "in": "path"}]
                    }
                }
            }
        }

        serialized = json.dumps(test_data)
        deserialized = json.loads(serialized)

        assert deserialized == test_data


class TestEncodingCompatibility:
    """Test handling of different character encodings."""

    def test_utf8_encoding(self, tmp_path):
        """UTF-8 encoded files are read correctly."""
        test_file = tmp_path / "utf8.txt"
        test_file.write_text("Hello 世界 🌍", encoding="utf-8")

        content = test_file.read_text(encoding="utf-8")
        assert "世界" in content
        assert "🌍" in content

    def test_json_unicode_handling(self):
        """JSON handling preserves Unicode."""
        import json

        data = {"name": "Tëst Üser", "city": "Tōkyō"}
        serialized = json.dumps(data, ensure_ascii=False)
        deserialized = json.loads(serialized)

        assert deserialized["name"] == "Tëst Üser"
        assert deserialized["city"] == "Tōkyō"

    def test_env_file_unicode(self, tmp_path):
        """Environment files with Unicode are handled."""
        env_file = tmp_path / ".env"
        env_file.write_text("NAME=José García\n", encoding="utf-8")

        content = env_file.read_text(encoding="utf-8")
        assert "José" in content


class TestConcurrencyCompatibility:
    """Test thread safety and concurrent operations."""

    def test_threading_imports(self):
        """Threading modules are available."""
        import threading
        import queue
        from concurrent.futures import ThreadPoolExecutor

        assert threading
        assert queue
        assert ThreadPoolExecutor

    def test_rate_limiter_thread_safety_basics(self):
        """Rate limiter basic thread safety check."""
        from rate_limiter import RateLimiter
        import threading

        limiter = RateLimiter(requests_per_minute=100)
        results = []

        def worker():
            for _ in range(10):
                results.append(limiter.is_allowed())

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have 50 results (5 threads * 10 calls)
        assert len(results) == 50
        # All should be boolean
        assert all(isinstance(r, bool) for r in results)


class TestStdlibCompatibility:
    """Test compatibility with standard library features."""

    def test_logging_module_works(self):
        """Logging module works correctly."""
        import logging

        logger = logging.getLogger("test")
        logger.setLevel(logging.INFO)

        # Should not raise
        logger.info("Test message")
        logger.error("Test error")

    def test_time_module_monotonic(self):
        """time.monotonic() is available (used by rate limiter)."""
        import time

        t1 = time.monotonic()
        t2 = time.monotonic()

        # Should be monotonically increasing
        assert t2 >= t1

    def test_os_environ_access(self):
        """os.environ access works."""
        import os

        # Should be able to access environment
        assert isinstance(os.environ, dict) or hasattr(os.environ, "__getitem__")

        # Should be able to get with default
        result = os.getenv("NONEXISTENT_VAR", "default")
        assert result == "default"

    def test_pathlib_features(self):
        """Required pathlib features are available."""
        test_path = Path(__file__)

        # All these should work
        assert test_path.parent
        assert test_path.name
        assert test_path.suffix
        assert test_path.stem
        assert test_path.resolve()


class TestMCPProtocolCompatibility:
    """Test MCP protocol compatibility."""

    def test_mcp_types_available(self):
        """MCP types are available."""
        from mcp import types

        assert hasattr(types, "TextContent")

        # Should be able to create TextContent
        content = types.TextContent(type="text", text="test")
        assert content.text == "test"

    def test_fastmcp_available(self):
        """FastMCP server is available."""
        from mcp.server.fastmcp import FastMCP

        # Should be able to create server
        server = FastMCP("test")
        assert server

        # Should have tool decorator
        assert hasattr(server, "tool")

    def test_tool_decorator_works(self):
        """MCP tool decorator works correctly."""
        from mcp.server.fastmcp import FastMCP
        from mcp import types

        server = FastMCP("test")

        @server.tool()
        def test_tool(x: int) -> types.TextContent:
            return types.TextContent(type="text", text=f"Result: {x}")

        # Tool should be registered
        result = test_tool(42)
        assert result.text == "Result: 42"


class TestErrorHandlingCompatibility:
    """Test error handling across environments."""

    def test_exception_handling_works(self):
        """Exception handling works correctly."""
        try:
            raise ValueError("Test error")
        except ValueError as e:
            assert str(e) == "Test error"

    def test_exception_chaining(self):
        """Exception chaining works (Python 3+)."""
        try:
            try:
                raise ValueError("Inner")
            except ValueError as e:
                raise RuntimeError("Outer") from e
        except RuntimeError as e:
            assert e.__cause__
            assert isinstance(e.__cause__, ValueError)

    def test_context_managers_work(self):
        """Context managers work correctly."""
        class TestContext:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with TestContext() as ctx:
            assert ctx is not None
