"""Test configuration and fixtures with MASTER RULESET type safety."""

# Type hint for pytest fixtures to resolve mypy decorator errors
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    pass


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
        "database_url": "sqlite:///:memory:",
    }
