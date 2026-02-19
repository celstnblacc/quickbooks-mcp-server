#!/usr/bin/env bash
# Automated script to set up your GitHub fork
# Usage: ./setup_fork.sh <your-github-username>

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

USERNAME=${1:-celstnblacc}
ORIGINAL_REPO="nikhilgy/quickbooks-mcp-server"
YOUR_FORK="$USERNAME/quickbooks-mcp-server"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}GitHub Fork Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if fork exists
echo -e "${YELLOW}Step 1: Checking if fork exists...${NC}"
echo "Have you forked https://github.com/$ORIGINAL_REPO to https://github.com/$YOUR_FORK ?"
echo ""
read -p "Have you completed the fork? (y/n): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}Please fork the repository first:${NC}"
    echo "1. Go to: https://github.com/$ORIGINAL_REPO"
    echo "2. Click the 'Fork' button"
    echo "3. Then run this script again"
    exit 1
fi

echo -e "${GREEN}✓ Fork confirmed${NC}"
echo ""

# Update remotes
echo -e "${YELLOW}Step 2: Updating git remotes...${NC}"
echo "Current remotes:"
git remote -v
echo ""

# Remove old origin
echo "Removing old origin..."
git remote remove origin 2>/dev/null || echo "  (origin already removed)"

# Add your fork as origin
echo "Adding your fork as origin..."
git remote add origin "https://github.com/$YOUR_FORK.git"

# Add upstream
echo "Adding original repo as upstream..."
git remote add upstream "https://github.com/$ORIGINAL_REPO.git" 2>/dev/null || echo "  (upstream already exists)"

echo ""
echo "New remotes:"
git remote -v
echo ""
echo -e "${GREEN}✓ Remotes updated${NC}"
echo ""

# Stage changes
echo -e "${YELLOW}Step 3: Staging all changes...${NC}"
git add .
echo ""

# Show status
echo "Files to be committed:"
git status --short
echo ""
echo -e "${GREEN}✓ Changes staged${NC}"
echo ""

# Commit
echo -e "${YELLOW}Step 4: Creating commit...${NC}"
COMMIT_MSG="Add comprehensive test suite with 470+ tests

- Implemented 10 missing test types (contract, error recovery, property-based, etc.)
- Added 19 test files with ~470 tests
- Created test runner scripts (run_tests.sh, run_mutation_tests.sh)
- Added comprehensive documentation (9 new MD files)
- Set up CI/CD with GitHub Actions
- Added mutation testing and multi-version testing (tox)

Changes include:
* Contract/schema validation tests
* Error recovery and resilience tests
* Property-based/fuzz testing with Hypothesis
* Cross-platform compatibility tests
* Functional regression (golden) tests
* End-to-end workflow tests
* Chaos engineering/fault injection tests
* Observability and logging tests
* Documentation accuracy tests
* Enhanced stress/performance tests

Total: ~470 tests across 19 test files
Documentation: 14 MD files
Test modes: fast (2m), standard (15m), all (25m)

See TEST_IMPLEMENTATION_SUMMARY.md for full details.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

git commit -m "$COMMIT_MSG"
echo ""
echo -e "${GREEN}✓ Commit created${NC}"
echo ""

# Push
echo -e "${YELLOW}Step 5: Pushing to your fork...${NC}"
echo "This will push to: https://github.com/$YOUR_FORK"
echo ""
read -p "Ready to push? (y/n): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Push cancelled. You can push manually later with:${NC}"
    echo "  git push -u origin master"
    exit 0
fi

echo "Pushing..."
if git push -u origin master; then
    echo ""
    echo -e "${GREEN}✓ Successfully pushed to your fork!${NC}"
else
    echo ""
    echo -e "${YELLOW}Push failed. Trying with --force-with-lease...${NC}"
    git push -u origin master --force-with-lease
    echo ""
    echo -e "${GREEN}✓ Successfully force-pushed to your fork!${NC}"
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Setup Complete! 🎉${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Your fork is now at: https://github.com/$YOUR_FORK"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo "1. View your fork: https://github.com/$YOUR_FORK"
echo "2. (Optional) Create Pull Request to contribute back:"
echo "   - Go to your fork"
echo "   - Click 'Contribute' → 'Open pull request'"
echo ""
echo "3. To sync with upstream in the future:"
echo "   git fetch upstream"
echo "   git merge upstream/master"
echo "   git push origin master"
echo ""
echo -e "${GREEN}All done! Your improvements are now on GitHub! 🚀${NC}"
