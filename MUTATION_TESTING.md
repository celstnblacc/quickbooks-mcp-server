# Mutation Testing Guide

## What is Mutation Testing?

Mutation testing is a technique to test the quality of your tests. It works by:
1. Making small changes (mutations) to your code
2. Running your tests against the mutated code
3. Checking if the tests catch the bugs

If a test catches the mutation → **Killed** (good!)
If a mutation survives → **Survived** (test gap!)

## Installation

```bash
pip install mutmut
```

## Running Mutation Tests

### Quick Start

```bash
# Run mutation testing
./run_mutation_tests.sh

# Clean cache and run fresh
./run_mutation_tests.sh --clean

# Show detailed results
./run_mutation_tests.sh --results
```

### Manual Commands

```bash
# Run mutations on all source files
mutmut run

# Run on specific file
mutmut run --paths-to-mutate=rate_limiter.py

# View summary
mutmut results

# Show survived mutations
mutmut show survived

# View specific mutation
mutmut show 42

# Apply a mutation to see the change
mutmut apply 42
```

## Interpreting Results

### Mutation Status

| Status | Meaning | Action |
|--------|---------|--------|
| **Killed** | Test caught the bug | ✅ Good! Test is working |
| **Survived** | Bug not caught | ❌ Add test to catch this |
| **Timeout** | Test took too long | ⚠️ May need optimization |
| **Suspicious** | Unclear result | 🔍 Manual review needed |

### Mutation Score

```
Mutation Score = (Killed / Total) × 100%
```

- **< 70%**: Poor test coverage
- **70-80%**: Acceptable
- **80-90%**: Good
- **> 90%**: Excellent

## Common Mutation Types

Mutmut introduces these types of mutations:

1. **Operator mutations**
   - `==` → `!=`
   - `<` → `<=`
   - `+` → `-`

2. **Constant mutations**
   - `True` → `False`
   - `0` → `1`
   - `""` → `"X"`

3. **Statement mutations**
   - Remove `break`/`continue`
   - Remove `return`
   - Swap conditionals

## Example Workflow

### 1. Run Mutation Tests

```bash
./run_mutation_tests.sh
```

Output:
```
Killed: 150
Survived: 10
Timeout: 2
Mutation Score: 92.6%
```

### 2. Review Survivors

```bash
mutmut show survived
```

Output:
```
Survived mutation 42:
--- rate_limiter.py
+++ rate_limiter.py
@@ -15,7 +15,7 @@
-    if self.tokens >= 1.0:
+    if self.tokens > 1.0:
```

### 3. Add Test

Create test to catch this mutation:

```python
def test_rate_limiter_exact_boundary():
    """Test with exactly 1.0 tokens (boundary condition)."""
    limiter = RateLimiter(requests_per_minute=60)
    # Set to exactly 1.0 token
    limiter.tokens = 1.0
    # Should allow (>= not >)
    assert limiter.is_allowed() is True
```

### 4. Re-run

```bash
./run_mutation_tests.sh
```

Mutation 42 should now be **Killed**!

## Files Tested

Mutation testing covers:
- `main_quickbooks_mcp.py` - MCP server and tool registration
- `quickbooks_interaction.py` - OAuth and API calls
- `rate_limiter.py` - Token bucket rate limiter
- `environment.py` - Environment variable handling
- `api_importer.py` - Schema loading

## Performance

Mutation testing is **slow** because it runs your entire test suite for each mutation.

**Typical runtime:** 10-30 minutes

**Optimization tips:**
- Use `--tests-dir=tests/` to limit test discovery
- Use `pytest -x` to stop on first failure
- Cache results (don't use `--clean` unless needed)
- Run on CI/CD nightly instead of every commit

## CI/CD Integration

Add to `.github/workflows/mutation-tests.yml`:

```yaml
name: Mutation Tests

on:
  schedule:
    - cron: '0 2 * * 0'  # Weekly, Sunday 2 AM

jobs:
  mutation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install mutmut pytest
      - name: Run mutation tests
        run: ./run_mutation_tests.sh
      - name: Check mutation score
        run: |
          SCORE=$(mutmut results | grep -oP '\d+\.\d+%' | head -1)
          echo "Mutation score: $SCORE"
```

## Troubleshooting

### Mutation tests hang

```bash
# Use timeout
mutmut run --runner="pytest -x -q --timeout=60"
```

### Too many survivors

- Review each survivor: `mutmut show <id>`
- Check if mutation is equivalent (same behavior)
- Add missing test cases
- Improve assertion specificity

### Cache issues

```bash
# Clear cache
rm -rf .mutmut-cache
./run_mutation_tests.sh
```

## Best Practices

1. **Run regularly** - Catch test gaps early
2. **Review survivors** - Each survivor is a potential bug
3. **Aim for > 80%** - Balance quality vs. time
4. **Don't obsess over 100%** - Some equivalent mutations can't be killed
5. **Use with coverage** - Mutation testing complements code coverage

## Resources

- [Mutmut Documentation](https://mutmut.readthedocs.io/)
- [Mutation Testing Wikipedia](https://en.wikipedia.org/wiki/Mutation_testing)
- [Testing Quality Metrics](https://martinfowler.com/bliki/MutationTesting.html)
