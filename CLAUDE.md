# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a high-performance Python backend for an MVP policy decision and management system, built with enterprise-grade standards. The project enforces **first principles thinking** and **precision engineering** through automated validation and defensive programming patterns.

## Technology Stack

- **Python**: 3.11+ (targeting modern performance improvements)
- **API Framework**: FastAPI (high-performance async)
- **Data Validation**: Pydantic v2 (Rust core for zero-copy operations)
- **Type Safety**: MyPy strict mode + Beartype runtime validation
- **Package Management**: uv (Rust-based, fast dependency management)
- **Build System**: Hatchling
- **Testing**: pytest with performance benchmarking

## Core Architecture Principles

### MASTER RULESET ENFORCEMENT (NON-NEGOTIABLE)

1. **NO QUICK FIXES OR WORKAROUNDS** - Always solve for root causes
2. **SEARCH BEFORE CREATING** - Always check for existing files before creating new ones
3. **PEAK EXCELLENCE STANDARD** - Represent premium enterprise grade as minimum standard

### Defensive Programming & Performance

- **ALL DATA MODELS MUST USE PYDANTIC** with `frozen=True` for immutability
- **100% TYPE COVERAGE** - No `Any` types except at system boundaries
- **@beartype DECORATORS** required on all public functions
- **PERFORMANCE QUALITY GATES**:
  - Functions >10 lines must have benchmarks
  - Memory allocation <1MB per function
  - No memory growth >1MB in 1000 iterations
  - Performance cannot degrade >5% between commits

### SAGE System Integration

This project uses the SAGE (Supervisor Agent-Generated Engineering) system for multi-wave code generation:

- **Wave 1**: Foundation (80% build, maximum parallelization)
- **Wave 2**: Feature Implementation (90% build, balanced)
- **Wave 3**: Polish & Optimization (100% build, sequential)

Refer to `.sage/MASTER_INSTRUCTION_SET.md` for complete SAGE orchestration protocols.

## Development Commands

### Setup

```bash
# Install dependencies
make dev
# or
uv sync --dev
uv run pre-commit install
```

### Development Workflow

```bash
# Run tests
make test
uv run pytest

# Run tests with coverage
make test-cov
uv run pytest --cov=src --cov-report=html --cov-report=term

# Type checking and linting
make lint
uv run mypy src
uv run flake8 src tests

# Code formatting
make format
uv run black src tests
uv run isort src tests

# Format check (CI)
make format-check
uv run black --check src tests
uv run isort --check-only src tests
```

### Performance Analysis

```bash
# Performance benchmarks
uv run pytest --benchmark-only
uv run pytest -m benchmark

# Memory profiling with memray
uv run python -m memray run --output profile.bin src/pd_prime_demo/main.py
uv run python -m memray flamegraph profile.bin

# CPU profiling with py-spy (no code changes needed)
py-spy record -o profile.svg -- python src/pd_prime_demo/main.py

# Type coverage analysis
uv run mypy --html-report type-coverage src/
```

### Master Ruleset Validation

```bash
# Validate Pydantic model compliance (pre-commit)
./scripts/validate-pydantic-compliance.sh

# Check performance quality gates (pre-push)
./scripts/validate-performance-gates.sh

# Run complete master ruleset validation
./scripts/validate-master-ruleset.sh
```

## Code Organization

```
src/pd_prime_demo/     # Main application package
├── main.py           # Application entry point with defensive programming examples
├── __init__.py       # Package initialization
tests/                # Test suite
├── unit/            # Unit tests
├── integration/     # Integration tests
├── conftest.py      # Pytest configuration
scripts/             # Development and validation scripts
├── benchmark_validation.py
├── memory_profiler.py
.sage/               # SAGE system configuration
├── MASTER_INSTRUCTION_SET.md
.cursor/rules/       # Cursor AI rules
├── master-ruleset.mdc
```

## Essential Patterns

### Pydantic Model Design

```python
class PolicyModel(BaseModel):
    model_config = ConfigDict(
        frozen=True,           # MANDATORY: Immutable by default
        extra="forbid",        # Strict validation
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True
    )

    policy_id: str = Field(..., min_length=1, max_length=50)
    premium: Decimal = Field(..., ge=0, decimal_places=2)

    @validator("policy_id")
    @classmethod
    def validate_policy_id(cls, v: str) -> str:
        # Custom business logic validation
        return v
```

### Result Type Pattern (NO EXCEPTIONS FOR CONTROL FLOW)

```python
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")

@define(frozen=True, slots=True)
class Result(Generic[T, E]):
    @classmethod
    def ok(cls, value: T) -> "Result[T, E]": ...

    @classmethod
    def err(cls, error: E) -> "Result[T, E]": ...
```

### Performance Monitoring

```python
@beartype
@performance_monitor  # Tracks memory and CPU usage
def process_policy(policy_data: dict[str, Any]) -> Result[Policy, str]:
    # Function implementation
    pass
```

## Quality Gates

The project enforces strict quality gates at different stages:

| Rule                   | Enforcement | Action          |
| ---------------------- | ----------- | --------------- |
| Pydantic Models Only   | Pre-commit  | ❌ Block commit |
| `frozen=True` Required | Pre-commit  | ❌ Block commit |
| MyPy `--strict` Mode   | Pre-commit  | ❌ Block commit |
| Performance Benchmarks | Pre-push    | ❌ Block push   |
| Memory Limit <1MB      | Pre-push    | ❌ Block push   |
| Security High Issues   | CI          | ❌ Fail build   |
| Type Coverage 100%     | CI          | ❌ Fail build   |

## Testing Strategy

- **Unit Tests**: All business logic with `@beartype` validation
- **Performance Benchmarks**: Mandatory for functions >10 lines
- **Memory Testing**: No leaks >1MB in 1000 iterations
- **Integration Tests**: End-to-end workflows
- **Property-Based Testing**: Using Hypothesis for edge cases

## Communication Style

The project follows ADHD-friendly communication principles:

- **TL;DR Summaries** at the beginning of explanations
- **Concrete Examples First** before abstract concepts
- **Progressive Disclosure** of complexity
- **Explicit Connections** between related concepts
- **Technical Accuracy** with accessible language

## Security Requirements

- **Zero tolerance** for high-severity security issues
- **Dependency scanning** with safety, pip-audit, semgrep
- **Static analysis** with bandit for vulnerability detection
- **Secret detection** with detect-secrets baseline management
- **Input validation** at all system boundaries

## Performance Requirements

- **API Response**: Sub-100ms for critical paths
- **Memory Efficiency**: <1MB temporary objects per function
- **CPU Efficiency**: O(n) operations within expected bounds
- **Benchmark Regression**: No degradation >5% between commits

## Common Pitfalls to Avoid

1. **Never use plain dictionaries** - Always use Pydantic models
2. **No `Any` types** except at system boundaries
3. **No exceptions for control flow** - Use Result types
4. **No missing `@beartype`** decorators on public functions
5. **No functions >10 lines without benchmarks**
6. **No unvalidated external input**
7. **No hardcoded secrets or configuration**

## When Working on This Codebase

1. **Always run the full test suite** before committing
2. **Check performance benchmarks** for any function changes
3. **Validate type coverage** remains at 100%
4. **Follow the SAGE workflow** for multi-component changes
5. **Refer to master ruleset** for decision-making guidance
6. **Use Result types** instead of raising exceptions
7. **Profile memory usage** for any data processing functions
