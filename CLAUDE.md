# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the MCP server (also how Claude Desktop invokes it)
uv run src/main_quickbooks_mcp.py

# Install test dependencies
uv sync --extra test

# Run all unit tests (no credentials required)
pytest tests/ -m "not integration" -v

# Run a single test file
pytest tests/test_rate_limiter.py -v

# Run with coverage
pytest tests/ -m "not integration" --cov=. --cov-report=term-missing

# Run integration tests (requires valid .env credentials)
pytest tests/ -m integration

# Full test suite via script
./scripts/run_tests.sh --fast
```

## Environment Setup

```bash
cp config/env_template.txt .env
chmod 600 .env
# Edit .env: QUICKBOOKS_CLIENT_ID, QUICKBOOKS_CLIENT_SECRET,
#   QUICKBOOKS_REFRESH_TOKEN, QUICKBOOKS_COMPANY_ID, QUICKBOOKS_ENV (sandbox|production)
```

## Architecture

Tool registration happens two ways at startup in `src/main_quickbooks_mcp.py`:

1. **Static tools** — `query_quickbooks` and `get_quickbooks_entity_schema` are defined directly with `@mcp.tool()`.
2. **Dynamic tools** — `register_all_apis()` reads `data/quickbooks_openapi_schema.json` via `src/api_importer.py`, then calls `_make_api_tool()` for each endpoint. This closure factory captures route, method, and parameter metadata — replacing the original `exec()`-based approach to eliminate code-injection risk from a tampered schema file.

All API calls flow through `src/quickbooks_interaction.py` (`QuickBooksSession`), which:
- Runs the OAuth2 refresh-token cycle, auto-retrying on 401
- Persists rotated tokens back to `.env` so they survive restarts (F-06)
- Validates the HTTP method against `ALLOWED_METHODS` frozenset before dispatching (F-02)

`src/rate_limiter.py` (token-bucket, 60 req/min) is checked before every API call. `src/environment.py` loads `.env` and warns once at startup if it has world-readable/writable permissions.

## Security Constraints

Ten vulnerabilities (F-01–F-10) were fixed in Feb 2026. Key invariants to maintain:

- **No `exec()`/`eval()`** — use the `_make_api_tool()` closure factory for dynamic tool generation.
- **SELECT-only queries** — `query_quickbooks` blocks `DELETE/UPDATE/INSERT/DROP/ALTER/CREATE`; do not relax this.
- **Generic error responses to MCP clients** — full details stay in the logger only (F-07).
- **HTTP method allowlist** — `ALLOWED_METHODS` in `quickbooks_interaction.py` must stay in place (F-02).
- **`data/quickbooks_openapi_schema.json` is authoritative** — do not edit it manually.

## Test Organization

- **Unit tests**: Fully mocked, no network or credentials needed (run by default).
- **Integration tests**: Marked `@pytest.mark.integration`, require sandbox `.env`.
- **Security regression tests** (`tests/test_security_regression.py`): Verify F-01–F-10 remain fixed.
- Full per-test catalogue in `docs/TESTING.md`.
