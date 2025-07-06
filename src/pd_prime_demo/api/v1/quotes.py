"""Quote API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID

from beartype import beartype

from ...services.quote_service import QuoteService
from ...services.quote_wizard import QuoteWizardService, WizardState
from ...services.performance_monitor import performance_tracker
from ...models.quote import (
    Quote, QuoteCreate, QuoteUpdate, QuoteStatus,
    QuoteConversionRequest
)
from ...schemas.quote import (
    QuoteResponse, QuoteCreateRequest, QuoteUpdateRequest,
    QuoteSearchResponse, QuoteConversionResponse,
    WizardSessionResponse, WizardStepResponse
)
from ..dependencies import (
    get_quote_service, get_wizard_service,
    get_current_user, get_optional_user
)
from ...models.user import User

router = APIRouter(prefix="/quotes", tags=["quotes"])


@router.post("/", response_model=QuoteResponse)
@beartype
async def create_quote(
    quote_data: QuoteCreateRequest,
    background_tasks: BackgroundTasks,
    quote_service: QuoteService = Depends(get_quote_service),
    current_user: Optional[User] = Depends(get_optional_user),
) -> Quote:
    """Create a new insurance quote."""
    # Convert request to domain model
    quote_create = QuoteCreate(**quote_data.model_dump())
    
    # Create quote
    result = await quote_service.create_quote(
        quote_create,
        current_user.id if current_user else None
    )
    
    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)
    
    quote = result.value
    
    # Trigger async calculation if data is complete
    if quote.vehicle_info and quote.drivers and quote.coverage_selections:
        background_tasks.add_task(
            quote_service.calculate_quote,
            quote.id
        )
    
    return quote


@router.get("/{quote_id}", response_model=QuoteResponse)
@beartype
async def get_quote(
    quote_id: UUID,
    quote_service: QuoteService = Depends(get_quote_service),
    current_user: Optional[User] = Depends(get_optional_user),
) -> Quote:
    """Get quote by ID."""
    result = await quote_service.get_quote(quote_id)
    
    if result.is_err():
        raise HTTPException(status_code=500, detail=result.error)
    
    quote = result.value
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
    current_user: Optional[User] = Depends(get_optional_user),
) -> Quote:
    """Update an existing quote."""
    # Convert request to domain model
    quote_update = QuoteUpdate(**update_data.model_dump(exclude_unset=True))
    
    result = await quote_service.update_quote(
        quote_id,
        quote_update,
        current_user.id if current_user else None
    )
    
    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.value


@router.post("/{quote_id}/calculate", response_model=QuoteResponse)
@beartype
async def calculate_quote(
    quote_id: UUID,
    quote_service: QuoteService = Depends(get_quote_service),
    current_user: Optional[User] = Depends(get_optional_user),
) -> Quote:
    """Calculate or recalculate quote pricing."""
    result = await quote_service.calculate_quote(quote_id)
    
    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.value


@router.post("/{quote_id}/convert", response_model=QuoteConversionResponse)
@beartype
async def convert_to_policy(
    quote_id: UUID,
    conversion_request: QuoteConversionRequest,
    quote_service: QuoteService = Depends(get_quote_service),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Convert quote to policy."""
    result = await quote_service.convert_to_policy(
        quote_id,
        conversion_request,
        current_user.id
    )
    
    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.value


@router.get("/", response_model=QuoteSearchResponse)
@beartype
async def search_quotes(
    customer_id: Optional[UUID] = None,
    status: Optional[QuoteStatus] = None,
    state: Optional[str] = None,
    created_after: Optional[datetime] = None,
    created_before: Optional[datetime] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    quote_service: QuoteService = Depends(get_quote_service),
    current_user: Optional[User] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Search quotes with filters."""
    # If user is logged in, only show their quotes
    if current_user and not current_user.is_admin:
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
        raise HTTPException(status_code=500, detail=result.error)
    
    quotes = result.value
    
    return {
        "quotes": quotes,
        "total": len(quotes),
        "limit": limit,
        "offset": offset,
    }


# Quote Wizard Endpoints

@router.post("/wizard/start", response_model=WizardSessionResponse)
@beartype
async def start_wizard_session(
    initial_data: Optional[Dict[str, Any]] = None,
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> WizardState:
    """Start a new quote wizard session."""
    result = await wizard_service.start_session(initial_data)
    
    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.value


@router.get("/wizard/{session_id}", response_model=WizardSessionResponse)
@beartype
async def get_wizard_session(
    session_id: UUID,
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> WizardState:
    """Get wizard session state."""
    result = await wizard_service.get_session(session_id)
    
    if result.is_err():
        raise HTTPException(status_code=500, detail=result.error)
    
    state = result.value
    if not state:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    return state


@router.put("/wizard/{session_id}/step", response_model=WizardSessionResponse)
@beartype
async def update_wizard_step(
    session_id: UUID,
    step_data: Dict[str, Any],
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> WizardState:
    """Update current wizard step with data."""
    result = await wizard_service.update_step(session_id, step_data)
    
    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.value


@router.post("/wizard/{session_id}/next", response_model=WizardSessionResponse)
@beartype
async def next_wizard_step(
    session_id: UUID,
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> WizardState:
    """Move to next step in wizard."""
    result = await wizard_service.next_step(session_id)
    
    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.value


@router.post("/wizard/{session_id}/previous", response_model=WizardSessionResponse)
@beartype
async def previous_wizard_step(
    session_id: UUID,
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> WizardState:
    """Move to previous step in wizard."""
    result = await wizard_service.previous_step(session_id)
    
    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.value


@router.post("/wizard/{session_id}/jump/{step_id}", response_model=WizardSessionResponse)
@beartype
async def jump_to_wizard_step(
    session_id: UUID,
    step_id: str,
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> WizardState:
    """Jump to a specific wizard step."""
    result = await wizard_service.jump_to_step(session_id, step_id)
    
    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.value


@router.post("/wizard/{session_id}/complete")
@beartype
async def complete_wizard_session(
    session_id: UUID,
    background_tasks: BackgroundTasks,
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
    quote_service: QuoteService = Depends(get_quote_service),
    current_user: Optional[User] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Complete wizard session and create quote."""
    # Complete wizard
    result = await wizard_service.complete_session(session_id)
    
    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)
    
    wizard_data = result.value
    
    # Create quote from wizard data
    quote_create = QuoteCreate(**wizard_data["quote_data"])
    quote_result = await quote_service.create_quote(
        quote_create,
        current_user.id if current_user else None
    )
    
    if quote_result.is_err():
        raise HTTPException(status_code=400, detail=quote_result.error)
    
    quote = quote_result.value
    
    # Trigger calculation
    background_tasks.add_task(
        quote_service.calculate_quote,
        quote.id
    )
    
    return {
        "session_id": wizard_data["session_id"],
        "quote_id": str(quote.id),
        "quote_number": quote.quote_number,
        "status": quote.status,
    }


@router.get("/wizard/steps/all", response_model=List[WizardStepResponse])
@beartype
async def get_all_wizard_steps(
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> List[Any]:
    """Get all wizard steps configuration."""
    result = await wizard_service.get_all_steps()
    
    if result.is_err():
        raise HTTPException(status_code=500, detail=result.error)
    
    return result.value


@router.post("/wizard/{session_id}/extend")
@beartype
async def extend_wizard_session(
    session_id: UUID,
    additional_minutes: int = Query(30, ge=1, le=120),
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> Dict[str, Any]:
    """Extend wizard session expiration."""
    result = await wizard_service.extend_session(session_id, additional_minutes)
    
    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)
    
    state = result.value
    
    return {
        "session_id": str(state.session_id),
        "expires_at": state.expires_at.isoformat(),
        "extended_by_minutes": additional_minutes,
    }


@router.get("/wizard/{session_id}/intelligence/{step_id}")
@beartype
async def get_step_business_intelligence(
    session_id: UUID,
    step_id: str,
    wizard_service: QuoteWizardService = Depends(get_wizard_service),
) -> Dict[str, Any]:
    """Get business intelligence for a specific wizard step."""
    result = await wizard_service.get_business_intelligence_for_step(session_id, step_id)
    
    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)
    
    return {
        "step_id": step_id,
        "session_id": str(session_id),
        "intelligence": result.value,
        "generated_at": datetime.now().isoformat(),
    }


@router.get("/performance/stats")
@beartype
async def get_performance_stats() -> Dict[str, Any]:
    """Get performance statistics for quote operations."""
    return {
        "performance_stats": performance_tracker.get_all_stats(),
        "collected_at": datetime.now().isoformat(),
        "description": "Performance metrics for quote service operations"
    }