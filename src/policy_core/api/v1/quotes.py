# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""Quote API endpoints."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from beartype import beartype
from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from policy_core.api.response_patterns import APIResponseHandler, ErrorResponse
from policy_core.models.base import BaseModelConfig

from ...models.quote import (
    Quote,
    QuoteConversionRequest,
    QuoteCreate,
    QuoteStatus,
    QuoteUpdate,
)
from ...models.user import User, UserRole
from ...schemas.quote import (
    QuoteConversionResponse,
    QuoteCreateRequest,
    QuoteResponse,
    QuoteSearchResponse,
    QuoteUpdateRequest,
    WizardSessionResponse,
)
from ...services.performance_monitor import performance_tracker
from ...services.quote_service import QuoteService
from ...services.quote_wizard import QuoteWizardService, WizardState
from ..dependencies import (
    get_current_user,
    get_optional_user,
    get_quote_service,
    get_wizard_service,
)


@beartype
class StepData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class IntelligenceData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class InitialData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class PerformanceStatsData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


router = APIRouter(prefix="/quotes", tags=["quotes"])


def _convert_quote_to_response(quote: Quote) -> QuoteResponse:
    """Convert Quote model to QuoteResponse schema."""
    return QuoteResponse(
        id=quote.id,
        quote_number=quote.quote_number,
        customer_id=quote.customer_id,
        product_type=quote.product_type,
        state=quote.state,
        zip_code=quote.zip_code,
        effective_date=quote.effective_date,
        status=quote.status,
        email=quote.email,
        phone=quote.phone,
        preferred_contact=quote.preferred_contact,
        vehicle_info=quote.vehicle_info,
        drivers=quote.drivers,
        coverage_selections=quote.coverage_selections,
        base_premium=quote.base_premium,
        total_premium=quote.total_premium,
        monthly_premium=quote.monthly_premium,
        discounts_applied=quote.discounts_applied,
        surcharges_applied=quote.surcharges_applied,
        total_discount_amount=quote.total_discount_amount,
        total_surcharge_amount=quote.total_surcharge_amount,
        rating_factors=quote.rating_factors,
        rating_tier=quote.rating_tier,
        ai_risk_score=(
            Decimal(str(quote.ai_risk_score))
            if quote.ai_risk_score is not None
            else None
        ),
        ai_risk_factors=quote.ai_risk_factors,
        expires_at=quote.expires_at,
        is_expired=quote.expires_at < datetime.now(timezone.utc),
        days_until_expiration=max(
            0, (quote.expires_at - datetime.now(timezone.utc)).days
        ),
        can_be_bound=quote.status == QuoteStatus.QUOTED,
        version=quote.version,
        created_at=quote.created_at,
        updated_at=quote.updated_at,
    )


def _handle_service_error(
    error: str, response: Response, success_status: int = 200
) -> ErrorResponse:
    """Handle service layer errors by mapping to appropriate HTTP status."""
    response.status_code = APIResponseHandler.map_error_to_status(error)
    return ErrorResponse(error=error)


def _convert_wizard_state_to_response(state: WizardState) -> WizardSessionResponse:
    """Convert WizardState to WizardSessionResponse."""
    # Convert dict data to WizardStepData
    from ...schemas.quote import FieldError, ValidationErrors, WizardStepData

    # Create WizardStepData with default values for missing fields
    # This is a simplified conversion - in production, you'd want proper mapping
    step_data = WizardStepData()

    # Convert validation errors from dict to ValidationErrors
    field_errors = []
    for field, errors in state.validation_errors.items():
        field_errors.append(
            FieldError(
                field_name=field,
                error_messages=errors,
                error_code=None,
                suggested_fix=None,
            )
        )

    validation_errors = ValidationErrors(
        field_errors=field_errors, form_errors=[], warning_messages=[]
    )

    return WizardSessionResponse(
        session_id=state.session_id,
        quote_id=state.quote_id,
        current_step=state.current_step,
        completed_steps=state.completed_steps,
        data=step_data,
        validation_errors=validation_errors,
        started_at=state.started_at,
        last_updated=state.last_updated,
        expires_at=state.expires_at,
        is_complete=state.is_complete,
        completion_percentage=int(
            len(state.completed_steps) * 100 / 10
        ),  # Assuming 10 steps total
    )


@router.post("/", status_code=201)
@beartype
async def create_quote(
    quote_data: QuoteCreateRequest,
    background_tasks: BackgroundTasks,
    response: Response,
    quote_service: QuoteService = Depends(get_quote_service),
    current_user: User | None = Depends(get_optional_user),
) -> QuoteResponse | ErrorResponse:
    """Create a new insurance quote."""
    # Convert request to domain model
    quote_create = QuoteCreate(**quote_data.model_dump())

    # Create quote
    result = await quote_service.create_quote(
        quote_create, current_user.id if current_user else None
    )

    if result.is_err():
        return _handle_service_error(result.unwrap_err(), response, 201)

    quote = result.ok_value
    if quote is None:
        return _handle_service_error("Quote creation failed", response, 201)

    # Trigger async calculation if data is complete
    if quote.vehicle_info and quote.drivers and quote.coverage_selections:
        background_tasks.add_task(quote_service.calculate_quote, quote.id)

    # Convert to response and return with proper status
    response.status_code = 201
    return _convert_quote_to_response(quote)


@router.get("/{quote_id}")
@beartype
async def get_quote(
    quote_id: UUID,
    response: Response,
    quote_service: QuoteService = Depends(get_quote_service),
    current_user: User | None = Depends(get_optional_user),
) -> QuoteResponse | ErrorResponse:
    """Get quote by ID."""
    result = await quote_service.get_quote(quote_id)

    if result.is_err():
        return _handle_service_error(result.unwrap_err(), response)

    quote = result.ok_value
    if not quote:
        return _handle_service_error("Quote not found", response)

    # Check access permissions
    if current_user:
        # Logged in users can see their own quotes
        if quote.customer_id and quote.customer_id != current_user.id:
            return _handle_service_error("Access denied", response)
    else:
        # Anonymous users need session validation (future enhancement)
        pass

    # Convert to response and return
    response.status_code = 200
    return _convert_quote_to_response(quote)


@router.put("/{quote_id}")
@beartype
async def update_quote(
    quote_id: UUID,
    update_data: QuoteUpdateRequest,
    response: Response,
    quote_service: QuoteService = Depends(get_quote_service),
    current_user: User | None = Depends(get_optional_user),
) -> QuoteResponse | ErrorResponse:
    """Update an existing quote."""
    # Convert request to domain model
    quote_update = QuoteUpdate(**update_data.model_dump(exclude_unset=True))

    result = await quote_service.update_quote(
        quote_id, quote_update, current_user.id if current_user else None
    )

    if result.is_err():
        return _handle_service_error(result.unwrap_err(), response)

    quote = result.ok_value
    if quote is None:
        return _handle_service_error("Quote not found", response)

    # Convert to response and return
    response.status_code = 200
    return _convert_quote_to_response(quote)


@router.post("/{quote_id}/calculate")
@beartype
async def calculate_quote(
    quote_id: UUID,
    response: Response,
    quote_service: QuoteService = Depends(get_quote_service),
    current_user: User | None = Depends(get_optional_user),
) -> QuoteResponse | ErrorResponse:
    """Calculate or recalculate quote pricing."""
    result = await quote_service.calculate_quote(quote_id)

    if result.is_err():
        return _handle_service_error(result.unwrap_err(), response)

    quote = result.ok_value
    if quote is None:
        return _handle_service_error("Quote not found", response)

    # Convert to response and return
    response.status_code = 200
    return _convert_quote_to_response(quote)


@router.post("/{quote_id}/convert", status_code=201)
@beartype
async def convert_to_policy(
    quote_id: UUID,
    conversion_request: QuoteConversionRequest,
    response: Response,
    quote_service: QuoteService = Depends(get_quote_service),
    current_user: User = Depends(get_current_user),
) -> QuoteConversionResponse | ErrorResponse:
    """Convert quote to policy."""
    result = await quote_service.convert_to_policy(
        quote_id, conversion_request, current_user.id
    )

    if result.is_err():
        return _handle_service_error(result.unwrap_err(), response, 201)

    if result.ok_value is None:
        return _handle_service_error("Policy conversion failed", response, 201)

    # Convert to response and return with proper status
    response.status_code = 201
    return QuoteConversionResponse(**result.ok_value)


@router.get("/")
@beartype
async def search_quotes(
    response: Response,
    customer_id: UUID | None = None,
    status: QuoteStatus | None = None,
    state: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    quote_service: QuoteService = Depends(get_quote_service),
    current_user: User | None = Depends(get_optional_user),
) -> QuoteSearchResponse | ErrorResponse:
    """Search quotes with filters."""
    # If user is logged in, only show their quotes
    if current_user and current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        customer_id = current_user.id

    result = await quote_service.search_quotes(
        customer_id=customer_id,
        status=status,
        state=state,
        created_after=created_after,
        created_before=created_before,
        limit=limit,
        offset=offset,
    )

    if result.is_err():
        return _handle_service_error(result.unwrap_err(), response)

    quotes: list[Quote] = result.ok_value or []

    # Convert Quote objects to QuoteResponse objects
    quote_responses = [_convert_quote_to_response(quote) for quote in quotes]

    # Return success with proper status
    response.status_code = 200
    return QuoteSearchResponse(
        quotes=quote_responses,
        total=len(quotes),
        limit=limit,
        offset=offset,
    )


# Quote Wizard Endpoints


@router.post("/wizard/start", status_code=201)
@beartype
async def start_wizard_session(
    response: Response,
    initial_data: InitialData | None = None,
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> WizardSessionResponse | ErrorResponse:
    """Start a new quote wizard session."""
    result = await wizard_service.start_session(initial_data)

    if result.is_err():
        return _handle_service_error(result.unwrap_err(), response, 201)

    wizard_state = result.ok_value
    if wizard_state is None:
        return _handle_service_error("Wizard session not found", response, 201)

    # Convert to response and return with proper status
    response.status_code = 201
    return _convert_wizard_state_to_response(wizard_state)


@router.get("/wizard/{session_id}")
@beartype
async def get_wizard_session(
    session_id: UUID,
    response: Response,
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> WizardSessionResponse | ErrorResponse:
    """Get wizard session state."""
    result = await wizard_service.get_session(session_id)

    if result.is_err():
        return _handle_service_error(result.unwrap_err(), response)

    state = result.ok_value
    if not state:
        return _handle_service_error("Session not found or expired", response)

    # Convert to response and return
    response.status_code = 200
    return _convert_wizard_state_to_response(state)


@router.put("/wizard/{session_id}/step")
@beartype
async def update_wizard_step(
    session_id: UUID,
    step_data: StepData,
    response: Response,
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> WizardSessionResponse | ErrorResponse:
    """Update current wizard step with data."""
    result = await wizard_service.update_step(session_id, step_data)

    if result.is_err():
        return _handle_service_error(result.unwrap_err(), response)

    wizard_state = result.ok_value
    if wizard_state is None:
        return _handle_service_error("Wizard session not found", response)

    # Convert to response and return
    response.status_code = 200
    return _convert_wizard_state_to_response(wizard_state)


@router.post("/wizard/{session_id}/next")
@beartype
async def next_wizard_step(
    session_id: UUID,
    response: Response,
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> WizardSessionResponse | ErrorResponse:
    """Move to next step in wizard."""
    result = await wizard_service.next_step(session_id)

    if result.is_err():
        return _handle_service_error(result.unwrap_err(), response)

    wizard_state = result.ok_value
    if wizard_state is None:
        return _handle_service_error("Wizard session not found", response)

    # Convert to response and return
    response.status_code = 200
    return _convert_wizard_state_to_response(wizard_state)


@router.post("/wizard/{session_id}/previous")
@beartype
async def previous_wizard_step(
    session_id: UUID,
    response: Response,
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> WizardSessionResponse | ErrorResponse:
    """Move to previous step in wizard."""
    result = await wizard_service.previous_step(session_id)

    if result.is_err():
        return _handle_service_error(result.unwrap_err(), response)

    wizard_state = result.ok_value
    if wizard_state is None:
        return _handle_service_error("Wizard session not found", response)

    # Convert to response and return
    response.status_code = 200
    return _convert_wizard_state_to_response(wizard_state)


@router.post("/wizard/{session_id}/jump/{step_id}")
@beartype
async def jump_to_wizard_step(
    session_id: UUID,
    step_id: str,
    response: Response,
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> WizardSessionResponse | ErrorResponse:
    """Jump to a specific wizard step."""
    result = await wizard_service.jump_to_step(session_id, step_id)

    if result.is_err():
        return _handle_service_error(result.unwrap_err(), response)

    wizard_state = result.ok_value
    if wizard_state is None:
        return _handle_service_error("Wizard session not found", response)

    # Convert to response and return
    response.status_code = 200
    return _convert_wizard_state_to_response(wizard_state)


class WizardCompletionResponse(BaseModel):
    """Response model for wizard completion."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    session_id: UUID = Field(..., description="Wizard session ID")
    quote_id: UUID = Field(..., description="Created quote ID")
    quote_number: str = Field(..., description="Quote number")
    status: QuoteStatus = Field(..., description="Quote status")


@router.post("/wizard/{session_id}/complete", status_code=201)
@beartype
async def complete_wizard_session(
    session_id: UUID,
    background_tasks: BackgroundTasks,
    response: Response,
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
    quote_service: QuoteService = Depends(get_quote_service),
    current_user: User | None = Depends(get_optional_user),
) -> WizardCompletionResponse | ErrorResponse:
    """Complete wizard session and create quote."""
    # Complete wizard
    result = await wizard_service.complete_session(session_id)

    if result.is_err():
        return _handle_service_error(result.unwrap_err(), response, 201)

    wizard_data = result.ok_value
    if not wizard_data:
        return _handle_service_error("Invalid wizard data", response, 201)

    # Create quote from wizard data
    quote_create = QuoteCreate(**wizard_data["quote_data"])
    quote_result = await quote_service.create_quote(
        quote_create, current_user.id if current_user else None
    )

    if quote_result.is_err():
        return _handle_service_error(quote_result.unwrap_err(), response, 201)

    quote = quote_result.ok_value
    if not quote:
        return _handle_service_error("Failed to create quote", response, 201)

    # Trigger calculation
    background_tasks.add_task(quote_service.calculate_quote, quote.id)

    # Return success with proper status
    response.status_code = 201
    return WizardCompletionResponse(
        session_id=wizard_data["session_id"],
        quote_id=quote.id,
        quote_number=quote.quote_number,
        status=quote.status,
    )


@router.get("/wizard/steps/all")
@beartype
async def get_all_wizard_steps(
    response: Response,
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> list[Any] | ErrorResponse:
    """Get all wizard steps configuration."""
    result = await wizard_service.get_all_steps()

    if result.is_err():
        return _handle_service_error(result.unwrap_err(), response)

    if result.ok_value is None:
        return _handle_service_error("No wizard steps available", response)

    # Return success
    response.status_code = 200
    return result.ok_value


class WizardExtensionResponse(BaseModel):
    """Response model for wizard session extension."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    session_id: UUID = Field(..., description="Wizard session ID")
    expires_at: datetime = Field(..., description="New expiration time")
    extended_by_minutes: int = Field(..., description="Minutes extended")


@router.post("/wizard/{session_id}/extend")
@beartype
async def extend_wizard_session(
    session_id: UUID,
    response: Response,
    additional_minutes: int = Query(30, ge=1, le=120),
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> WizardExtensionResponse | ErrorResponse:
    """Extend wizard session expiration."""
    result = await wizard_service.extend_session(session_id, additional_minutes)

    if result.is_err():
        return _handle_service_error(result.unwrap_err(), response)

    state = result.ok_value

    # Type narrowing - this should never be None due to service logic
    if state is None:
        return _handle_service_error(
            "Internal server error: session state is None", response
        )

    # Return success
    response.status_code = 200
    return WizardExtensionResponse(
        session_id=state.session_id,
        expires_at=state.expires_at,
        extended_by_minutes=additional_minutes,
    )


class StepIntelligenceResponse(BaseModel):
    """Response model for step business intelligence."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    step_id: str = Field(..., description="Step identifier")
    session_id: UUID = Field(..., description="Session identifier")
    intelligence: IntelligenceData = Field(..., description="Intelligence data")
    generated_at: datetime = Field(..., description="Generation timestamp")


@router.get("/wizard/{session_id}/intelligence/{step_id}")
@beartype
async def get_step_business_intelligence(
    session_id: UUID,
    step_id: str,
    response: Response,
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> StepIntelligenceResponse | ErrorResponse:
    """Get business intelligence for a specific wizard step."""
    result = await wizard_service.get_business_intelligence_for_step(
        session_id, step_id
    )

    if result.is_err():
        return _handle_service_error(result.unwrap_err(), response)

    # Return success
    response.status_code = 200
    return StepIntelligenceResponse(
        step_id=step_id,
        session_id=session_id,
        intelligence=result.ok_value if result.ok_value is not None else {},
        generated_at=datetime.now(),
    )


class PerformanceStatsResponse(BaseModel):
    """Response model for performance statistics."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    performance_stats: PerformanceStatsData = Field(
        ..., description="Performance statistics"
    )
    collected_at: datetime = Field(..., description="Collection timestamp")
    description: str = Field(..., description="Statistics description")


@router.get("/performance/stats", response_model=PerformanceStatsResponse)
@beartype
async def get_performance_stats() -> PerformanceStatsResponse:
    """Get performance statistics for quote operations."""
    return PerformanceStatsResponse(
        performance_stats=performance_tracker.get_all_stats(),
        collected_at=datetime.now(),
        description="Performance metrics for quote service operations",
    )
