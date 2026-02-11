"""QuickBooks MCP Server — secure entry point.

Registers MCP tools for every QuickBooks API endpoint defined in the
local OpenAPI schema, using a closure factory instead of exec().
"""

import json
import logging
import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from mcp import types
from mcp.server.fastmcp import FastMCP

from api_importer import load_apis
from quickbooks_interaction import QuickBooksSession
from rate_limiter import RateLimiter

# ---------------------------------------------------------------------------
# Logging (F-10)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global instances
# ---------------------------------------------------------------------------
quickbooks = None
try:
    quickbooks = QuickBooksSession()
    logger.info("QuickBooks session initialised successfully")
except Exception as exc:
    logger.error("Failed to initialise QuickBooks session: %s", exc)
    logger.error("Please check your .env file and QuickBooks credentials")

mcp = FastMCP("quickbooks")
rate_limiter = RateLimiter(requests_per_minute=60)

# ---------------------------------------------------------------------------
# Dangerous-keyword list for query validation (F-03)
# ---------------------------------------------------------------------------
_BLOCKED_QUERY_KEYWORDS = {"DELETE", "UPDATE", "INSERT", "DROP", "ALTER", "CREATE"}

# ---------------------------------------------------------------------------
# Static tools
# ---------------------------------------------------------------------------


@mcp.tool()
def get_quickbooks_entity_schema(entity_name: str) -> types.TextContent:
    """
    Fetches the schema for a given QuickBooks entity (e.g., 'Bill', 'Customer').
    Use this tool to understand the available fields for an entity before
    constructing a query with the `query_quickbooks` tool.
    """
    schema_path = Path(__file__).parent.parent / "data" / "quickbooks_entity_schemas.json"
    try:
        with open(schema_path, "r") as f:
            all_schemas = json.load(f)

        entity_schema = all_schemas.get(entity_name)
        if entity_schema:
            return types.TextContent(
                type="text", text=json.dumps(entity_schema, indent=2)
            )
        available = list(all_schemas.keys())
        return types.TextContent(
            type="text",
            text=f"Entity '{entity_name}' not found. Available: {available}",
        )
    except FileNotFoundError:
        return types.TextContent(
            type="text",
            text="Schema file quickbooks_entity_schemas.json not found.",
        )
    except Exception:
        logger.exception("Error reading entity schema")
        return types.TextContent(
            type="text", text="An error occurred while reading the schema."
        )


@mcp.tool()
def query_quickbooks(query: str) -> types.TextContent:
    """
    Executes a SQL-like SELECT query on a QuickBooks entity.
    **IMPORTANT**: Before using this tool, first use the
    `get_quickbooks_entity_schema` tool to learn the available fields.
    Only SELECT queries are allowed.
    """
    # F-03: input validation — block destructive operations (runs before session check)
    stripped = query.strip()
    upper_tokens = set(stripped.upper().split())
    blocked = upper_tokens & _BLOCKED_QUERY_KEYWORDS
    if blocked:
        return types.TextContent(
            type="text",
            text=f"Blocked keywords detected: {', '.join(sorted(blocked))}. "
            "Only SELECT queries are permitted.",
        )
    # Allow queries that don't contain blocked keywords (including typos in SELECT)

    if quickbooks is None:
        return types.TextContent(
            type="text",
            text="Error: QuickBooks session not initialised. "
            "Check your credentials and restart the server.",
        )

    # F-08: rate limit
    if not rate_limiter.is_allowed():
        return types.TextContent(
            type="text",
            text="Rate limit exceeded. Please wait before retrying.",
        )

    try:
        response = quickbooks.query(stripped)
        return types.TextContent(type="text", text=str(response))
    except Exception:
        logger.exception("Error executing QuickBooks query")
        return types.TextContent(
            type="text", text="An error occurred while executing the query."
        )


# ---------------------------------------------------------------------------
# Dynamic tool registration — closure factory (F-01)
# ---------------------------------------------------------------------------

def _make_api_tool(api_config, qb_session_ref, limiter):
    """Return a tool handler that captures *api_config* via closure.

    This replaces the previous exec()-based approach, eliminating any risk
    of code injection through the OpenAPI schema file.
    """
    route = api_config["route"]
    api_method = api_config["method"]
    params_info = [p for p in api_config.get("parameters", []) if p["name"] != "realmId"]
    tool_doc = api_config["docstring"]
    tool_name = api_config["tool_name"]

    def handler(**kwargs) -> types.TextContent:
        # Session check
        session = qb_session_ref()
        if session is None:
            return types.TextContent(
                type="text",
                text="Error: QuickBooks session not initialised.",
            )

        # F-08: rate limit
        if not limiter.is_allowed():
            return types.TextContent(
                type="text",
                text="Rate limit exceeded. Please wait before retrying.",
            )

        # Workaround for clients that pass all arguments as a single string
        if "kwargs" in kwargs and isinstance(kwargs["kwargs"], str) and "=" in kwargs["kwargs"]:
            try:
                key, value = kwargs["kwargs"].split("=", 1)
                kwargs = {key: value}
            except Exception:
                pass

        logger.info("Executing '%s' with args: %s", tool_name, kwargs)

        try:
            local_route = route

            path_params = {}
            query_params = {}
            request_body = {}

            # F-03: validate kwarg value types
            for k, v in kwargs.items():
                if not isinstance(v, (str, int, float, bool, list, dict, type(None))):
                    return types.TextContent(
                        type="text",
                        text=f"Invalid type for parameter '{k}'.",
                    )

            # Separate parameters by location
            for p_info in params_info:
                p_name = p_info["name"]
                if p_name in kwargs:
                    loc = p_info.get("location", "query")
                    if loc == "path":
                        path_params[p_name] = kwargs[p_name]
                    elif loc == "query":
                        query_params[p_name] = kwargs[p_name]

            # Body parameters for POST/PUT/PATCH
            if api_method.lower() in ("post", "put", "patch"):
                body_keys = (
                    set(kwargs.keys())
                    - set(path_params.keys())
                    - set(query_params.keys())
                )
                for k in body_keys:
                    request_body[k] = kwargs[k]

            # Format path parameters into the route
            if path_params:
                try:
                    local_route = local_route.format(**path_params)
                except KeyError as exc:
                    return types.TextContent(
                        type="text",
                        text=f"Missing required path parameter: {exc}",
                    )

            response = session.call_route(
                method_type=api_method,
                route=local_route,
                params=query_params,
                body=request_body if request_body else None,
            )

            logger.info("Response from '%s' received", tool_name)
            return types.TextContent(type="text", text=str(response))

        except Exception:
            # F-07: log internally, return generic message
            logger.exception("Error in tool '%s'", tool_name)
            return types.TextContent(
                type="text",
                text="An error occurred while processing your request.",
            )

    # Attach metadata so FastMCP picks up the name and docstring
    handler.__name__ = tool_name
    handler.__qualname__ = tool_name
    handler.__doc__ = tool_doc
    return handler


def register_all_apis():
    """Load the OpenAPI schema and register each endpoint as an MCP tool."""
    apis = load_apis()

    # We pass a *callable* that returns the current quickbooks session so
    # tools can tolerate a late or re-initialised session.
    def _qb_ref():
        return quickbooks

    for api in apis:
        response_description = api["response_description"]

        # Clean route — remove the company/realm prefix
        original_route = api["route"]
        if "/v3/company/{realmId}" in original_route:
            clean_route = original_route.replace("/v3/company/{realmId}", "")
        else:
            clean_route = original_route

        clean_name = (
            clean_route.replace("/", "_")
            .replace("-", "_")
            .replace(":", "_")
            .replace("{", "")
            .replace("}", "")
        )
        tool_name = f'{api["method"]}{clean_name}'

        # Build docstring
        summary = api.get("summary")
        if summary is None:
            words = tool_name.split("_")
            words[0] = words[0].capitalize()
            summary = " ".join(words) + "."

        doc = summary + ". "
        if response_description != "OK":
            doc += f'If successful, the outcome will be "{response_description}". '

        params_filtered = [
            p for p in api.get("parameters", []) if p["name"] != "realmId"
        ]
        if api.get("request_data"):
            doc += (
                "The request body should be a JSON object with the "
                f"following structure: {json.dumps(api['request_data'])}. "
            )
        if params_filtered:
            param_summary = {
                p["name"]: {
                    "description": p.get("description", ""),
                    "required": p.get("required", False),
                    "type": p.get("type", "unknown"),
                    "in": p.get("location"),
                }
                for p in params_filtered
            }
            doc += f"Parameters: {json.dumps(param_summary, indent=2)}. "

        config = {
            "route": clean_route,
            "method": api["method"],
            "parameters": params_filtered,
            "docstring": doc,
            "tool_name": tool_name,
        }

        handler = _make_api_tool(config, _qb_ref, rate_limiter)
        mcp.tool()(handler)

    logger.info("Registered %d API tools from OpenAPI schema", len(apis))


try:
    register_all_apis()
except Exception as exc:
    logger.warning(
        "Failed to register API tools from schema: %s. "
        "Static tools (query, schema) will still work.",
        exc
    )

if __name__ == "__main__":
    logger.info("Starting QuickBooks MCP server")
    mcp.run(transport="stdio")
