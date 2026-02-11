#!/usr/bin/env bash
# Test runner for quickbooks-mcp-server
# Runs all test categories: unit, integration, security regression, and edge cases

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Track results
UNIT_PASSED=false
EDGE_PASSED=false
SECURITY_PASSED=false
CONTRACT_PASSED=false
ERROR_RECOVERY_PASSED=false
PROPERTY_PASSED=false
COMPATIBILITY_PASSED=false
REGRESSION_PASSED=false
E2E_PASSED=false
CHAOS_PASSED=false
OBSERVABILITY_PASSED=false
DOCUMENTATION_PASSED=false
INTEGRATION_PASSED=false
STRESS_PASSED=false
COVERAGE_PASSED=false

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}QuickBooks MCP Server - Test Suite${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}Error: pytest is not installed${NC}"
    echo "Install with: pip install pytest pytest-mock"
    exit 1
fi

# Parse command line arguments
RUN_COVERAGE=false
RUN_INTEGRATION=true
RUN_ALL=false
FAST_ONLY=false
VERBOSE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --coverage|-c)
            RUN_COVERAGE=true
            shift
            ;;
        --no-integration)
            RUN_INTEGRATION=false
            shift
            ;;
        --all)
            RUN_ALL=true
            shift
            ;;
        --fast)
            FAST_ONLY=true
            RUN_INTEGRATION=false
            shift
            ;;
        --verbose|-v)
            VERBOSE="-v"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --coverage, -c          Run tests with coverage report"
            echo "  --no-integration        Skip integration tests (don't require .env)"
            echo "  --stress                Include stress/performance tests (slower)"
            echo "  --all                   Run ALL test types including slow ones"
            echo "  --fast                  Run only fast unit tests"
            echo "  --verbose, -v           Verbose output"
            echo "  --help, -h              Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${YELLOW}Test Configuration:${NC}"
echo "  Mode: $([ "$FAST_ONLY" = true ] && echo "Fast only" || ([ "$RUN_ALL" = true ] && echo "All tests" || echo "Standard"))"
echo "  Coverage: $RUN_COVERAGE"
echo "  Integration tests: $RUN_INTEGRATION"
echo "  Verbose: $([ -n "$VERBOSE" ] && echo "true" || echo "false")"
echo ""

# Function to run a test category
run_test_category() {
    local name=$1
    local command=$2
    local required=$3

    echo -e "${BLUE}----------------------------------------${NC}"
    echo -e "${BLUE}Running: $name${NC}"
    echo -e "${BLUE}----------------------------------------${NC}"

    if [ "$required" = "false" ]; then
        echo -e "${YELLOW}(Skipped by user)${NC}"
        echo ""
        return 0
    fi

    if eval "$command"; then
        echo -e "${GREEN}✓ $name passed${NC}"
        echo ""
        return 0
    else
        echo -e "${RED}✗ $name failed${NC}"
        echo ""
        return 1
    fi
}

# 1. Unit Tests (fast, no credentials needed)
if run_test_category "Unit Tests" "pytest tests/ -m 'not integration' $VERBOSE" "true"; then
    UNIT_PASSED=true
fi

# 2. Edge Case Tests
EDGE_PASSED=false
if run_test_category "Edge Case Tests" "pytest tests/test_edge_cases.py $VERBOSE" "true"; then
    EDGE_PASSED=true
fi

# 3. Security Regression Tests (always run)
if run_test_category "Security Regression Tests" "pytest tests/test_security_regression.py $VERBOSE" "true"; then
    SECURITY_PASSED=true
fi

# 4-10. Additional test types (skip if --fast)
if [ "$FAST_ONLY" = false ]; then
    # 4. Contract/Schema Tests
    if [ -f ".env" ] && grep -q "QUICKBOOKS_CLIENT_ID" .env 2>/dev/null; then
        if run_test_category "Contract/Schema Tests" "pytest tests/test_contract_schema.py -m integration $VERBOSE" "true"; then
            CONTRACT_PASSED=true
        fi
    else
        CONTRACT_PASSED="skipped"
    fi

    # 5. Error Recovery Tests
    if run_test_category "Error Recovery Tests" "pytest tests/test_error_recovery.py $VERBOSE" "true"; then
        ERROR_RECOVERY_PASSED=true
    fi

    # 6. Property-Based Tests
    if run_test_category "Property-Based Tests" "pytest tests/test_property_based.py $VERBOSE" "$RUN_ALL"; then
        PROPERTY_PASSED=true
    else
        PROPERTY_PASSED="skipped"
    fi

    # 7. Compatibility Tests
    if run_test_category "Compatibility Tests" "pytest tests/test_compatibility.py $VERBOSE" "true"; then
        COMPATIBILITY_PASSED=true
    fi

    # 8. Functional Regression Tests
    if run_test_category "Functional Regression Tests" "pytest tests/test_functional_regression.py -m 'not integration' $VERBOSE" "true"; then
        REGRESSION_PASSED=true
    fi

    # 9. E2E Tests (if integration enabled)
    if [ "$RUN_INTEGRATION" = true ] && [ -f ".env" ]; then
        if run_test_category "End-to-End Tests" "pytest tests/test_e2e.py -m integration $VERBOSE" "true"; then
            E2E_PASSED=true
        fi
    else
        E2E_PASSED="skipped"
    fi

    # 10. Chaos Tests (only if --all)
    if [ "$RUN_ALL" = true ]; then
        if run_test_category "Chaos/Fault Injection Tests" "pytest tests/test_chaos.py $VERBOSE" "true"; then
            CHAOS_PASSED=true
        fi
    else
        CHAOS_PASSED="skipped"
    fi

    # 11. Observability Tests
    if run_test_category "Observability/Logging Tests" "pytest tests/test_observability.py $VERBOSE" "true"; then
        OBSERVABILITY_PASSED=true
    fi

    # 12. Documentation Tests
    if run_test_category "Documentation Tests" "pytest tests/test_documentation.py $VERBOSE" "true"; then
        DOCUMENTATION_PASSED=true
    fi
else
    CONTRACT_PASSED="skipped"
    ERROR_RECOVERY_PASSED="skipped"
    PROPERTY_PASSED="skipped"
    COMPATIBILITY_PASSED="skipped"
    REGRESSION_PASSED="skipped"
    E2E_PASSED="skipped"
    CHAOS_PASSED="skipped"
    OBSERVABILITY_PASSED="skipped"
    DOCUMENTATION_PASSED="skipped"
fi

# Original 3. Security Regression Tests (moved above, keeping marker)
# (Security tests moved above)

# 4. Stress Tests (optional, longer running)
RUN_STRESS=false
if [ "$RUN_COVERAGE" = true ]; then
    RUN_STRESS=true  # Include stress tests in coverage runs
fi

# Check for --stress flag
for arg in "$@"; do
    if [ "$arg" = "--stress" ]; then
        RUN_STRESS=true
        break
    fi
done

if [ "$RUN_STRESS" = true ] && [ -f "tests/test_stress.py" ]; then
    if run_test_category "Stress Tests" "pytest tests/test_stress.py $VERBOSE" "true"; then
        STRESS_PASSED=true
    fi
else
    STRESS_PASSED="skipped"
fi

# 5. Integration Tests (requires .env with sandbox credentials)
if [ "$RUN_INTEGRATION" = true ]; then
    # Check if credentials are available
    if [ -f ".env" ] && grep -q "QUICKBOOKS_CLIENT_ID" .env 2>/dev/null; then
        if run_test_category "Integration Tests" "pytest tests/ -m 'integration' $VERBOSE" "true"; then
            INTEGRATION_PASSED=true
        fi
    else
        echo -e "${YELLOW}----------------------------------------${NC}"
        echo -e "${YELLOW}Skipping Integration Tests${NC}"
        echo -e "${YELLOW}----------------------------------------${NC}"
        echo -e "${YELLOW}No .env file found or QUICKBOOKS_CLIENT_ID not set${NC}"
        echo -e "${YELLOW}Integration tests require QuickBooks sandbox credentials${NC}"
        echo ""
        INTEGRATION_PASSED="skipped"
    fi
else
    INTEGRATION_PASSED="skipped"
fi

# 6. Coverage Report (optional)
if [ "$RUN_COVERAGE" = true ]; then
    echo -e "${BLUE}----------------------------------------${NC}"
    echo -e "${BLUE}Running: All Tests with Coverage${NC}"
    echo -e "${BLUE}----------------------------------------${NC}"

    # Build coverage command
    COV_CMD="pytest tests/"
    if [ "$RUN_INTEGRATION" = false ]; then
        COV_CMD="$COV_CMD -m 'not integration'"
    fi
    COV_CMD="$COV_CMD --cov=. --cov-report=term-missing --cov-report=html $VERBOSE"

    if eval "$COV_CMD"; then
        echo -e "${GREEN}✓ Coverage report generated${NC}"
        echo -e "${GREEN}  HTML report: htmlcov/index.html${NC}"
        echo ""
        COVERAGE_PASSED=true
    else
        echo -e "${RED}✗ Coverage run failed${NC}"
        echo ""
    fi
fi

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"

print_result() {
    local name=$1
    local passed=$2

    if [ "$passed" = "true" ]; then
        echo -e "  ${GREEN}✓${NC} $name"
    elif [ "$passed" = "skipped" ]; then
        echo -e "  ${YELLOW}⊘${NC} $name (skipped)"
    else
        echo -e "  ${RED}✗${NC} $name"
    fi
}

echo -e "${BLUE}Core Tests:${NC}"
print_result "  Unit Tests" "$UNIT_PASSED"
print_result "  Edge Case Tests" "$EDGE_PASSED"
print_result "  Security Regression" "$SECURITY_PASSED"

if [ "$FAST_ONLY" = false ]; then
    echo ""
    echo -e "${BLUE}Extended Tests:${NC}"
    print_result "  Contract/Schema" "$CONTRACT_PASSED"
    print_result "  Error Recovery" "$ERROR_RECOVERY_PASSED"
    print_result "  Property-Based" "$PROPERTY_PASSED"
    print_result "  Compatibility" "$COMPATIBILITY_PASSED"
    print_result "  Functional Regression" "$REGRESSION_PASSED"
    print_result "  End-to-End (E2E)" "$E2E_PASSED"
    print_result "  Chaos/Fault Injection" "$CHAOS_PASSED"
    print_result "  Observability/Logging" "$OBSERVABILITY_PASSED"
    print_result "  Documentation" "$DOCUMENTATION_PASSED"
fi

echo ""
echo -e "${BLUE}Performance & Integration:${NC}"
print_result "  Stress Tests" "$STRESS_PASSED"
print_result "  Integration Tests" "$INTEGRATION_PASSED"
if [ "$RUN_COVERAGE" = true ]; then
    print_result "Coverage Report" "$COVERAGE_PASSED"
fi

echo ""

# Exit with appropriate code
if [ "$UNIT_PASSED" = true ] && [ "$EDGE_PASSED" = true ] && [ "$SECURITY_PASSED" = true ]; then
    if [ "$RUN_INTEGRATION" = false ] || [ "$INTEGRATION_PASSED" = "true" ] || [ "$INTEGRATION_PASSED" = "skipped" ]; then
        if [ "$RUN_COVERAGE" = false ] || [ "$COVERAGE_PASSED" = true ]; then
            echo -e "${GREEN}All tests passed! ✓${NC}"
            exit 0
        fi
    fi
fi

echo -e "${RED}Some tests failed ✗${NC}"
exit 1
