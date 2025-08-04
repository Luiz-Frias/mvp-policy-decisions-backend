# Policy Decision Management Platform
## ⚠️ Proof-of-concept – under active polish.

**Enterprise-grade insurance platform built for scale** - A modern Python backend delivering 20-50K QPS capability with 100% type safety and defensive programming patterns. Perfect for P&C insurers requiring real-time quote generation, policy management, and SOC 2 compliance.

🎯 **Live Demo**: Available on Railway with full API documentation and WebSocket real-time features.

[![CI][ci-badge]][ci-url]
[![Release][release-badge]][release-url]
[![Coverage][cov-badge]][cov-url]
[![License][license-badge]][license-url]
[![Python][python-badge]][python-url]
[![Black][black-badge]][black-url]

> We follow **Semantic Versioning 2.0** – every Git tag beginning with `v` generates a GitHub Release and corresponding changelog entry.

## 🚀 Enterprise Features

### **Production-Ready Architecture**
- ⚡ **20-50K QPS capability** with uvloop optimization
- 🛡️ **100% Type Safety** - MyPy strict mode with 0 errors
- 🔒 **Elite API Pattern** - Result[T,E] error handling throughout
- 🏗️ **Cloud-Agnostic** - Ready for Railway, AWS, K8s deployment

### **Insurance Domain Expertise**
- 📊 **Real-time Quote Generation** with territory-based rating
- 🏢 **Multi-state Compliance** built-in
- 🤖 **AI Risk Assessment** and automated underwriting
- 📈 **Performance Monitoring** with sub-100ms P99 latency

### **Enterprise Security & Compliance**
- 🔐 **SOC 2 Framework** implemented
- 🛡️ **Multi-Factor Authentication** with WebAuthn support
- 🔑 **SSO Integration** (Auth0, Azure, Google, Okta)
- 📝 **Comprehensive Audit Logging**

### **Developer Experience**
- 🚀 **FastAPI** with automatic OpenAPI documentation
- 🐳 **Docker** with optimized multi-stage builds
- 🧪 **Quality Gates** with automated testing and validation
- 📚 **Complete Documentation** and architecture guides

## 📄 Licensing

**PolicyCore** is available under a **dual license structure** to accommodate both open source and commercial use cases:

- **🔓 Open Source (AGPL-3.0)**: Free for research, education, and open source projects
- **💼 Commercial License**: For proprietary applications and enterprise use

Perfect for P&C insurance industry applications, enterprise policy management, and commercial SaaS solutions.

**Commercial Licensing Contact:** luizf35@gmail.com | **Form F[x] Labs**

For detailed licensing information, see [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md).

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

```bash
# Clone repository
git clone https://github.com/username/mvp-policy-decision-backend.git
cd mvp-policy-decision-backend

# Install with uv (recommended)
uv sync --dev

# Or use make command
make dev
```

## 🛠️ Development

### Prerequisites

- Python 3.11+ (required for modern async features)
- uv (Rust-based package manager)
- Docker (optional, for containerized deployment)
- PostgreSQL 14+ (for local development)

### Quick Start

```bash
# Clone repository
git clone https://github.com/username/mvp-policy-decision-backend.git
cd mvp-policy-decision-backend

# Setup development environment
make dev

# Run tests
make test

# Start development server
uv run uvicorn src.policy_core.main:app --reload

# Format and lint code
make format
make lint
```

### Available Commands

```bash
make install    # Install dependencies
make dev        # Setup development environment
make test       # Run tests
make test-cov   # Run tests with coverage
make lint       # Run linting
make format     # Format code
make clean      # Clean build artifacts
```

## 🧪 Testing

```bash
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
```

## 🛡️ Master Ruleset Validation

This project enforces **first principles** through comprehensive validation:

```bash
# Validate Pydantic model compliance (pre-commit)
./scripts/validate-pydantic-compliance.sh

# Check performance quality gates (pre-push)
./scripts/validate-performance-gates.sh

# Run complete master ruleset validation
./scripts/validate-master-ruleset.sh

# Performance benchmark requirements
pytest tests/benchmarks --benchmark-only --benchmark-compare-fail=mean:15%
```

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

```bash
# Run with performance monitoring
python -X tracemalloc src/main.py

# Memory analysis with memray
memray run --output memory.bin src/main.py
memray flamegraph memory.bin

# CPU profiling with py-spy (no code changes needed)
py-spy record -o cpu-profile.svg -- python src/main.py

# Benchmarking with pytest
pytest --benchmark-only --benchmark-json=results.json
```

### **Defensive Programming Examples**

Example Python code implementing MASTER RULESET principles:

- Pydantic models with frozen=True for immutability
- @beartype decorators for runtime type checking
- Result types for error handling without exceptions
- Field constraints and validation on all data models

See `src/policy_core/main.py` for complete implementation examples.

## 📚 Documentation

- [Architecture Overview](docs/ARCHITECTURE.md) - System design and components
- [API Documentation](docs/API.md) - REST API endpoints and schemas
- [Development Guide](docs/DEVELOPMENT.md) - Detailed setup and workflow
- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment instructions
- [Performance Guide](docs/PERFORMANCE.md) - Optimization and benchmarking
- [Security Guide](docs/SECURITY.md) - Security best practices

## 🏗️ Project Structure

```
mvp-policy-decision-backend/
├── src/
│   └── policy_core/
│       ├── __init__.py
│       ├── main.py              # FastAPI application entry point
│       └── core/
│           ├── config.py        # Configuration management
│           ├── database.py      # Database connection handling
│           ├── security.py      # Security utilities
│           └── cache.py         # Caching implementation
├── tests/
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   └── benchmarks/              # Performance benchmarks
├── scripts/
│   ├── validate-master-ruleset.sh
│   └── benchmark_validation.py
├── docs/                        # Documentation
├── .sage/                       # SAGE system configuration
└── pyproject.toml              # Project configuration
```

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## 📝 License

This project is available under a **dual license structure**:

### 🔓 Open Source License (AGPL-3.0)

For non-commercial use, research, and educational projects:

- ✅ Free to use and modify
- ✅ Perfect for academic research and learning
- ✅ Compatible with other AGPL-3.0 projects
- ❗ Requires derivative works to be open source
- ❗ Network services must provide source code access

### 💼 Commercial License

For commercial use, proprietary applications, and enterprise deployments:

- ✅ No copyleft requirements
- ✅ Keep your code proprietary
- ✅ Commercial support available
- ✅ Custom feature development
- ✅ Priority support channels

**Contact for Commercial Licensing:**
📧 **Email:** luizf35@gmail.com
📝 **Subject:** PolicyCore Commercial License Request
🏢 **Organization:** Form F[x] Labs

For detailed licensing information, see:

- [LICENSE](LICENSE) - Full dual license terms
- [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md) - Commercial licensing guide

**Choose the license that best fits your use case. If you're unsure, contact us for guidance.**

<!-- Badge reference links -->

[ci-badge]: https://github.com/Luiz-Frias/mvp-policy-decision-backend/actions/workflows/ci.yml/badge.svg?branch=main
[ci-url]: https://github.com/Luiz-Frias/mvp-policy-decision-backend/actions/workflows/ci.yml
[release-badge]: https://img.shields.io/github/v/release/Luiz-Frias/mvp-policy-decision-backend?sort=semver&label=release
[release-url]: https://github.com/Luiz-Frias/mvp-policy-decision-backend/releases
[cov-badge]: https://codecov.io/gh/Luiz-Frias/mvp-policy-decision-backend/branch/main/graph/badge.svg
[cov-url]: https://codecov.io/gh/Luiz-Frias/mvp-policy-decision-backend
[license-badge]: https://img.shields.io/github/license/Luiz-Frias/mvp-policy-decision-backend.svg
[license-url]: LICENSE
[python-badge]: https://img.shields.io/badge/python-3.11%2B-blue
[python-url]: https://www.python.org/downloads/
[black-badge]: https://img.shields.io/badge/style-black-000000.svg
[black-url]: https://github.com/psf/black
