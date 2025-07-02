"""Policy business logic service."""

from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg
from beartype import beartype

from ..core.cache import Cache
from ..core.database import Database
from ..models.policy import Policy, PolicyCreate, PolicyStatus, PolicyType, PolicyUpdate
from .result import Err, Ok, Result


class PolicyService:
    """Service for policy business logic."""

    def __init__(self, db: Database, cache: Cache) -> None:
        """Initialize policy service."""
        self._db = db
        self._cache = cache
        self._cache_prefix = "policy:"
        self._cache_ttl = 3600  # 1 hour

    @beartype
    async def create(
        self,
        policy_data: PolicyCreate,
        customer_id: UUID,
    ) -> Result[Policy, str]:
        """Create a new policy."""
        try:
            # Validate business rules
            validation_result = await self._validate_policy_data(policy_data)
            if isinstance(validation_result, Err):
                return validation_result

            # Create policy in database
            query = """
                INSERT INTO policies (customer_id, policy_number, data, status, effective_date, expiration_date)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id, customer_id, policy_number, data, status, effective_date, expiration_date, created_at, updated_at
            """

            # Prepare JSONB data
            policy_json = {
                "type": policy_data.policy_type,
                "premium": str(policy_data.premium_amount),
                "coverage_amount": str(policy_data.coverage_amount),
                "deductible": str(policy_data.deductible),
            }

            row = await self._db.fetchrow(
                query,
                customer_id,
                policy_data.policy_number,
                policy_json,
                policy_data.status,
                policy_data.effective_date,
                policy_data.expiration_date,
            )

            if not row:
                return Err("Failed to create policy")

            # Create Policy model from database row
            policy = self._row_to_policy(row)

            # Invalidate customer cache
            await self._cache.delete(f"customer:{customer_id}:policies")

            return Ok(policy)

        except asyncpg.UniqueViolationError:
            return Err(f"Policy number {policy_data.policy_number} already exists")
        except Exception as e:
            return Err(f"Database error: {str(e)}")

    @beartype
    async def get(self, policy_id: UUID) -> Result[Policy | None, str]:
        """Get policy by ID."""
        # Check cache first
        cache_key = f"{self._cache_prefix}{policy_id}"
        cached = await self._cache.get(cache_key)
        if cached:
            return Ok(Policy(**cached))

        # Query database
        query = """
            SELECT id, customer_id, policy_number, data, status,
                   effective_date, expiration_date, created_at, updated_at
            FROM policies
            WHERE id = $1
        """

        row = await self._db.fetchrow(query, policy_id)
        if not row:
            return Ok(None)

        policy = self._row_to_policy(row)

        # Cache the result
        await self._cache.set(
            cache_key,
            policy.model_dump(mode="json"),
            self._cache_ttl,
        )

        return Ok(policy)

    @beartype
    async def list(
        self,
        customer_id: UUID | None = None,
        status: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> Result[list[Policy], str]:
        """List policies with optional filters."""
        query_parts = ["SELECT * FROM policies WHERE 1=1"]
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

        query_parts.append("ORDER BY created_at DESC")

        param_count += 1
        query_parts.append(f"LIMIT ${param_count}")
        params.append(limit)

        param_count += 1
        query_parts.append(f"OFFSET ${param_count}")
        params.append(offset)

        query = " ".join(query_parts)
        rows = await self._db.fetch(query, *params)

        policies = [self._row_to_policy(row) for row in rows]
        return Ok(policies)

    @beartype
    async def update(
        self,
        policy_id: UUID,
        policy_update: PolicyUpdate,
    ) -> Result[Policy | None, str]:
        """Update policy."""
        # Get existing policy
        existing_result = await self.get(policy_id)
        if isinstance(existing_result, Err):
            return existing_result

        existing = existing_result.unwrap()
        if not existing:
            return Ok(None)

        # Validate update
        if policy_update.status == "CANCELLED" and existing.status == "CANCELLED":
            return Err("Policy is already cancelled")

        # Build update query using defensive parameterized approach
        # 🛡️ SECURITY: Use predefined query templates to prevent SQL injection
        update_parts = []
        params: list[Any] = []
        param_count = 0

        # Define immutable query templates for each allowed field update
        SAFE_UPDATE_TEMPLATES = {
            "status": "status = ${}",
            "data_merge": "data = data || ${}::jsonb",
        }

        if policy_update.status is not None:
            param_count += 1
            update_parts.append(SAFE_UPDATE_TEMPLATES["status"].format(param_count))
            params.append(policy_update.status)

        # Update JSONB data fields if provided
        data_updates = {}
        if policy_update.premium_amount is not None:
            data_updates["premium"] = str(policy_update.premium_amount)
        if policy_update.coverage_amount is not None:
            data_updates["coverage_amount"] = str(policy_update.coverage_amount)
        if policy_update.deductible is not None:
            data_updates["deductible"] = str(policy_update.deductible)

        if data_updates:
            param_count += 1
            update_parts.append(SAFE_UPDATE_TEMPLATES["data_merge"].format(param_count))
            params.append(data_updates)

        if not update_parts:
            return Ok(existing)

        param_count += 1
        params.append(policy_id)

        # 🛡️ SECURITY: Use immutable query template with parameterized values only
        SAFE_UPDATE_QUERY_TEMPLATE = """
            UPDATE policies
            SET {update_clauses}, updated_at = NOW()
            WHERE id = ${where_param}
            RETURNING *
        """

        query = SAFE_UPDATE_QUERY_TEMPLATE.format(
            update_clauses=", ".join(update_parts), where_param=param_count
        )

        row = await self._db.fetchrow(query, *params)
        if not row:
            return Err("Failed to update policy")

        policy = self._row_to_policy(row)

        # Invalidate cache
        await self._cache.delete(f"{self._cache_prefix}{policy_id}")

        return Ok(policy)

    @beartype
    async def delete(self, policy_id: UUID) -> Result[bool, str]:
        """Soft delete a policy by setting status to CANCELLED."""
        result = await self.update(
            policy_id,
            PolicyUpdate(
                status=PolicyStatus.CANCELLED,
                premium_amount=None,
                coverage_amount=None,
                deductible=None,
                notes=None,
            ),
        )

        if isinstance(result, Err):
            return result

        policy = result.unwrap()
        return Ok(policy is not None)

    @beartype
    async def _validate_policy_data(
        self, policy_data: PolicyCreate
    ) -> Result[bool, str]:
        """Validate policy business rules."""
        # Check dates
        if policy_data.expiration_date <= policy_data.effective_date:
            return Err("Expiration date must be after effective date")

        # Check premium
        if policy_data.premium_amount <= 0:
            return Err("Premium must be positive")

        # Check coverage
        if policy_data.coverage_amount <= 0:
            return Err("Coverage amount must be positive")

        # Check deductible
        if policy_data.deductible < 0:
            return Err("Deductible cannot be negative")

        if policy_data.deductible > policy_data.coverage_amount:
            return Err("Deductible cannot exceed coverage amount")

        return Ok(True)

    @beartype
    def _row_to_policy(self, row: asyncpg.Record) -> Policy:
        """Convert database row to Policy model."""
        data = dict(row["data"])

        # Parse policy type from data or infer from policy number
        policy_type_str = data.get("type", "AUTO")  # Default to AUTO
        try:
            policy_type = PolicyType(policy_type_str.upper())
        except ValueError:
            policy_type = PolicyType.AUTO  # Fallback to AUTO for invalid types

        return Policy(
            id=row["id"],
            customer_id=row["customer_id"],
            policy_number=row["policy_number"],
            policy_type=policy_type,
            status=PolicyStatus(row["status"]),
            premium_amount=Decimal(
                str(data.get("coverage", {}).get("base_premium", "0"))
            ),
            coverage_amount=Decimal(
                str(data.get("coverage", {}).get("coverage_limit", "0"))
            ),
            deductible=Decimal(str(data.get("coverage", {}).get("deductible", "0"))),
            effective_date=row["effective_date"],
            expiration_date=row["expiration_date"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            notes=data.get("notes"),
            cancelled_at=None,
        )
