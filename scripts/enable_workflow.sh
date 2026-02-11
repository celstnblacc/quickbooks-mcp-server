#!/usr/bin/env bash
# Script to add GitHub Actions workflow after token is updated with workflow scope
# Usage: ./enable_workflow.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Enable GitHub Actions Workflow${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if workflow file already exists
if [ -f ".github/workflows/tests.yml" ]; then
    echo -e "${GREEN}✓ Workflow file already exists!${NC}"
    echo "Location: .github/workflows/tests.yml"
    echo ""
    read -p "Do you want to commit and push it? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 0
    fi
else
    echo -e "${YELLOW}Workflow file not found. Creating it...${NC}"

    # Create .github/workflows directory
    mkdir -p .github/workflows

    # Create the workflow file
    cat > .github/workflows/tests.yml << 'EOF'
name: Test Suite

on:
  push:
    branches: [ master, main, feature/comprehensive-test-suite ]
  pull_request:
    branches: [ master, main ]
  schedule:
    - cron: '0 2 * * 0'  # Weekly on Sunday at 2 AM

jobs:
  fast-tests:
    name: Fast Tests (2 min)
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python 3.12
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    - name: Install dependencies
      run: pip install uv && uv sync --extra test
    - name: Run fast tests
      run: ./run_tests.sh --fast

  standard-tests:
    name: Standard Test Suite (15 min)
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python 3.12
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    - name: Install dependencies
      run: pip install uv && uv sync --extra test
    - name: Run standard test suite with coverage
      run: ./run_tests.sh --coverage --no-integration
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        files: ./coverage.xml

  multi-version:
    name: Python ${{ matrix.python-version }}
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12', '3.13']
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    - name: Install dependencies
      run: pip install uv && uv sync --extra test
    - name: Run compatibility tests
      run: pytest tests/test_compatibility.py -v
EOF

    echo -e "${GREEN}✓ Workflow file created!${NC}"
    echo ""
fi

# Show current branch
CURRENT_BRANCH=$(git branch --show-current)
echo "Current branch: ${CURRENT_BRANCH}"
echo ""

# Check if token has workflow scope
echo -e "${YELLOW}⚠️  IMPORTANT: Your token needs 'workflow' scope${NC}"
echo ""
echo "To update your token:"
echo "1. Go to: https://github.com/settings/tokens"
echo "2. Find your token and click 'Edit'"
echo "3. Check the ✅ 'workflow' scope"
echo "4. Click 'Update token'"
echo ""
read -p "Have you updated your token with 'workflow' scope? (y/n): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo -e "${YELLOW}Please update your token first, then run this script again.${NC}"
    echo "Workflow file saved at: .github/workflows/tests.yml"
    exit 0
fi

# Commit and push
echo ""
echo -e "${BLUE}Committing workflow file...${NC}"
git add .github/workflows/tests.yml

if git diff --cached --quiet; then
    echo -e "${YELLOW}No changes to commit${NC}"
else
    git commit -m "Add GitHub Actions CI/CD workflow

- Fast tests (2 min) on every push
- Standard tests with coverage (15 min)
- Multi-version testing (Python 3.10-3.13)"
    echo -e "${GREEN}✓ Committed!${NC}"
fi

echo ""
echo -e "${BLUE}Pushing to GitHub...${NC}"

if git push; then
    echo ""
    echo -e "${GREEN}✓ SUCCESS! Workflow enabled!${NC}"
    echo ""
    echo "View workflows at:"
    echo "https://github.com/celstnblacc/quickbooks-mcp-server/actions"
else
    echo ""
    echo -e "${RED}Push failed! Token might still need 'workflow' scope.${NC}"
    exit 1
fi
