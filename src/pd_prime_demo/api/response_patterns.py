"""Elite API response patterns following Result[T,E] + HTTP semantics."""

from typing import Any, Generic, TypeVar, Union
from fastapi import Response
from pydantic import BaseModel, ConfigDict, Field
from beartype import beartype

from pd_prime_demo.core.result_types import Result

T = TypeVar('T')


@beartype
class ErrorResponse(BaseModel):
    """Standardized error response for business logic failures."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    success: bool = Field(default=False, description="Always false for error responses")
    error: str = Field(..., description="Human-readable error message")
    error_code: str | None = Field(default=None, description="Machine-readable error code")
    details: dict[str, Any] | None = Field(default=None, description="Additional error context")


@beartype
class SuccessResponse(BaseModel, Generic[T]):
    """Standardized success response wrapper."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid", 
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    success: bool = Field(default=True, description="Always true for success responses")
    data: T = Field(..., description="Response payload")


class APIResponseHandler:
    """Elite API response handler implementing Result[T,E] + HTTP semantics pattern."""
    
    @staticmethod
    @beartype
    def map_error_to_status(error: str) -> int:
        """Map business logic errors to appropriate HTTP status codes.
        
        Args:
            error: Business logic error message
            
        Returns:
            HTTP status code following RESTful conventions
        """
        error_lower = error.lower()
        
        # Resource not found
        if any(phrase in error_lower for phrase in ["not found", "does not exist", "missing"]):
            return 404
            
        # Authorization failures  
        if any(phrase in error_lower for phrase in ["unauthorized", "not authorized", "access denied"]):
            return 401
            
        # Permission failures
        if any(phrase in error_lower for phrase in ["forbidden", "insufficient permissions", "not allowed"]):
            return 403
            
        # Validation failures
        if any(phrase in error_lower for phrase in [
            "validation", "invalid", "malformed", "bad request", "required field"
        ]):
            return 400
            
        # Conflict states
        if any(phrase in error_lower for phrase in [
            "already exists", "conflict", "duplicate", "concurrent modification"
        ]):
            return 409
            
        # Rate limiting
        if any(phrase in error_lower for phrase in ["rate limit", "too many requests", "throttled"]):
            return 429
            
        # Default to 422 for business logic errors
        return 422
    
    @staticmethod
    @beartype 
    def from_result(
        result: Result[T, str], 
        response: Response,
        success_status: int = 200
    ) -> Union[T, ErrorResponse]:
        """Convert Result[T,E] to HTTP response with proper status codes.
        
        Args:
            result: Service layer Result
            response: FastAPI Response object to set status code
            success_status: HTTP status for successful operations (default 200)
            
        Returns:
            Either the unwrapped success value or ErrorResponse
        """
        if result.is_err():
            error_msg = result.unwrap_err()
            response.status_code = APIResponseHandler.map_error_to_status(error_msg)
            return ErrorResponse(error=error_msg)
            
        response.status_code = success_status
        return result.unwrap()
    
    @staticmethod
    @beartype
    def from_result_wrapped(
        result: Result[T, str],
        response: Response, 
        success_status: int = 200
    ) -> Union[SuccessResponse[T], ErrorResponse]:
        """Convert Result[T,E] to wrapped response format.
        
        Args:
            result: Service layer Result
            response: FastAPI Response object to set status code
            success_status: HTTP status for successful operations
            
        Returns:
            Either SuccessResponse[T] or ErrorResponse
        """
        if result.is_err():
            error_msg = result.unwrap_err() 
            response.status_code = APIResponseHandler.map_error_to_status(error_msg)
            return ErrorResponse(error=error_msg)
            
        response.status_code = success_status
        return SuccessResponse(data=result.unwrap())


# Convenience type aliases for common response patterns
# These are generic aliases that need to be parameterized when used

# Convenience functions for common patterns
@beartype
def handle_result(
    result: Result[T, str], 
    response: Response,
    success_status: int = 200
) -> Union[T, ErrorResponse]:
    """Convenience function for standard result handling."""
    return APIResponseHandler.from_result(result, response, success_status)

@beartype  
def handle_result_wrapped(
    result: Result[T, str],
    response: Response,
    success_status: int = 200  
) -> Union[SuccessResponse[T], ErrorResponse]:
    """Convenience function for wrapped result handling."""
    return APIResponseHandler.from_result_wrapped(result, response, success_status)