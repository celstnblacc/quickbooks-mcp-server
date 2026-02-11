"""QuickBooks API client with OAuth 2.0 refresh-token flow."""

import logging
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth

from environment import Environment

logger = logging.getLogger(__name__)

# F-02: Only allow real HTTP verbs
ALLOWED_METHODS = frozenset({"get", "post", "put", "patch", "delete"})


class QuickBooksSession:
    """Manages QuickBooks API authentication and requests.

    Handles OAuth 2.0 refresh token flow, automatic token refresh on 401,
    HTTP method allowlisting, and token persistence to .env file.
    """

    def __init__(self):
        # Get credentials from environment variables
        self.client_id = Environment.get("QUICKBOOKS_CLIENT_ID")
        self.client_secret = Environment.get("QUICKBOOKS_CLIENT_SECRET")
        self.refresh_token = Environment.get("QUICKBOOKS_REFRESH_TOKEN")
        self.company_id = Environment.get("QUICKBOOKS_COMPANY_ID")

        # Set base URL based on environment
        env = Environment.get("QUICKBOOKS_ENV", "sandbox").lower()
        base_urls = {
            "production": "https://quickbooks.api.intuit.com",
            "sandbox": "https://sandbox-quickbooks.api.intuit.com",
        }
        self.base_url = base_urls.get(env, base_urls["sandbox"])

        self.token_url = (
            "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
        )
        self.access_token = None
        self.refresh_access_token()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_headers(self):
        if self.access_token is None:
            return None
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    def _persist_refresh_token(self, env_path=None):
        """Write the current refresh token back to the .env file (F-06)."""
        if env_path is None:
            env_path = Path(__file__).parent / ".env"
        if not env_path.exists():
            logger.debug(".env file not found; skipping token persistence")
            return

        try:
            lines = env_path.read_text().splitlines()
            updated = False
            for i, line in enumerate(lines):
                if line.startswith("QUICKBOOKS_REFRESH_TOKEN="):
                    lines[i] = f"QUICKBOOKS_REFRESH_TOKEN={self.refresh_token}"
                    updated = True
                    break
            if not updated:
                lines.append(
                    f"QUICKBOOKS_REFRESH_TOKEN={self.refresh_token}"
                )
            env_path.write_text("\n".join(lines) + "\n")
            logger.info("Refresh token persisted to .env")
        except OSError as exc:
            logger.warning(
                "Could not persist refresh token: %s. "
                "Token rotation will be lost on restart.",
                exc,
            )

    # ------------------------------------------------------------------
    # OAuth token management
    # ------------------------------------------------------------------

    def refresh_access_token(self):
        """Refresh the access token using the refresh token."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }
        # F-09: explicit TLS verification
        response = requests.post(
            self.token_url,
            headers=headers,
            data=data,
            auth=HTTPBasicAuth(self.client_id, self.client_secret),
            verify=True,
        )

        if response.status_code == 200:
            tokens = response.json()
            self.access_token = tokens["access_token"]
            new_refresh = tokens.get("refresh_token", self.refresh_token)
            if new_refresh != self.refresh_token:
                self.refresh_token = new_refresh
                self._persist_refresh_token()  # F-06
        else:
            # F-07: log details internally, raise a generic message
            logger.error(
                "Token refresh failed (HTTP %s)", response.status_code
            )
            raise RuntimeError("Failed to refresh QuickBooks access token")

    # ------------------------------------------------------------------
    # API dispatch
    # ------------------------------------------------------------------

    def call_route(self, method_type, route, params=None, body=None):
        """Execute an HTTP request against the QuickBooks API."""
        # F-02: validate HTTP method
        method_lower = method_type.lower()
        if method_lower not in ALLOWED_METHODS:
            raise ValueError(
                f"Invalid HTTP method '{method_type}'. "
                f"Allowed: {sorted(ALLOWED_METHODS)}"
            )

        http_method = getattr(requests, method_lower)

        if not route.startswith("/"):
            route = "/" + route
        url = f"{self.base_url}/v3/company/{self.company_id}{route}"

        try:
            response = self._send(http_method, url, params, body)
        except requests.exceptions.RequestException as exc:
            # Catch network errors (Timeout, ConnectionError, etc.)
            logger.error(
                "Network error on %s %s: %s",
                method_lower.upper(),
                route,
                exc,
            )
            return {"error": f"Network error: {type(exc).__name__}"}

        if response.status_code == 200:
            try:
                return response.json()
            except (ValueError, TypeError) as exc:
                logger.error(
                    "Invalid JSON response from %s %s: %s",
                    method_lower.upper(),
                    route,
                    exc,
                )
                return {"error": "Invalid JSON response from API"}

        if response.status_code == 401:
            logger.info("Access token expired — refreshing")
            self.refresh_access_token()
            try:
                response = self._send(http_method, url, params, body)
            except requests.exceptions.RequestException as exc:
                logger.error(
                    "Network error on retry %s %s: %s",
                    method_lower.upper(),
                    route,
                    exc,
                )
                return {"error": f"Network error: {type(exc).__name__}"}
            if response.status_code == 200:
                try:
                    return response.json()
                except (ValueError, TypeError) as exc:
                    logger.error(
                        "Invalid JSON response from %s %s: %s",
                        method_lower.upper(),
                        route,
                        exc,
                    )
                    return {"error": "Invalid JSON response from API"}

        # F-07: never leak raw response body to the caller
        logger.error(
            "QuickBooks API error: HTTP %s on %s %s",
            response.status_code,
            method_lower.upper(),
            route,
        )
        return {
            "error": f"QuickBooks API returned HTTP {response.status_code}"
        }

    def _send(self, http_method, url, params, body):
        """Fire a single HTTP request with auth headers and TLS (F-09)."""
        headers = self._get_headers()
        if http_method == requests.get:
            return http_method(
                url, params=params, headers=headers, verify=True
            )
        return http_method(
            url, json=body, params=params, headers=headers, verify=True
        )

    # ------------------------------------------------------------------
    # Convenience query helpers
    # ------------------------------------------------------------------

    def query(self, query_str: str):
        """Execute a QuickBooks query."""
        return self.call_route("get", "/query", params={"query": query_str})

    def get_account(self, account_id: str):
        return self.call_route("get", f"/account/{account_id}")

    def get_bill(self, bill_id: str):
        return self.call_route("get", f"/bill/{bill_id}")

    def get_customer(self, customer_id: str):
        return self.call_route("get", f"/customer/{customer_id}")

    def get_vendor(self, vendor_id: str):
        return self.call_route("get", f"/vendor/{vendor_id}")

    def get_invoice(self, invoice_id: str):
        return self.call_route("get", f"/invoice/{invoice_id}")


# F-04: removed debug block that printed access token to stdout
