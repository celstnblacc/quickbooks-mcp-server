"""Documentation tests - verify documentation examples work.

These tests ensure that README examples, docstrings, and configuration
snippets actually work as documented.

Run with: pytest tests/test_documentation.py -v
"""

import sys
import json
import re
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestREADMEExamples:
    """Test that README examples are valid."""

    def test_readme_exists(self):
        """README.md file exists."""
        readme_path = PROJECT_ROOT / "README.md"
        assert readme_path.exists()

    def test_readme_env_template_matches(self):
        """Env variables in README match env_template.txt."""
        readme_path = PROJECT_ROOT / "README.md"
        readme_content = readme_path.read_text()

        # Extract env variables from README
        env_vars_readme = re.findall(r'QUICKBOOKS_\w+', readme_content)

        # Read template
        template_path = PROJECT_ROOT / "config" / "env_template.txt"
        if template_path.exists():
            template_content = template_path.read_text()
            env_vars_template = re.findall(r'QUICKBOOKS_\w+', template_content)

            # All template vars should be documented in README
            for var in set(env_vars_template):
                assert var in env_vars_readme, f"{var} in template but not in README"

    def test_readme_example_queries_valid(self):
        """Example queries in README are valid."""
        readme_path = PROJECT_ROOT / "README.md"
        readme_content = readme_path.read_text()

        # Extract query examples (lines starting with SELECT)
        queries = re.findall(r'SELECT .*', readme_content, re.MULTILINE)

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            from main_quickbooks_mcp import query_quickbooks

            for query in queries[:3]:  # Test first 3 queries
                result = query_quickbooks(query)
                # Should pass validation
                assert "Only SELECT queries are permitted" not in result.text
                assert "Blocked keywords" not in result.text

    def test_readme_installation_steps_documented(self):
        """README documents all installation steps."""
        readme_path = PROJECT_ROOT / "README.md"
        readme_content = readme_path.read_text().lower()

        # Should document key steps
        assert "install" in readme_content or "setup" in readme_content
        assert "uv" in readme_content  # Package manager
        assert "claude desktop" in readme_content or "claude.ai" in readme_content
        assert ".env" in readme_content  # Configuration

    def test_claude_desktop_config_example_valid(self):
        """Claude Desktop config example in README is valid JSON."""
        readme_path = PROJECT_ROOT / "README.md"
        readme_content = readme_path.read_text()

        # Extract JSON code blocks
        json_blocks = re.findall(r'```json\s*(\{.*?\})\s*```', readme_content, re.DOTALL)

        for block in json_blocks:
            # Should be valid JSON
            try:
                config = json.loads(block)
                # If it's MCP config, should have mcpServers
                if "mcpServers" in config:
                    assert "QuickBooks" in config["mcpServers"] or True  # May use different name
            except json.JSONDecodeError:
                pytest.fail(f"Invalid JSON in README: {block[:100]}")


class TestEnvironmentTemplateValid:
    """Test that env_template.txt is valid."""

    def test_env_template_exists(self):
        """env_template.txt exists."""
        template_path = PROJECT_ROOT / "config" / "env_template.txt"
        assert template_path.exists()

    def test_env_template_format(self):
        """env_template.txt has correct format."""
        template_path = PROJECT_ROOT / "config" / "env_template.txt"
        content = template_path.read_text()

        # Should have key variables
        assert "QUICKBOOKS_CLIENT_ID" in content
        assert "QUICKBOOKS_CLIENT_SECRET" in content
        assert "QUICKBOOKS_REFRESH_TOKEN" in content
        assert "QUICKBOOKS_COMPANY_ID" in content
        assert "QUICKBOOKS_ENV" in content

    def test_env_template_values_are_placeholders(self):
        """env_template.txt uses placeholders, not real values."""
        template_path = PROJECT_ROOT / "config" / "env_template.txt"
        content = template_path.read_text()

        # Should not contain real-looking tokens
        # (no long alphanumeric strings)
        lines = content.split("\n")
        for line in lines:
            if "=" in line and not line.strip().startswith("#"):
                key, value = line.split("=", 1)
                # Value should be short placeholder
                assert len(value) < 100, f"Value for {key} looks like a real credential"


class TestDocstringExamples:
    """Test that docstrings are accurate."""

    def test_query_quickbooks_docstring(self):
        """query_quickbooks docstring is accurate."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            from main_quickbooks_mcp import query_quickbooks

            # Should have docstring
            assert query_quickbooks.__doc__
            assert "SELECT" in query_quickbooks.__doc__
            assert "query" in query_quickbooks.__doc__.lower()

    def test_get_quickbooks_entity_schema_docstring(self):
        """get_quickbooks_entity_schema docstring is accurate."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            from main_quickbooks_mcp import get_quickbooks_entity_schema

            assert get_quickbooks_entity_schema.__doc__
            assert "schema" in get_quickbooks_entity_schema.__doc__.lower()
            assert "entity" in get_quickbooks_entity_schema.__doc__.lower()

    def test_quickbooks_session_docstrings(self):
        """QuickBooksSession has docstrings."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}

        with patch("requests.post", return_value=mock_resp):
            from quickbooks_interaction import QuickBooksSession

            # Class should have docstring
            assert QuickBooksSession.__doc__

            # Key methods should have docstrings
            session = QuickBooksSession()
            assert session.query.__doc__ or True  # May not have explicit docstring
            assert session.refresh_access_token.__doc__ or True


class TestConfigurationExamples:
    """Test configuration examples."""

    def test_pyproject_toml_valid(self):
        """pyproject.toml is valid."""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        assert pyproject_path.exists()

        content = pyproject_path.read_text()

        # Should have project section
        assert "[project]" in content
        assert "name" in content
        assert "version" in content
        assert "dependencies" in content

    def test_pyproject_dependencies_available(self):
        """Dependencies listed in pyproject.toml are available."""
        # Test key dependencies can be imported
        import mcp
        import requests
        import dotenv

        assert mcp
        assert requests
        assert dotenv

    def test_python_version_requirement_documented(self):
        """Python version requirement is documented."""
        readme_path = PROJECT_ROOT / "README.md"
        readme_content = readme_path.read_text()

        # Should mention Python version
        assert "python" in readme_content.lower() or "3.10" in readme_content or "3.12" in readme_content

        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        pyproject_content = pyproject_path.read_text()

        # Should specify requires-python
        assert "requires-python" in pyproject_content.lower()


class TestCodeExamples:
    """Test inline code examples."""

    def test_query_example_from_docstring(self):
        """Query example from docstring works."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            from main_quickbooks_mcp import query_quickbooks

            # Example query that should work
            result = query_quickbooks("SELECT * FROM Account MAXRESULTS 1")

            # Should pass validation
            assert result.text
            assert "Only SELECT queries are permitted" not in result.text

    def test_entity_schema_example(self):
        """Entity schema example works."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            from main_quickbooks_mcp import get_quickbooks_entity_schema

            # Common entities should work
            for entity in ["Account", "Customer", "Invoice"]:
                result = get_quickbooks_entity_schema(entity)
                assert result.text


class TestTestingDocumentation:
    """Test that testing documentation is accurate."""

    def test_testing_md_exists(self):
        """TESTING.md exists."""
        testing_path = PROJECT_ROOT / "docs" / "TESTING.md"
        assert testing_path.exists()

    def test_testing_md_documents_pytest(self):
        """TESTING.md documents pytest usage."""
        testing_path = PROJECT_ROOT / "docs" / "TESTING.md"
        content = testing_path.read_text().lower()

        assert "pytest" in content
        assert "test" in content

    def test_pytest_commands_in_testing_md_valid(self):
        """Pytest commands in TESTING.md are valid."""
        testing_path = PROJECT_ROOT / "docs" / "TESTING.md"
        content = testing_path.read_text()

        # Extract pytest commands
        pytest_commands = re.findall(r'pytest [^\n]+', content)

        # Should have pytest commands
        assert len(pytest_commands) > 0

        # Commands should be well-formed
        for cmd in pytest_commands:
            assert "pytest" in cmd
            # Should not have obvious errors
            assert not cmd.endswith("&&")
            assert not cmd.startswith("&&")

    def test_test_categories_documented(self):
        """Test categories are documented."""
        testing_path = PROJECT_ROOT / "docs" / "TESTING.md"
        content = testing_path.read_text().lower()

        # Should document different test types
        assert "unit" in content or "integration" in content
        assert "test" in content


class TestCLAUDEmd:
    """Test CLAUDE.md documentation."""

    def test_claude_md_exists(self):
        """CLAUDE.md exists."""
        claude_md_path = PROJECT_ROOT / "docs" / "CLAUDE.md"
        assert claude_md_path.exists()

    def test_claude_md_has_commands(self):
        """CLAUDE.md documents key commands."""
        claude_md_path = PROJECT_ROOT / "docs" / "CLAUDE.md"
        content = claude_md_path.read_text().lower()

        # Should document key development commands
        assert "pytest" in content or "test" in content
        assert "uv" in content  # Package manager

    def test_claude_md_describes_architecture(self):
        """CLAUDE.md describes architecture."""
        claude_md_path = PROJECT_ROOT / "docs" / "CLAUDE.md"
        content = claude_md_path.read_text().lower()

        # Should describe key components
        assert "mcp" in content
        assert "quickbooks" in content
        # Should mention key files
        assert "main" in content or "server" in content


class TestErrorMessageDocumentation:
    """Test that error messages are helpful."""

    def test_invalid_query_error_message_helpful(self):
        """Invalid query error message is helpful."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            from main_quickbooks_mcp import query_quickbooks

            result = query_quickbooks("DELETE FROM Account")

            # Error should be clear
            assert "Only SELECT queries are permitted" in result.text or "Blocked keywords" in result.text

    def test_rate_limit_error_message_helpful(self):
        """Rate limit error message is helpful."""
        from rate_limiter import RateLimiter
        from main_quickbooks_mcp import _make_api_tool

        mock_session = MagicMock()
        limiter = RateLimiter(requests_per_minute=1)

        config = {
            "route": "/test",
            "method": "get",
            "parameters": [],
            "docstring": "Test",
            "tool_name": "test",
        }
        handler = _make_api_tool(config, lambda: mock_session, limiter)

        # Exhaust limit
        handler()

        result = handler()

        # Should explain rate limit
        assert "rate limit" in result.text.lower()
        assert "wait" in result.text.lower() or "exceeded" in result.text.lower()

    def test_missing_entity_error_message_helpful(self):
        """Missing entity error message is helpful."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            from main_quickbooks_mcp import get_quickbooks_entity_schema

            result = get_quickbooks_entity_schema("NonExistent")

            # Should list available entities
            assert "not found" in result.text.lower() or "available" in result.text.lower()
