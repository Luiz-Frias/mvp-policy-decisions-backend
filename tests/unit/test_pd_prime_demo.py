"""Tests for pd_prime_demo foundation classes."""

import pytest

from pd_prime_demo import __version__
from pd_prime_demo.main import BaseAppModel, Result


def test_version() -> None:
    """Test version is defined following MASTER RULESET security standards."""
    # Use pytest-style assertions (secure, not disabled by -O optimization)
    assert __version__ is not None, "Version should be defined"
    assert isinstance(__version__, str), (
        f"Version should be string, got {type(__version__)}"
    )


def test_result_ok() -> None:
    """Test Result.ok() creates successful result."""
    result: Result[str, str] = Result.ok("success")
    assert result.is_ok(), "Result should be ok"
    assert not result.is_err(), "Result should not be error"
    assert result.unwrap() == "success", f"Expected 'success', got {result.unwrap()}"


def test_result_err() -> None:
    """Test Result.err() creates error result."""
    result: Result[str, str] = Result.err("failure")
    assert result.is_err(), "Result should be error"
    assert not result.is_ok(), "Result should not be ok"
    assert result.unwrap_err() == "failure", (
        f"Expected 'failure', got {result.unwrap_err()}"
    )


def test_result_unwrap_panic() -> None:
    """Test Result.unwrap() panics on error result."""
    result: Result[str, str] = Result.err("failure")
    with pytest.raises(RuntimeError, match="Called unwrap\\(\\) on error result"):
        result.unwrap()


def test_result_unwrap_err_panic() -> None:
    """Test Result.unwrap_err() panics on ok result."""
    result: Result[str, str] = Result.ok("success")
    with pytest.raises(RuntimeError, match="Called unwrap_err\\(\\) on ok result"):
        result.unwrap_err()


def test_base_app_model() -> None:
    """Test BaseAppModel provides frozen Pydantic base."""

    # Create a test model that inherits from BaseAppModel
    class TestModel(BaseAppModel):
        name: str
        value: int = 42

    model = TestModel(name="test")
    assert model.name == "test", f"Expected 'test', got {model.name}"
    assert model.value == 42, f"Expected 42, got {model.value}"

    # Test that model is frozen (immutable)
    with pytest.raises(Exception):  # Pydantic ValidationError for frozen model
        model.name = "changed"


def test_base_app_model_validation() -> None:
    """Test BaseAppModel validation follows MASTER RULESET principles."""

    class TestModel(BaseAppModel):
        name: str
        age: int

    # Valid data should work
    model = TestModel(name="Alice", age=30)
    assert model.name == "Alice"
    assert model.age == 30

    # Invalid data should raise validation error
    with pytest.raises(Exception):  # Pydantic ValidationError
        TestModel(name=123, age="not_an_int")  # type: ignore[arg-type] # Wrong types should fail
