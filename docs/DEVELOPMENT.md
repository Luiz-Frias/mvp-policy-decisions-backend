# Development Guide

## Prerequisites

### Required Software

- **Python 3.11+**: Required for modern async features and performance
- **uv**: Rust-based Python package manager for fast dependency resolution
- **PostgreSQL 14+**: Primary database
- **Redis 7+**: Caching and session storage
- **Docker & Docker Compose**: For containerized development
- **Git**: Version control

### Recommended Tools

- **VS Code** or **PyCharm**: IDE with Python support
- **HTTPie** or **Postman**: API testing
- **pgAdmin** or **DBeaver**: Database management
- **Redis Insight**: Redis GUI

## Setting Up Development Environment

### 1. Clone Repository

```bash
git clone https://github.com/username/mvp-policy-decision-backend.git
cd mvp-policy-decision-backend
```

### 2. Install uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 3. Create Virtual Environment

```bash
# uv automatically creates and manages virtual environment
uv sync --dev
```

### 4. Environment Configuration

Create `.env` file in project root:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Application
APP_NAME=MVP Policy Decision Backend
APP_ENV=development
DEBUG=true
LOG_LEVEL=DEBUG

# API
API_HOST=0.0.0.0
API_PORT=8000
API_PREFIX=/api/v1

# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/policy_db
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=0

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=

# Security
SECRET_KEY=$(openssl rand -hex 32)  # Generate secure key automatically
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=60

# AI Service
AI_SERVICE_URL=http://localhost:8001
AI_SERVICE_API_KEY=${AI_SERVICE_API_KEY:-dev-placeholder}  # Use environment variable

# Performance
ENABLE_PROFILING=true
BENCHMARK_THRESHOLD_MS=100
MEMORY_LIMIT_MB=1024
```

### 5. Database Setup

#### Using Docker:

```bash
# Start PostgreSQL and Redis
docker-compose up -d postgres redis

# Wait for services to be ready
docker-compose ps
```

#### Manual Installation:

```bash
# PostgreSQL
sudo apt-get install postgresql-14
sudo -u postgres createdb policy_db
sudo -u postgres createuser --interactive

# Redis
sudo apt-get install redis-server
sudo systemctl start redis-server
```

### 6. Run Database Migrations

```bash
# Create initial tables
uv run alembic upgrade head

# Create new migration
uv run alembic revision --autogenerate -m "Add new table"
```

### 7. Load Development Data

```bash
# Load sample data
uv run python scripts/load_dev_data.py
```

## Development Workflow

### 1. Starting the Development Server

```bash
# Run with auto-reload
uv run uvicorn src.pd_prime_demo.main:app --reload --host 0.0.0.0 --port 8000

# Or use the Makefile
make run-dev
```

### 2. Running Tests

```bash
# Run all tests
make test

# Run specific test file
uv run pytest tests/unit/test_policy_service.py

# Run with coverage
make test-cov

# Run only unit tests
uv run pytest tests/unit/

# Run only integration tests
uv run pytest tests/integration/

# Run with verbose output
uv run pytest -vv

# Run tests matching pattern
uv run pytest -k "test_policy"
```

### 3. Code Quality Checks

```bash
# Format code
make format

# Check formatting
make format-check

# Run linters
make lint

# Type checking
uv run mypy src

# Security scan
uv run bandit -r src

# Check for vulnerabilities
uv run safety check
uv run pip-audit
```

### 4. Performance Testing

```bash
# Run benchmarks
uv run pytest tests/benchmarks/ --benchmark-only

# Memory profiling
uv run python -m memray run --output profile.bin src/pd_prime_demo/main.py
uv run python -m memray flamegraph profile.bin

# CPU profiling
py-spy record -o profile.svg -- python src/pd_prime_demo/main.py
```

## Project Structure

```
mvp-policy-decision-backend/
├── src/
│   └── pd_prime_demo/
│       ├── __init__.py
│       ├── main.py                 # FastAPI app entry point
│       ├── api/
│       │   ├── __init__.py
│       │   ├── deps.py            # Dependencies (auth, db)
│       │   └── v1/
│       │       ├── __init__.py
│       │       ├── endpoints/
│       │       │   ├── policies.py
│       │       │   ├── quotes.py
│       │       │   └── rates.py
│       │       └── router.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py         # Settings management
│       │   ├── database.py       # Database connection
│       │   ├── security.py        # Auth utilities
│       │   └── cache.py          # Cache implementation
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── models/           # Domain models
│       │   ├── services/         # Business logic
│       │   └── repositories/     # Data access interfaces
│       ├── infrastructure/
│       │   ├── __init__.py
│       │   ├── database/         # DB implementations
│       │   └── external/         # External services
│       └── utils/
│           ├── __init__.py
│           └── validators.py     # Custom validators
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Pytest fixtures
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   └── benchmarks/              # Performance tests
├── scripts/
│   ├── benchmark_validation.py
│   ├── memory_profiler.py
│   └── load_dev_data.py
├── alembic/                     # Database migrations
│   ├── versions/
│   └── alembic.ini
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
└── docs/                        # Documentation
```

## Coding Standards

### Python Style Guide

Follow PEP 8 with these additions:

1. **Type Hints Required**

   ```python
   # Good
   def calculate_premium(policy: Policy) -> Decimal:
       pass

   # Bad
   def calculate_premium(policy):
       pass
   ```

2. **Pydantic Models**

   ```python
   from pydantic import BaseModel, Field
   from decimal import Decimal

   class PolicyCreate(BaseModel):
       model_config = ConfigDict(
           frozen=True,  # REQUIRED: Immutability
           str_strip_whitespace=True,
           validate_default=True
       )

       policy_type: PolicyType
       premium: Decimal = Field(..., ge=0, decimal_places=2)
   ```

3. **Beartype Decorators**

   ```python
   from beartype import beartype

   @beartype
   def process_quote(quote_data: dict[str, Any]) -> Result[Quote, QuoteError]:
       # Implementation
       pass
   ```

4. **Result Types**
   ```python
   # Use Result types instead of exceptions
   result = calculate_rate(data)
   match result:
       case Ok(rate):
           return {"rate": rate}
       case Err(error):
           return {"error": str(error)}
   ```

### Git Workflow

1. **Branch Naming**

   ```
   feature/add-quote-generation
   fix/policy-calculation-error
   refactor/optimize-rate-engine
   docs/update-api-documentation
   ```

2. **Commit Messages**

   ```
   feat: add quote generation endpoint
   fix: correct premium calculation for multi-car policies
   refactor: optimize database queries in policy service
   docs: update API documentation for v1.2
   test: add unit tests for underwriting service
   perf: improve rate calculation performance by 30%
   ```

3. **Pull Request Process**

   ```bash
   # Create feature branch
   git checkout -b feature/new-feature

   # Make changes and commit
   git add .
   git commit -m "feat: add new feature"

   # Push and create PR
   git push origin feature/new-feature
   gh pr create --title "feat: Add new feature" --body "Description..."
   ```

## Common Development Tasks

### Adding a New Endpoint

1. **Define Pydantic Models**

   ```python
   # src/pd_prime_demo/api/v1/schemas/policy.py
   class PolicyCreate(BaseModel):
       model_config = ConfigDict(frozen=True)

       policy_type: PolicyType
       effective_date: date
       coverage: CoverageSchema
   ```

2. **Create Endpoint**

   ```python
   # src/pd_prime_demo/api/v1/endpoints/policies.py
   @router.post("/", response_model=PolicyResponse)
   @beartype
   async def create_policy(
       policy_data: PolicyCreate,
       db: AsyncSession = Depends(get_db),
       current_user: User = Depends(get_current_user)
   ) -> PolicyResponse:
       result = await policy_service.create_policy(db, policy_data, current_user)
       match result:
           case Ok(policy):
               return PolicyResponse.from_orm(policy)
           case Err(error):
               raise HTTPException(status_code=400, detail=str(error))
   ```

3. **Add Tests**
   ```python
   # tests/unit/test_policy_endpoint.py
   @pytest.mark.asyncio
   async def test_create_policy_success(client: AsyncClient):
       response = await client.post(
           "/api/v1/policies",
           json={"policy_type": "auto", "effective_date": "2024-01-01"}
       )
       assert response.status_code == 201
       assert response.json()["policy_number"]
   ```

### Adding a New Service

1. **Define Service Interface**

   ```python
   # src/pd_prime_demo/domain/services/interfaces.py
   class PolicyServiceInterface(Protocol):
       async def create_policy(
           self, db: AsyncSession, data: PolicyCreate, user: User
       ) -> Result[Policy, PolicyError]:
           ...
   ```

2. **Implement Service**
   ```python
   # src/pd_prime_demo/domain/services/policy_service.py
   class PolicyService:
       @beartype
       async def create_policy(
           self, db: AsyncSession, data: PolicyCreate, user: User
       ) -> Result[Policy, PolicyError]:
           # Validate business rules
           # Calculate premium
           # Save to database
           # Return result
   ```

### Database Migrations

```bash
# Create migration after model changes
uv run alembic revision --autogenerate -m "Add policy_endorsements table"

# Review generated migration
cat alembic/versions/latest_*.py

# Apply migration
uv run alembic upgrade head

# Rollback if needed
uv run alembic downgrade -1
```

## Debugging

### VS Code Configuration

`.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["src.pd_prime_demo.main:app", "--reload"],
      "jinja": true,
      "justMyCode": false
    }
  ]
}
```

### Common Issues

1. **Import Errors**

   ```bash
   # Ensure PYTHONPATH includes src
   export PYTHONPATH="${PYTHONPATH}:${PWD}/src"
   ```

2. **Database Connection**

   ```bash
   # Check PostgreSQL is running
   docker-compose ps

   # Check connection
   psql postgresql://postgres:password@localhost:5432/policy_db
   ```

3. **Type Checking Errors**

   ```bash
   # Generate type stubs
   uv run mypy --install-types

   # Ignore specific error
   # type: ignore[specific-error]
   ```

## Performance Optimization

### Profiling Code

```python
# Add performance monitoring decorator
from src.pd_prime_demo.utils.monitoring import performance_monitor

@performance_monitor
@beartype
async def expensive_operation(data: ComplexData) -> Result:
    # Code to profile
    pass
```

### Database Optimization

1. **Use Select N+1 Prevention**

   ```python
   # Bad
   policies = await db.execute(select(Policy))
   for policy in policies:
       claims = await db.execute(
           select(Claim).where(Claim.policy_id == policy.id)
       )

   # Good
   policies = await db.execute(
       select(Policy).options(selectinload(Policy.claims))
   )
   ```

2. **Add Indexes**
   ```python
   # In model definition
   __table_args__ = (
       Index('idx_policy_number', 'policy_number'),
       Index('idx_effective_date', 'effective_date'),
   )
   ```

## Continuous Integration

### Pre-commit Hooks

```bash
# Install pre-commit
uv run pre-commit install

# Run manually
uv run pre-commit run --all-files
```

### GitHub Actions

Automated checks on every push:

- Type checking with mypy
- Linting with flake8, black, isort
- Security scanning with bandit, safety
- Unit and integration tests
- Performance benchmarks
- Code coverage reporting

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Project Wiki](https://github.com/username/mvp-policy-decision-backend/wiki)
- [API Playground](http://localhost:8000/docs)
