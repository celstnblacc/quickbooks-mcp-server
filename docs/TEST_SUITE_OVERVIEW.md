# QuickBooks MCP Server - Test Suite Overview

## Quick Start

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all core tests (fast, ~2-5 minutes)
../scripts/run_tests.sh

# Run all tests including extended (10-15 minutes)
../scripts/run_tests.sh --all

# Run only fast unit tests (30 seconds)
../scripts/run_tests.sh --fast

# Run with coverage
../scripts/run_tests.sh --coverage

# Run mutation testing (20-30 minutes)
./run_mutation_tests.sh
```

## Test Categories

### 1. Core Tests (Always Run)

#### Unit Tests
- **Files**: `test_rate_limiter.py`, `test_query_validation.py`, `test_method_allowlist.py`, etc.
- **Purpose**: Test individual components in isolation
- **Speed**: Fast (~30 seconds)
- **Dependencies**: None (fully mocked)

#### Edge Case Tests
- **Files**: `test_edge_cases.py`
- **Purpose**: Test boundary conditions and edge cases
- **Speed**: Fast (~1 minute)
- **Dependencies**: None

#### Security Regression Tests
- **Files**: `test_security_regression.py`
- **Purpose**: Prevent reintroduction of F-01 through F-10 vulnerabilities
- **Speed**: Medium (~2 minutes)
- **Dependencies**: None

### 2. Extended Tests (Standard Run)

#### Contract/Schema Tests
- **Files**: `test_contract_schema.py`
- **Purpose**: Validate OpenAPI schema matches actual API behavior
- **Speed**: Slow (~3-5 minutes)
- **Dependencies**: QuickBooks sandbox credentials (.env)
- **Skip with**: `--fast` or no `.env`

#### Error Recovery Tests
- **Files**: `test_error_recovery.py`
- **Purpose**: Test recovery from network failures, API errors
- **Speed**: Medium (~2 minutes)
- **Dependencies**: None

#### Property-Based Tests
- **Files**: `test_property_based.py`
- **Purpose**: Fuzz testing with randomized inputs (Hypothesis)
- **Speed**: Medium (~3 minutes, 200 examples)
- **Dependencies**: `hypothesis`
- **Skip with**: `--fast`

#### Compatibility Tests
- **Files**: `test_compatibility.py`, `tox.ini`
- **Purpose**: Test across Python 3.10-3.13, platforms
- **Speed**: Medium (~2 minutes)
- **Dependencies**: None (platform-aware)

#### Functional Regression Tests
- **Files**: `test_functional_regression.py`
- **Purpose**: Golden tests - critical behavior must not change
- **Speed**: Medium (~2 minutes)
- **Dependencies**: None (some integration tests need .env)

#### End-to-End (E2E) Tests
- **Files**: `test_e2e.py`
- **Purpose**: Complete user workflows from Claude Desktop
- **Speed**: Slow (~5 minutes)
- **Dependencies**: QuickBooks sandbox credentials
- **Skip with**: `--fast` or `--no-integration`

#### Chaos/Fault Injection Tests
- **Files**: `test_chaos.py`
- **Purpose**: Test resilience under adverse conditions
- **Speed**: Slow (~5-10 minutes)
- **Dependencies**: None
- **Run with**: `--all` only

#### Observability/Logging Tests
- **Files**: `test_observability.py`
- **Purpose**: Verify logging, no sensitive data leaks
- **Speed**: Fast (~1 minute)
- **Dependencies**: None

#### Documentation Tests
- **Files**: `test_documentation.py`
- **Purpose**: Validate README examples, docstrings work
- **Speed**: Fast (~1 minute)
- **Dependencies**: None

### 3. Performance & Integration Tests

#### Stress/Performance Tests
- **Files**: `test_stress.py`
- **Purpose**: Load testing, concurrency, benchmarks
- **Speed**: Slow (~5-10 minutes)
- **Dependencies**: None
- **Run with**: `--stress` or `--all`

#### Integration Tests
- **Files**: `test_integration_*.py`
- **Purpose**: Real QuickBooks API calls
- **Speed**: Slow (~5 minutes)
- **Dependencies**: QuickBooks sandbox credentials
- **Skip with**: `--no-integration`

### 4. Mutation Testing

#### Mutation Tests
- **Script**: `./run_mutation_tests.sh`
- **Purpose**: Test quality of tests (meta-testing)
- **Speed**: Very slow (~20-30 minutes)
- **Dependencies**: `mutmut`
- **Run**: Separately, not in `run_tests.sh`

## Test Execution Modes

### Fast Mode (`--fast`)
Run only fast unit tests for quick feedback during development.

```bash
../scripts/run_tests.sh --fast
```

**Runs**: Unit, Edge Case, Security Regression
**Time**: ~2 minutes
**Use case**: Pre-commit, development loop

### Standard Mode (default)
Run core and extended tests (except slow chaos/mutation).

```bash
../scripts/run_tests.sh
```

**Runs**: All except Chaos, Mutation
**Time**: ~10-15 minutes
**Use case**: Pre-push, CI/CD

### All Mode (`--all`)
Run everything including chaos tests.

```bash
../scripts/run_tests.sh --all
```

**Runs**: Everything except Mutation
**Time**: ~20-25 minutes
**Use case**: Weekly CI/CD, major releases

### Coverage Mode (`--coverage`)
Standard run with code coverage report.

```bash
../scripts/run_tests.sh --coverage
```

**Output**: HTML report in `htmlcov/index.html`
**Time**: ~12-18 minutes
**Use case**: Coverage analysis, documentation

## Test Statistics

| Category | Files | Tests | Time | Dependencies |
|----------|-------|-------|------|--------------|
| Unit | 7 | ~50 | 30s | None |
| Edge Case | 1 | ~9 | 1m | None |
| Security | 1 | ~10 | 2m | None |
| Contract | 1 | ~15 | 5m | .env |
| Error Recovery | 1 | ~20 | 2m | None |
| Property-Based | 1 | 200+ | 3m | hypothesis |
| Compatibility | 1 | ~30 | 2m | None |
| Regression | 1 | ~25 | 2m | None |
| E2E | 1 | ~20 | 5m | .env |
| Chaos | 1 | ~20 | 10m | None |
| Observability | 1 | ~20 | 1m | None |
| Documentation | 1 | ~20 | 1m | None |
| Stress | 1 | ~20 | 10m | None |
| Integration | 3 | ~15 | 5m | .env |
| **Total** | **22** | **~470** | **50m** | - |

## CI/CD Recommendations

### Pre-Commit Hook
```bash
../scripts/run_tests.sh --fast
```
Time: ~2 minutes

### Pull Request
```bash
../scripts/run_tests.sh --coverage
```
Time: ~15 minutes

### Main Branch / Nightly
```bash
../scripts/run_tests.sh --all --coverage
```
Time: ~25 minutes

### Weekly
```bash
./run_mutation_tests.sh
tox  # Multi-version testing
```
Time: ~1 hour

## Dependencies

### Required
- `pytest>=7.0.0`
- `pytest-mock>=3.10.0`

### Optional (Extended Tests)
- `pytest-cov>=4.0.0` - Coverage reports
- `hypothesis>=6.0.0` - Property-based testing
- `mutmut>=2.4.0` - Mutation testing
- `tox>=4.0.0` - Multi-version testing

### Install All
```bash
pip install -r requirements-test.txt
```

## Test Data Requirements

### No Credentials Needed
- Unit tests
- Edge case tests
- Security regression tests
- Error recovery tests
- Property-based tests
- Compatibility tests
- Functional regression tests (most)
- Chaos tests
- Observability tests
- Documentation tests
- Stress tests

### QuickBooks Sandbox Credentials Required
- Contract/schema tests
- Integration tests
- E2E tests
- Some functional regression tests

**Setup**: Create `.env` file with sandbox credentials (see `config/env_template.txt`)

## Common Issues

### Hypothesis tests fail
```bash
# Install hypothesis
pip install hypothesis

# Or skip property-based tests
../scripts/run_tests.sh --fast
```

### Integration tests skipped
```bash
# Check .env file exists
ls -la .env

# Verify credentials set
cat .env | grep QUICKBOOKS_CLIENT_ID

# If missing, copy template
cp config/env_template.txt .env
# Then edit .env with real credentials
```

### Mutation tests hang
```bash
# Clear cache
rm -rf .mutmut-cache
./run_mutation_tests.sh --clean
```

### Tox fails
```bash
# Install missing Python versions
# macOS with pyenv:
pyenv install 3.10 3.11 3.12 3.13

# Or skip multi-version testing
pytest tests/ -v
```

## Documentation

- **TESTING.md** - Detailed test descriptions
- **MUTATION_TESTING.md** - Mutation testing guide
- **TEST_COVERAGE_ANALYSIS.md** - Coverage analysis and missing test types

## Contributing Tests

When adding new features, add tests in this order:

1. **Unit test** - Test the component in isolation
2. **Edge case test** - Test boundary conditions
3. **Integration test** - Test with real API (if applicable)
4. **E2E test** - Test user workflow (if user-facing)
5. **Documentation test** - Add example to README/docstrings

Run mutation testing to verify test quality:

```bash
./run_mutation_tests.sh --results
```
