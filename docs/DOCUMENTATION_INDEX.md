# Documentation Index

Complete guide to all documentation for the QuickBooks MCP Server.

## 🚀 Quick Start

**New to the project?** Start here:
1. [README.md](../README.md) - Project overview, installation, usage
2. [TESTING.md](TESTING.md) - How to run tests
3. [CLAUDE.md](CLAUDE.md) - Development guide for Claude Code

## 📚 Main Documentation

### Project Documentation
- **[README.md](../README.md)** - Project overview, setup instructions, security hardening details
- **[CLAUDE.md](CLAUDE.md)** - Developer guide for working with this codebase in Claude Code

### Testing Documentation
- **[TESTING.md](TESTING.md)** - Complete test suite documentation (~470 tests across 19 files)
- **[TEST_SUITE_OVERVIEW.md](TEST_SUITE_OVERVIEW.md)** - Comprehensive guide to all test categories
- **[TEST_COVERAGE_ANALYSIS.md](TEST_COVERAGE_ANALYSIS.md)** - Analysis of test coverage and gaps
- **[TEST_IMPLEMENTATION_SUMMARY.md](TEST_IMPLEMENTATION_SUMMARY.md)** - Implementation details of new tests
- **[MUTATION_TESTING.md](MUTATION_TESTING.md)** - Guide to mutation testing (meta-testing)

### Configuration Files
- **[pyproject.toml](../pyproject.toml)** - Python project configuration
- **[pyproject.toml [test]](../pyproject.toml [test])** - Test dependencies
- **[tox.ini](../tox.ini)** - Multi-version Python testing configuration
- **[config/env_template.txt](../config/env_template.txt)** - Template for `.env` file

## 🎯 By Use Case

### I want to...

#### Set Up the Project
1. Read [README.md](../README.md) - Requirements & Step 1-3
2. Copy `config/env_template.txt` to `.env` and configure
3. Run `uv run src/main_quickbooks_mcp.py`

#### Run Tests
1. Quick start: [TESTING.md](TESTING.md) - Quick Reference section
2. Detailed guide: [TEST_SUITE_OVERVIEW.md](TEST_SUITE_OVERVIEW.md)
3. Run: `../scripts/run_tests.sh`

#### Understand the Test Suite
1. [TEST_SUITE_OVERVIEW.md](TEST_SUITE_OVERVIEW.md) - All test categories
2. [TESTING.md](TESTING.md) - Detailed test descriptions
3. [TEST_IMPLEMENTATION_SUMMARY.md](TEST_IMPLEMENTATION_SUMMARY.md) - What was implemented

#### Run Mutation Testing
1. [MUTATION_TESTING.md](MUTATION_TESTING.md) - Complete guide
2. Run: `../scripts/run_mutation_tests.sh`

#### Contribute Code
1. [CLAUDE.md](CLAUDE.md) - Development workflow
2. [TESTING.md](TESTING.md) - How to add tests

#### Set Up CI/CD
1. [.github/workflows/tests.yml](../.github/workflows/tests.yml) - GitHub Actions workflow
2. [TEST_SUITE_OVERVIEW.md](TEST_SUITE_OVERVIEW.md) - CI/CD Recommendations section

## 📊 Test Documentation Breakdown

### Core Test Categories
| Document | Tests Covered | Time |
|----------|---------------|------|
| Unit Tests | ~50 tests | 30s |
| Edge Case Tests | ~9 tests | 1m |
| Security Regression | ~10 tests | 2m |

### Extended Test Categories
| Document | Tests Covered | Time |
|----------|---------------|------|
| Contract/Schema Tests | ~15 tests | 5m |
| Error Recovery Tests | ~20 tests | 2m |
| Property-Based Tests | 200+ tests | 3m |
| Compatibility Tests | ~30 tests | 2m |
| Functional Regression | ~25 tests | 2m |
| E2E Tests | ~20 tests | 5m |
| Observability Tests | ~20 tests | 1m |
| Documentation Tests | ~20 tests | 1m |

### Performance Tests
| Document | Tests Covered | Time |
|----------|---------------|------|
| Stress Tests | ~20 tests | 10m |
| Chaos Tests | ~20 tests | 10m |
| Integration Tests | ~15 tests | 5m |

### Meta-Testing
| Document | Purpose | Time |
|----------|---------|------|
| Mutation Testing | Test quality validation | 30m |

**Total: ~470 tests across 19 test files**

## 🔍 Finding Specific Information

### Security
- **Security hardening**: [README.md](../README.md) - "Security Hardening (Feb 2026)" section
- **F-01 through F-10 fixes**: [README.md](../README.md) - Vulnerability table
- **Security tests**: [TESTING.md](TESTING.md) - Section 3

### Architecture
- **High-level overview**: [CLAUDE.md](CLAUDE.md) - "Architecture" section
- **Component interaction**: [CLAUDE.md](CLAUDE.md) - Entry point, OAuth2, Schema loading
- **File structure**: [CLAUDE.md](CLAUDE.md) - Important File Locations

### Commands
- **Development commands**: [CLAUDE.md](CLAUDE.md) - "Commands" section
- **Test commands**: [TESTING.md](TESTING.md) - "Running the Tests" section
- **Quick reference**: [TEST_SUITE_OVERVIEW.md](TEST_SUITE_OVERVIEW.md) - Top of file

### Configuration
- **Environment variables**: [README.md](../README.md) - Step 2
- **Claude Desktop setup**: [README.md](../README.md) - Step 3
- **Test configuration**: [tox.ini](../tox.ini), [pyproject.toml [test]](../pyproject.toml [test])

## 📖 Documentation Files

### Primary (Read First)
1. [README.md](../README.md) - 122 lines
2. [CLAUDE.md](CLAUDE.md) - Comprehensive developer guide
3. [TESTING.md](TESTING.md) - 800+ lines of test documentation

### Testing Guides
4. [TEST_SUITE_OVERVIEW.md](TEST_SUITE_OVERVIEW.md) - Most comprehensive test guide
5. [TEST_COVERAGE_ANALYSIS.md](TEST_COVERAGE_ANALYSIS.md) - Gap analysis
6. [MUTATION_TESTING.md](MUTATION_TESTING.md) - Mutation testing guide

### Reference
7. [TEST_IMPLEMENTATION_SUMMARY.md](TEST_IMPLEMENTATION_SUMMARY.md) - Implementation details
8. [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md) - This file

### Configuration
9. [pyproject.toml](../pyproject.toml) - Project metadata
10. [pyproject.toml [test]](../pyproject.toml [test]) - Test dependencies
11. [tox.ini](../tox.ini) - Multi-version testing
12. [config/env_template.txt](../config/env_template.txt) - Environment template

### CI/CD
13. [.github/workflows/tests.yml](../.github/workflows/tests.yml) - GitHub Actions

## 🆘 Getting Help

### Common Questions

**Q: How do I run tests quickly?**
A: `../scripts/run_tests.sh --fast` (2 minutes)

**Q: How do I see test coverage?**
A: `../scripts/run_tests.sh --coverage` → open `htmlcov/index.html`

**Q: What tests require QuickBooks credentials?**
A: Contract, E2E, and Integration tests (auto-skipped without `.env`)

**Q: How do I test on multiple Python versions?**
A: `tox` (requires Python 3.10-3.13 installed)

**Q: What's mutation testing?**
A: See [MUTATION_TESTING.md](MUTATION_TESTING.md) - tests the quality of your tests

**Q: Where's the architecture documentation?**
A: [CLAUDE.md](CLAUDE.md) - "Architecture" section

**Q: How were the vulnerabilities fixed?**
A: [README.md](../README.md) - "Security Hardening" section with F-01 through F-10 table

## 📈 Documentation Statistics

- **Total Documentation Files**: 9 (+ README.md in root)
- **Total Lines**: 5,000+
- **Test Files Documented**: 19
- **Test Categories**: 15
- **Code Examples**: 100+
- **Location**: All documentation in `docs/` folder except README.md

## 🎉 Documentation Highlights

✅ **Comprehensive** - Every test category fully documented
✅ **Well-organized** - Clear hierarchy and cross-references
✅ **Practical** - Lots of examples and quick-start guides
✅ **Searchable** - This index helps find anything quickly
✅ **Up-to-date** - Reflects latest test implementation (Feb 2026)

## 📝 Contributing to Documentation

When updating documentation:
1. Update the relevant file in `docs/` (or README.md in root)
2. Update cross-references if needed
3. Run tests to verify examples work: `../scripts/run_tests.sh`

All documentation (except README.md) is in the `docs/` folder.

---

**Last Updated**: 2026-02-11
**Documentation Version**: 2.0 (comprehensive test suite)
