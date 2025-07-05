# Agent 05: Quote Service Developer

## YOUR MISSION

Implement comprehensive quote business logic with multi-step wizard support, real-time pricing, versioning, and conversion workflows.

## NO SILENT FALLBACKS PRINCIPLE

### Quote Service Configuration Requirements

**NEVER use default policy types when not specified:**

```python
# ❌ FORBIDDEN: Assume policy type when missing
class QuoteService:
    async def create_quote(self, quote_data: dict) -> Result[Quote, str]:
        product_type = quote_data.get("product_type", "auto")  # Silent default
        # Creates quote without explicit product validation

# ✅ REQUIRED: Explicit policy type validation
class QuoteService:
    async def create_quote(self, quote_data: QuoteCreate) -> Result[Quote, str]:
        if not quote_data.product_type:
            return Err("Product type required: must be 'auto', 'home', or 'commercial'")

        if quote_data.product_type not in SUPPORTED_PRODUCT_TYPES:
            return Err(f"Unsupported product type: {quote_data.product_type}")

        # Validate product-specific requirements
        validation = await self._validate_product_requirements(quote_data)
        if validation.is_err():
            return validation
```

**NEVER implement silent quote validation workflows:**

```python
# ❌ FORBIDDEN: Skip validation steps silently
async def validate_quote_data(self, data) -> bool:
    # Skips validation if external service is down
    try:
        await external_validation_service.validate(data)
    except Exception:
        return True  # Silent pass when service unavailable

# ✅ REQUIRED: Explicit validation requirements
async def validate_quote_data(self, data: QuoteCreate) -> Result[bool, str]:
    required_validators = [
        ("customer_eligibility", self._validate_customer_eligibility),
        ("state_regulations", self._validate_state_regulations),
        ("product_rules", self._validate_product_rules),
        ("underwriting_rules", self._validate_underwriting_rules)
    ]

    for validator_name, validator in required_validators:
        result = await validator(data)
        if result.is_err():
            return Err(f"Validation failed - {validator_name}: {result.error}")

        if not result.value:
            return Err(f"Validation failed - {validator_name}: requirements not met")

    return Ok(True)
```

**NEVER use silent quote-to-policy conversion rules:**

```python
# ❌ FORBIDDEN: Implicit conversion behavior
class QuoteService:
    async def convert_to_policy(self, quote_id: UUID) -> Policy:
        quote = await self.get_quote(quote_id)
        # Assumes conversion rules based on quote status
        if quote.status == "quoted":
            return await self._create_policy(quote)  # No explicit validation

# ✅ REQUIRED: Explicit conversion validation
class QuoteService:
    async def convert_to_policy(
        self,
        quote_id: UUID,
        conversion_request: QuoteConversionRequest
    ) -> Result[Policy, str]:
        # Explicit validation chain
        validations = [
            self._validate_quote_convertible(quote_id),
            self._validate_payment_authorization(conversion_request.payment),
            self._validate_effective_date(conversion_request.effective_date),
            self._validate_state_filing_requirements(quote_id),
            self._validate_underwriting_approval(quote_id)
        ]

        for validation in validations:
            result = await validation
            if result.is_err():
                return result

        # Explicit conversion with audit trail
        return await self._execute_conversion_with_audit(
            quote_id,
            conversion_request
        )
```

### Fail Fast Validation

If ANY quote business rule is not explicitly configured, you MUST:

1. **Document the specific business rule** that applies
2. **Implement explicit validation** for the rule
3. **Never proceed** with assumed behavior
4. **Return detailed error** explaining what configuration is needed

### Explicit Error Remediation

**When quote validation fails:**

- Never auto-correct invalid data silently
- Always return Result[T, E] with specific error details
- Provide exact steps needed to fix validation failure
- Log validation failures for business rule refinement

**Required validation for quote operations:**

- State-specific insurance regulations compliance
- Product-specific underwriting rules verification
- Customer eligibility and risk assessment completion
- Pricing calculation validation with audit trail
- Policy conversion authorization and payment verification

## MANDATORY PRE-WORK

1. Read ALL documents listed in AGENT_TEMPLATE.md FIRST
2. Specifically study:
   - Agent 04's quote models (coordinate closely)
   - `src/pd_prime_demo/services/policy_service.py` for service patterns
   - `src/pd_prime_demo/services/result.py` for Result[T, E] pattern
   - `.sage/source_documents/DEMO_OVERALL_PRD.md` for quote requirements

## SPECIFIC TASKS

### 1. Create Quote Service (`src/pd_prime_demo/services/quote_service.py`)

```python
"""Quote generation and management service."""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional, List
from uuid import UUID, uuid4

import asyncpg
from beartype import beartype

from ..core.cache import Cache
from ..core.database import Database
from ..models.quote import (
    Quote, QuoteCreate, QuoteUpdate, QuoteStatus,
    VehicleInfo, DriverInfo, CoverageSelection, Discount
)
from .result import Err, Ok, Result
from .rating_engine import RatingEngine  # From Agent 06


class QuoteService:
    """Service for quote generation and management."""

    def __init__(
        self,
        db: Database,
        cache: Cache,
        rating_engine: RatingEngine,
    ) -> None:
        """Initialize quote service."""
        self._db = db
        self._cache = cache
        self._rating_engine = rating_engine
        self._cache_prefix = "quote:"
        self._cache_ttl = 3600  # 1 hour

    @beartype
    async def create_quote(
        self,
        quote_data: QuoteCreate,
        user_id: Optional[UUID] = None,
    ) -> Result[Quote, str]:
        """Create a new quote with initial calculations."""
        try:
            # Validate business rules
            validation = await self._validate_quote_data(quote_data)
            if isinstance(validation, Err):
                return validation

            # Generate quote number
            quote_number = await self._generate_quote_number()

            # Start with draft status
            status = QuoteStatus.DRAFT

            # Set expiration (30 days default)
            expires_at = datetime.now() + timedelta(days=30)

            # Begin transaction
            async with self._db.transaction():
                # Insert quote
                query = """
                    INSERT INTO quotes (
                        quote_number, customer_id, status, product_type,
                        state, zip_code, effective_date, vehicle_info,
                        drivers, coverage_selections, expires_at,
                        created_by, email, phone, preferred_contact
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                        $11, $12, $13, $14, $15
                    ) RETURNING *
                """

                row = await self._db.fetchrow(
                    query,
                    quote_number,
                    quote_data.customer_id,
                    status,
                    quote_data.product_type,
                    quote_data.state,
                    quote_data.zip_code,
                    quote_data.effective_date,
                    quote_data.vehicle_info.model_dump() if quote_data.vehicle_info else None,
                    [d.model_dump() for d in quote_data.drivers],
                    [c.model_dump() for c in quote_data.coverage_selections],
                    expires_at,
                    user_id,
                    quote_data.email,
                    quote_data.phone,
                    quote_data.preferred_contact,
                )

                if not row:
                    return Err("Failed to create quote")

                quote = self._row_to_quote(row)

                # Start async calculation
                asyncio.create_task(
                    self._calculate_quote_async(quote.id)
                )

                # Track analytics event
                await self._track_quote_created(quote)

                return Ok(quote)

        except asyncpg.UniqueViolationError:
            return Err(f"Quote number {quote_number} already exists")
        except Exception as e:
            return Err(f"Database error: {str(e)}")

    @beartype
    async def calculate_quote(self, quote_id: UUID) -> Result[Quote, str]:
        """Calculate or recalculate quote pricing."""
        try:
            # Get quote
            quote_result = await self.get_quote(quote_id)
            if isinstance(quote_result, Err):
                return quote_result

            quote = quote_result.unwrap()
            if not quote:
                return Err("Quote not found")

            # Update status
            await self._update_quote_status(quote_id, QuoteStatus.CALCULATING)

            # Calculate rating
            rating_result = await self._rating_engine.calculate_premium(
                state=quote.state,
                product_type=quote.product_type,
                vehicle_info=quote.vehicle_info,
                drivers=quote.drivers,
                coverage_selections=quote.coverage_selections,
                customer_id=quote.customer_id,
            )

            if isinstance(rating_result, Err):
                await self._update_quote_status(quote_id, QuoteStatus.DRAFT)
                return rating_result

            rating = rating_result.unwrap()

            # Update quote with pricing
            update_query = """
                UPDATE quotes SET
                    base_premium = $2,
                    total_premium = $3,
                    monthly_premium = $4,
                    discounts_applied = $5,
                    surcharges_applied = $6,
                    total_discount_amount = $7,
                    total_surcharge_amount = $8,
                    rating_factors = $9,
                    rating_tier = $10,
                    ai_risk_score = $11,
                    ai_risk_factors = $12,
                    status = $13,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $1
                RETURNING *
            """

            # Calculate monthly (10% down + 9 payments)
            down_payment = rating.total_premium * Decimal('0.10')
            monthly = (rating.total_premium - down_payment) / 9

            row = await self._db.fetchrow(
                update_query,
                quote_id,
                rating.base_premium,
                rating.total_premium,
                monthly.quantize(Decimal('0.01')),
                [d.model_dump() for d in rating.discounts],
                rating.surcharges,
                rating.total_discount_amount,
                rating.total_surcharge_amount,
                rating.factors,
                rating.tier,
                rating.ai_risk_score,
                rating.ai_risk_factors,
                QuoteStatus.QUOTED,
            )

            if not row:
                return Err("Failed to update quote with pricing")

            quote = self._row_to_quote(row)

            # Invalidate cache
            await self._cache.delete(f"{self._cache_prefix}{quote_id}")

            # Track pricing event
            await self._track_quote_priced(quote)

            # Send real-time update
            await self._send_realtime_update(quote)

            return Ok(quote)

        except Exception as e:
            return Err(f"Calculation error: {str(e)}")

    @beartype
    async def update_quote(
        self,
        quote_id: UUID,
        update_data: QuoteUpdate,
        user_id: Optional[UUID] = None,
    ) -> Result[Quote, str]:
        """Update quote and create new version if needed."""
        try:
            # Get existing quote
            existing_result = await self.get_quote(quote_id)
            if isinstance(existing_result, Err):
                return existing_result

            existing = existing_result.unwrap()
            if not existing:
                return Err("Quote not found")

            # Check if quote is editable
            if existing.status in [QuoteStatus.BOUND, QuoteStatus.EXPIRED]:
                return Err(f"Cannot update quote in {existing.status} status")

            # Determine if we need a new version
            needs_new_version = self._requires_new_version(existing, update_data)

            if needs_new_version:
                # Create new version
                return await self._create_quote_version(existing, update_data, user_id)
            else:
                # Update in place
                return await self._update_quote_inplace(quote_id, update_data, user_id)

        except Exception as e:
            return Err(f"Update error: {str(e)}")

    @beartype
    async def convert_to_policy(
        self,
        quote_id: UUID,
        payment_info: dict[str, Any],
        user_id: Optional[UUID] = None,
    ) -> Result[dict[str, Any], str]:
        """Convert quote to policy."""
        try:
            # Get quote
            quote_result = await self.get_quote(quote_id)
            if isinstance(quote_result, Err):
                return quote_result

            quote = quote_result.unwrap()
            if not quote:
                return Err("Quote not found")

            # Validate quote can be converted
            if quote.status != QuoteStatus.QUOTED:
                return Err(f"Quote must be in QUOTED status, current: {quote.status}")

            if quote.is_expired:
                return Err("Quote has expired")

            if not quote.total_premium:
                return Err("Quote has no pricing")

            # Process payment (mock for now)
            payment_result = await self._process_payment(payment_info, quote.total_premium)
            if isinstance(payment_result, Err):
                return payment_result

            # Create policy
            policy_data = {
                "customer_id": quote.customer_id,
                "quote_id": quote.id,
                "policy_type": quote.product_type,
                "premium_amount": quote.total_premium,
                "coverage_amount": self._calculate_coverage_amount(quote),
                "deductible": self._get_primary_deductible(quote),
                "effective_date": quote.effective_date,
                "expiration_date": quote.effective_date + timedelta(days=365),
            }

            # Call PolicyService to create policy
            # This would be injected dependency
            # policy_result = await self._policy_service.create_from_quote(policy_data)

            # For now, mock the policy creation
            policy_id = uuid4()

            # Update quote status
            await self._db.execute(
                """
                UPDATE quotes SET
                    status = $2,
                    converted_to_policy_id = $3,
                    converted_at = $4,
                    updated_by = $5,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                quote_id,
                QuoteStatus.BOUND,
                policy_id,
                datetime.now(),
                user_id,
            )

            # Track conversion
            await self._track_quote_converted(quote, policy_id)

            return Ok({
                "quote_id": quote_id,
                "policy_id": policy_id,
                "policy_number": f"POL-{datetime.now().year}-{policy_id.hex[:6].upper()}",
                "effective_date": quote.effective_date,
                "premium": quote.total_premium,
            })

        except Exception as e:
            return Err(f"Conversion error: {str(e)}")

    @beartype
    async def get_quote(self, quote_id: UUID) -> Result[Optional[Quote], str]:
        """Get quote by ID with caching."""
        # Check cache first
        cache_key = f"{self._cache_prefix}{quote_id}"
        cached = await self._cache.get(cache_key)
        if cached:
            return Ok(Quote(**cached))

        # Query database
        query = "SELECT * FROM quotes WHERE id = $1"
        row = await self._db.fetchrow(query, quote_id)

        if not row:
            return Ok(None)

        quote = self._row_to_quote(row)

        # Cache the result
        await self._cache.set(
            cache_key,
            quote.model_dump(mode="json"),
            self._cache_ttl,
        )

        return Ok(quote)

    @beartype
    async def search_quotes(
        self,
        customer_id: Optional[UUID] = None,
        status: Optional[QuoteStatus] = None,
        state: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Result[List[Quote], str]:
        """Search quotes with filters."""
        query_parts = ["SELECT * FROM quotes WHERE 1=1"]
        params: list[Any] = []
        param_count = 0

        if customer_id:
            param_count += 1
            query_parts.append(f"AND customer_id = ${param_count}")
            params.append(customer_id)

        if status:
            param_count += 1
            query_parts.append(f"AND status = ${param_count}")
            params.append(status)

        if state:
            param_count += 1
            query_parts.append(f"AND state = ${param_count}")
            params.append(state)

        if created_after:
            param_count += 1
            query_parts.append(f"AND created_at >= ${param_count}")
            params.append(created_after)

        if created_before:
            param_count += 1
            query_parts.append(f"AND created_at <= ${param_count}")
            params.append(created_before)

        query_parts.append("ORDER BY created_at DESC")

        param_count += 1
        query_parts.append(f"LIMIT ${param_count}")
        params.append(limit)

        param_count += 1
        query_parts.append(f"OFFSET ${param_count}")
        params.append(offset)

        query = " ".join(query_parts)
        rows = await self._db.fetch(query, *params)

        quotes = [self._row_to_quote(row) for row in rows]
        return Ok(quotes)

    @beartype
    async def _generate_quote_number(self) -> str:
        """Generate unique quote number."""
        year = datetime.now().year

        # Get next sequence number
        sequence = await self._db.fetchval(
            """
            INSERT INTO quote_sequences (year, last_number)
            VALUES ($1, 1)
            ON CONFLICT (year) DO UPDATE
            SET last_number = quote_sequences.last_number + 1
            RETURNING last_number
            """,
            year,
        )

        return f"QUOT-{year}-{sequence:06d}"

    # ... Additional helper methods ...
```

### 2. Create Quote Wizard State Manager (`src/pd_prime_demo/services/quote_wizard.py`)

```python
"""Multi-step quote wizard state management."""

from typing import Any, Optional, Dict, List
from uuid import UUID
from datetime import datetime, timedelta

from beartype import beartype
from pydantic import BaseModel, Field

from ..core.cache import Cache
from .result import Result, Ok, Err


class WizardStep(BaseModel):
    """Individual wizard step configuration."""

    step_id: str
    title: str
    description: str
    fields: List[str]
    validations: Dict[str, Any]
    next_step: Optional[str]
    previous_step: Optional[str]


class WizardState(BaseModel):
    """Current state of quote wizard."""

    session_id: UUID
    quote_id: Optional[UUID]
    current_step: str
    completed_steps: List[str]
    data: Dict[str, Any]
    started_at: datetime
    last_updated: datetime
    expires_at: datetime


class QuoteWizardService:
    """Manage multi-step quote wizard state."""

    def __init__(self, cache: Cache) -> None:
        """Initialize wizard service."""
        self._cache = cache
        self._cache_prefix = "wizard:"
        self._session_ttl = 3600  # 1 hour

        # Define wizard flow
        self._steps = {
            "start": WizardStep(
                step_id="start",
                title="Get Started",
                description="Basic information about your insurance needs",
                fields=["product_type", "state", "zip_code"],
                validations={"state": "required|in:CA,TX,NY"},
                next_step="customer",
                previous_step=None,
            ),
            "customer": WizardStep(
                step_id="customer",
                title="About You",
                description="Tell us about yourself",
                fields=["email", "phone", "date_of_birth"],
                validations={"email": "required|email"},
                next_step="vehicle",
                previous_step="start",
            ),
            "vehicle": WizardStep(
                step_id="vehicle",
                title="Vehicle Information",
                description="Details about your vehicle",
                fields=["vin", "year", "make", "model", "annual_mileage"],
                validations={"vin": "required|length:17"},
                next_step="drivers",
                previous_step="customer",
            ),
            "drivers": WizardStep(
                step_id="drivers",
                title="Driver Information",
                description="Who will be driving?",
                fields=["drivers"],
                validations={"drivers": "required|min:1"},
                next_step="coverage",
                previous_step="vehicle",
            ),
            "coverage": WizardStep(
                step_id="coverage",
                title="Coverage Selection",
                description="Choose your coverage levels",
                fields=["coverage_selections"],
                validations={"coverage_selections": "required|min:1"},
                next_step="review",
                previous_step="drivers",
            ),
            "review": WizardStep(
                step_id="review",
                title="Review Quote",
                description="Review and get your price",
                fields=[],
                validations={},
                next_step=None,
                previous_step="coverage",
            ),
        }

    @beartype
    async def start_session(self) -> Result[WizardState, str]:
        """Start a new wizard session."""
        session_id = uuid4()

        state = WizardState(
            session_id=session_id,
            quote_id=None,
            current_step="start",
            completed_steps=[],
            data={},
            started_at=datetime.now(),
            last_updated=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=self._session_ttl),
        )

        # Save to cache
        cache_key = f"{self._cache_prefix}{session_id}"
        await self._cache.set(
            cache_key,
            state.model_dump_json(),
            self._session_ttl,
        )

        return Ok(state)
```

### 3. Create Quote API Endpoints (`src/pd_prime_demo/api/v1/quotes.py`)

Implement comprehensive REST endpoints for the quote system.

## SEARCH TRIGGERS (30-second timeout)

If confidence < 95% on:

- Quote workflows → Search: "insurance quote generation best practices"
- Wizard patterns → Search: "multi-step form state management"
- Async patterns → Search: "python asyncio task management"

## DELIVERABLES

1. **Quote Service**: Full CRUD + business logic
2. **Wizard Service**: Multi-step state management
3. **API Endpoints**: Complete REST interface
4. **Real-time Updates**: WebSocket integration hooks
5. **Analytics Tracking**: Event logging

## SUCCESS CRITERIA

1. Quote generation in <2 seconds
2. Wizard state persists across sessions
3. Proper versioning for quote changes
4. Seamless policy conversion
5. Real-time price updates

## PARALLEL COORDINATION

- Agent 04 provides the models you'll use
- Agent 06 provides rating engine
- Agent 08 will add WebSocket support
- Agent 01 creates your database tables

Track all integration points in your progress reports!

## ADDITIONAL REQUIREMENT: Admin Quote Management

**IMPORTANT**: You must ALSO read `.sage/wave_contexts/wave_2/AGENT_DEPLOYMENT_SUMMARY.md` to understand the full system context.

### 4. Create Admin Quote Service Extensions

Add administrative capabilities to the quote service:

#### Extend Quote Service with Admin Methods

```python
# Add these methods to QuoteService class:

@beartype
async def admin_search_quotes(
    self,
    admin_user_id: UUID,
    filters: Dict[str, Any],
    include_pii: bool = False,
) -> Result[List[Quote], str]:
    """Admin search with advanced filters and PII control."""
    # Verify admin permissions
    # Apply complex filters (date ranges, premium ranges, etc.)
    # Optionally mask PII data
    # Log admin access
    pass

@beartype
async def admin_override_quote(
    self,
    quote_id: UUID,
    admin_user_id: UUID,
    override_data: Dict[str, Any],
    reason: str,
) -> Result[Quote, str]:
    """Allow admin to override quote pricing or terms."""
    try:
        # Verify admin has QUOTE_OVERRIDE permission
        # Get existing quote
        # Apply overrides (premium adjustment, coverage changes)
        # Create audit trail
        # Send notification to original agent

        await self._db.execute(
            """
            INSERT INTO quote_admin_overrides
            (quote_id, admin_user_id, override_type, original_value,
             new_value, reason, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            quote_id, admin_user_id, override_data['type'],
            override_data['original'], override_data['new'],
            reason, datetime.now()
        )

        # Recalculate quote with overrides
        return await self.calculate_quote(quote_id)

    except Exception as e:
        return Err(f"Override failed: {str(e)}")

@beartype
async def admin_bulk_operations(
    self,
    admin_user_id: UUID,
    operation: str,
    quote_ids: List[UUID],
    parameters: Dict[str, Any],
) -> Result[Dict[str, Any], str]:
    """Perform bulk operations on quotes."""
    # Operations: expire, extend, recalculate, export
    # Verify permissions
    # Execute in batches
    # Track progress
    # Return summary
    pass

@beartype
async def get_quote_analytics(
    self,
    date_from: datetime,
    date_to: datetime,
    group_by: str = "day",
) -> Result[Dict[str, Any], str]:
    """Get quote analytics for admin dashboards."""
    query = """
        WITH quote_metrics AS (
            SELECT
                date_trunc($1, created_at) as period,
                COUNT(*) as total_quotes,
                COUNT(DISTINCT customer_id) as unique_customers,
                COUNT(*) FILTER (WHERE status = 'quoted') as completed_quotes,
                COUNT(*) FILTER (WHERE status = 'bound') as converted_quotes,
                AVG(total_premium) as avg_premium,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_premium) as median_premium,
                SUM(total_premium) FILTER (WHERE status = 'bound') as bound_premium
            FROM quotes
            WHERE created_at BETWEEN $2 AND $3
            GROUP BY period
        )
        SELECT * FROM quote_metrics ORDER BY period
    """

    results = await self._db.fetch(query, group_by, date_from, date_to)

    return Ok({
        "metrics": [dict(row) for row in results],
        "summary": {
            "total_quotes": sum(r['total_quotes'] for r in results),
            "conversion_rate": self._calculate_conversion_rate(results),
            "average_premium": self._calculate_avg_premium(results),
        }
    })
```

### 5. Create Admin Quote Endpoints (`src/pd_prime_demo/api/v1/admin/quotes.py`)

```python
"""Admin quote management endpoints."""

from fastapi import APIRouter, Depends, Query
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID

from beartype import beartype

from ....services.quote_service import QuoteService
from ....models.quote import Quote
from ...dependencies import get_quote_service, get_current_admin_user
from ....models.admin import AdminUser

router = APIRouter()


@router.get("/search", response_model=List[Quote])
@beartype
async def admin_search_quotes(
    # Search filters
    status: Optional[str] = None,
    state: Optional[str] = None,
    min_premium: Optional[float] = None,
    max_premium: Optional[float] = None,
    created_after: Optional[datetime] = None,
    created_before: Optional[datetime] = None,
    customer_email: Optional[str] = None,

    # Pagination
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),

    # PII control
    include_pii: bool = Query(False),

    # Dependencies
    quote_service: QuoteService = Depends(get_quote_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> List[Quote]:
    """Search quotes with admin privileges."""
    filters = {
        "status": status,
        "state": state,
        "min_premium": min_premium,
        "max_premium": max_premium,
        "created_after": created_after,
        "created_before": created_before,
        "customer_email": customer_email,
    }

    result = await quote_service.admin_search_quotes(
        admin_user.id,
        filters,
        include_pii,
    )

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)

    return result.value


@router.post("/{quote_id}/override")
@beartype
async def override_quote(
    quote_id: UUID,
    override_request: QuoteOverrideRequest,
    quote_service: QuoteService = Depends(get_quote_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Quote:
    """Override quote pricing or terms."""
    # Check permission
    if "quote:override" not in admin_user.effective_permissions:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await quote_service.admin_override_quote(
        quote_id,
        admin_user.id,
        override_request.override_data,
        override_request.reason,
    )

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)

    return result.value


@router.get("/analytics")
@beartype
async def get_quote_analytics(
    date_from: datetime,
    date_to: datetime,
    group_by: str = Query("day", regex="^(hour|day|week|month)$"),
    quote_service: QuoteService = Depends(get_quote_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """Get quote analytics for dashboards."""
    result = await quote_service.get_quote_analytics(
        date_from,
        date_to,
        group_by,
    )

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)

    return result.value
```

### 6. Add Admin Tables for Quote Management

Tell Agent 01 to also create:

```sql
-- Quote admin overrides tracking
CREATE TABLE quote_admin_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id UUID REFERENCES quotes(id),
    admin_user_id UUID REFERENCES admin_users(id),
    override_type VARCHAR(50) NOT NULL,
    original_value JSONB,
    new_value JSONB,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Quote approval workflow
CREATE TABLE quote_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id UUID REFERENCES quotes(id),
    approval_type VARCHAR(50) NOT NULL, -- 'high_value', 'exception', etc.
    requested_by UUID REFERENCES users(id),
    requested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    reviewed_by UUID REFERENCES admin_users(id),
    reviewed_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
    notes TEXT
);
```

Make sure all admin operations are properly logged and have permission checks!

## ADDITIONAL GAPS TO WATCH

### Quote Service Business Logic Anti-Patterns and Edge Cases

**Quote Workflow State Validation Failures:**

- **Similar Gap**: Allowing quote status transitions that violate business rules (expired → bound without renewal validation)
- **Lateral Gap**: Not validating quote modification permissions based on user role and quote ownership
- **Inverted Gap**: Over-restrictive state transitions preventing legitimate business operations (emergency policy binding)
- **Meta-Gap**: Not testing quote state transitions under concurrent modification scenarios

**Business Hour Logic Inconsistencies:**

- **Similar Gap**: Quote expiration calculations not accounting for business days vs calendar days in different states
- **Lateral Gap**: Policy effective date validation using local business hours but serving national customer base
- **Inverted Gap**: Ignoring business hours entirely for time-sensitive insurance deadlines
- **Meta-Gap**: Not testing business hour logic across timezone boundaries and holiday schedules

**Effective Date Calculation Edge Cases:**

- **Similar Gap**: Not handling policy effective dates that fall on state holidays when DMV offices are closed
- **Lateral Gap**: Quote effective dates that conflict with claim periods or other policy restrictions
- **Inverted Gap**: Over-flexible effective date rules allowing coverage gaps or overlaps
- **Meta-Gap**: Not validating effective date business rules across different insurance product types

**Quote Version Management Complexity:**

- **Similar Gap**: Quote versioning that loses critical audit trail information during major quote modifications
- **Lateral Gap**: Not handling quote version conflicts when multiple agents modify the same quote simultaneously
- **Inverted Gap**: Creating too many quote versions for minor changes, cluttering quote history
- **Meta-Gap**: Not testing quote version management under high-concurrency agent workflows

**Time-Based Service Operations:**

- **Quote Expiration Processing**: Batch expiration jobs not handling timezone differences for multi-state quotes
- **Real-Time Updates**: Quote change notifications not properly sequenced causing out-of-order updates
- **Renewal Timing**: Quote renewal logic not accounting for state-specific renewal period requirements

**Scale-Based Service Failures:**

- **Bulk Quote Operations**: Admin bulk operations not implementing proper pagination and timeout handling
- **Concurrent Quote Access**: Multiple agents working on same customer quotes without proper coordination
- **Quote Search Performance**: Complex quote search filters not optimized for large quote databases

**Payment and Financial Integration:**

- **Similar Gap**: Quote-to-policy conversion not properly validating payment authorization timing and scope
- **Lateral Gap**: Currency conversion and precision handling for international customers or multi-currency operations
- **Inverted Gap**: Over-strict payment validation preventing legitimate policy binding scenarios

**External Service Dependencies:**

- **Rating Engine Integration**: Not handling rating engine failures gracefully, leaving quotes in calculating state indefinitely
- **Document Generation**: Quote document generation failures not properly rolled back or retried
- **Notification Services**: Failed quote notifications not queued for retry, causing customer communication gaps

**Quote Analytics and Reporting:**

- **Conversion Tracking**: Not properly attributing quote conversions when customers return through different channels
- **Performance Metrics**: Quote service metrics not capturing business-relevant KPIs (time to quote, conversion rates)
- **Data Consistency**: Quote analytics data not staying consistent with quote service data during high-volume periods

**Security and Compliance Integration:**

- **Data Privacy**: Quote PII handling not meeting state-specific privacy requirements
- **Audit Requirements**: Quote modification audit logs not capturing sufficient detail for regulatory compliance
- **Access Control**: Quote access permissions not properly inherited when quotes are transferred between agents

**Integration with Admin Override Systems:**

- **Override Validation**: Admin quote overrides not properly validated against business rule constraints
- **Override Audit**: Admin override actions not creating sufficient audit trail for compliance review
- **Override Scope**: Admin overrides affecting quote calculation consistency across similar customer scenarios
