# $project_name

$description

[![CI](https://github.com/username/$project_name/workflows/CI/badge.svg)](https://github.com/username/$project_name/actions)
[![Coverage](https://codecov.io/gh/username/$project_name/branch/main/graph/badge.svg)](https://codecov.io/gh/username/$project_name)
[![PyPI version](https://badge.fury.io/py/$project_name.svg)](https://badge.fury.io/py/$project_name)
[![Python versions](https://img.shields.io/pypi/pyversions/$project_name.svg)](https://pypi.org/project/$project_name/)

## 🚀 Features

- ✨ Modern Python with strict type safety
- 🔧 uv for fast dependency management
- 🧪 pytest with performance benchmarking
- 📦 Modern packaging with hatchling
- 🐳 Docker support
- 🔄 GitHub Actions CI/CD
- 📚 Complete documentation

## 🛡️ MASTER RULESET ENFORCEMENT

This project **ENFORCES FIRST PRINCIPLES** through automated validation:

### **🔒 MANDATORY: Pydantic Model Design Principles**

- **ALL DATA STRUCTURES MUST USE PYDANTIC**: No plain dictionaries allowed
- **IMMUTABLE BY DEFAULT**: `frozen=True` on all models
- **FIELD CONSTRAINTS**: Every field must have appropriate constraints
- **STRICT VALIDATION**: `str_strict=True`, `validate_default=True`
- **CUSTOM VALIDATORS**: Business logic validation using Pydantic validators
- **ZERO-COPY OPERATIONS**: Leverage Pydantic's Rust core for performance

### **⚡ MANDATORY: Performance Quality Gates**

- **FUNCTIONS >10 LINES MUST HAVE BENCHMARKS**: Automated detection in CI
- **MEMORY ALLOCATION LIMITS**: <1MB temporary objects per function
- **MEMORY LEAK DETECTION**: No growth >1MB in 1000 iterations
- **CPU EFFICIENCY**: O(n) operations must complete within expected bounds
- **BENCHMARK REGRESSION TESTS**: Performance cannot degrade >5% between commits

### **🔒 MANDATORY: Type Safety & Runtime Validation**

- **100% TYPE COVERAGE**: No `Any` types except at system boundaries
- **MYPY STRICT MODE**: Must pass `--strict` without ignores
- **RUNTIME TYPE CHECKING**: `@beartype` decorator on ALL public functions
- **EXHAUSTIVE PATTERN MATCHING**: Use match/case for enum handling
- **RESULT TYPES**: Use Result[T, E] pattern instead of exceptions

### **🛡️ MANDATORY: Security-First Development**

- **HIGH-SEVERITY ISSUES = CI FAILURE**: Zero tolerance for security vulnerabilities
- **DEPENDENCY SCANNING**: safety, pip-audit, snyk integration
- **STATIC ANALYSIS**: bandit, semgrep automated scanning
- **SECRET DETECTION**: detect-secrets with baseline management

### **📊 Automated Enforcement**

- **Pre-commit Hooks**: Validate all rules before commit
- **Pre-push Hooks**: Run performance benchmarks and quality gates
- **CI/CD Pipeline**: Master ruleset enforcement in GitHub Actions
- **Quality Gates**: Fail fast on violations, no exceptions

## 📦 Installation

\`\`\`bash

# From PyPI

pip install $project_name

# From source

git clone https://github.com/username/$project_name.git
cd $project_name
uv sync --dev
\`\`\`

## 🛠️ Development

### Prerequisites

- Python 3.8+
- uv

### Setup

\`\`\`bash

# Clone repository

git clone https://github.com/username/$project_name.git
cd $project_name

# Install dependencies

make dev

# Run tests

make test

# Format code

make format
\`\`\`

### Available Commands

\`\`\`bash
make install # Install dependencies
make dev # Setup development environment
make test # Run tests
make test-cov # Run tests with coverage
make lint # Run linting
make format # Format code
make clean # Clean build artifacts
\`\`\`

## 🧪 Testing

\`\`\`bash

# Run all tests

uv run pytest

# Run with coverage

uv run pytest --cov=src --cov-report=html

# Run specific test

uv run pytest tests/test_specific.py

# Performance benchmarks

uv run pytest --benchmark-only
uv run pytest -m benchmark

# Memory profiling

uv run python -m memray run --output profile.bin src/main.py
uv run python -m memray flamegraph profile.bin

# CPU profiling

py-spy record -o profile.svg -- python src/main.py

# Type coverage analysis

uv run mypy --html-report type-coverage src/

# MASTER RULESET VALIDATION

./scripts/validate-master-ruleset.sh
\`\`\`

## 🛡️ Master Ruleset Validation

This project enforces **first principles** through comprehensive validation:

\`\`\`bash

# Validate Pydantic model compliance (pre-commit)

./scripts/validate-pydantic-compliance.sh

# Check performance quality gates (pre-push)

./scripts/validate-performance-gates.sh

# Run complete master ruleset validation

./scripts/validate-master-ruleset.sh

# Performance benchmark requirements

pytest tests/benchmarks --benchmark-only --benchmark-compare-fail=mean:15%
\`\`\`

### **🎯 Quality Gates Enforced**

| Rule                              | Enforcement | Failure Action  |
| --------------------------------- | ----------- | --------------- |
| Pydantic Models Only              | Pre-commit  | ❌ Block commit |
| \`frozen=True\` Required          | Pre-commit  | ❌ Block commit |
| \`@beartype\` on Public Functions | Pre-commit  | ⚠️ Warning      |
| MyPy \`--strict\` Mode            | Pre-commit  | ❌ Block commit |
| Performance Benchmarks            | Pre-push    | ❌ Block push   |
| Memory Limit <1MB                 | Pre-push    | ❌ Block push   |
| Security High Issues              | CI          | ❌ Fail build   |
| Type Coverage 100%                | CI          | ❌ Fail build   |

## 🔬 Performance Analysis

### **Built-in Profiling**

\`\`\`bash

# Run with performance monitoring

python -X tracemalloc src/main.py

# Memory analysis with memray

memray run --output memory.bin src/main.py
memray flamegraph memory.bin

# CPU profiling with py-spy (no code changes needed)

py-spy record -o cpu-profile.svg -- python src/main.py

# Benchmarking with pytest

pytest --benchmark-only --benchmark-json=results.json
\`\`\`

### **Defensive Programming Examples**

Example Python code implementing MASTER RULESET principles:

- Pydantic models with frozen=True for immutability
- @beartype decorators for runtime type checking
- Result types for error handling without exceptions
- Field constraints and validation on all data models

See src/${project_name}/main.py for complete implementation examples.

## 📝 License

This project is licensed under the MIT License.
