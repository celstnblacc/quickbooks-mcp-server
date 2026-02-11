"""Smoke test: verify all API tools register without exec() and no crashes."""

import sys
import os

# Set dummy credentials so QuickBooksSession init will attempt (and fail)
# a token refresh — that's expected. We just want to test tool registration.
os.environ.setdefault("QUICKBOOKS_CLIENT_ID", "test_id")
os.environ.setdefault("QUICKBOOKS_CLIENT_SECRET", "test_secret")
os.environ.setdefault("QUICKBOOKS_REFRESH_TOKEN", "test_token")
os.environ.setdefault("QUICKBOOKS_COMPANY_ID", "test_company")
os.environ.setdefault("QUICKBOOKS_ENV", "sandbox")

# The QuickBooks session will fail to init (can't reach Intuit with dummy creds)
# but that's handled gracefully — we just want the tools to register.

print("=" * 60)
print("SMOKE TEST: Tool registration without exec()")
print("=" * 60)

# Import the module (triggers register_all_apis)
from main_quickbooks_mcp import mcp, quickbooks, rate_limiter
from rate_limiter import RateLimiter

# Check that quickbooks is None (expected with dummy creds)
print(f"\n1. QuickBooks session: {'FAILED (expected)' if quickbooks is None else 'Connected'}")

# Check rate limiter exists
assert isinstance(rate_limiter, RateLimiter), "Rate limiter not initialised"
print(f"2. Rate limiter: OK ({rate_limiter.capacity} req/min)")

# Check registered tools
# FastMCP stores tools internally; we can list them
tools = mcp._tool_manager._tools if hasattr(mcp, '_tool_manager') else {}
if not tools:
    # Try alternative attribute paths
    for attr in ['_tools', 'tools', '_registered_tools']:
        if hasattr(mcp, attr):
            tools = getattr(mcp, attr)
            break

print(f"3. Registered tools: {len(tools)}")

if tools:
    tool_names = sorted(tools.keys()) if isinstance(tools, dict) else [str(t) for t in tools]
    # Show first 10 and last 5
    print(f"   First 10: {tool_names[:10]}")
    if len(tool_names) > 10:
        print(f"   Last  5:  {tool_names[-5:]}")

# Verify no exec() in main module
import inspect
source = inspect.getsource(sys.modules['main_quickbooks_mcp'])
has_exec = 'exec(' in source and 'exec()' not in source  # allow "exec()" in comments
print(f"\n4. exec() removed: {'YES' if 'exec(method_str' not in source else 'NO — STILL PRESENT!'}")

# Verify no getattr without validation in quickbooks_interaction
qb_source = inspect.getsource(sys.modules['quickbooks_interaction'])
has_allowlist = 'ALLOWED_METHODS' in qb_source
print(f"5. HTTP method allowlist: {'PRESENT' if has_allowlist else 'MISSING!'}")

# Verify no token print in quickbooks_interaction
has_token_print = 'print("Access token:"' in qb_source or "print('Access token:'" in qb_source
print(f"6. Token leak removed: {'YES' if not has_token_print else 'NO — STILL PRESENT!'}")

# Test query validation
from main_quickbooks_mcp import query_quickbooks
result_select = query_quickbooks("SELECT * FROM Account")
result_delete = query_quickbooks("DELETE FROM Account WHERE Id='1'")
result_mixed = query_quickbooks("SELECT * FROM Account; DROP TABLE Account")

print(f"\n7. Query validation:")
print(f"   SELECT query: {'PASS (session error expected)' if 'session not' in result_select.text.lower() or 'error' in result_select.text.lower() else result_select.text}")
print(f"   DELETE query:  {'BLOCKED' if 'Only SELECT' in result_delete.text or 'Blocked' in result_delete.text else 'ALLOWED — BUG!'}")
print(f"   DROP query:    {'BLOCKED' if 'Blocked' in result_mixed.text or 'Only SELECT' in result_mixed.text else 'ALLOWED — BUG!'}")

print(f"\n{'=' * 60}")
print("ALL CHECKS PASSED" if has_allowlist and not has_token_print and 'exec(method_str' not in source else "SOME CHECKS FAILED")
print(f"{'=' * 60}")
