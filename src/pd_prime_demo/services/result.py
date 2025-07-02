"""Result type implementation for error handling without exceptions."""

from collections.abc import Callable
from typing import Any, Generic, TypeVar, Union

from attrs import field, frozen
from beartype import beartype

T = TypeVar("T")
E = TypeVar("E")
U = TypeVar("U")


@frozen
class Ok(Generic[T]):
    """Successful result container."""

    value: T = field()

    @beartype
    def is_ok(self) -> bool:
        """Check if result is Ok."""
        return True

    @beartype
    def is_err(self) -> bool:
        """Check if result is Err."""
        return False

    @beartype
    def unwrap(self) -> T:
        """Get the success value."""
        return self.value

    @beartype
    def unwrap_or(self, default: T) -> T:
        """Get the success value."""
        return self.value

    @beartype
    def unwrap_err(self) -> None:
        """Raise ValueError as this is Ok."""
        raise ValueError("Called unwrap_err on Ok value")

    @beartype
    def map(self, func: Callable[[T], U]) -> "Result[U, Any]":
        """Transform the success value."""
        return Ok(func(self.value))

    @beartype
    def map_err(self, func: Callable[[Any], Any]) -> "Result[T, Any]":
        """No-op for Ok values."""
        return self

    @beartype
    def and_then(self, func: Callable[[T], "Result[U, Any]"]) -> "Result[U, Any]":
        """Chain operations that return Results."""
        return func(self.value)


@frozen
class Err(Generic[E]):
    """Error result container."""

    error: E = field()

    @beartype
    def is_ok(self) -> bool:
        """Check if result is Ok."""
        return False

    @beartype
    def is_err(self) -> bool:
        """Check if result is Err."""
        return True

    @beartype
    def unwrap(self) -> None:
        """Raise ValueError as this is Err."""
        raise ValueError(f"Called unwrap on Err value: {self.error}")

    @beartype
    def unwrap_or(self, default: Any) -> Any:
        """Return default value."""
        return default

    @beartype
    def unwrap_err(self) -> E:
        """Get the error value."""
        return self.error

    @beartype
    def map(self, func: Callable[[Any], Any]) -> "Result[Any, E]":
        """No-op for Err values."""
        return self

    @beartype
    def map_err(self, func: Callable[[E], U]) -> "Result[Any, U]":
        """Transform the error value."""
        return Err(func(self.error))

    @beartype
    def and_then(self, func: Callable[[Any], "Result[Any, E]"]) -> "Result[Any, E]":
        """No-op for Err values."""
        return self


# Union type for Result
Result = Union[Ok[T], Err[E]]


@beartype
def result_from_optional(value: T | None, error: E) -> Result[T, E]:
    """Convert Optional to Result."""
    if value is None:
        return Err(error)
    return Ok(value)


@beartype
def collect_results(results: list[Result[T, E]]) -> Result[list[T], E]:
    """Collect a list of Results into a Result of list."""
    values = []
    for result in results:
        if isinstance(result, Err):
            return result
        values.append(result.value)
    return Ok(values)


@beartype
def try_result(func: Callable[[], T]) -> Result[T, Exception]:
    """Execute function and return Result."""
    try:
        return Ok(func())
    except Exception as e:
        return Err(e)
