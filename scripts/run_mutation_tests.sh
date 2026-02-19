#!/usr/bin/env bash
# Mutation testing runner for quickbooks-mcp-server
# Tests the tests by introducing bugs and checking if tests catch them

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}QuickBooks MCP - Mutation Testing${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo -e "${RED}Error: uv is not installed${NC}"
    echo "Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Sync dependencies (ensure test dependencies including mutmut are installed)
echo -e "${BLUE}Syncing dependencies...${NC}"
uv sync --extra test
echo ""

# Parse arguments
CLEAN=false
SHOW_RESULTS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --clean)
            CLEAN=true
            shift
            ;;
        --results)
            SHOW_RESULTS=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --clean          Remove previous mutation cache"
            echo "  --results        Show detailed results after run"
            echo "  --help, -h       Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Clean cache if requested
if [ "$CLEAN" = true ]; then
    echo -e "${YELLOW}Cleaning mutation cache...${NC}"
    rm -rf .mutmut-cache
    echo ""
fi

# Check if cache exists
if [ -f ".mutmut-cache" ]; then
    echo -e "${YELLOW}Note: Mutation cache exists. Use --clean to start fresh.${NC}"
    echo ""
fi

echo -e "${BLUE}Running mutation tests...${NC}"
echo -e "${YELLOW}This may take 10-30 minutes depending on your system${NC}"
echo ""

# Configure mutmut to test specific modules
PATHS_TO_MUTATE="src/main_quickbooks_mcp.py src/quickbooks_interaction.py src/rate_limiter.py src/environment.py src/api_importer.py"

echo "Mutating: $PATHS_TO_MUTATE"
echo ""

# Run mutmut
if uv run mutmut run --paths-to-mutate="$PATHS_TO_MUTATE" --tests-dir=tests/ --runner="uv run pytest -x -q"; then
    echo -e "${GREEN}✓ Mutation testing completed${NC}"
else
    echo -e "${YELLOW}⚠ Mutation testing completed with some survivors${NC}"
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Mutation Testing Summary${NC}"
echo -e "${BLUE}========================================${NC}"

# Show summary
uv run mutmut results

echo ""
echo -e "${YELLOW}Interpreting Results:${NC}"
echo "  - ${GREEN}Killed${NC}: Test caught the mutation (good!)"
echo "  - ${RED}Survived${NC}: Mutation not caught - may indicate missing tests"
echo "  - ${YELLOW}Timeout${NC}: Test took too long - may need optimization"
echo "  - ${BLUE}Suspicious${NC}: Needs manual review"
echo ""

# Show detailed results if requested
if [ "$SHOW_RESULTS" = true ]; then
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Survived Mutations (Not Caught by Tests)${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    # Show survived mutations
    uv run mutmut show survived || echo "No survived mutations (perfect score!)"

    echo ""
    echo "To view specific mutation: uv run mutmut show <mutation-id>"
fi

# Calculate mutation score
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Mutation Score${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "A good mutation score is > 80%"
echo "Excellent mutation score is > 90%"
echo ""
echo "To improve score:"
echo "  1. Review survived mutations: uv run mutmut show survived"
echo "  2. Add tests to catch those mutations"
echo "  3. Run again: ./run_mutation_tests.sh"
echo ""
