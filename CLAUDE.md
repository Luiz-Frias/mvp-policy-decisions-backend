# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

PRE-WAVE 2.5 DEPLOYMENT:

# TODO: integrate last wave 2 implementation learnings into the right locations within .sage/ (learned_patterns.json in root vs in .sage/core/registry/)+(.sage/{reusable_components_guide.md, wave_2_best_practices.md} in the right docs or .sage/languages/python/{guardrails/, patterns/, templates/})

# TODO: Move all core/communication/messages/\*.md into .sage/core/communication/history/ if you believe thats where it should go. Else leave for now and relay you're reasoning why it needs a different location.

# TODO: supervising agent to review and pull coderabbit.ai comments from the extension in Cursor's IDE and integrate every single comment (I insist) into the full implementation of wave 2.

# TODO: run pre-commit run --all-files to identify what's broken and what needs fixing in addition to the rest of the above as part 2 of wave 2's implementation!

# TODO: supervising agent (you) to read all \*.py files in scripts/ to then relay to agents what's currently available so that no duplicate work is implemented.

AT WAVE 2.5 DEPLOYMENT TIME:

# TODO: Update CLAUDE.md with FULL context to be able to 'pick up the pen' in a hand-off type way.

# TODO: Instruct the agents to come to you as the acting git commit manager (I strongly insist that no --no-verify commands are added to commits). Context: we faced git locks in wave 2 as a result of the pre-commits running. If you have a way to solve for this, bring this solution up during pre-deployment.

# TODO: have agents read master-ruleset, read their instructions and all doc references, audit the implementation of their domain/scope, idenitfy what left to be implemented for full production grade enterprise level system implementation. No DEMO level code generation. This IS the real thing.

POST WAVE 2.5 DEPLOYMENT:

# TODO: Implement proper logging instead of print across codebase, not just patches.

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

## Wave 1 Implementation Status (Current State)

### Completed ✅ (80% Foundation Achieved)

- **Core Infrastructure**: Database (asyncpg), Redis cache, JWT auth, config management
- **Domain Models**: Complete with frozen=True, validation, and business rules
- **API Layer**: Full REST endpoints for policies, customers, claims, health
- **Type Safety**: 100% beartype coverage, Result types, no Any types
- **Code Quality**: Passes all master ruleset validations

### Critical Gaps ❌ (Blocking Demo)

1. **Quote Generation System** - PRIMARY demo feature not implemented
2. **Rating/Pricing Engine** - No rate tables or pricing calculations
3. **Database Integration** - All services return mock data only
4. **AI Features** - Config exists but no OpenAI integration
5. **Real-time Updates** - No WebSocket implementation
6. **Deployment** - Railway/Doppler configured but not tested

### Test Coverage

- ✅ Unit tests: Models, schemas, core functionality
- ⚠️ Integration tests: 67% passing (DB tests skipped)
- ❌ Performance benchmarks: Infrastructure exists, no implementations
- ❌ Load/security testing: Not implemented

## Wave 2: Full Production System Implementation (90% Build)

**Mission**: Build a COMPLETE production-ready insurance platform demonstrating SAGE's ability to create enterprise software. This is NOT a simple demo - we are building a ROCKETSHIP as requested.

### Scope: FULL Implementation

**The ONLY excluded feature**: AI document processing. **ALL other features MUST be implemented**.

### Core Systems to Build

#### 1. Complete Quote Generation System

- **Multi-Step Quote Wizard**
  - Customer information collection
  - Vehicle/property details with VIN decoding
  - Coverage selection with real-time pricing
  - Driver history and credit check integration
  - Document upload and verification
- **Quote Management**
  - Quote versioning and comparison
  - Quote-to-policy conversion workflow
  - Automated expiration and follow-up
  - Quote sharing and collaboration
  - A/B testing for conversion optimization

#### 2. Full Production Rating Engine

- **Comprehensive Rating Factors**
  - Base rates by state/territory/ZIP
  - Vehicle factors (year/make/model/trim/safety)
  - Driver factors (age/experience/violations/claims)
  - Credit-based insurance scores
  - Usage-based insurance (UBI) factors
  - Multi-policy and household considerations
- **Advanced Pricing Features**
  - Real-time competitive rate analysis
  - Dynamic pricing based on market conditions
  - Discount stacking and optimization
  - Surcharge calculations and justifications
  - Rate experimentation framework
- **State-Specific Compliance**
  - California Proposition 103 rules
  - State-mandated coverages
  - Filing compliance tracking

#### 3. WebSocket Real-Time Infrastructure

- **Quote Real-Time Features**
  - Live premium updates as user makes selections
  - Collaborative quote editing for agents/customers
  - Real-time availability of coverages
  - Instant competitor rate comparisons
- **Analytics Dashboard**
  - Live conversion funnel metrics
  - Real-time quote-to-bind ratios
  - Agent performance tracking
  - Geographic heat maps of quotes
- **Notification System**
  - Push notifications for quote expiration
  - Real-time alerts for special offers
  - Agent assignment notifications
  - System-wide announcements

#### 4. Enterprise Security Architecture

- **Single Sign-On (SSO)**
  - Google Workspace integration
  - Microsoft Azure AD support
  - Okta SAML/OIDC integration
  - Auth0 universal login
  - Custom SSO provider framework
- **OAuth2 Authorization Server**
  - Full RFC 6749 implementation
  - JWT with refresh tokens
  - Scope-based permissions
  - API key management for partners
  - Rate limiting per client
- **Multi-Factor Authentication**
  - TOTP (Google Authenticator compatible)
  - WebAuthn/FIDO2 support
  - SMS backup (with anti-SIM swap)
  - Biometric authentication
  - Risk-based authentication
- **Zero-Trust Architecture**
  - Service mesh with mTLS
  - Policy-based access control
  - Continuous verification
  - Least privilege enforcement

#### 5. SOC 2 Type II Compliance Implementation

- **Security Controls**
  - Encryption at rest (AES-256)
  - Encryption in transit (TLS 1.3)
  - Key management with HSM
  - Vulnerability scanning automation
  - Penetration testing framework
- **Availability Controls**
  - 99.9% uptime SLA monitoring
  - Automated failover
  - Disaster recovery procedures
  - Multi-region deployment
  - Chaos engineering tests
- **Processing Integrity**
  - Data validation at every layer
  - Automated reconciliation
  - Change control processes
  - Deployment audit trails
- **Confidentiality Controls**
  - Data classification system
  - Access control matrices
  - Data retention policies
  - Secure data disposal
- **Privacy Controls**
  - GDPR compliance engine
  - CCPA rights management
  - Consent management platform
  - Data portability APIs
  - Right to deletion workflows

#### 6. Performance & Scale Architecture

- **Caching Strategy**
  - Redis for hot data (quotes, rates)
  - PostgreSQL materialized views
  - CDN for static assets
  - Application-level caching
  - Cache warming strategies
- **Database Optimization**
  - Connection pooling with pgBouncer
  - Read replicas for reporting
  - Partitioning for large tables
  - Query optimization with EXPLAIN
  - Automated index recommendations
- **Horizontal Scaling**
  - Kubernetes deployment ready
  - Auto-scaling policies
  - Load balancer configuration
  - Session affinity for WebSockets
  - Graceful shutdown handling

### Implementation Timeline (14 Days)

**Days 1-2: Foundation Fixes**

- Fix all Wave 1 TODOs and database integration
- Implement proper connection pooling
- Add missing database tables
- Verify all CRUD operations work

**Days 3-4: Quote System Core**

- Multi-step quote wizard backend
- Quote persistence and retrieval
- Quote versioning system
- Basic quote-to-policy conversion

**Days 5-6: Full Rating Engine**

- Complete rate table structure
- All rating factors implementation
- State-specific rules engine
- Performance optimization for <50ms calculations

**Days 7-8: Real-Time WebSocket**

- WebSocket infrastructure setup
- Real-time quote updates
- Analytics dashboard streaming
- Notification system

**Days 9-10: Enterprise Security**

- SSO provider integrations
- OAuth2 server implementation
- MFA system setup
- Zero-trust policies

**Days 11-12: SOC 2 Compliance**

- Audit logging system
- Encryption implementation
- Compliance reporting
- Privacy controls

**Days 13-14: Performance & Deploy**

- Load testing and optimization
- Caching implementation
- Production deployment
- Final integration testing

### Success Metrics

- **Performance**: All API calls <100ms (p99)
- **Scale**: Support 10,000 concurrent users
- **Security**: Pass security audit
- **Compliance**: SOC 2 ready
- **Quality**: 95% test coverage
- **Reliability**: 99.9% uptime

## Wave 2 Agent Deployment Instructions

### Pre-Deployment Checklist

```bash
# 1. Verify environment
uv sync --dev
uv run pre-commit install

# 2. Validate current state
./scripts/validate-master-ruleset.sh
uv run pytest tests/

# 3. Check Wave 1 status
git status
git log --oneline -10
```

### Agent Deployment Strategy

Deploy agents in parallel groups for maximum efficiency:

**Group 1: Foundation (Days 1-2)**

- Agent 1: Database Migration Specialist - Create all new tables
- Agent 2: Service Integration Specialist - Fix all Wave 1 TODOs
- Agent 3: Connection Pool Specialist - Optimize database performance

**Group 2: Core Features (Days 3-6)**

- Agent 4: Quote Model Builder - Create comprehensive quote models
- Agent 5: Quote Service Developer - Implement quote business logic
- Agent 6: Rating Engine Architect - Build full rating system
- Agent 7: Rating Calculator - Implement all pricing factors

**Group 3: Real-Time & Security (Days 7-10)**

- Agent 8: WebSocket Engineer - Build real-time infrastructure
- Agent 9: SSO Integration Specialist - Implement all SSO providers
- Agent 10: OAuth2 Server Developer - Build authorization server
- Agent 11: MFA Implementation Expert - Add all MFA methods

**Group 4: Compliance & Performance (Days 11-14)**

- Agent 12: SOC 2 Compliance Engineer - Implement all controls
- Agent 13: Performance Optimization Expert - Ensure <100ms responses
- Agent 14: Deployment Specialist - Production deployment
- Agent 15: Integration Test Master - End-to-end testing

### SAGE Communication Protocol

All agents must follow the SAGE communication protocol:

1. Write status updates to `core/communication/message-queue/`
2. Check for inter-agent messages every 30 minutes
3. Report blockers immediately in conflict log
4. Update progress in wave context files

### Success Validation

After Wave 2 completion:

```bash
# Run full test suite
uv run pytest tests/ -v

# Check performance benchmarks
uv run pytest -m benchmark

# Validate type coverage
uv run mypy --html-report type-coverage src/

# Security scan
uv run bandit -r src/

# Deploy to staging
./scripts/deploy-staging.sh
```

Remember: We're building a ROCKETSHIP, not a paper airplane. Every feature must be production-ready.
