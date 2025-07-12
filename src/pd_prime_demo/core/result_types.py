"""Result types for error handling without exceptions."""

from typing import TYPE_CHECKING, Any, Generic, NoReturn, TypeVar

from attrs import frozen
from beartype import beartype

T = TypeVar("T")
E = TypeVar("E")


@frozen
class Ok(Generic[T]):
    """Success result wrapper."""

    value: T

    @beartype
    def is_ok(self) -> bool:
        """Check if result is Ok."""
        return True

    @beartype
    def is_err(self) -> bool:
        """Check if result is Error."""
        return False

    @property
    @beartype
    def ok_value(self) -> T:
        """Get the Ok value."""
        return self.value

    @property
    @beartype
    def err_value(self) -> None:
        """Get the Error value (None for Ok)."""
        return None

    @beartype
    def unwrap(self) -> T:
        """Get the success value."""
        return self.value

    @beartype
    def unwrap_or(self, default: T) -> T:
        """Get the success value."""
        return self.value

    @beartype
    def unwrap_err(self) -> NoReturn:
        """Raise ValueError as this is Ok."""
        raise ValueError("Called unwrap_err on Ok value")


@frozen
class Err(Generic[E]):
    """Error result wrapper."""

    error: E

    @beartype
    def is_ok(self) -> bool:
        """Check if result is Ok."""
        return False

    @beartype
    def is_err(self) -> bool:
        """Check if result is Error."""
        return True

    @property
    @beartype
    def ok_value(self) -> None:
        """Get the Ok value (None for Err)."""
        return None

    @property
    @beartype
    def err_value(self) -> E:
        """Get the Error value."""
        return self.error

    @beartype
    def unwrap(self) -> NoReturn:
        """Raise ValueError as this is Err."""
        raise ValueError(f"Called unwrap on Err value: {self.error}")

    @beartype
    def unwrap_or(self, default: T) -> T:
        """Return default value."""
        return default

    @beartype
    def unwrap_err(self) -> E:
        """Get the error value."""
        return self.error


# Type alias for Result - this is the proper way to define Result[T, E]
if TYPE_CHECKING:
    # For type checking, Result[T, E] is just an alias for Ok[T] | Err[E]
    Result = Ok[T] | Err[E]
else:
    # At runtime, provide a convenient factory class
    class Result(Generic[T, E]):
        """Result class with class methods for convenient creation and generic type support."""

        @staticmethod
        @beartype
        def ok(value: T) -> Ok[T]:
            """Create an Ok result."""
            return Ok(value)

        @staticmethod
        @beartype
        def err(error: E) -> Err[E]:
            """Create an Err result."""
            return Err(error)

        def __class_getitem__(cls, params: Any) -> type[Ok[Any] | Err[Any]]:
            """Support generic type annotations like Result[T, E]."""
            # This is primarily for runtime generic support
            # Type checkers will use the TYPE_CHECKING branch above
            return Ok[Any] | Err[Any]  # type: ignore[return-value]
