# 🧾 QuickBooks MCP Server

> A secure, local-first Model Context Protocol (MCP) server to query QuickBooks data using natural language inside Claude Desktop.

--- 

## ✅ MCP Review Certification

This MCP Server is **[certified by MCP Review](https://mcpreview.com/mcp-servers/nikhilgy/quickbooks-mcp-server)**.

Being listed and certified on MCP Review ensures this server adheres to MCP standards and best practices, and is trusted by the developer community.

---

## Requirements:
1. Python 3.10 or higher

## Environment Setup
For local development, create a `.env` file in the project root with your QuickBooks credentials:

```bash
# Copy the template and fill in your actual credentials
cp env_template.txt .env
```

Then edit the `.env` file with your actual QuickBooks API credentials:
```
QUICKBOOKS_CLIENT_ID=your_actual_client_id
QUICKBOOKS_CLIENT_SECRET=your_actual_client_secret
QUICKBOOKS_REFRESH_TOKEN=your_actual_refresh_token
QUICKBOOKS_COMPANY_ID=your_actual_company_id
QUICKBOOKS_ENV='sandbox' or 'production'
```

**Note:** The `.env` file is automatically ignored by git for security reasons.

## Step 1. Install uv:
   - MacOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh
   - Windows: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

## Step 2. Configure Claude Desktop
1. Download [Claude Desktop](https://claude.ai/download).
2. Launch Claude and go to Settings > Developer > Edit Config.
3. Modify `claude_desktop_config.json` with:
```json
{
  "mcpServers": {
    "QuickBooks": {
      "command": "uv",
      "args": [
        "--directory",
        "<absolute_path_to_quickbooks_mcp_folder>",
        "run",
        "main_quickbooks_mcp.py"
      ]
    }
  }
}
```
4. Relaunch Claude Desktop.

The first time you open Claude Desktop with these setting it may take
10-20 seconds before the QuickBooks tools appear in the interface due to
the installation of the required packages and the download of the most 
recent QuickBooks API documentation.

Everytime you launch Claude Desktop, the most recent QuickBooks API tools are made available 
to your AI assistant.

## Step 3. Launch Claude Desktop and let your assistant help you
### Examples
**Query Accounts**
```text
Get all accounts from QuickBooks.
```

**Query Bills**
```text
Get all bills from QuickBooks created after 2024-01-01.
```

**Query Customers**
```text
Get all customers from QuickBooks.
```

---

## Architecture

The server consists of four core modules:

| File | Purpose |
|------|---------|
| `main_quickbooks_mcp.py` | MCP entry point — registers static tools (`query_quickbooks`, `get_quickbooks_entity_schema`) and dynamically registers tools for every QuickBooks API endpoint using a closure factory |
| `quickbooks_interaction.py` | `QuickBooksSession` class — OAuth 2.0 refresh-token flow, HTTP dispatch with method allowlisting, automatic 401 retry, token persistence |
| `environment.py` | `Environment` class — loads `.env` via `python-dotenv`, checks file permissions on startup |
| `rate_limiter.py` | `RateLimiter` class — token-bucket rate limiter (default: 60 req/min) |

Supporting files:

| File | Purpose |
|------|---------|
| `api_importer.py` | Loads and parses the OpenAPI schema JSON to produce API config dicts |
| `quickbooks_entity_schemas.json` | Entity field schemas used by `get_quickbooks_entity_schema` |

### How tool registration works

At startup, `register_all_apis()` reads the OpenAPI schema via `api_importer.load_apis()`, then calls `_make_api_tool()` for each endpoint. This closure factory captures the route, HTTP method, and parameter metadata in a closure — producing a handler function that FastMCP registers as a tool. This approach replaced the original `exec()`-based code generation, eliminating code injection risk from tampered schema files.

---

## Security Hardening (Feb 2026)

A full security audit was performed on the original codebase. Ten vulnerabilities were identified and fixed across four files. The changes preserve full backward compatibility with the MCP tool interface.

### What was found and fixed

| ID | Severity | Issue | Fix |
|----|----------|-------|-----|
| F-01 | **CRITICAL** | `exec()` used to generate tool functions from OpenAPI schema data — allows arbitrary code execution if the JSON file is tampered with | Replaced with a closure-based factory function (`_make_api_tool`) that captures API metadata safely without any code generation |
| F-02 | **HIGH** | `getattr(requests, method_type)` dispatches HTTP methods without validation — any `requests` module attribute could be invoked | Added `ALLOWED_METHODS` frozenset; `call_route()` now rejects anything outside `{get, post, put, patch, delete}` |
| F-03 | **HIGH** | `query_quickbooks()` passes user input directly to the API with no validation — DELETE/UPDATE/DROP queries could be sent | Queries must now start with `SELECT`; `DELETE`, `UPDATE`, `INSERT`, `DROP`, `ALTER`, `CREATE` keywords are blocked. Dynamic tool kwargs are type-validated |
| F-04 | **HIGH** | `quickbooks_interaction.py` printed the live OAuth access token to stdout in its `__main__` block | Debug block removed entirely |
| F-05 | **MEDIUM** | `.env` file permissions not checked — credentials could be world-readable | `environment.py` now warns on startup if `.env` has overly permissive modes (recommends `chmod 600`) |
| F-06 | **MEDIUM** | Rotated refresh tokens stored only in memory — lost on restart, causing auth failures | New `_persist_refresh_token()` method writes the updated token back to `.env` automatically |
| F-07 | **MEDIUM** | Raw API response bodies and Python exceptions returned to the MCP client — leaks internal state | Error messages returned to the client are now generic; full details logged internally only |
| F-08 | **MEDIUM** | No rate limiting on tool invocations — API quotas could be exhausted | New `rate_limiter.py` with a token-bucket limiter (default: 60 req/min) checked before every API call |
| F-09 | **LOW** | No explicit `verify=True` on `requests` calls — TLS verification could be disabled via env vars | All HTTP calls now pass `verify=True` explicitly |
| F-10 | **LOW** | Logging via `print()` to stderr with no structure or timestamps | Replaced with Python `logging` module: timestamped, leveled, routed to stderr |

### Files changed

- **`main_quickbooks_mcp.py`** — `exec()` replaced with closure factory (`_make_api_tool`), query validation (SELECT-only with blocked keywords), rate limiting before every API call, structured logging via `logging` module, sanitized error responses (generic messages to MCP client, details logged internally)
- **`quickbooks_interaction.py`** — HTTP method allowlist (`ALLOWED_METHODS` frozenset), debug `__main__` block with token print removed, `_persist_refresh_token()` writes rotated tokens back to `.env`, explicit `verify=True` on all `requests` calls, error responses return `{"error": "HTTP {status}"}` without raw body, `_send()` converted from `@staticmethod` to instance method with auth headers
- **`environment.py`** — `_check_env_permissions()` warns if `.env` is world-readable (`S_IROTH`) or world-writable (`S_IWOTH`), runs once via `_PERMISSIONS_CHECKED` guard
- **`rate_limiter.py`** *(new)* — Token-bucket rate limiter with configurable `requests_per_minute`, burst capacity equal to the per-minute limit

### Recommended .env permissions

After creating your `.env` file, restrict access:

```bash
chmod 600 .env
```

---

## Testing

The project includes a comprehensive test suite with **82 tests** across 9 test modules. All tests run without network access or QuickBooks credentials.

### Quick start

```bash
# Install test dependencies
pip install pytest pytest-mock

# Run all tests
python -m pytest tests/ -v
```

### Test coverage by security fix

| Fix | Test file(s) | Tests |
|-----|-------------|-------|
| F-01 (exec → closure) | `test_closure_factory.py`, `test_security_regression.py` | 19 |
| F-02 (method allowlist) | `test_method_allowlist.py`, `test_security_regression.py` | 19 |
| F-03 (query validation) | `test_query_validation.py`, `test_closure_factory.py` | 15 |
| F-04 (token print removed) | `test_security_regression.py` | 2 |
| F-05 (.env permissions) | `test_environment.py` | 5 |
| F-06 (token persistence) | `test_token_persistence.py` | 5 |
| F-07 (error sanitization) | `test_error_sanitization.py`, `test_security_regression.py` | 7 |
| F-08 (rate limiting) | `test_rate_limiter.py`, `test_edge_cases.py` | 9 |

See [TESTING.md](TESTING.md) for the full test catalogue with individual test descriptions, fixtures, and testing patterns.
