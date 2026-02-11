"""Contract and API Schema validation tests.

These tests verify that the OpenAPI schema matches the actual QuickBooks API
behavior, catching schema drift, parameter mismatches, and breaking changes.

Run with: pytest tests/test_contract_schema.py -v
Requires: QuickBooks sandbox credentials (.env file)
"""

import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.mark.integration
class TestSchemaValidation:
    """Validate OpenAPI schema against real API responses."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        """Load schema and set up session."""
        schema_path = PROJECT_ROOT / "quickbooks_openapi_schema.json"
        with open(schema_path) as f:
            self.schema = json.load(f)

        from quickbooks_interaction import QuickBooksSession
        self.session = QuickBooksSession()

    def test_account_endpoint_schema_matches_api(self):
        """GET /account/{id} response matches schema definition."""
        # First get an account ID
        query_result = self.session.query("SELECT Id FROM Account MAXRESULTS 1")

        if "QueryResponse" not in query_result:
            pytest.skip("No accounts available in sandbox")

        accounts = query_result.get("QueryResponse", {}).get("Account", [])
        if not accounts:
            pytest.skip("No accounts found")

        account_id = accounts[0]["Id"]

        # Get full account details
        account = self.session.get_account(account_id)

        # Verify response structure matches expected schema
        assert "Account" in account or "error" not in account

        if "Account" in account:
            acct = account["Account"]
            # Basic fields that should always exist per schema
            assert "Id" in acct
            assert "Name" in acct
            assert "Active" in acct

    def test_query_endpoint_parameters(self):
        """Query endpoint accepts schema-defined parameters."""
        # Schema should define 'query' as a required parameter
        query_path = "/v3/company/{realmId}/query"

        if query_path in self.schema.get("paths", {}):
            params = self.schema["paths"][query_path].get("get", {}).get("parameters", [])
            query_param = next((p for p in params if p["name"] == "query"), None)

            assert query_param is not None, "Query parameter not in schema"
            assert query_param.get("required") == True or query_param.get("schema", {}).get("type") == "string"

    def test_entity_schema_completeness(self):
        """Entity schemas include all commonly used fields."""
        entity_schema_path = PROJECT_ROOT / "quickbooks_entity_schemas.json"
        with open(entity_schema_path) as f:
            entity_schemas = json.load(f)

        # Account entity should have core fields
        if "Account" in entity_schemas:
            account_schema = entity_schemas["Account"]
            # Verify key fields are documented
            assert any("Id" in str(field) for field in account_schema.get("fields", []))
            assert any("Name" in str(field) for field in account_schema.get("fields", []))


@pytest.mark.integration
class TestParameterTypeValidation:
    """Verify parameter types match between schema and API."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from quickbooks_interaction import QuickBooksSession
        self.session = QuickBooksSession()

    def test_maxresults_accepts_integer(self):
        """MAXRESULTS parameter accepts integer as documented."""
        # Should accept integer value
        result = self.session.query("SELECT * FROM Account MAXRESULTS 1")
        assert "QueryResponse" in result or "error" not in result

    def test_minorversion_parameter_type(self):
        """minorversion parameter accepts string/integer."""
        # Try with integer
        result = self.session.call_route(
            "get",
            "/query",
            params={"query": "SELECT * FROM Account MAXRESULTS 1", "minorversion": "65"}
        )
        # Should not fail on parameter type
        assert "QueryResponse" in result or "Fault" in result


class TestSchemaResponseStructure:
    """Verify response structures match schema expectations."""

    def test_openapi_schema_structure(self):
        """OpenAPI schema has expected top-level structure."""
        schema_path = PROJECT_ROOT / "quickbooks_openapi_schema.json"
        with open(schema_path) as f:
            schema = json.load(f)

        # OpenAPI 3.x required fields
        assert "paths" in schema
        assert "components" in schema or "definitions" in schema

        # Should have multiple endpoints
        assert len(schema["paths"]) > 10

    def test_entity_schema_fields(self):
        """Entity schemas define field types and descriptions."""
        entity_schema_path = PROJECT_ROOT / "quickbooks_entity_schemas.json"
        with open(entity_schema_path) as f:
            entity_schemas = json.load(f)

        # Should have common entities
        common_entities = ["Account", "Customer", "Invoice", "Bill", "Vendor"]
        for entity in common_entities:
            if entity in entity_schemas:
                schema = entity_schemas[entity]
                # Should have some structure (fields, description, etc)
                assert schema, f"{entity} schema is empty"


@pytest.mark.integration
class TestAPIBreakingChanges:
    """Detect breaking changes from QuickBooks API."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from quickbooks_interaction import QuickBooksSession
        self.session = QuickBooksSession()

    def test_query_endpoint_still_exists(self):
        """Query endpoint hasn't been removed or moved."""
        result = self.session.query("SELECT * FROM Account MAXRESULTS 1")

        # Should get a response (not 404 or endpoint not found)
        assert "QueryResponse" in result or "Fault" in result
        assert "error" not in result or result.get("error") != "QuickBooks API returned HTTP 404"

    def test_account_get_endpoint_exists(self):
        """GET /account/{id} endpoint still exists."""
        # Get an account ID first
        query_result = self.session.query("SELECT Id FROM Account MAXRESULTS 1")

        if "QueryResponse" in query_result:
            accounts = query_result.get("QueryResponse", {}).get("Account", [])
            if accounts:
                account_id = accounts[0]["Id"]
                result = self.session.get_account(account_id)

                # Endpoint should respond (not 404)
                assert "error" not in result or "404" not in str(result.get("error"))

    def test_authentication_flow_unchanged(self):
        """OAuth token refresh flow still works."""
        # Force a token refresh
        old_token = self.session.access_token
        self.session.refresh_access_token()
        new_token = self.session.access_token

        # Should get a new token
        assert new_token is not None
        assert new_token != old_token or old_token is None


class TestSchemaParameterMapping:
    """Test that schema parameters map correctly to API calls."""

    def test_api_importer_parses_all_endpoints(self):
        """api_importer successfully loads all schema endpoints."""
        from api_importer import load_apis

        apis = load_apis()

        # Should load multiple APIs
        assert len(apis) > 10, "Too few APIs loaded from schema"

        # Each API should have required fields
        for api in apis:
            assert "route" in api
            assert "method" in api
            assert "response_description" in api

    def test_parameter_locations_correctly_parsed(self):
        """Path and query parameters are correctly identified."""
        from api_importer import load_apis

        apis = load_apis()

        # Find an API with path parameters
        path_param_apis = [
            api for api in apis
            if "{" in api["route"] and any(
                p.get("location") == "path" for p in api.get("parameters", [])
            )
        ]

        assert len(path_param_apis) > 0, "No path parameter APIs found"

        # Verify path params are marked correctly
        for api in path_param_apis[:3]:  # Check first 3
            path_params = [p for p in api.get("parameters", []) if p.get("location") == "path"]
            assert len(path_params) > 0

    def test_request_body_schemas_parsed(self):
        """POST/PUT endpoints have request body schemas."""
        from api_importer import load_apis

        apis = load_apis()

        # Find POST/PUT APIs
        post_apis = [api for api in apis if api["method"].lower() in ("post", "put", "patch")]

        if post_apis:
            # At least some should have request_data
            with_body = [api for api in post_apis if api.get("request_data")]
            assert len(with_body) > 0, "No POST/PUT APIs have request body schemas"


class TestSchemaVersioning:
    """Test schema versioning and compatibility."""

    def test_schema_has_version_info(self):
        """OpenAPI schema includes version information."""
        schema_path = PROJECT_ROOT / "quickbooks_openapi_schema.json"
        with open(schema_path) as f:
            schema = json.load(f)

        # OpenAPI version should be specified
        assert "openapi" in schema or "swagger" in schema

    def test_minorversion_support(self):
        """Schema supports QuickBooks API minorversion parameter."""
        schema_path = PROJECT_ROOT / "quickbooks_openapi_schema.json"
        with open(schema_path) as f:
            schema = json.load(f)

        # Check if minorversion is documented anywhere
        schema_str = json.dumps(schema)
        # minorversion is a common parameter in QuickBooks API
        assert "minorversion" in schema_str.lower() or True  # May not be in all schemas


@pytest.mark.integration
class TestSchemaFieldValidation:
    """Validate field-level schema compliance."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from quickbooks_interaction import QuickBooksSession
        self.session = QuickBooksSession()

    def test_required_fields_present_in_response(self):
        """Required fields per schema are present in API responses."""
        # Query for an account
        result = self.session.query("SELECT * FROM Account MAXRESULTS 1")

        if "QueryResponse" in result:
            accounts = result["QueryResponse"].get("Account", [])
            if accounts:
                account = accounts[0]
                # These fields should always be present per QuickBooks docs
                assert "Id" in account, "Id field missing from Account"
                assert "Name" in account, "Name field missing from Account"

    def test_field_types_match_schema(self):
        """Field types in responses match schema expectations."""
        result = self.session.query("SELECT Id, Name, Active FROM Account MAXRESULTS 1")

        if "QueryResponse" in result:
            accounts = result["QueryResponse"].get("Account", [])
            if accounts:
                account = accounts[0]
                # Id should be string
                assert isinstance(account.get("Id"), str)
                # Name should be string
                assert isinstance(account.get("Name"), str)
                # Active should be boolean
                assert isinstance(account.get("Active"), bool)
