"""Claim business logic service."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg
from beartype import beartype

from pd_prime_demo.core.result_types import Err, Ok, Result

from ..core.cache import Cache
from ..core.database import Database
from ..models.claim import (
    Claim,
    ClaimCreate,
    ClaimStatus,
    ClaimStatusUpdate,
    ClaimUpdate,
)
from .cache_keys import CacheKeys
from .performance_monitor import performance_monitor


class ClaimService:
    """Service for claim business logic."""

    def __init__(self, db: Database, cache: Cache) -> None:
        """Initialize claim service with dependency validation."""
        if not db or not hasattr(db, "execute"):
            raise ValueError("Database connection required and must be active")
        if not cache or not hasattr(cache, "get"):
            raise ValueError("Cache connection required and must be available")

        self._db = db
        self._cache = cache
        self._cache_ttl = 3600  # 1 hour

    @beartype
    @performance_monitor("create_claim")
    async def create(
        self,
        claim_data: ClaimCreate,
        policy_id: UUID,
    ) -> Result[Claim, str]:
        """Create a new claim."""
        try:
            # Validate business rules
            validation_result = await self._validate_claim_data(claim_data, policy_id)
            if isinstance(validation_result, Err):
                return validation_result

            # Create claim in database
            query = """
                INSERT INTO claims (
                    policy_id, claim_number, data, status,
                    amount_claimed, amount_approved, submitted_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id, policy_id, claim_number, data, status,
                          amount_claimed, amount_approved, submitted_at,
                          resolved_at, created_at, updated_at
            """

            # Prepare JSONB data
            claim_json = {
                "type": claim_data.claim_type.value,
                "description": claim_data.description,
                "documents": claim_data.supporting_documents,
                "incident_date": claim_data.incident_date.isoformat(),
                "incident_location": claim_data.incident_location,
                "priority": claim_data.priority.value,
                "contact_phone": claim_data.contact_phone,
                "contact_email": claim_data.contact_email,
                "notes": [],
            }

            # Generate claim number
            claim_number = await self._generate_claim_number()

            row = await self._db.fetchrow(
                query,
                policy_id,
                claim_number,
                claim_json,
                ClaimStatus.SUBMITTED.value,  # New claims start as SUBMITTED
                str(claim_data.claimed_amount),
                "0",  # amount_approved starts at 0
                datetime.now(timezone.utc),
            )

            if not row:
                return Err("Failed to create claim")

            # Create Claim model from database row
            claim = self._row_to_claim(row)

            # Invalidate policy cache
            await self._cache.delete(CacheKeys.policy_claims(policy_id))
            await self._cache.delete(CacheKeys.claims_by_policy(policy_id))

            return Ok(claim)

        except asyncpg.UniqueViolationError:
            return Err(f"Claim number {claim_number} already exists")
        except Exception as e:
            return Err(f"Database error: {str(e)}")

    @beartype
    @performance_monitor("get_claim")
    async def get(self, claim_id: UUID):
        """Get claim by ID."""
        # Check cache first
        cache_key = CacheKeys.claim_by_id(claim_id)
        cached = await self._cache.get(cache_key)
        if cached:
            return Ok(Claim(**cached))

        # Query database
        query = """
            SELECT id, policy_id, claim_number, data, status,
                   amount_claimed, amount_approved, submitted_at,
                   resolved_at, created_at, updated_at
            FROM claims
            WHERE id = $1
        """

        row = await self._db.fetchrow(query, claim_id)
        if not row:
            return Ok(None)

        claim = self._row_to_claim(row)

        # Cache the result
        await self._cache.set(
            cache_key,
            claim.model_dump(mode="json"),
            self._cache_ttl,
        )

        return Ok(claim)

    @beartype
    @performance_monitor("list_claims")
    async def list(
        self,
        policy_id: UUID | None = None,
        status: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> Result[list[Claim], str]:
        """List claims with optional filters."""
        query_parts = ["SELECT * FROM claims WHERE 1=1"]
        params: list[Any] = []
        param_count = 0

        if policy_id:
            param_count += 1
            query_parts.append(f"AND policy_id = ${param_count}")
            params.append(policy_id)

        if status:
            param_count += 1
            query_parts.append(f"AND status = ${param_count}")
            params.append(status)

        query_parts.append("ORDER BY submitted_at DESC")

        param_count += 1
        query_parts.append(f"LIMIT ${param_count}")
        params.append(limit)

        param_count += 1
        query_parts.append(f"OFFSET ${param_count}")
        params.append(offset)

        query = " ".join(query_parts)
        rows = await self._db.fetch(query, *params)

        claims = [self._row_to_claim(row) for row in rows]
        return Ok(claims)

    @beartype
    async def update(
        self,
        claim_id: UUID,
        claim_update: ClaimUpdate,
    ):
        """Update claim details."""
        # Get existing claim
        existing_result = await self.get(claim_id)
        if isinstance(existing_result, Err):
            return existing_result

        existing = existing_result.unwrap()
        if not existing:
            return Ok(None)

        # Validate update
        if existing.status not in ["SUBMITTED", "UNDER_REVIEW"]:
            return Err("Can only update claims in SUBMITTED or UNDER_REVIEW status")

        # Build update data
        update_data = {}

        # ClaimUpdate doesn't have description field - it's not updatable
        # Only supporting_documents can be updated from ClaimUpdate
        if claim_update.supporting_documents is not None:
            update_data["documents"] = claim_update.supporting_documents

        if not update_data:
            return Ok(existing)

        query = """
            UPDATE claims
            SET data = data || $1::jsonb, updated_at = NOW()
            WHERE id = $2
            RETURNING *
        """

        row = await self._db.fetchrow(query, update_data, claim_id)
        if not row:
            return Err("Failed to update claim")

        claim = self._row_to_claim(row)

        # Invalidate cache
        await self._cache.delete(CacheKeys.claim_by_id(claim_id))
        await self._cache.delete(CacheKeys.claims_by_policy(claim.policy_id))

        return Ok(claim)

    @beartype
    async def update_status(
        self,
        claim_id: UUID,
        status_update: ClaimStatusUpdate,
    ):
        """Update claim status with business logic."""
        # Get existing claim
        existing_result = await self.get(claim_id)
        if isinstance(existing_result, Err):
            return existing_result

        existing = existing_result.unwrap()
        if not existing:
            return Ok(None)

        # Validate status transition
        valid_transition = self._validate_status_transition(
            existing.status,
            status_update.status,
        )
        if not valid_transition:
            return Err(
                f"Invalid status transition from {existing.status} to {status_update.status}"
            )

        # Build update query
        update_fields = ["status = $1"]
        params: list[Any] = [status_update.status.value]
        param_count = 1

        # Update amount_approved if provided
        if status_update.amount_approved is not None:
            param_count += 1
            update_fields.append(f"amount_approved = ${param_count}")
            params.append(str(status_update.amount_approved))

        # Set resolved_at for final statuses
        if status_update.status in [
            ClaimStatus.APPROVED,
            ClaimStatus.DENIED,
            ClaimStatus.CLOSED,
        ]:
            param_count += 1
            update_fields.append(f"resolved_at = ${param_count}")
            params.append(datetime.now(timezone.utc))

        # Add note to data
        if status_update.notes:
            param_count += 1
            update_fields.append(
                f"data = data || jsonb_build_object('notes', "
                f"COALESCE(data->'notes', '[]'::jsonb) || ${param_count}::jsonb)"
            )
            note = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": status_update.status.value,
                "note": status_update.notes,
            }
            params.append([note])

        param_count += 1
        params.append(claim_id)

        # Build query - update_fields are constructed programmatically and safe
        query = f"""
            UPDATE claims
            SET {", ".join(update_fields)}, updated_at = NOW()
            WHERE id = ${param_count}
            RETURNING *
        """  # nosec B608 - update_fields are not user-provided

        row = await self._db.fetchrow(query, *params)
        if not row:
            return Err("Failed to update claim status")

        claim = self._row_to_claim(row)

        # Invalidate cache
        await self._cache.delete(CacheKeys.claim_by_id(claim_id))
        await self._cache.delete(CacheKeys.claims_by_policy(claim.policy_id))

        return Ok(claim)

    @beartype
    async def delete(self, claim_id: UUID):
        """Delete a claim (only allowed for DRAFT status)."""
        # Get existing claim
        existing_result = await self.get(claim_id)
        if isinstance(existing_result, Err):
            return existing_result

        existing = existing_result.unwrap()
        if not existing:
            return Ok(False)

        if existing.status != "DRAFT":
            return Err("Can only delete claims in DRAFT status")

        query = "DELETE FROM claims WHERE id = $1"
        result = await self._db.execute(query, claim_id)

        deleted = result.split()[-1] != "0"

        if deleted:
            # Invalidate cache
            await self._cache.delete(CacheKeys.claim_by_id(claim_id))

        return Ok(deleted)

    @beartype
    async def _validate_claim_data(
        self,
        claim_data: ClaimCreate,
        policy_id: UUID,
    ):
        """Validate claim business rules."""
        # Check if policy exists and is active
        policy_query = """
            SELECT status, data->>'coverage_amount' as coverage_amount
            FROM policies
            WHERE id = $1
        """

        policy_row = await self._db.fetchrow(policy_query, policy_id)
        if not policy_row:
            return Err("Policy not found")

        if policy_row["status"] != "ACTIVE":
            return Err("Cannot create claim for inactive policy")

        # Check claim amount
        if claim_data.claimed_amount <= 0:
            return Err("Claim amount must be positive")

        coverage_amount = Decimal(policy_row["coverage_amount"])
        if claim_data.claimed_amount > coverage_amount:
            return Err("Claim amount exceeds policy coverage")

        return Ok(True)

    @beartype
    def _validate_status_transition(self, from_status: str, to_status: str) -> bool:
        """Validate claim status transitions."""
        valid_transitions = {
            "DRAFT": ["SUBMITTED"],
            "SUBMITTED": ["UNDER_REVIEW", "DENIED"],
            "UNDER_REVIEW": ["APPROVED", "DENIED", "PENDING_INFO"],
            "PENDING_INFO": ["UNDER_REVIEW", "DENIED"],
            "APPROVED": ["PAID", "CLOSED"],
            "DENIED": ["CLOSED", "UNDER_REVIEW"],  # Allow appeal
            "PAID": ["CLOSED"],
            "CLOSED": [],  # Terminal state
        }

        return to_status in valid_transitions.get(from_status, [])

    @beartype
    async def _generate_claim_number(self) -> str:
        """Generate a unique claim number in format CLM-YYYY-NNNNNNN."""
        year = datetime.now().year

        # Get the next claim number for this year
        query = """
            SELECT COUNT(*) + 1 as next_num
            FROM claims
            WHERE claim_number LIKE $1
        """

        pattern = f"CLM-{year}-%"
        row = await self._db.fetchrow(query, pattern)
        next_num = row["next_num"] if row else 1

        # Format as CLM-YYYY-NNNNNNN
        return f"CLM-{year}-{next_num:07d}"

    @beartype
    def _row_to_claim(self, row: asyncpg.Record) -> Claim:
        """Convert database row to Claim model."""
        from ..models.claim import ClaimPriority, ClaimType

        data = dict(row["data"])

        # Extract claim fields from JSONB data
        claim_type = ClaimType(data.get("type", ClaimType.OTHER.value))
        priority = ClaimPriority(data.get("priority", ClaimPriority.MEDIUM.value))

        return Claim(
            # IdentifiableModel fields
            id=row["id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            # ClaimBase fields
            policy_id=row["policy_id"],
            claim_type=claim_type,
            incident_date=(
                datetime.fromisoformat(data["incident_date"]).date()
                if data.get("incident_date")
                else datetime.now().date()
            ),
            incident_location=data.get("incident_location", ""),
            description=data.get("description", ""),
            claimed_amount=Decimal(row["amount_claimed"]),
            # Claim-specific fields
            claim_number=row["claim_number"],
            status=ClaimStatus(row["status"]),
            priority=priority,
            approved_amount=(
                Decimal(row["amount_approved"])
                if row["amount_approved"] and row["amount_approved"] != "0"
                else None
            ),
            paid_amount=None,  # Will be set when payment is processed
            denial_reason=data.get("denial_reason"),
            adjuster_id=UUID(data["adjuster_id"]) if data.get("adjuster_id") else None,
            adjuster_notes=data.get("adjuster_notes"),
            supporting_documents=data.get("documents", []),
            submitted_at=row["submitted_at"],
            approved_at=(
                datetime.fromisoformat(data["approved_at"])
                if data.get("approved_at")
                else None
            ),
            paid_at=(
                datetime.fromisoformat(data["paid_at"]) if data.get("paid_at") else None
            ),
            closed_at=row["resolved_at"],
        )
