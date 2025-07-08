"""Result types for error handling without exceptions."""

from typing import Any, Generic, TypeVar, Union

from attrs import frozen

T = TypeVar("T")
E = TypeVar("E")


@frozen
class Ok(Generic[T]):
    """Success result wrapper."""

    value: T

    def is_ok(self) -> bool:
        """Check if result is Ok."""
        return True

    def is_err(self) -> bool:
        """Check if result is Error."""
        return False

    @property
    def ok_value(self) -> T:
        """Get the Ok value."""
        return self.value

    @property
    def err_value(self) -> None:
        """Get the Error value (None for Ok)."""
        return None

    def unwrap(self) -> T:
        """Get the success value."""
        return self.value

    def unwrap_or(self, default: T) -> T:
        """Get the success value."""
        return self.value

    def unwrap_err(self) -> None:
        """Raise ValueError as this is Ok."""
        raise ValueError("Called unwrap_err on Ok value")


@frozen
class Err(Generic[E]):
    """Error result wrapper."""

    error: E

    def is_ok(self) -> bool:
        """Check if result is Ok."""
        return False

    def is_err(self) -> bool:
        """Check if result is Error."""
        return True

    @property
    def ok_value(self) -> None:
        """Get the Ok value (None for Err)."""
        return None

    @property
    def err_value(self) -> E:
        """Get the Error value."""
        return self.error

    def unwrap(self) -> None:
        """Raise ValueError as this is Err."""
        raise ValueError(f"Called unwrap on Err value: {self.error}")

    def unwrap_or(self, default: T) -> T:
        """Return default value."""
        return default

    def unwrap_err(self) -> E:
        """Get the error value."""
        return self.error


# Type alias for Result
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

    def __class_getitem__(cls, params: tuple[Any, ...]) -> type[Ok[Any] | Err[Any]]:
        """Support generic type annotations like Result[T, E]."""
        if not isinstance(params, tuple) or len(params) != 2:
            raise TypeError(f"Result expects 2 type parameters, got {params}")
        return Union[Ok[params[0]], Err[params[1]]]  # type: ignore[misc]
