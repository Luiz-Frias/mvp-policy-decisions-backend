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
    def map(self, func: Callable[[T], U]) -> "Ok[U]":
        """Transform the success value."""
        return Ok(func(self.value))

    @beartype
    def map_err(self, func: Callable[[Any], Any]) -> "Ok[T]":
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
    def map(self, func: Callable[[Any], Any]) -> "Err[E]":
        """No-op for Err values."""
        return self

    @beartype
    def map_err(self, func: Callable[[E], U]) -> "Err[U]":
        """Transform the error value."""
        return Err(func(self.error))

    @beartype
    def and_then(self, func: Callable[[Any], "Result[Any, E]"]) -> "Result[Any, E]":
        """No-op for Err values."""
        return self  # type: ignore[return-value]


# Union type for Result
ResultType = Union[Ok[T], Err[E]]


class Result(Generic[T, E]):
    """Result class with class methods for convenient creation and generic type support."""

    @staticmethod
    def ok(value: T) -> Ok[T]:
        """Create an Ok result."""
        return Ok(value)

    @staticmethod
    def err(error: E) -> Err[E]:
        """Create an Err result."""
        return Err(error)

    @classmethod
    def __class_getitem__(cls, params: tuple[type, type]) -> type:
        """Support generic type annotations like Result[T, E]."""
        return cls


@beartype
def result_from_optional(value: T | None, error: E) -> Ok[T] | Err[E]:
    """Convert Optional to Result."""
    if value is None:
        return Err(error)
    return Ok(value)


@beartype
def collect_results(results: list[Ok[T] | Err[E]]) -> Ok[list[T]] | Err[E]:
    """Collect a list of Results into a Result of list."""
    values = []
    for result in results:
        if isinstance(result, Err):
            return result
        values.append(result.value)
    return Ok(values)


@beartype
def try_result(func: Callable[[], T]) -> Ok[T] | Err[Exception]:
    """Execute function and return Result."""
    try:
        return Ok(func())
    except Exception as e:
        return Err(e)
