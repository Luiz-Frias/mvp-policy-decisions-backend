"""Quote API endpoints."""

from datetime import datetime
from typing import Any
from uuid import UUID

from beartype import beartype
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from pd_prime_demo.core.result_types import Err

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
    WizardStepResponse,
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

router = APIRouter(prefix="/quotes", tags=["quotes"])


@router.post("/", response_model=QuoteResponse)
@beartype
async def create_quote(
    quote_data: QuoteCreateRequest,
    background_tasks: BackgroundTasks,
    quote_service: QuoteService = Depends(get_quote_service),
    current_user: User | None = Depends(get_optional_user),
) -> Quote:
    """Create a new insurance quote."""
    # Convert request to domain model
    quote_create = QuoteCreate(**quote_data.model_dump())

    # Create quote
    result = await quote_service.create_quote(
        quote_create, current_user.id if current_user else None
    )

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.err_value)

    quote = result.ok_value

    # Trigger async calculation if data is complete
    if quote.vehicle_info and quote.drivers and quote.coverage_selections:
        background_tasks.add_task(quote_service.calculate_quote, quote.id)

    return quote


@router.get("/{quote_id}", response_model=QuoteResponse)
@beartype
async def get_quote(
    quote_id: UUID,
    quote_service: QuoteService = Depends(get_quote_service),
    current_user: User | None = Depends(get_optional_user),
) -> Quote:
    """Get quote by ID."""
    result = await quote_service.get_quote(quote_id)

    if result.is_err():
        raise HTTPException(status_code=500, detail=result.err_value)

    quote = result.ok_value
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    # Check access permissions
    if current_user:
        # Logged in users can see their own quotes
        if quote.customer_id and quote.customer_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        # Anonymous users need session validation (future enhancement)
        pass

    return quote


@router.put("/{quote_id}", response_model=QuoteResponse)
@beartype
async def update_quote(
    quote_id: UUID,
    update_data: QuoteUpdateRequest,
    quote_service: QuoteService = Depends(get_quote_service),
    current_user: User | None = Depends(get_optional_user),
) -> Quote:
    """Update an existing quote."""
    # Convert request to domain model
    quote_update = QuoteUpdate(**update_data.model_dump(exclude_unset=True))

    result = await quote_service.update_quote(
        quote_id, quote_update, current_user.id if current_user else None
    )

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.err_value)

    return result.ok_value


@router.post("/{quote_id}/calculate", response_model=QuoteResponse)
@beartype
async def calculate_quote(
    quote_id: UUID,
    quote_service: QuoteService = Depends(get_quote_service),
    current_user: User | None = Depends(get_optional_user),
) -> Quote:
    """Calculate or recalculate quote pricing."""
    result = await quote_service.calculate_quote(quote_id)

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.err_value)

    return result.ok_value


@router.post("/{quote_id}/convert", response_model=QuoteConversionResponse)
@beartype
async def convert_to_policy(
    quote_id: UUID,
    conversion_request: QuoteConversionRequest,
    quote_service: QuoteService = Depends(get_quote_service),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Convert quote to policy."""
    result = await quote_service.convert_to_policy(
        quote_id, conversion_request, current_user.id
    )

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.err_value)

    return result.ok_value


@router.get("/", response_model=QuoteSearchResponse)
@beartype
async def search_quotes(
    customer_id: UUID | None = None,
    status: QuoteStatus | None = None,
    state: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    quote_service: QuoteService = Depends(get_quote_service),
    current_user: User | None = Depends(get_optional_user),
) -> dict[str, Any]:
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
        raise HTTPException(status_code=500, detail=result.err_value)

    quotes = result.ok_value

    return QuoteSearchResponse(
        quotes=quotes,
        total=len(quotes),
        limit=limit,
        offset=offset,
    )


# Quote Wizard Endpoints


@router.post("/wizard/start", response_model=WizardSessionResponse)
@beartype
async def start_wizard_session(
    initial_data: dict[str, Any] | None = None,
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> WizardState:
    """Start a new quote wizard session."""
    result = await wizard_service.start_session(initial_data)

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.err_value)

    return result.ok_value


@router.get("/wizard/{session_id}", response_model=WizardSessionResponse)
@beartype
async def get_wizard_session(
    session_id: UUID,
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> WizardState:
    """Get wizard session state."""
    result = await wizard_service.get_session(session_id)

    if result.is_err():
        raise HTTPException(status_code=500, detail=result.err_value)

    state = result.ok_value
    if not state:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    return state


@router.put("/wizard/{session_id}/step", response_model=WizardSessionResponse)
@beartype
async def update_wizard_step(
    session_id: UUID,
    step_data: dict[str, Any],
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> WizardState:
    """Update current wizard step with data."""
    result = await wizard_service.update_step(session_id, step_data)

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.err_value)

    return result.ok_value


@router.post("/wizard/{session_id}/next", response_model=WizardSessionResponse)
@beartype
async def next_wizard_step(
    session_id: UUID,
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> WizardState:
    """Move to next step in wizard."""
    result = await wizard_service.next_step(session_id)

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.err_value)

    return result.ok_value


@router.post("/wizard/{session_id}/previous", response_model=WizardSessionResponse)
@beartype
async def previous_wizard_step(
    session_id: UUID,
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> WizardState:
    """Move to previous step in wizard."""
    result = await wizard_service.previous_step(session_id)

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.err_value)

    return result.ok_value


@router.post(
    "/wizard/{session_id}/jump/{step_id}", response_model=WizardSessionResponse
)
@beartype
async def jump_to_wizard_step(
    session_id: UUID,
    step_id: str,
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> WizardState:
    """Jump to a specific wizard step."""
    result = await wizard_service.jump_to_step(session_id, step_id)

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.err_value)

    return result.ok_value


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


@router.post("/wizard/{session_id}/complete", response_model=WizardCompletionResponse)
@beartype
async def complete_wizard_session(
    session_id: UUID,
    background_tasks: BackgroundTasks,
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
    quote_service: QuoteService = Depends(get_quote_service),
    current_user: User | None = Depends(get_optional_user),
) -> WizardCompletionResponse:
    """Complete wizard session and create quote."""
    # Complete wizard
    result = await wizard_service.complete_session(session_id)

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.err_value)

    wizard_data = result.ok_value
    if not wizard_data:
        raise HTTPException(status_code=400, detail="Invalid wizard data")

    # Create quote from wizard data
    quote_create = QuoteCreate(**wizard_data["quote_data"])
    quote_result = await quote_service.create_quote(
        quote_create, current_user.id if current_user else None
    )

    if quote_result.is_err():
        raise HTTPException(status_code=400, detail=quote_result.err_value)

    quote = quote_result.ok_value

    # Trigger calculation
    background_tasks.add_task(quote_service.calculate_quote, quote.id)

    return WizardCompletionResponse(
        session_id=wizard_data["session_id"],
        quote_id=quote.id,
        quote_number=quote.quote_number,
        status=quote.status,
    )


@router.get("/wizard/steps/all", response_model=list[WizardStepResponse])
@beartype
async def get_all_wizard_steps(
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> list[Any]:
    """Get all wizard steps configuration."""
    result = await wizard_service.get_all_steps()

    if result.is_err():
        raise HTTPException(status_code=500, detail=result.err_value)

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


@router.post("/wizard/{session_id}/extend", response_model=WizardExtensionResponse)
@beartype
async def extend_wizard_session(
    session_id: UUID,
    additional_minutes: int = Query(30, ge=1, le=120),
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> WizardExtensionResponse:
    """Extend wizard session expiration."""
    result = await wizard_service.extend_session(session_id, additional_minutes)

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.err_value)

    state = result.ok_value

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
    intelligence: dict[str, Any] = Field(..., description="Intelligence data")
    generated_at: datetime = Field(..., description="Generation timestamp")


@router.get(
    "/wizard/{session_id}/intelligence/{step_id}",
    response_model=StepIntelligenceResponse,
)
@beartype
async def get_step_business_intelligence(
    session_id: UUID,
    step_id: str,
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> StepIntelligenceResponse:
    """Get business intelligence for a specific wizard step."""
    result = await wizard_service.get_business_intelligence_for_step(
        session_id, step_id
    )

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.err_value)

    return StepIntelligenceResponse(
        step_id=step_id,
        session_id=session_id,
        intelligence=result.ok_value,
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

    performance_stats: dict[str, Any] = Field(..., description="Performance statistics")
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
