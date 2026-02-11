"""Security regression tests — prevent reintroduction of fixed vulnerabilities."""

import ast
import sys
import inspect
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestNoExecInSource:
    """F-01 regression: exec() must never appear as a call in the source."""

    def test_no_exec_calls_in_main(self):
        source_path = PROJECT_ROOT / "main_quickbooks_mcp.py"
        source = source_path.read_text()
        tree = ast.parse(source)

        exec_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "exec":
                    exec_calls.append(node.lineno)

        assert exec_calls == [], f"exec() found at lines: {exec_calls}"

    def test_no_eval_calls_in_main(self):
        source_path = PROJECT_ROOT / "main_quickbooks_mcp.py"
        source = source_path.read_text()
        tree = ast.parse(source)

        eval_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "eval":
                    eval_calls.append(node.lineno)

        assert eval_calls == [], f"eval() found at lines: {eval_calls}"

    def test_no_exec_in_any_py_file(self):
        """No .py file in the project should use exec() or eval()."""
        dangerous = []
        for py_file in PROJECT_ROOT.glob("*.py"):
            if py_file.name.startswith("test_"):
                continue
            source = py_file.read_text()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name) and func.id in ("exec", "eval"):
                        dangerous.append(f"{py_file.name}:{node.lineno} → {func.id}()")

        assert dangerous == [], f"Dangerous calls found: {dangerous}"


class TestNoTokenInOutput:
    """F-04 regression: access token must never be printed."""

    def test_no_token_print_in_interaction(self):
        source_path = PROJECT_ROOT / "quickbooks_interaction.py"
        source = source_path.read_text()
        # Should not contain print statements that include access_token
        assert 'print("Access token:' not in source
        assert "print('Access token:" not in source
        assert "print(f" not in source or "access_token" not in source.split("print(f")[-1].split(")")[0] if "print(f" in source else True

    def test_no_main_block_with_token(self):
        source_path = PROJECT_ROOT / "quickbooks_interaction.py"
        source = source_path.read_text()
        # The __main__ block should not reference access_token
        if '__name__' in source and '__main__' in source:
            # Find the __main__ block
            idx = source.index("__main__")
            rest = source[idx:]
            assert "access_token" not in rest


class TestSchemaPoisoningSafe:
    """F-01 regression: malicious OpenAPI schema data should not execute code."""

    def test_malicious_summary_becomes_docstring(self):
        """A schema summary containing Python code should just be a string."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if mod in ("main_quickbooks_mcp", "quickbooks_interaction", "rate_limiter", "api_importer", "environment"):
                    del sys.modules[mod]
            from main_quickbooks_mcp import _make_api_tool

        # Simulate a poisoned API config
        evil_config = {
            "route": "/test",
            "method": "get",
            "parameters": [],
            "docstring": '"; import os; os.system("echo pwned"); "',
            "tool_name": "evil_tool",
        }

        # The factory should just create a handler with the evil string as docstring
        mock_session = MagicMock()
        mock_session.call_route.return_value = {"ok": True}
        limiter = MagicMock()
        limiter.is_allowed.return_value = True

        handler = _make_api_tool(evil_config, lambda: mock_session, limiter)

        # The evil string is just a docstring, not executed code
        assert 'import os' in handler.__doc__
        assert handler.__name__ == "evil_tool"

        # Calling the handler should work normally — no code execution
        result = handler()
        assert result.text  # should return something (either success or error)


class TestGetAttrGuarded:
    """F-02 regression: getattr must be guarded by the allowlist."""

    def test_dunder_class_rejected(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}
        with patch("requests.post", return_value=mock_resp):
            from quickbooks_interaction import QuickBooksSession
            session = QuickBooksSession()

        with pytest.raises(ValueError, match="Invalid HTTP method"):
            session.call_route("__class__", "/test")


class TestErrorResponsesClean:
    """F-07 regression: no sensitive data patterns in error responses."""

    SENSITIVE_PATTERNS = [
        "Traceback",
        'File "',
        "client_secret",
        "refresh_token=",
        "Bearer ",
    ]

    def test_api_errors_are_clean(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}
        with patch("requests.post", return_value=mock_resp):
            from quickbooks_interaction import QuickBooksSession
            session = QuickBooksSession()

        error_resp = MagicMock()
        error_resp.status_code = 500
        error_resp.text = (
            'Traceback: File "/app/secrets.py" line 42\n'
            "client_secret=abc refresh_token=xyz Bearer tok123"
        )

        with patch("requests.get", return_value=error_resp):
            result = session.call_route("get", "/fail")

        result_str = str(result)
        for pattern in self.SENSITIVE_PATTERNS:
            assert pattern not in result_str, f"Sensitive pattern '{pattern}' found in: {result_str}"
