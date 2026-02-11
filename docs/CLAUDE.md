# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Python MCP (Model Context Protocol) server that provides Claude Desktop with access to QuickBooks APIs via natural language. The server dynamically generates MCP tools from OpenAPI schema definitions and implements comprehensive security hardening.

## Development Commands

### Environment Setup
```bash
# Install uv package manager
# MacOS/Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows:
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Create .env from template
cp config/env_template.txt .env
# Then edit .env with QuickBooks credentials

# Set secure permissions on .env
chmod 600 .env
```

### Running the Server
```bash
# Run MCP server (typically invoked by Claude Desktop)
uv run src/main_quickbooks_mcp.py
```

### Testing
```bash
# Install test dependencies
uv sync --extra test

# Run all test types (recommended)
./scripts/run_tests.sh

# Run with coverage report
./scripts/run_tests.sh --coverage

# Skip integration tests (no credentials needed)
./scripts/run_tests.sh --no-integration

# Verbose output
./scripts/run_tests.sh --verbose

# Manual test commands:
# Run all unit tests (no credentials required)
pytest tests/ -m "not integration"

# Run integration tests (requires sandbox .env)
pytest tests/ -m integration

# Run specific test category
pytest tests/ -k "security_regression"

# Run with coverage
pytest tests/ --cov=. --cov-report=term-missing

# Run a single test file
pytest tests/test_rate_limiter.py -v
```

## Git Workflow (MANDATORY)

**Before EVERY commit, you MUST:**

1. **Run all tests:**
   ```bash
   ./scripts/run_tests.sh --fast
   # Or for full test suite:
   ./scripts/run_tests.sh
   ```

2. **Update documentation:**
   - Update relevant docs if code changes affect usage
   - Check: README.md, docs/CLAUDE.md, docs/TESTING.md
   - Update examples if function signatures changed

3. **Confirm each commit:**
   - Review all changes: `git status` and `git diff`
   - Write clear, descriptive commit messages
   - Follow format: "Action: Description\n\nDetails..."

4. **Confirm before push:**
   - Review commits: `git log --oneline -5`
   - Verify branch: `git branch --show-current`
   - Only push after explicit confirmation

**Never:**
- ❌ Commit without running tests
- ❌ Push without updating docs
- ❌ Auto-push without user confirmation
- ❌ Skip the verification steps

## Architecture

### Entry Point and MCP Setup
**`src/main_quickbooks_mcp.py`** is the main entry point. It:
- Initializes the `FastMCP` server and `QuickBooksSession`
- Registers static tools (`query_quickbooks`, `get_quickbooks_entity_schema`)
- Dynamically registers API tools from OpenAPI schema via `register_all_apis()`
- Uses a **closure-based factory** (`_make_api_tool()`) instead of `exec()` to generate tool handlers safely

### OAuth2 Session Management
**`src/quickbooks_interaction.py`** handles all QuickBooks API communication:
- Manages OAuth2 refresh token flow with automatic token refresh on 401
- Persists rotated refresh tokens back to `.env` to survive restarts
- Validates HTTP methods against an allowlist (`ALLOWED_METHODS`)
- Enforces TLS verification (`verify=True`) on all requests
- Provides convenience methods (`query()`, `get_account()`, etc.)

### Schema Loading
**`src/api_importer.py`** parses `data/quickbooks_openapi_schema.json`:
- Extracts route, method, parameters, request body structure, and response descriptions
- Distinguishes between path parameters (in URL) and query parameters
- Returns a list of API configurations consumed by the tool factory

### Security Components
- **`src/rate_limiter.py`**: Token-bucket limiter (default: 60 req/min) checked before every API call
- **`src/environment.py`**: Loads `.env` with one-time permission check (warns if mode > 0o600)
- **Query validation** (in `src/main_quickbooks_mcp.py`): Only allows `SELECT` queries; blocks `DELETE`, `UPDATE`, `INSERT`, `DROP`, `ALTER`, `CREATE`
- **Error sanitization**: All error responses returned to MCP clients are generic; full details logged internally only

### Data Files
- **`data/quickbooks_openapi_schema.json`**: Full OpenAPI spec for QuickBooks API endpoints
- **`data/quickbooks_entity_schemas.json`**: Metadata for QuickBooks entities (Account, Bill, Customer, etc.) to help construct queries

## Security Context

In February 2026, a comprehensive security audit identified and fixed 10 vulnerabilities (F-01 through F-10). Key fixes:
- **F-01**: Replaced `exec()` with closure factory for tool generation
- **F-02**: Added HTTP method allowlist to prevent attribute injection
- **F-03**: Query validation blocks destructive SQL keywords
- **F-04**: Removed debug code that leaked OAuth tokens to stdout
- **F-05**: Added `.env` permission checks at startup
- **F-06**: Automatic refresh token persistence to `.env`
- **F-07**: Sanitized all error messages returned to clients
- **F-08**: Added rate limiting on all tool invocations
- **F-09**: Explicit `verify=True` on all HTTP requests
- **F-10**: Structured logging with timestamps

**When modifying this codebase:**
- Never use `exec()` or `eval()` for code generation
- Always validate user input before passing to APIs
- Never log or return sensitive data (tokens, full tracebacks) to MCP clients
- Maintain the HTTP method allowlist and query keyword blocklist
- Check `.env` is not committed (it's in `.gitignore`)

## Test Organization

Tests live in `tests/` and are organized by category (see `TESTING.md` for full details):
- **Unit tests**: Fast, mocked, no network access (default)
- **Integration tests**: Require sandbox credentials, use `@pytest.mark.integration`
- **Security regression tests**: Verify vulnerabilities F-01 through F-10 remain fixed

## Claude Desktop Configuration

Users configure Claude Desktop to run this server by editing `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "QuickBooks": {
      "command": "uv",
      "args": [
        "--directory",
        "<absolute_path_to_this_folder>",
        "run",
        "src/main_quickbooks_mcp.py"
      ]
    }
  }
}
```

## Important File Locations

- `.env` — QuickBooks credentials (git-ignored, should be mode 0600)
- `config/env_template.txt` — Template for creating `.env`
- `src/` — Source code directory
- `data/` — JSON schema files
- `scripts/` — Shell scripts for testing and setup
- `docs/` — Documentation files
- `tests/` — Test suite
- `pyproject.toml` — Python dependencies (requires Python >=3.12)
- `uv.lock` — Locked dependency versions

## Notes

- The server initializes on first Claude Desktop launch; expect 10-20 seconds for initial package installation
- All API calls go through rate limiting and OAuth token refresh logic
- If `.env` credentials are invalid, tools will return generic error messages; check server logs for details
- Never modify `data/quickbooks_openapi_schema.json` manually — it's authoritative QuickBooks API documentation
