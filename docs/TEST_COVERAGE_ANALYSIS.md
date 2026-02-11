# Test Coverage Analysis - Missing Test Types

## Currently Implemented ✅

1. **Unit Tests** ✅
   - Rate limiter
   - Query validation
   - HTTP method allowlist
   - Environment variable handling
   - Token persistence
   - Error sanitization
   - Closure factory

2. **Edge Case Tests** ✅
   - Boundary conditions
   - Empty/malformed inputs
   - Concurrent access patterns

3. **Security Regression Tests** ✅
   - Prevents reintroduction of F-01 through F-10 vulnerabilities

4. **Integration Tests** ✅
   - OAuth flow
   - Real API queries
   - Tool registration

5. **Stress/Performance Tests** ✅ (just added)
   - Load testing
   - Concurrency testing
   - Memory leak detection
   - Performance benchmarks

---

## Missing Test Types 🔴

### 1. **Contract/API Schema Tests**
**Purpose**: Verify the OpenAPI schema matches actual QuickBooks API behavior

**What to test**:
- Schema validation against real API responses
- Parameter type mismatches (schema says `string`, API requires `integer`)
- Required vs optional field detection
- Response structure changes from QuickBooks

**Risk**: High - Schema drift could cause runtime failures

**Example**:
```python
def test_schema_matches_api_response():
    # Load schema definition for /account/{id}
    # Make real API call
    # Validate response matches schema expectations
```

---

### 2. **Compatibility Tests**
**Purpose**: Ensure compatibility across different environments

**What to test**:
- Python version compatibility (3.10, 3.11, 3.12, 3.13)
- Operating system differences (macOS, Linux, Windows)
- Different MCP client versions
- Claude Desktop version compatibility

**Risk**: Medium - Users on different systems may experience failures

**Example**:
```python
@pytest.mark.parametrize("python_version", ["3.10", "3.11", "3.12"])
def test_server_starts_on_python_version(python_version):
    # Run server with specific Python version via tox
```

---

### 3. **Error Recovery Tests**
**Purpose**: Verify system recovers gracefully from failures

**What to test**:
- Network timeouts and retries
- Partial response handling
- Rate limit recovery (wait and retry)
- Token refresh failure recovery
- Database/API unavailability scenarios

**Risk**: Medium - Real-world failures not well-tested

**Example**:
```python
def test_recovery_after_network_timeout():
    # Simulate timeout on first call
    # Verify server retries and succeeds on second call
```

---

### 4. **Regression Tests (Functional)**
**Purpose**: Prevent breaking changes to existing functionality

**What to test**:
- Baseline queries that must always work (golden tests)
- Tool registration stability across versions
- Backward compatibility with older .env formats
- MCP protocol compliance

**Risk**: Medium - Changes might break existing user workflows

**Example**:
```python
def test_golden_query_account():
    # This exact query must work in all versions
    result = query_quickbooks("SELECT * FROM Account MAXRESULTS 1")
    assert "QueryResponse" in result.text
```

---

### 5. **Property-Based Tests (Fuzzing)**
**Purpose**: Find unexpected edge cases through randomized inputs

**What to test**:
- Random query strings (using Hypothesis)
- Random parameter combinations
- Random JSON structures for POST bodies
- Unicode/special characters in inputs

**Risk**: Low-Medium - May find unexpected crashes

**Example**:
```python
from hypothesis import given, strategies as st

@given(st.text(min_size=1, max_size=1000))
def test_query_validation_never_crashes(random_query):
    # Should never crash, always return TextContent
    result = query_quickbooks(random_query)
    assert result.text is not None
```

---

### 6. **End-to-End (E2E) Tests**
**Purpose**: Test complete user workflows in Claude Desktop

**What to test**:
- Full workflow: User asks question → Claude calls tool → Response displayed
- Multiple tool calls in sequence
- Tool call with follow-up questions
- Error handling from user perspective

**Risk**: Medium - User experience issues may not be caught

**Example**:
```python
def test_e2e_get_accounts_then_query():
    # 1. Claude calls get_quickbooks_entity_schema("Account")
    # 2. Claude constructs query based on schema
    # 3. Claude calls query_quickbooks()
    # 4. Verify user gets valid response
```

---

### 7. **Chaos/Fault Injection Tests**
**Purpose**: Verify resilience under adverse conditions

**What to test**:
- Randomly kill threads/connections mid-request
- Corrupt .env file during runtime
- Fill disk during token persistence
- Exhaust file descriptors
- Clock skew/system time changes

**Risk**: Low - Rare but catastrophic failures

**Example**:
```python
def test_token_persistence_disk_full():
    # Mock write failure (disk full)
    # Verify server logs error but continues operating
```

---

### 8. **Observability/Logging Tests**
**Purpose**: Verify logging and monitoring work correctly

**What to test**:
- Critical errors are logged at ERROR level
- Sensitive data (tokens) never logged
- Log format is parseable (JSON/structured)
- Metrics are emitted correctly (if applicable)

**Risk**: Low - Operational debugging will be harder

**Example**:
```python
def test_no_tokens_in_logs(caplog):
    # Trigger various operations
    # Grep all log messages for token patterns
    for record in caplog.records:
        assert not re.search(r'[A-Za-z0-9]{100,}', record.message)
```

---

### 9. **Documentation Tests (Doctest)**
**Purpose**: Ensure code examples in docs actually work

**What to test**:
- README examples are valid
- Docstrings have working code examples
- Configuration snippets are correct

**Risk**: Low - Users may copy broken examples

**Example**:
```python
def test_readme_setup_instructions():
    # Parse README.md
    # Extract code blocks
    # Execute them and verify they work
```

---

### 10. **Mutation Tests**
**Purpose**: Verify tests actually catch bugs (test the tests)

**What to test**:
- Use tools like `mutmut` to introduce bugs
- Verify existing tests fail when bugs are introduced
- Measure mutation score (% of mutations caught)

**Risk**: Low - But indicates test suite quality

**Example**:
```bash
# Run mutation testing
mutmut run
mutmut results  # Should show high kill rate (>80%)
```

---

## Priority Recommendations

### 🔴 **High Priority** (Implement Soon)
1. **Contract/API Schema Tests** - Catch QuickBooks API changes
2. **Error Recovery Tests** - Real-world failure scenarios
3. **Property-Based Tests** - Find unexpected edge cases

### 🟡 **Medium Priority** (Consider Adding)
4. **Compatibility Tests** - Multi-platform support
5. **Functional Regression Tests** - Protect user workflows
6. **End-to-End Tests** - User experience validation

### 🟢 **Low Priority** (Nice to Have)
7. **Chaos/Fault Injection** - Rare but catastrophic scenarios
8. **Observability Tests** - Operational concerns
9. **Documentation Tests** - User education
10. **Mutation Tests** - Test suite quality metrics

---

## Implementation Effort Estimate

| Test Type | Effort | Value | Priority |
|-----------|--------|-------|----------|
| Contract/Schema | Medium | High | 🔴 High |
| Error Recovery | Medium | High | 🔴 High |
| Property-Based | Low | Medium | 🔴 High |
| Compatibility | High | Medium | 🟡 Medium |
| Regression | Medium | Medium | 🟡 Medium |
| E2E | High | Medium | 🟡 Medium |
| Chaos | High | Low | 🟢 Low |
| Observability | Low | Low | 🟢 Low |
| Documentation | Low | Low | 🟢 Low |
| Mutation | Low | Low | 🟢 Low |
