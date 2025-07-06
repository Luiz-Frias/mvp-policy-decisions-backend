"""Result types for error handling without exceptions."""

from typing import TypeVar, Generic, Union
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


# Type alias for Result
Result = Union[Ok[T], Err[E]]