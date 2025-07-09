"""Example implementation of elite Result[T,E] + HTTP semantics pattern.

This file demonstrates the proper conversion from HTTPException to Result handling.
Use this as a reference for the systematic conversion.
"""

from fastapi import APIRouter, Response, Depends
from typing import Union
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from beartype import beartype

from pd_prime_demo.api.response_patterns import (
    APIResponseHandler,
    ErrorResponse,
    handle_result
)
from pd_prime_demo.schemas.responses import (
    CreatedResponse,
    UpdatedResponse,
    DeletedResponse,
    CreatedResult,
    UpdatedResult,
    DeletedResult
)
from pd_prime_demo.schemas.quote import QuoteCreateRequest, QuoteResponse
from pd_prime_demo.core.result_types import Result
from pd_prime_demo.api.dependencies import get_current_user

router = APIRouter(prefix="/examples", tags=["Elite Pattern Examples"])


# ❌ OLD PATTERN (HTTPException) - DON'T USE
"""
@router.post("/quotes/old")
async def create_quote_old(request: QuoteRequest) -> QuoteResponse:
    result = await quote_service.create_quote(request)
    if result.is_err():
        raise HTTPException(status_code=500, detail=result.err_value)  # ❌ WRONG
    return result.unwrap()
"""


# ✅ NEW PATTERN (Result + HTTP Semantics) - USE THIS
@router.post("/quotes", status_code=201)
@beartype
async def create_quote(
    request: QuoteCreateRequest,
    response: Response,
    current_user = Depends(get_current_user)
) -> Union[QuoteResponse, ErrorResponse]:
    """Create a new quote using elite Result[T,E] + HTTP semantics pattern.

    Returns:
        QuoteResponse on success (201 Created)
        ErrorResponse on failure (400/404/422 with business-appropriate status)
    """
    # Mock service call for example
    from pd_prime_demo.core.result_types import Ok
    result: Result[QuoteResponse, str] = Ok(QuoteResponse(
        quote_id=UUID("12345678-1234-5678-1234-567812345678"),
        policy_type="auto",
        customer_id=current_user.user_id,
        state="CA",
        premium=1200.00,
        status="draft",
        created_at=datetime.now(),
        updated_at=datetime.now()
    ))

    # Convert Result to HTTP response with proper status codes
    return APIResponseHandler.from_result(result, response, success_status=201)


@router.get("/quotes/{quote_id}")
@beartype
async def get_quote(
    quote_id: UUID,
    response: Response,
    current_user = Depends(get_current_user)
) -> Union[QuoteResponse, ErrorResponse]:
    """Get quote by ID using elite pattern."""
    # Mock service call for example
    from pd_prime_demo.core.result_types import Ok, Err

    if str(quote_id) == "12345678-1234-5678-1234-567812345678":
        result: Result[QuoteResponse, str] = Ok(QuoteResponse(
            quote_id=quote_id,
            policy_type="auto",
            customer_id=current_user.user_id,
            state="CA",
            premium=Decimal("1200.00"),
            status="draft",
            created_at=datetime.now(),
            updated_at=datetime.now()
        ))
    else:
        result = Err("Quote not found")

    # Using convenience function (equivalent to above)
    return handle_result(result, response)


@router.put("/quotes/{quote_id}")
@beartype
async def update_quote(
    quote_id: UUID,
    request: QuoteRequest,
    response: Response,
    current_user = Depends(get_current_user)
) -> UpdatedResult:
    """Update quote using standard response schema."""
    result = await quote_service.update_quote(quote_id, request, current_user.user_id)

    return handle_result(result, response)


@router.delete("/quotes/{quote_id}", status_code=204)
@beartype
async def delete_quote(
    quote_id: UUID,
    response: Response,
    current_user = Depends(get_current_user)
) -> DeletedResult:
    """Delete quote with proper HTTP semantics."""
    result = await quote_service.delete_quote(quote_id, current_user.user_id)

    return handle_result(result, response, success_status=204)


# Example of handling different error types
@router.post("/quotes/{quote_id}/validate")
@beartype
async def validate_quote(
    quote_id: UUID,
    response: Response,
    current_user = Depends(get_current_user)
) -> Union[dict, ErrorResponse]:
    """Demonstrate automatic error type mapping."""

    # Service returns different error types
    result = await quote_service.validate_quote(quote_id)

    # APIResponseHandler automatically maps:
    # "Quote not found" -> 404
    # "Invalid coverage amount" -> 400
    # "Insufficient permissions" -> 403
    # "Rate limit exceeded" -> 429
    # "Quote already finalized" -> 409
    # Other errors -> 422

    return handle_result(result, response)


# Example showing the power of the pattern
@beartype
async def business_logic_example() -> Result[str, str]:
    """Example service layer function."""
    # This could return various business errors:

    # return Err("Quote not found")  # -> 404
    # return Err("Invalid coverage amount")  # -> 400
    # return Err("Insufficient permissions")  # -> 403
    # return Err("Quote processing failed")  # -> 422

    return Ok("Success")


"""
CONVERSION CHECKLIST FOR AGENTS:

1. ✅ Import required types:
   - from fastapi import Response
   - from pd_prime_demo.api.response_patterns import handle_result, ErrorResponse
   - from typing import Union

2. ✅ Update function signature:
   - Add `response: Response` parameter
   - Change return type to Union[OriginalResponse, ErrorResponse]

3. ✅ Replace HTTPException pattern:
   OLD: if result.is_err(): raise HTTPException(status_code=X, detail=result.err_value)
   NEW: return handle_result(result, response, success_status=X)

4. ✅ Update route decorators:
   - Add status_code parameter for success cases
   - Remove any status codes from HTTPException handling

5. ✅ Test the conversion:
   - Verify status codes are correctly mapped
   - Check error response format is consistent
   - Ensure success responses work as expected

AGENT SCOPE CATEGORIES:
- Core Business (quotes, policies, claims)
- Admin Operations (user management, system config)
- Authentication/Security (mfa, oauth, api_keys)
- Compliance/Monitoring (audit, performance)
- Middleware/Dependencies (global error handling)
"""
