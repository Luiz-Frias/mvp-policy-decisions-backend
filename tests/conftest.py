"""Test configuration and fixtures with MASTER RULESET type safety.

This module provides pytest configuration and fixtures for the MVP Policy Decision Backend.
It includes async support, database fixtures, test client setup, and mock services.
"""

from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from beartype import beartype
from fakeredis import FakeRedis
from fastapi.testclient import TestClient
from httpx import AsyncClient
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

if TYPE_CHECKING:
    from fastapi import FastAPI

# Configure pytest-asyncio
pytest_plugins = ["pytest_asyncio"]


@pytest.fixture(scope="session")
def event_loop_policy() -> Any:
    """Configure event loop policy for asyncio."""
    import asyncio
    import sys

    if sys.platform == "win32":
        # Windows ProactorEventLoop policy
        return asyncio.WindowsProactorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture
def sample_data() -> dict[str, Any]:
    """Sample data for testing."""
    return {"key": "value", "number": 42}


@pytest.fixture
def mock_config() -> dict[str, Any]:
    """Mock configuration for testing."""
    return {
        "debug": True,
        "testing": True,
        "database_url": "sqlite+aiosqlite:///:memory:",
        "redis_url": "redis://localhost:6379/0",
        "secret_key": "test-secret-key-for-testing-only",
        "algorithm": "HS256",
        "access_token_expire_minutes": 30,
    }


@pytest.fixture
def test_database_url() -> str:
    """Test database URL for SQLite in-memory database."""
    return "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture  # type: ignore[misc]
async def async_engine(test_database_url: str) -> AsyncGenerator[Any, None]:
    """Create async SQLAlchemy engine for testing."""
    engine = create_async_engine(
        test_database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    # Import your Base model here when available
    # from pd_prime_demo.models import Base
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture  # type: ignore[misc]
async def async_session(async_engine: Any) -> AsyncGenerator[AsyncSession, None]:
    """Create async database session for testing."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    async_session_maker = async_sessionmaker(
        async_engine,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session


@pytest.fixture
def sync_engine() -> Generator[Any, None, None]:
    """Create sync SQLAlchemy engine for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    # Import your Base model here when available
    # from pd_prime_demo.models import Base
    # Base.metadata.create_all(bind=engine)

    yield engine

    engine.dispose()


@pytest.fixture
def sync_session(sync_engine: Any) -> Generator[Session, None, None]:
    """Create sync database session for testing."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest_asyncio.fixture  # type: ignore[misc]
async def mock_redis() -> AsyncGenerator[Any, None]:
    """Create mock Redis client for testing."""
    # Use fakeredis for testing
    redis_client = FakeRedis()
    yield redis_client
    # FakeRedis.close() returns None and is not awaitable
    redis_client.close()


@pytest.fixture
def mock_cache_service() -> MagicMock:
    """Create mock cache service."""
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=True)
    cache.delete = AsyncMock(return_value=True)
    cache.exists = AsyncMock(return_value=False)
    cache.expire = AsyncMock(return_value=True)
    return cache


@pytest.fixture
def mock_db() -> MagicMock:
    """Create mock database connection for testing."""
    db = MagicMock()
    db.fetchval = AsyncMock(return_value=None)
    db.fetchrow = AsyncMock(return_value=None)
    db.fetch = AsyncMock(return_value=[])
    db.execute = AsyncMock(return_value=None)
    db.executemany = AsyncMock(return_value=None)
    return db


@pytest.fixture
def mock_cache() -> MagicMock:
    """Create mock cache for testing (alias for consistency)."""
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=True)
    cache.delete = AsyncMock(return_value=True)
    cache.exists = AsyncMock(return_value=False)
    cache.expire = AsyncMock(return_value=True)
    return cache


@pytest.fixture
def test_app(mock_config: dict[str, Any], mock_redis: Any) -> "FastAPI":
    """Create FastAPI test application.

    Note: Import and create your actual app here when available.
    """
    from fastapi import FastAPI

    app = FastAPI(title="Test App")

    # Add test routes or override dependencies here
    # app.dependency_overrides[get_settings] = lambda: mock_config
    # app.dependency_overrides[get_redis] = lambda: mock_redis

    return app


@pytest.fixture
def test_client(test_app: "FastAPI") -> TestClient:
    """Create test client for FastAPI app."""
    return TestClient(test_app)


@pytest_asyncio.fixture  # type: ignore[misc]
async def async_test_client(test_app: "FastAPI") -> AsyncGenerator[AsyncClient, None]:
    """Create async test client for FastAPI app."""
    from httpx import AsyncClient
    from httpx._transports.asgi import ASGITransport

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def sample_uuid() -> UUID:
    """Generate sample UUID for testing."""
    return uuid4()


@pytest.fixture
def sample_timestamp() -> datetime:
    """Generate sample timestamp for testing."""
    return datetime.now(timezone.utc)


@pytest.fixture
def sample_policy_data() -> dict[str, Any]:
    """Sample policy data for testing."""
    return {
        "policy_id": "POL-2024-001",
        "policy_holder": "John Doe",
        "premium": "1500.50",
        "coverage_amount": "100000.00",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "status": "active",
    }


@pytest.fixture
def sample_decision_data() -> dict[str, Any]:
    """Sample decision data for testing."""
    return {
        "decision_id": str(uuid4()),
        "policy_id": "POL-2024-001",
        "decision_type": "approval",
        "confidence_score": 0.95,
        "factors": [
            {"name": "risk_score", "value": 0.3, "weight": 0.4},
            {"name": "credit_score", "value": 750, "weight": 0.3},
            {"name": "claims_history", "value": 0, "weight": 0.3},
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@beartype
class MockPydanticModel(BaseModel):
    """Mock Pydantic model for testing base model behaviors."""

    model_config = {
        "frozen": True,
        "extra": "forbid",
        "validate_assignment": True,
    }

    id: UUID
    name: str
    value: Decimal
    created_at: datetime


@pytest.fixture
def mock_model_instance() -> MockPydanticModel:
    """Create mock model instance for testing."""
    return MockPydanticModel(
        id=uuid4(),
        name="Test Model",
        value=Decimal("123.45"),
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def performance_threshold() -> dict[str, float]:
    """Provide performance thresholds for benchmark tests."""
    return {
        "max_response_time_ms": 100.0,  # 100ms max response time
        "max_memory_mb": 1.0,  # 1MB max memory per operation
        "max_cpu_percent": 80.0,  # 80% max CPU usage
    }


@pytest.fixture(autouse=True)
def reset_singletons() -> Generator[None, None, None]:
    """Reset singleton instances between tests."""
    # Add any singleton reset logic here
    yield
    # Cleanup after test


@pytest.fixture
def mock_http_client() -> MagicMock:
    """Create mock HTTP client for external API calls."""
    client = MagicMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.put = AsyncMock()
    client.delete = AsyncMock()
    return client


@pytest_asyncio.fixture  # type: ignore[misc]
async def rating_engine(mock_db: MagicMock, mock_cache: MagicMock) -> Any:
    """Create rating engine instance for testing."""
    from src.pd_prime_demo.services.rating_engine import RatingEngine
    
    # Set up mock database responses for rating data
    mock_db.fetch.return_value = [
        {
            "state": "CA",
            "product_type": "auto", 
            "coverage_type": "bodily_injury",
            "base_rate": "0.85"
        },
        {
            "state": "CA",
            "product_type": "auto",
            "coverage_type": "property_damage", 
            "base_rate": "0.65"
        },
        {
            "state": "CA",
            "product_type": "auto",
            "coverage_type": "comprehensive",
            "base_rate": "0.45"
        },
        {
            "state": "CA",
            "product_type": "auto",
            "coverage_type": "collision",
            "base_rate": "0.55"
        },
    ]
    
    # Mock state rules data
    mock_db.fetchrow.side_effect = [
        {"minimum_premium": "500.00"},  # Minimum premium
        {"policy_count": 0},            # Customer policy count
        {"first_policy_date": None},    # Customer tenure
        {"lapse_count": 0},             # Coverage lapse check
        {"claim_count": 0},             # Claims history
    ]
    
    engine = RatingEngine(mock_db, mock_cache)
    
    # Initialize with mock data
    await engine.initialize()
    
    return engine
