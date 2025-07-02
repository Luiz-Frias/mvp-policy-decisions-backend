"""Tests for pd_prime_demo foundation classes."""

import pytest

from pd_prime_demo import __version__
from pd_prime_demo.models.base import BaseModelConfig
from pd_prime_demo.services.result import Err, Ok, Result


def test_version() -> None:
    """Test version is defined following MASTER RULESET security standards."""
    # Use pytest-style assertions (secure, not disabled by -O optimization)
    assert __version__ is not None, "Version should be defined"
    assert isinstance(__version__, str), (
        f"Version should be string, got {type(__version__)}"
    )


def test_result_ok() -> None:
    """Test Ok() creates successful result."""
    result: Result[str, str] = Ok("success")
    assert result.is_ok(), "Result should be ok"
    assert not result.is_err(), "Result should not be error"
    assert result.unwrap() == "success", f"Expected 'success', got {result.unwrap()}"


def test_result_err() -> None:
    """Test Err() creates error result."""
    result: Result[str, str] = Err("failure")
    assert result.is_err(), "Result should be error"
    assert not result.is_ok(), "Result should not be ok"
    assert result.unwrap_err() == "failure", (
        f"Expected 'failure', got {result.unwrap_err()}"
    )


def test_result_unwrap_panic() -> None:
    """Test Result.unwrap() panics on error result."""
    result: Result[str, str] = Err("failure")
    with pytest.raises(ValueError, match="Called unwrap on Err value"):
        result.unwrap()


def test_result_unwrap_err_panic() -> None:
    """Test Result.unwrap_err() panics on ok result."""
    result: Result[str, str] = Ok("success")
    with pytest.raises(ValueError, match="Called unwrap_err on Ok value"):
        result.unwrap_err()


def test_base_app_model() -> None:
    """Test BaseModelConfig provides frozen Pydantic base."""

    # Create a test model that inherits from BaseModelConfig
    class TestModel(BaseModelConfig):
        name: str
        value: int = 42

    model = TestModel(name="test")
    assert model.name == "test", f"Expected 'test', got {model.name}"
    assert model.value == 42, f"Expected 42, got {model.value}"

    # Test that model is frozen (immutable)
    with pytest.raises(Exception):  # Pydantic ValidationError for frozen model
        model.name = "changed"


def test_base_app_model_validation() -> None:
    """Test BaseModelConfig validation follows MASTER RULESET principles."""

    class TestModel(BaseModelConfig):
        name: str
        age: int

    # Valid data should work
    model = TestModel(name="Alice", age=30)
    assert model.name == "Alice"
    assert model.age == 30

    # Invalid data should raise validation error
    with pytest.raises(Exception):  # Pydantic ValidationError
        invalid_name: object = 123
        invalid_age: object = "not_an_int"
        TestModel(name=invalid_name, age=invalid_age)
