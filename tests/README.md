# Testing Framework Documentation

This directory contains the comprehensive testing infrastructure for the MVP Policy Decision Backend, built with pytest and following MASTER RULESET principles.

## Test Structure

```
tests/
├── conftest.py          # Pytest configuration and shared fixtures
├── fixtures/            # Test data factories and fixtures
│   ├── __init__.py
│   └── test_data.py     # Reusable test data and factories
├── unit/                # Unit tests
│   ├── __init__.py
│   ├── test_models.py   # Pydantic model tests
│   └── test_services.py # Service layer tests
└── integration/         # Integration tests
    ├── __init__.py
    └── test_api.py      # API endpoint tests
```

## Key Features

### 1. Comprehensive Fixtures (conftest.py)

- **Async Support**: Full async/await testing capabilities
- **Database Fixtures**: Both sync and async SQLAlchemy sessions
- **Redis Mock**: FakeRedis for cache testing
- **FastAPI Client**: Both sync and async test clients
- **Performance Thresholds**: Configurable performance benchmarks

### 2. Test Data Factory (fixtures/test_data.py)

- **Pydantic Models**: Test models with `frozen=True` compliance
- **Data Factories**: Realistic test data generation
- **Edge Cases**: Invalid and edge case data sets
- **Performance Data**: Large datasets for benchmark testing

### 3. Unit Tests

- **Model Validation**: Complete Pydantic model testing
- **Service Logic**: Business logic with Result type patterns
- **Error Handling**: Comprehensive error scenario coverage
- **Performance**: Benchmark tests for critical functions

### 4. Integration Tests

- **API Testing**: Full endpoint coverage
- **Concurrency**: Parallel request handling
- **Response Format**: Standard API response validation
- **Performance**: Sub-100ms response time verification

## Running Tests

### Basic Test Execution

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_models.py

# Run with verbose output
uv run pytest -v
```

### Test Categories

```bash
# Run only unit tests
uv run pytest tests/unit/

# Run only integration tests
uv run pytest tests/integration/

# Run benchmark tests
uv run pytest -m benchmark

# Run async tests
uv run pytest -m asyncio
```

### Performance Testing

```bash
# Run performance benchmarks
uv run pytest --benchmark-only

# Generate benchmark report
uv run pytest --benchmark-save=baseline

# Compare benchmarks
uv run pytest --benchmark-compare=baseline
```

## Writing Tests

### Model Test Example

```python
def test_policy_validation(self) -> None:
    """Test policy model validation."""
    policy = TestDataFactory.create_policy()
    assert policy.is_active
    assert policy.premium > 0
```

### Service Test Example

```python
@pytest.mark.asyncio
async def test_create_policy(self, policy_service: PolicyService) -> None:
    """Test policy creation."""
    result = await policy_service.create_policy(VALID_POLICY_DATA)
    assert result.is_ok()
```

### API Test Example

```python
@pytest.mark.asyncio
async def test_api_endpoint(self, async_test_client: AsyncClient) -> None:
    """Test API endpoint."""
    response = await async_test_client.get("/health")
    assert response.status_code == 200
```

## Test Standards

### MASTER RULESET Compliance

- All models use `frozen=True` for immutability
- No `Any` types except at system boundaries
- Result types for error handling (no exceptions for control flow)
- Performance benchmarks for functions >10 lines
- 100% type coverage requirement

### Performance Requirements

- API responses < 100ms
- Memory usage < 1MB per operation
- No performance regression > 5%
- Concurrent operation support

### Best Practices

1. Use fixtures for reusable test data
2. Test both success and failure cases
3. Include edge cases and validation errors
4. Mock external dependencies
5. Use async tests for async code
6. Benchmark critical operations

## Continuous Integration

The test suite is designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Tests
  run: |
    uv run pytest --cov=src --cov-report=xml
    uv run pytest --benchmark-only --benchmark-json=benchmark.json
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure `PYTHONPATH` includes src directory
2. **Async Warnings**: Use `pytest-asyncio` markers
3. **Database Errors**: Check test database fixtures
4. **Performance Failures**: Review benchmark thresholds

### Debug Mode

```bash
# Run with debugging
uv run pytest -vv --tb=short

# Run with pdb on failure
uv run pytest --pdb

# Run specific test with output
uv run pytest -s tests/unit/test_models.py::TestPolicyModel::test_valid_policy_creation
```
