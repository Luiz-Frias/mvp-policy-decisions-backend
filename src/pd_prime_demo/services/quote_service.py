"""Quote generation and management service."""

import asyncio
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import asyncpg
from beartype import beartype

from pd_prime_demo.core.result_types import Err, Ok, Result

from ..core.cache import Cache
from ..core.database import Database
from ..models.quote import (
    CoverageSelection,
    Discount,
    DriverInfo,
    ProductType,
    Quote,
    QuoteConversionRequest,
    QuoteCreate,
    QuoteOverrideRequest,
    QuoteStatus,
    QuoteUpdate,
    VehicleInfo,
)
from .performance_monitor import performance_monitor

# Optional imports for production features
try:
    from .rating_engine import RatingEngine

    HAS_RATING_ENGINE = True
except ImportError:
    RatingEngine = None  # type: ignore[assignment,misc]
    HAS_RATING_ENGINE = False

try:
    from ..websocket.manager import ConnectionManager

    HAS_WEBSOCKET = True
except ImportError:
    ConnectionManager = None  # type: ignore[assignment,misc]
    HAS_WEBSOCKET = False


class QuoteService:
    """Service for quote generation and management."""

    def __init__(
        self,
        db: Database,
        cache: Cache,
        rating_engine: Any | None = None,  # RatingEngine when available
        websocket_manager: Any | None = None,  # ConnectionManager when available
    ) -> None:
        """Initialize quote service with dependency validation."""
        if not db or not hasattr(db, "execute"):
            raise ValueError("Database connection required and must be active")
        if not cache or not hasattr(cache, "get"):
            raise ValueError("Cache connection required and must be available")

        # CRITICAL: Rating engine is now REQUIRED for production
        # No fallbacks allowed - explicit configuration required
        if rating_engine is None:
            import warnings

            warnings.warn(
                "QuoteService initialized without RatingEngine. "
                "Quote calculations will fail until RatingEngine is configured. "
                "This is only acceptable during initial setup.",
                RuntimeWarning,
                stacklevel=2,
            )

        self._db = db
        self._cache = cache
        self._rating_engine = rating_engine
        self._websocket_manager = websocket_manager
        self._cache_prefix = "quote:"
        self._cache_ttl = 3600  # 1 hour

    @beartype
    @performance_monitor("quote_creation", max_duration_ms=2000)
    async def create_quote(
        self,
        quote_data: QuoteCreate,
        user_id: UUID | None = None,
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
                        created_by, email, phone, preferred_contact,
                        referral_source, version
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb,
                        $10::jsonb, $11, $12, $13, $14, $15, $16, $17
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
                    (
                        quote_data.vehicle_info.model_dump()
                        if quote_data.vehicle_info
                        else None
                    ),
                    [d.model_dump() for d in quote_data.drivers],
                    [c.model_dump() for c in quote_data.coverage_selections],
                    expires_at,
                    user_id,
                    quote_data.email,
                    quote_data.phone,
                    quote_data.preferred_contact,
                    "web",  # Default referral source
                    1,  # Initial version
                )

                if not row:
                    return Err("Failed to create quote")

                quote = self._row_to_quote(row)

                # Start async calculation if we have vehicle info and drivers
                if quote_data.vehicle_info and quote_data.drivers:
                    asyncio.create_task(self._calculate_quote_async(quote.id))

                # Track analytics event
                await self._track_quote_created(quote)

                return Ok(quote)

        except asyncpg.UniqueViolationError:
            return Err(f"Quote number {quote_number} already exists")
        except Exception as e:
            return Err(f"Database error: {str(e)}")

    @beartype
    @performance_monitor("quote_calculation", max_duration_ms=1000)
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

            # Initialize rating engine if available
            if self._rating_engine and not getattr(
                self._rating_engine, "_initialized", False
            ):
                init_result = await self._rating_engine.initialize()
                if isinstance(init_result, Err):
                    await self._update_quote_status(quote_id, QuoteStatus.DRAFT)
                    return init_result
                self._rating_engine._initialized = True

            # ALWAYS require rating engine - NO FALLBACKS
            if not self._rating_engine:
                return Err(
                    "Rating engine not configured. "
                    "Service must be initialized with RatingEngine instance. "
                    "Contact system administrator to configure rating service."
                )

            # Calculate rating using actual engine
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

            rating_obj = rating_result.unwrap()
            # Convert RatingResult to dict for consistency
            rating = {
                "base_premium": rating_obj.base_premium,
                "total_premium": rating_obj.total_premium,
                "discounts": [d.model_dump() for d in rating_obj.discounts],
                "surcharges": rating_obj.surcharges,
                "total_discount_amount": rating_obj.total_discount_amount,
                "total_surcharge_amount": rating_obj.total_surcharge_amount,
                "factors": rating_obj.rating_factors.model_dump(),  # Convert structured model to dict
                "tier": rating_obj.tier,
                "ai_risk_score": rating_obj.ai_risk_score,
                "ai_risk_factors": rating_obj.ai_risk_factors,
            }

            # Calculate monthly (10% down + 9 payments)
            down_payment = rating["total_premium"] * Decimal("0.10")
            monthly = (rating["total_premium"] - down_payment) / 9

            # Update quote with pricing
            update_query = """
                UPDATE quotes SET
                    base_premium = $2,
                    total_premium = $3,
                    monthly_premium = $4,
                    discounts_applied = $5::jsonb,
                    surcharges_applied = $6::jsonb,
                    total_discount_amount = $7,
                    total_surcharge_amount = $8,
                    rating_factors = $9::jsonb,
                    rating_tier = $10,
                    ai_risk_score = $11,
                    ai_risk_factors = $12::jsonb,
                    status = $13,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $1
                RETURNING *
            """

            row = await self._db.fetchrow(
                update_query,
                quote_id,
                rating["base_premium"],
                rating["total_premium"],
                monthly.quantize(Decimal("0.01")),
                rating.get("discounts", []),
                rating.get("surcharges", []),
                rating.get("total_discount_amount", Decimal("0")),
                rating.get("total_surcharge_amount", Decimal("0")),
                rating.get("factors", {}),
                rating.get("tier", "STANDARD"),
                rating.get("ai_risk_score"),
                rating.get("ai_risk_factors", {}),
                QuoteStatus.QUOTED,
            )

            if not row:
                return Err("Failed to update quote with pricing")

            quote = self._row_to_quote(row)

            # Invalidate cache
            await self._cache.delete(f"{self._cache_prefix}{quote_id}")

            # Track pricing event
            await self._track_quote_priced(quote)

            # Send real-time update (placeholder for WebSocket)
            await self._send_realtime_update(quote)

            return Ok(quote)

        except Exception as e:
            return Err(f"Calculation error: {str(e)}")

    @beartype
    @performance_monitor("update_quote")
    async def update_quote(
        self,
        quote_id: UUID,
        update_data: QuoteUpdate,
        user_id: UUID | None = None,
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
    @performance_monitor("quote_conversion", max_duration_ms=3000)
    async def convert_to_policy(
        self,
        quote_id: UUID,
        conversion_request: QuoteConversionRequest,
        user_id: UUID | None = None,
    ) -> Ok[dict[str, Any]] | Err[str]:
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
            validation = self._validate_quote_conversion(quote)
            if isinstance(validation, Err):
                return validation

            # Process payment (mock for now)
            if quote.total_premium is None:
                return Err("Quote has no total premium")
            payment_result = await self._process_payment(
                conversion_request, quote.total_premium
            )
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
                "effective_date": conversion_request.effective_date
                or quote.effective_date,
                "expiration_date": (
                    conversion_request.effective_date or quote.effective_date
                )
                + timedelta(days=365),
                "payment_info": payment_result.unwrap(),
            }

            # Generate policy number
            policy_id = uuid4()
            policy_number = f"POL-{datetime.now().year}-{policy_id.hex[:6].upper()}"

            # Update quote status in transaction
            async with self._db.transaction():
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

            # Invalidate cache
            await self._cache.delete(f"{self._cache_prefix}{quote_id}")

            return Ok(
                {
                    "quote_id": quote_id,
                    "policy_id": policy_id,
                    "policy_number": policy_number,
                    "effective_date": policy_data["effective_date"],
                    "premium": quote.total_premium,
                    "payment_confirmation": payment_result.unwrap(),
                }
            )

        except Exception as e:
            return Err(f"Conversion error: {str(e)}")

    @beartype
    @performance_monitor("get_quote")
    async def get_quote(self, quote_id: UUID) -> Result[Quote | None, str]:
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
    @performance_monitor("search_quotes")
    async def search_quotes(
        self,
        customer_id: UUID | None = None,
        status: QuoteStatus | None = None,
        state: str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Ok[list[Quote]] | Err[str]:
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
            params.append(str(created_after))

        if created_before:
            param_count += 1
            query_parts.append(f"AND created_at <= ${param_count}")
            params.append(str(created_before))

        query_parts.append("ORDER BY created_at DESC")

        param_count += 1
        query_parts.append(f"LIMIT ${param_count}")
        params.append(str(limit))

        param_count += 1
        query_parts.append(f"OFFSET ${param_count}")
        params.append(str(offset))

        query = " ".join(query_parts)
        rows = await self._db.fetch(query, *params)

        quotes = [self._row_to_quote(row) for row in rows]
        return Ok(quotes)

    @beartype
    @performance_monitor("admin_search_quotes")
    async def admin_search_quotes(
        self,
        admin_user_id: UUID,
        filters: dict[str, Any],
        include_pii: bool = False,
    ) -> Result[list[Quote], str]:
        """Admin search with advanced filters and PII control."""
        # Verify admin permissions
        admin_check = await self._verify_admin_permissions(
            admin_user_id, "quote:admin_search"
        )
        if isinstance(admin_check, Err):
            return admin_check

        query_parts = ["SELECT * FROM quotes WHERE 1=1"]
        params: list[Any] = []
        param_count = 0

        # Apply filters
        for key, value in filters.items():
            if value is None:
                continue

            param_count += 1
            if key == "min_premium":
                query_parts.append(f"AND total_premium >= ${param_count}")
                params.append(value)
            elif key == "max_premium":
                query_parts.append(f"AND total_premium <= ${param_count}")
                params.append(value)
            elif key == "customer_email":
                query_parts.append(f"AND email ILIKE ${param_count}")
                params.append(f"%{value}%")
            elif key in ["status", "state", "created_after", "created_before"]:
                op = ">=" if "after" in key else "<=" if "before" in key else "="
                field = "created_at" if "created" in key else key
                query_parts.append(f"AND {field} {op} ${param_count}")
                params.append(value)

        query_parts.append("ORDER BY created_at DESC LIMIT 100")

        query = " ".join(query_parts)
        rows = await self._db.fetch(query, *params)

        quotes = []
        for row in rows:
            quote = self._row_to_quote(row)
            if not include_pii:
                # Mask PII data
                quote = self._mask_quote_pii(quote)
            quotes.append(quote)

        # Log admin access
        await self._log_admin_access(admin_user_id, "quote_search", len(quotes))

        return Ok(quotes)

    @beartype
    @performance_monitor("admin_override_quote")
    async def admin_override_quote(
        self,
        quote_id: UUID,
        admin_user_id: UUID,
        override_request: QuoteOverrideRequest,
    ) -> Result[Quote, str]:
        """Allow admin to override quote pricing or terms."""
        try:
            # Get existing quote
            quote_result = await self.get_quote(quote_id)
            if isinstance(quote_result, Err):
                return quote_result

            quote = quote_result.unwrap()
            if not quote:
                return Err("Quote not found")

            # Create audit trail
            async with self._db.transaction():
                await self._db.execute(
                    """
                    INSERT INTO quote_admin_overrides
                    (quote_id, admin_user_id, override_type, original_value,
                     new_value, reason, created_at)
                    VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6, $7)
                    """,
                    quote_id,
                    admin_user_id,
                    override_request.override_type,
                    override_request.override_data.original_value,
                    override_request.override_data.new_value,
                    override_request.reason,
                    datetime.now(),
                )

                # Apply override based on type
                if override_request.override_type == "premium":
                    new_premium = Decimal(str(override_request.override_data.new_value))
                    await self._db.execute(
                        """
                        UPDATE quotes SET
                            total_premium = $2,
                            monthly_premium = $3,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = $1
                        """,
                        quote_id,
                        new_premium,
                        (new_premium * Decimal("0.9") / 9).quantize(Decimal("0.01")),
                    )

            # Invalidate cache
            await self._cache.delete(f"{self._cache_prefix}{quote_id}")

            # Get updated quote
            updated_result = await self.get_quote(quote_id)
            if isinstance(updated_result, Err):
                return updated_result

            updated_quote = updated_result.unwrap()
            if not updated_quote:
                return Err("Quote not found after override")

            return Ok(updated_quote)

        except Exception as e:
            return Err(f"Override failed: {str(e)}")

    @beartype
    @performance_monitor("get_quote_analytics")
    async def get_quote_analytics(
        self,
        date_from: datetime,
        date_to: datetime,
        group_by: str = "day",
    ) -> Ok[dict[str, Any]] | Err[str]:
        """Get quote analytics for admin dashboards."""
        query = """
            WITH quote_metrics AS (
                SELECT
                    date_trunc($1, created_at) as period,
                    COUNT(*) as total_quotes,
                    COUNT(DISTINCT customer_id) as unique_customers,
                    COUNT(*) FILTER (WHERE status = 'QUOTED') as completed_quotes,
                    COUNT(*) FILTER (WHERE status = 'BOUND') as converted_quotes,
                    AVG(total_premium) as avg_premium,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_premium) as median_premium,
                    SUM(total_premium) FILTER (WHERE status = 'BOUND') as bound_premium
                FROM quotes
                WHERE created_at BETWEEN $2 AND $3
                GROUP BY period
            )
            SELECT * FROM quote_metrics ORDER BY period
        """

        rows = await self._db.fetch(query, group_by, date_from, date_to)

        results = [dict(row) for row in rows]

        # Calculate summary metrics
        total_quotes = sum(r["total_quotes"] for r in results)
        converted_quotes = sum(r["converted_quotes"] for r in results)

        return Ok(
            {
                "metrics": results,
                "summary": {
                    "total_quotes": total_quotes,
                    "conversion_rate": (
                        converted_quotes / total_quotes if total_quotes > 0 else 0
                    ),
                    "average_premium": (
                        sum(r["avg_premium"] or 0 for r in results) / len(results)
                        if results
                        else 0
                    ),
                    "total_bound_premium": sum(
                        r["bound_premium"] or 0 for r in results
                    ),
                },
            }
        )

    # Private helper methods

    @beartype
    @performance_monitor("generate_quote_number")
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

    @beartype
    @performance_monitor("validate_quote_data")
    async def _validate_quote_data(self, quote_data: QuoteCreate) -> Result[None, str]:
        """Validate quote business rules."""
        # Check state support
        supported_states = ["CA", "TX", "NY"]  # Demo states
        if quote_data.state not in supported_states:
            return Err(
                f"State {quote_data.state} not supported. Available: {', '.join(supported_states)}"
            )

        # Check effective date
        today = date.today()
        max_future_date = today + timedelta(days=60)

        if quote_data.effective_date < today:
            return Err("Effective date cannot be in the past")

        if quote_data.effective_date > max_future_date:
            return Err("Effective date cannot be more than 60 days in the future")

        # Product-specific validation
        if quote_data.product_type == ProductType.AUTO:
            if not quote_data.vehicle_info:
                return Err("Vehicle information required for auto quotes")
            if not quote_data.drivers:
                return Err("At least one driver required for auto quotes")
            if not quote_data.coverage_selections:
                return Err("Coverage selections required for auto quotes")

        return Ok(None)

    # REMOVED: _mock_calculate_premium - NO MOCK DATA ALLOWED
    # All calculations MUST use real RatingEngine with database-backed rate tables

    @beartype
    @performance_monitor("requires_new_version")
    def _requires_new_version(self, existing: Quote, update: QuoteUpdate) -> bool:
        """Determine if update requires new version."""
        # Major changes that require versioning
        if update.vehicle_info and existing.vehicle_info:
            # Changed vehicle
            if (
                update.vehicle_info.vin != existing.vehicle_info.vin
                or update.vehicle_info.year != existing.vehicle_info.year
            ):
                return True

        if update.drivers and len(update.drivers) != len(existing.drivers):
            return True

        if update.coverage_selections:
            # Major coverage changes
            existing_types = {c.coverage_type for c in existing.coverage_selections}
            new_types = {c.coverage_type for c in update.coverage_selections}
            if existing_types != new_types:
                return True

        return False

    @beartype
    @performance_monitor("create_quote_version")
    async def _create_quote_version(
        self, existing: Quote, update_data: QuoteUpdate, user_id: UUID | None
    ) -> Result[Quote, str]:
        """Create new version of quote."""
        # Create new quote with updated data
        new_quote_data = QuoteCreate(
            customer_id=existing.customer_id,
            product_type=existing.product_type,
            state=existing.state,
            zip_code=existing.zip_code,
            effective_date=update_data.effective_date or existing.effective_date,
            email=update_data.email or existing.email,
            phone=update_data.phone or existing.phone,
            preferred_contact=update_data.preferred_contact
            or existing.preferred_contact,
            vehicle_info=update_data.vehicle_info or existing.vehicle_info,
            drivers=update_data.drivers or existing.drivers,
            coverage_selections=update_data.coverage_selections
            or existing.coverage_selections,
        )

        # Create new quote
        result = await self.create_quote(new_quote_data, user_id)
        if isinstance(result, Err):
            return result

        new_quote = result.unwrap()

        # Update version info
        await self._db.execute(
            """
            UPDATE quotes SET
                version = $2,
                parent_quote_id = $3
            WHERE id = $1
            """,
            new_quote.id,
            existing.version + 1,
            existing.id,
        )

        # Get the new quote with updated version
        new_result = await self.get_quote(new_quote.id)
        if isinstance(new_result, Err):
            return new_result

        new_quote_updated = new_result.unwrap()
        if not new_quote_updated:
            return Err("New quote not found after version creation")

        return Ok(new_quote_updated)

    @beartype
    @performance_monitor("update_quote_inplace")
    async def _update_quote_inplace(
        self, quote_id: UUID, update_data: QuoteUpdate, user_id: UUID | None
    ) -> Result[Quote, str]:
        """Update quote in place for minor changes."""
        update_parts = []
        params: list[Any] = [quote_id]
        param_count = 1

        if update_data.email:
            param_count += 1
            update_parts.append(f"email = ${param_count}")
            params.append(update_data.email)

        if update_data.phone:
            param_count += 1
            update_parts.append(f"phone = ${param_count}")
            params.append(update_data.phone)

        if update_data.preferred_contact:
            param_count += 1
            update_parts.append(f"preferred_contact = ${param_count}")
            params.append(update_data.preferred_contact)

        if update_data.effective_date:
            param_count += 1
            update_parts.append(f"effective_date = ${param_count}")
            params.append(str(update_data.effective_date))

        if user_id:
            param_count += 1
            update_parts.append(f"updated_by = ${param_count}")
            params.append(user_id)

        update_parts.append("updated_at = CURRENT_TIMESTAMP")
        update_parts.append("status = 'DRAFT'")  # Reset to draft

        # Safe query construction - update_parts are built from trusted column names
        query = (
            """
            UPDATE quotes SET
                """
            + ", ".join(update_parts)
            + """
            WHERE id = $1
            RETURNING *
        """
        )

        row = await self._db.fetchrow(query, *params)
        if not row:
            return Err("Failed to update quote")

        # Invalidate cache
        await self._cache.delete(f"{self._cache_prefix}{quote_id}")

        return Ok(self._row_to_quote(row))

    @beartype
    @performance_monitor("validate_quote_conversion")
    def _validate_quote_conversion(self, quote: Quote) -> Result[None, str]:
        """Validate quote can be converted to policy."""
        if quote.status != QuoteStatus.QUOTED:
            return Err(f"Quote must be in QUOTED status, current: {quote.status}")

        if quote.is_expired:
            return Err("Quote has expired")

        if not quote.total_premium:
            return Err("Quote has no pricing")

        if quote.total_premium <= 0:
            return Err("Invalid premium amount")

        if not quote.coverage_selections:
            return Err("No coverage selections")

        return Ok(None)

    @beartype
    @performance_monitor("process_payment")
    async def _process_payment(
        self, conversion_request: QuoteConversionRequest, amount: Decimal
    ) -> Ok[dict[str, Any]] | Err[str]:
        """Process payment for policy binding."""
        # Mock payment processing
        if conversion_request.payment_method not in ["card", "bank"]:
            return Err("Invalid payment method")

        # Simulate payment gateway response
        return Ok(
            {
                "transaction_id": f"TXN-{uuid4().hex[:8].upper()}",
                "amount": float(amount),
                "status": "approved",
                "timestamp": datetime.now().isoformat(),
                "method": conversion_request.payment_method,
            }
        )

    @beartype
    def _calculate_coverage_amount(self, quote: Quote) -> Decimal:
        """Calculate total coverage amount from selections."""
        total = Decimal("0")
        for coverage in quote.coverage_selections:
            if coverage.limit > 0:
                total += coverage.limit
        return total

    @beartype
    def _get_primary_deductible(self, quote: Quote) -> Decimal:
        """Get primary deductible from coverage selections."""
        for coverage in quote.coverage_selections:
            if coverage.coverage_type in ["COLLISION", "COMPREHENSIVE"]:
                return coverage.deductible or Decimal("500")
        return Decimal("500")  # Default

    @beartype
    async def _update_quote_status(self, quote_id: UUID, status: QuoteStatus) -> None:
        """Update quote status."""
        await self._db.execute(
            "UPDATE quotes SET status = $2, updated_at = CURRENT_TIMESTAMP WHERE id = $1",
            quote_id,
            status,
        )

    @beartype
    @performance_monitor("row_to_quote")
    def _row_to_quote(self, row: Any) -> Quote:
        """Convert database row to Quote model."""

        # Handle both asyncpg.Record and dict (for testing)
        def get_field(name: str) -> Any:
            if hasattr(row, "__getitem__"):
                return row[name]
            else:
                return getattr(row, name)

        return Quote(
            id=get_field("id"),
            quote_number=get_field("quote_number"),
            customer_id=get_field("customer_id"),
            status=QuoteStatus(get_field("status")),
            product_type=ProductType(get_field("product_type")),
            state=get_field("state"),
            zip_code=get_field("zip_code"),
            effective_date=get_field("effective_date"),
            email=get_field("email"),
            phone=get_field("phone"),
            preferred_contact=get_field("preferred_contact"),
            vehicle_info=(
                VehicleInfo(**get_field("vehicle_info"))
                if get_field("vehicle_info")
                else None
            ),
            drivers=(
                [DriverInfo(**d) for d in get_field("drivers")]
                if get_field("drivers")
                else []
            ),
            coverage_selections=(
                [CoverageSelection(**c) for c in get_field("coverage_selections")]
                if get_field("coverage_selections")
                else []
            ),
            base_premium=(
                Decimal(str(get_field("base_premium")))
                if get_field("base_premium")
                else None
            ),
            total_premium=(
                Decimal(str(get_field("total_premium")))
                if get_field("total_premium")
                else None
            ),
            monthly_premium=(
                Decimal(str(get_field("monthly_premium")))
                if get_field("monthly_premium")
                else None
            ),
            discounts_applied=(
                [Discount(**d) for d in get_field("discounts_applied")]
                if get_field("discounts_applied")
                else []
            ),
            surcharges_applied=get_field("surcharges_applied") or [],
            total_discount_amount=(
                Decimal(str(get_field("total_discount_amount")))
                if get_field("total_discount_amount")
                else None
            ),
            total_surcharge_amount=(
                Decimal(str(get_field("total_surcharge_amount")))
                if get_field("total_surcharge_amount")
                else None
            ),
            rating_factors=get_field("rating_factors"),
            rating_tier=get_field("rating_tier"),
            ai_risk_score=(
                float(get_field("ai_risk_score"))
                if get_field("ai_risk_score")
                else None
            ),
            ai_risk_factors=get_field("ai_risk_factors"),
            expires_at=get_field("expires_at"),
            converted_to_policy_id=get_field("converted_to_policy_id"),
            converted_at=get_field("converted_at"),
            created_by=get_field("created_by"),
            updated_by=get_field("updated_by"),
            referral_code=get_field("referral_source"),
            version=get_field("version"),
            parent_quote_id=get_field("parent_quote_id"),
            created_at=get_field("created_at"),
            updated_at=get_field("updated_at"),
        )

    @beartype
    def _mask_quote_pii(self, quote: Quote) -> Quote:
        """Mask PII data in quote for admin viewing."""
        # Create a copy with masked data
        masked_data = quote.model_dump()

        # Mask email
        if quote.email:
            parts = quote.email.split("@")
            masked_data["email"] = f"{parts[0][:2]}***@{parts[1]}"

        # Mask phone
        if quote.phone:
            masked_data["phone"] = f"***-***-{quote.phone[-4:]}"

        # Mask driver info
        for i, driver in enumerate(masked_data["drivers"]):
            driver["first_name"] = f"{driver['first_name'][:1]}***"
            driver["last_name"] = f"{driver['last_name'][:1]}***"
            driver["license_number"] = "***"

        return Quote(**masked_data)

    # Analytics tracking methods (placeholders)

    @beartype
    async def _track_quote_created(self, quote: Quote) -> None:
        """Track quote creation event."""
        try:
            # Insert analytics event
            await self._db.execute(
                """
                INSERT INTO quote_analytics_events
                (quote_id, event_type, event_data, created_at)
                VALUES ($1, $2, $3::jsonb, $4)
                """,
                quote.id,
                "quote_created",
                {
                    "quote_number": quote.quote_number,
                    "product_type": quote.product_type,
                    "state": quote.state,
                    "zip_code": quote.zip_code,
                    "customer_id": (
                        str(quote.customer_id) if quote.customer_id else None
                    ),
                    "referral_source": "web",  # Default
                    "channel": "website",
                },
                datetime.now(),
            )

            # Real-time analytics update
            if self._websocket_manager:
                await self._websocket_manager.broadcast_to_group(
                    "admin_dashboard",
                    {
                        "type": "quote_metrics_update",
                        "event": "quote_created",
                        "quote_id": str(quote.id),
                        "state": quote.state,
                        "product_type": quote.product_type,
                        "timestamp": datetime.now().isoformat(),
                    },
                )
        except Exception:
            # Don't fail quote creation if analytics fails
            pass

    @beartype
    async def _track_quote_priced(self, quote: Quote) -> None:
        """Track quote pricing event."""
        try:
            # Calculate pricing completion time
            time_to_price = None
            if quote.created_at:
                time_to_price = (datetime.now() - quote.created_at).total_seconds()

            await self._db.execute(
                """
                INSERT INTO quote_analytics_events
                (quote_id, event_type, event_data, created_at)
                VALUES ($1, $2, $3::jsonb, $4)
                """,
                quote.id,
                "quote_priced",
                {
                    "quote_number": quote.quote_number,
                    "base_premium": (
                        float(quote.base_premium) if quote.base_premium else None
                    ),
                    "total_premium": (
                        float(quote.total_premium) if quote.total_premium else None
                    ),
                    "monthly_premium": (
                        float(quote.monthly_premium) if quote.monthly_premium else None
                    ),
                    "total_discount_amount": (
                        float(quote.total_discount_amount)
                        if quote.total_discount_amount
                        else None
                    ),
                    "rating_tier": quote.rating_tier,
                    "ai_risk_score": quote.ai_risk_score,
                    "time_to_price_seconds": time_to_price,
                    "num_drivers": len(quote.drivers),
                    "num_coverages": len(quote.coverage_selections),
                },
                datetime.now(),
            )

            # Update quote metrics cache for dashboard
            await self._update_quote_metrics_cache(quote)

        except Exception:
            # Don't fail quote pricing if analytics fails
            pass

    @beartype
    async def _track_quote_converted(self, quote: Quote, policy_id: UUID) -> None:
        """Track quote conversion event."""
        try:
            # Calculate conversion time
            time_to_convert = None
            if quote.created_at:
                time_to_convert = (datetime.now() - quote.created_at).total_seconds()

            await self._db.execute(
                """
                INSERT INTO quote_analytics_events
                (quote_id, event_type, event_data, created_at)
                VALUES ($1, $2, $3::jsonb, $4)
                """,
                quote.id,
                "quote_converted",
                {
                    "quote_number": quote.quote_number,
                    "policy_id": str(policy_id),
                    "premium_bound": (
                        float(quote.total_premium) if quote.total_premium else None
                    ),
                    "time_to_convert_seconds": time_to_convert,
                    "quote_version": quote.version,
                    "followup_count": quote.followup_count,
                },
                datetime.now(),
            )

            # Real-time conversion notification
            if self._websocket_manager:
                await self._websocket_manager.broadcast_to_group(
                    "admin_dashboard",
                    {
                        "type": "quote_metrics_update",
                        "event": "quote_converted",
                        "quote_id": str(quote.id),
                        "policy_id": str(policy_id),
                        "premium": (
                            float(quote.total_premium) if quote.total_premium else None
                        ),
                        "state": quote.state,
                        "product_type": quote.product_type,
                        "timestamp": datetime.now().isoformat(),
                    },
                )

        except Exception:
            # Don't fail quote conversion if analytics fails
            pass

    @beartype
    async def _send_realtime_update(self, quote: Quote) -> None:
        """Send real-time update via WebSocket."""
        if not self._websocket_manager:
            return

        try:
            # Use the WebSocket message structure directly
            from ..websocket.manager import MessageType, WebSocketMessage

            # Send update to quote-specific room
            room_id = f"quote:{quote.id}"
            quote_msg = WebSocketMessage(
                type=MessageType.QUOTE_UPDATE,
                data={
                    "quote_id": str(quote.id),
                    "quote_number": quote.quote_number,
                    "status": quote.status,
                    "total_premium": (
                        float(quote.total_premium) if quote.total_premium else None
                    ),
                    "updated_at": (
                        quote.updated_at.isoformat() if quote.updated_at else None
                    ),
                },
            )
            await self._websocket_manager.send_to_room(room_id, quote_msg)

            # Send to customer room if customer exists
            if quote.customer_id:
                customer_room = f"customer:{quote.customer_id}"
                customer_msg = WebSocketMessage(
                    type=MessageType.QUOTE_UPDATE,
                    data={
                        "quote_id": str(quote.id),
                        "quote_number": quote.quote_number,
                        "status": quote.status,
                        "total_premium": (
                            float(quote.total_premium) if quote.total_premium else None
                        ),
                    },
                )
                await self._websocket_manager.send_to_room(customer_room, customer_msg)

            # Send to admin analytics room
            admin_room = "analytics:admin"
            admin_msg = WebSocketMessage(
                type=MessageType.QUOTE_UPDATE,
                data={
                    "event": "quote_priced",
                    "quote_id": str(quote.id),
                    "premium": (
                        float(quote.total_premium) if quote.total_premium else None
                    ),
                    "state": quote.state,
                    "product_type": quote.product_type,
                    "timestamp": datetime.now().isoformat(),
                },
            )
            await self._websocket_manager.send_to_room(admin_room, admin_msg)

        except Exception:
            # Don't let WebSocket errors affect quote operations
            pass

    @beartype
    async def _calculate_quote_async(self, quote_id: UUID) -> None:
        """Async task to calculate quote in background."""
        try:
            await asyncio.sleep(0.5)  # Brief delay
            await self.calculate_quote(quote_id)
        except Exception:
            # Log error but don't crash
            pass

    @beartype
    async def _log_admin_access(
        self, admin_user_id: UUID, action: str, affected_count: int
    ) -> None:
        """Log admin access for audit trail."""
        try:
            await self._db.execute(
                """
                INSERT INTO admin_access_logs
                (admin_user_id, action, affected_count, created_at, details)
                VALUES ($1, $2, $3, $4, $5::jsonb)
                """,
                admin_user_id,
                action,
                affected_count,
                datetime.now(),
                {
                    "service": "quote_service",
                    "method": action,
                    "result_count": affected_count,
                },
            )
        except Exception:
            # Don't fail operations if audit logging fails
            pass

    @beartype
    async def _update_quote_metrics_cache(self, quote: Quote) -> None:
        """Update cached metrics for real-time dashboard."""
        try:
            cache_key = (
                f"dashboard_metrics:quotes:{datetime.now().strftime('%Y-%m-%d')}"
            )

            # Get current metrics from cache
            current_metrics = await self._cache.get(cache_key) or {}
            if isinstance(current_metrics, str):
                current_metrics = json.loads(current_metrics)

            # Update metrics
            current_metrics.setdefault("total_quotes", 0)
            current_metrics.setdefault("total_premium", 0.0)
            current_metrics.setdefault("quotes_by_state", {})
            current_metrics.setdefault("quotes_by_product", {})
            current_metrics.setdefault("avg_premium", 0.0)

            # Update counts
            if quote.status == QuoteStatus.QUOTED and quote.total_premium:
                current_metrics["total_quotes"] += 1
                current_metrics["total_premium"] += float(quote.total_premium)
                current_metrics["quotes_by_state"][quote.state] = (
                    current_metrics["quotes_by_state"].get(quote.state, 0) + 1
                )
                current_metrics["quotes_by_product"][quote.product_type] = (
                    current_metrics["quotes_by_product"].get(quote.product_type, 0) + 1
                )

                # Calculate new average
                if current_metrics["total_quotes"] > 0:
                    current_metrics["avg_premium"] = (
                        current_metrics["total_premium"]
                        / current_metrics["total_quotes"]
                    )

            # Cache for 24 hours
            await self._cache.set(cache_key, json.dumps(current_metrics), 86400)

        except Exception:
            # Don't fail if metrics cache update fails
            pass

    @beartype
    async def _verify_admin_permissions(
        self,
        admin_user_id: UUID,
        required_permission: str,
    ) -> Result[bool, str]:
        """Verify admin user has required permission.

        Args:
            admin_user_id: ID of admin user
            required_permission: Permission string to check

        Returns:
            Result indicating permission status or error
        """
        try:
            # Get admin user with permissions
            admin_row = await self._db.fetchrow(
                """
                SELECT au.id, au.status,
                       r.permissions,
                       au.is_super_admin
                FROM admin_users au
                LEFT JOIN admin_roles r ON au.role_id = r.id
                WHERE au.id = $1 AND au.status = 'ACTIVE'
                """,
                admin_user_id,
            )

            if not admin_row:
                return Err("Admin user not found or inactive")

            # Super admins have all permissions
            if admin_row.get("is_super_admin"):
                return Ok(True)

            # Check specific permission
            permissions = admin_row.get("permissions", [])
            if required_permission in permissions:
                return Ok(True)

            # Check wildcard permissions
            permission_parts = required_permission.split(":")
            if len(permission_parts) >= 2:
                wildcard_permission = f"{permission_parts[0]}:*"
                if wildcard_permission in permissions:
                    return Ok(True)

            return Err(f"Admin user lacks required permission: {required_permission}")

        except Exception as e:
            return Err(f"Failed to verify admin permissions: {str(e)}")
