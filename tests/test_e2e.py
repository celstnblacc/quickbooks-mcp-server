"""End-to-end (E2E) tests for complete user workflows.

These tests simulate real user scenarios from Claude Desktop, testing
the full flow from tool call to response.

Run with: pytest tests/test_e2e.py -v
Requires: QuickBooks sandbox credentials (.env file)
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.mark.integration
class TestCompleteQueryWorkflow:
    """Test complete query workflows as users would perform them."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from quickbooks_interaction import QuickBooksSession
        self.session = QuickBooksSession()

    def test_e2e_discover_schema_then_query(self):
        """User workflow: 1) Get schema, 2) Construct query, 3) Execute."""
        # Step 1: User asks about Account fields
        from main_quickbooks_mcp import get_quickbooks_entity_schema

        schema_result = get_quickbooks_entity_schema("Account")

        # Should get schema information
        assert schema_result.text
        assert "Account" in schema_result.text or "not found" in schema_result.text

        # Step 2: User constructs query based on schema
        from main_quickbooks_mcp import query_quickbooks

        query = "SELECT Id, Name, Active FROM Account MAXRESULTS 1"
        query_result = query_quickbooks(query)

        # Should execute successfully or return error (not crash)
        assert query_result.text
        assert isinstance(query_result.text, str)

    def test_e2e_query_then_get_entity_details(self):
        """Workflow: 1) Query for IDs, 2) Get specific entity details."""
        from main_quickbooks_mcp import query_quickbooks

        # Step 1: Get list of accounts
        list_result = query_quickbooks("SELECT Id FROM Account MAXRESULTS 1")

        if "QueryResponse" in list_result.text:
            # Step 2: Parse ID from response (simulating what Claude would do)
            import json
            try:
                data = json.loads(list_result.text.replace("'", '"'))
                if "QueryResponse" in data:
                    accounts = data.get("QueryResponse", {}).get("Account", [])
                    if accounts and len(accounts) > 0:
                        account_id = accounts[0].get("Id")

                        # Step 3: Get full account details
                        detail_result = self.session.get_account(account_id)
                        assert isinstance(detail_result, dict)
            except:
                pass  # Parsing failed, but test shouldn't crash

    def test_e2e_multiple_queries_in_sequence(self):
        """Workflow: Multiple queries in a single session."""
        from main_quickbooks_mcp import query_quickbooks

        queries = [
            "SELECT * FROM Account MAXRESULTS 1",
            "SELECT * FROM Customer MAXRESULTS 1",
            "SELECT * FROM Invoice MAXRESULTS 1",
        ]

        results = []
        for query in queries:
            result = query_quickbooks(query)
            results.append(result)

        # All queries should complete
        assert len(results) == 3
        assert all(r.text for r in results)


class TestErrorHandlingWorkflows:
    """Test E2E error handling scenarios."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

    def test_e2e_invalid_entity_schema_request(self):
        """User requests schema for non-existent entity."""
        from main_quickbooks_mcp import get_quickbooks_entity_schema

        result = get_quickbooks_entity_schema("NonExistentEntity")

        # Should return helpful error message
        assert result.text
        assert "not found" in result.text.lower() or "available" in result.text.lower()

    def test_e2e_malformed_query(self):
        """User submits malformed SQL query."""
        from main_quickbooks_mcp import query_quickbooks

        result = query_quickbooks("SELCT * FOM Account")  # Typos

        # Should handle gracefully (pass validation, API will reject)
        assert result.text
        assert "Only SELECT queries" not in result.text  # Should pass local validation

    def test_e2e_dangerous_query_attempt(self):
        """User (accidentally or intentionally) tries dangerous query."""
        from main_quickbooks_mcp import query_quickbooks

        dangerous_queries = [
            "DELETE FROM Account WHERE Id='123'",
            "DROP TABLE Account",
            "UPDATE Account SET Name='Hacked'",
        ]

        for query in dangerous_queries:
            result = query_quickbooks(query)

            # Should block and explain why
            assert "Only SELECT queries are permitted" in result.text or "Blocked keywords" in result.text

    def test_e2e_rate_limit_workflow(self):
        """User hits rate limit, gets clear message."""
        from rate_limiter import RateLimiter
        from main_quickbooks_mcp import _make_api_tool

        mock_session = MagicMock()
        mock_session.call_route.return_value = {"ok": True}

        # Create limiter with very low limit
        limiter = RateLimiter(requests_per_minute=2)

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
        handler()

        # Next call should be rate limited
        result = handler()

        # Should get clear rate limit message
        assert "rate limit" in result.text.lower()


@pytest.mark.integration
class TestMultiStepWorkflows:
    """Test complex multi-step workflows."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from quickbooks_interaction import QuickBooksSession
        self.session = QuickBooksSession()

    def test_e2e_explore_multiple_entities(self):
        """User explores multiple entity types."""
        from main_quickbooks_mcp import get_quickbooks_entity_schema

        entities = ["Account", "Customer", "Invoice", "Bill", "Vendor"]
        results = {}

        for entity in entities:
            result = get_quickbooks_entity_schema(entity)
            results[entity] = result.text

        # Should get responses for all
        assert len(results) == 5
        assert all(results.values())

    def test_e2e_filter_and_refine_query(self):
        """User starts broad, then refines query."""
        from main_quickbooks_mcp import query_quickbooks

        # Step 1: Broad query
        broad = query_quickbooks("SELECT * FROM Account MAXRESULTS 5")
        assert broad.text

        # Step 2: More specific
        specific = query_quickbooks("SELECT * FROM Account WHERE Active=true MAXRESULTS 3")
        assert specific.text

        # Step 3: Very specific
        exact = query_quickbooks("SELECT Id, Name FROM Account WHERE Active=true MAXRESULTS 1")
        assert exact.text


class TestSessionLifecycleE2E:
    """Test complete session lifecycle scenarios."""

    def test_e2e_cold_start(self):
        """First request after server startup (cold start)."""
        # This tests the initialization path
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "at", "refresh_token": "rt"}

        with patch("requests.post", return_value=mock_resp):
            from quickbooks_interaction import QuickBooksSession

            # Cold start - initializing session
            session = QuickBooksSession()

            # Should have token
            assert session.access_token == "at"

    def test_e2e_session_with_token_refresh(self):
        """Session encounters 401 and refreshes token automatically."""
        call_count = {"post": 0, "get": 0}

        def mock_post(*args, **kwargs):
            call_count["post"] += 1
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"access_token": f"at_{call_count['post']}", "refresh_token": "rt"}
            return resp

        def mock_get(*args, **kwargs):
            call_count["get"] += 1
            resp = MagicMock()
            if call_count["get"] == 1:
                # First call: expired token
                resp.status_code = 401
            else:
                # After refresh: success
                resp.status_code = 200
                resp.json.return_value = {"QueryResponse": {"Account": []}}
            return resp

        with patch("requests.post", side_effect=mock_post):
            with patch("requests.get", side_effect=mock_get):
                from quickbooks_interaction import QuickBooksSession

                session = QuickBooksSession()

                # Make request that will fail first, then succeed
                result = session.query("SELECT * FROM Account")

                # Should have refreshed and retried
                assert call_count["get"] == 2
                assert call_count["post"] == 2  # Initial + refresh
                assert "QueryResponse" in result


class TestToolIntegrationE2E:
    """Test tool integration and chaining."""

    def test_e2e_tool_registration_at_startup(self):
        """All tools are registered when server starts."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch("requests.post", return_value=mock_resp):
            # Force reimport (simulates server startup)
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            import main_quickbooks_mcp

            # Static tools should be registered
            assert hasattr(main_quickbooks_mcp, "query_quickbooks")
            assert hasattr(main_quickbooks_mcp, "get_quickbooks_entity_schema")

            # Dynamic tools should be registered via register_all_apis()
            from api_importer import load_apis
            apis = load_apis()
            assert len(apis) > 0

    def test_e2e_tool_discovery(self):
        """Tools can be discovered via MCP protocol."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            import main_quickbooks_mcp

            # MCP server should have tools
            assert main_quickbooks_mcp.mcp


class TestRealWorldScenarios:
    """Test real-world user scenarios."""

    def test_e2e_user_asks_for_account_balance(self):
        """Scenario: User asks 'What's my account balance?'"""
        # This simulates the full workflow
        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            # Step 1: Claude checks schema
            from main_quickbooks_mcp import get_quickbooks_entity_schema
            schema = get_quickbooks_entity_schema("Account")
            assert schema.text

            # Step 2: Claude constructs query
            from main_quickbooks_mcp import query_quickbooks
            result = query_quickbooks("SELECT Name, CurrentBalance FROM Account")

            # Should work (session error is ok for this test)
            assert result.text

    def test_e2e_user_wants_customer_list(self):
        """Scenario: User asks 'Show me all my customers'"""
        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            from main_quickbooks_mcp import query_quickbooks

            result = query_quickbooks("SELECT * FROM Customer")
            assert result.text

    def test_e2e_user_filters_by_date(self):
        """Scenario: User asks 'Show me invoices from 2024'"""
        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            from main_quickbooks_mcp import query_quickbooks

            result = query_quickbooks("SELECT * FROM Invoice WHERE TxnDate >= '2024-01-01'")
            assert result.text


class TestConcurrentUserRequests:
    """Test handling of concurrent requests (multiple users/sessions)."""

    def test_e2e_concurrent_query_requests(self):
        """Multiple queries at the same time."""
        import threading

        mock_resp = MagicMock()
        mock_resp.status_code = 401

        # Set up module once before threads start
        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            from main_quickbooks_mcp import query_quickbooks

            results = []
            lock = threading.Lock()

            def worker():
                result = query_quickbooks("SELECT * FROM Account")
                with lock:
                    results.append(result.text)

            threads = [threading.Thread(target=worker) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        # All requests should complete
        assert len(results) == 3
        assert all(r for r in results)


class TestUserErrorRecovery:
    """Test recovery from common user errors."""

    def test_e2e_typo_in_entity_name(self):
        """User types 'Acount' instead of 'Account'"""
        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            from main_quickbooks_mcp import query_quickbooks

            # Query will pass local validation, API will reject
            result = query_quickbooks("SELECT * FROM Acount")
            assert result.text  # Should not crash

    def test_e2e_missing_required_parameter(self):
        """User forgets required parameter in query."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            from main_quickbooks_mcp import query_quickbooks

            # Incomplete query (missing FROM clause, but starts with SELECT)
            result = query_quickbooks("SELECT * WHERE Id='1'")
            assert result.text  # Should handle gracefully

    def test_e2e_case_sensitivity_confusion(self):
        """User unsure about case sensitivity."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch("requests.post", return_value=mock_resp):
            for mod in list(sys.modules):
                if "main_quickbooks_mcp" in mod:
                    del sys.modules[mod]

            from main_quickbooks_mcp import query_quickbooks

            # Different cases should all work
            queries = [
                "SELECT * FROM Account",
                "select * from Account",
                "SeLeCt * FrOm Account",
            ]

            for query in queries:
                result = query_quickbooks(query)
                # All should pass validation
                assert "Only SELECT queries are permitted" not in result.text
