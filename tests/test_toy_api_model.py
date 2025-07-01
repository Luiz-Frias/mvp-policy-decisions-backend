"""Tests for toy_api_model with performance benchmarks."""

import tracemalloc
from typing import Any

import pytest

from toy_api_model import __version__
from toy_api_model.main import PersonModel, safe_greet_person


def test_version() -> None:
    """Test version is defined following MASTER RULESET security standards."""
    # Use pytest-style assertions (secure, not disabled by -O optimization)
    assert __version__ is not None, "Version should be defined"
    assert isinstance(
        __version__, str
    ), f"Version should be string, got {type(__version__)}"


def test_safe_greet_person_success() -> None:
    """Test successful greeting with valid data."""
    result = safe_greet_person({"name": "Alice", "age": 30})
    assert (
        result.is_ok()
    ), f"Expected success, got error: {result._error if not result.is_ok() else None}"
    greeting = result.unwrap()
    assert "Alice" in greeting, f"Expected 'Alice' in greeting '{greeting}'"


def test_safe_greet_person_validation_error() -> None:
    """Test greeting with invalid data."""
    result = safe_greet_person({"name": "", "age": -5})
    assert not result.is_ok(), "Expected validation error for invalid data"
    error_msg = str(result._error).lower()
    assert "error" in error_msg, f"Expected error message, got: {result._error}"


def test_pydantic_model_validation() -> None:
    """Test Pydantic model validation with MASTER RULESET principles."""
    # Valid data - should succeed
    person = PersonModel(name="John Doe", age=25, email="john@example.com")
    assert person.name == "John Doe", f"Expected 'John Doe', got '{person.name}'"
    assert person.age == 25, f"Expected age 25, got {person.age}"

    # Invalid data should raise validation error - test defensive programming
    with pytest.raises(Exception, match="validation|value"):
        PersonModel(name="", age=-1, email="invalid@test.com")


# Performance benchmarks with MASTER RULESET security compliance
@pytest.mark.benchmark
def test_greeting_performance(benchmark: Any) -> None:
    """Benchmark greeting function performance with security-compliant assertions."""
    test_data = {"name": "Alice", "age": 30, "email": "alice@example.com"}

    result = benchmark(safe_greet_person, test_data)
    assert (
        result.is_ok()
    ), f"Performance test failed: {result._error if not result.is_ok() else None}"


@pytest.mark.benchmark
def test_pydantic_validation_performance(benchmark: Any) -> None:
    """Benchmark Pydantic validation performance with proper error context."""
    test_data = {"name": "John Doe", "age": 25, "email": "john@example.com"}

    result = benchmark(PersonModel, **test_data)
    assert result.name == "John Doe", f"Expected 'John Doe', got '{result.name}'"


@pytest.mark.benchmark(group="memory")
def test_memory_usage() -> None:
    """Test memory usage with MASTER RULESET quality gates."""
    tracemalloc.start()

    # Test with multiple greetings - PERFORMANCE QUALITY GATE
    test_people = [
        {"name": f"Person{i}", "age": 25 + i, "email": f"person{i}@example.com"}
        for i in range(1000)
    ]

    results = [safe_greet_person(person) for person in test_people]

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # MASTER RULESET: Verify all operations succeeded (defensive programming)
    successful_greetings = sum(1 for r in results if r.is_ok())
    assert (
        successful_greetings == 1000
    ), f"Expected 1000 successful greetings, got {successful_greetings}"

    # MASTER RULESET: Memory allocation limit enforcement (<10MB per function)
    max_memory_mb = 10 * 1024 * 1024
    assert peak < max_memory_mb, f"Memory limit exceeded: {peak/1024/1024:.2f}MB > 10MB"

    # Performance metrics logging
    print(f"✅ PERFORMANCE: Current={current/1024:.2f}KB, Peak={peak/1024:.2f}KB")
