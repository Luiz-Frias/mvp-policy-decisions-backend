"""Rate table management and versioning.

This module handles rate table CRUD operations, versioning,
and deployment with proper audit trails.
"""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from beartype import beartype
from pydantic import Field

from pd_prime_demo.core.result_types import Err, Ok, Result

from ...core.cache import Cache
from ...core.database import Database
from ...models.base import BaseModelConfig
from ...schemas.rating import RateTableData, RateTableValidation


@beartype
class RateTableVersion(BaseModelConfig):
    """Rate table version with metadata."""

    id: UUID = Field(default_factory=uuid4)
    table_name: str = Field(..., min_length=1, max_length=100)
    version_number: int = Field(..., ge=1)
    rate_data: RateTableData = Field(...)
    effective_date: date = Field(...)
    expiration_date: date | None = Field(None)
    status: str = Field(
        "pending",
        pattern="^(pending|approved|active|superseded|rejected)$",
    )

    # Audit fields
    created_by: UUID = Field(...)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    approved_by: UUID | None = Field(None)
    approved_at: datetime | None = Field(None)
    approval_notes: str | None = Field(None, max_length=1000)
    notes: str | None = Field(None, max_length=1000)


@beartype
class RateTableService:
    """Service for managing rate tables and versions."""

    def __init__(self, db: Database, cache: Cache) -> None:
        """Initialize rate table service."""
        self._db = db
        self._cache = cache
        self._cache_prefix = "rate_tables:"

    @beartype
    async def create_rate_table_version(
        self,
        table_name: str,
        rate_data: dict[str, Any],
        admin_user_id: UUID,
        effective_date: date,
        notes: str | None = None,
    ) -> Result[RateTableVersion, str]:
        """Create new version of rate table requiring approval."""
        try:
            # Validate rate structure
            validation = await self._validate_rate_structure(table_name, rate_data)
            if isinstance(validation, Err):
                return validation

            # Get next version number
            version_number = await self._get_next_version_number(table_name)

            # Create rate table version
            version = RateTableVersion(
                table_name=table_name,
                version_number=version_number,
                rate_data=rate_data,
                effective_date=effective_date,
                status="pending",
                created_by=admin_user_id,
                notes=notes,
            )

            # Save to database
            query = """
                INSERT INTO rate_table_versions (
                    id, table_name, version_number, rate_data,
                    effective_date, status, created_by, created_at, notes
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING *
            """

            row = await self._db.fetchrow(
                query,
                version.id,
                version.table_name,
                version.version_number,
                json.dumps(version.rate_data),
                version.effective_date,
                version.status,
                version.created_by,
                version.created_at,
                version.notes,
            )

            if not row:
                return Err("Failed to create rate table version")

            # Invalidate cache
            await self._invalidate_rate_cache(table_name)

            return Ok(version)

        except Exception as e:
            return Err(f"Rate table creation failed: {str(e)}")

    @beartype
    async def approve_rate_version(
        self,
        version_id: UUID,
        admin_user_id: UUID,
        approval_notes: str | None = None,
    ) -> Result[bool, str]:
        """Approve rate table version and potentially activate it."""
        try:
            # Get version
            version_result = await self.get_rate_version(version_id)
            if isinstance(version_result, Err):
                return version_result

            version = version_result.value

            if version.status != "pending":
                return Err(
                    f"Cannot approve rate version in '{version.status}' status. "
                    f"Only 'pending' versions can be approved."
                )

            # Update to approved
            approval_time = datetime.utcnow()
            update_query = """
                UPDATE rate_table_versions
                SET status = 'approved',
                    approved_by = $2,
                    approved_at = $3,
                    approval_notes = $4
                WHERE id = $1
            """

            await self._db.execute(
                update_query,
                version_id,
                admin_user_id,
                approval_time,
                approval_notes,
            )

            # Check if should be activated immediately
            if version.effective_date <= date.today():
                activate_result = await self._activate_rate_version(version_id)
                if isinstance(activate_result, Err):
                    return activate_result

            # Invalidate cache
            await self._invalidate_rate_cache(version.table_name)

            return Ok(True)

        except Exception as e:
            return Err(f"Rate approval failed: {str(e)}")

    @beartype
    async def get_rate_version(self, version_id: UUID) -> Result[RateTableVersion, str]:
        """Get specific rate table version."""
        query = """
            SELECT * FROM rate_table_versions
            WHERE id = $1
        """

        row = await self._db.fetchrow(query, version_id)

        if not row:
            return Err(f"Rate version {version_id} not found")

        return Ok(self._row_to_rate_version(row))

    @beartype
    async def get_active_rates(
        self, state: str, product_type: str
    ) -> Result[dict[str, Decimal], str]:
        """Get currently active rates for state/product."""
        # Check cache first
        cache_key = f"active:{state}:{product_type}"
        cached = await self._cache.get(f"{self._cache_prefix}{cache_key}")
        if cached:
            rates = json.loads(cached)
            return Ok({k: Decimal(v) for k, v in rates.items()})

        # Query active rates
        query = """
            SELECT rt.coverage_type, rt.base_rate
            FROM rate_tables rt
            INNER JOIN rate_table_versions rtv ON rtv.id = rt.version_id
            WHERE rt.state = $1
                AND rt.product_type = $2
                AND rtv.status = 'active'
                AND rtv.effective_date <= CURRENT_DATE
                AND (rtv.expiration_date IS NULL OR rtv.expiration_date > CURRENT_DATE)
        """

        rows = await self._db.fetch(query, state, product_type)

        if not rows:
            return Err(
                f"No active rates found for {state} {product_type}. "
                f"Admin must create and approve rate tables before quotes can be generated. "
                f"Go to Admin Panel > Rate Management to configure rates."
            )

        rates = {row["coverage_type"]: Decimal(str(row["base_rate"])) for row in rows}

        # Cache for performance
        await self._cache.set(
            f"{self._cache_prefix}{cache_key}",
            json.dumps({k: str(v) for k, v in rates.items()}),
            3600,  # 1 hour
        )

        return Ok(rates)

    @beartype
    async def list_rate_versions(
        self,
        table_name: str,
        include_inactive: bool = False,
    ) -> Result[list[RateTableVersion], str]:
        """List rate table versions."""
        query = """
            SELECT * FROM rate_table_versions
            WHERE table_name = $1
        """

        params = [table_name]

        if not include_inactive:
            query += " AND status IN ('pending', 'approved', 'active')"

        query += " ORDER BY version_number DESC"

        rows = await self._db.fetch(query, *params)

        versions = [self._row_to_rate_version(row) for row in rows]
        return Ok(versions)

    @beartype
    async def compare_rate_versions(
        self, version_id_1: UUID, version_id_2: UUID
    ) -> Result[dict[str, Any], str]:
        """Compare two rate versions."""
        # Get both versions
        v1_result = await self.get_rate_version(version_id_1)
        if isinstance(v1_result, Err):
            return v1_result

        v2_result = await self.get_rate_version(version_id_2)
        if isinstance(v2_result, Err):
            return v2_result

        v1 = v1_result.value
        v2 = v2_result.value

        # Calculate differences
        differences = self._calculate_rate_differences(v1.rate_data, v2.rate_data)

        comparison = {
            "version_1": {
                "id": v1.id,
                "version": v1.version_number,
                "effective_date": v1.effective_date,
                "status": v1.status,
            },
            "version_2": {
                "id": v2.id,
                "version": v2.version_number,
                "effective_date": v2.effective_date,
                "status": v2.status,
            },
            "differences": differences,
            "impact_summary": self._calculate_impact_summary(differences),
        }

        return Ok(comparison)

    @beartype
    async def schedule_rate_deployment(
        self,
        version_id: UUID,
        deployment_date: date,
        admin_user_id: UUID,
    ) -> Result[UUID, str]:
        """Schedule a rate version for future deployment."""
        # Get version
        version_result = await self.get_rate_version(version_id)
        if isinstance(version_result, Err):
            return version_result

        version = version_result.value

        if version.status != "approved":
            return Err(
                f"Only approved rate versions can be scheduled for deployment. "
                f"Current status: {version.status}"
            )

        # Create deployment schedule
        deployment_id = uuid4()
        query = """
            INSERT INTO rate_deployments (
                id, version_id, scheduled_date, scheduled_by, status
            ) VALUES ($1, $2, $3, $4, 'scheduled')
            RETURNING id
        """

        await self._db.execute(
            query, deployment_id, version_id, deployment_date, admin_user_id
        )

        return Ok(deployment_id)

    @beartype
    async def _validate_rate_structure(
        self, table_name: str, rate_data: dict[str, Any]
    ) -> Result[bool, str]:
        """Validate rate table structure and data."""
        # Check required fields
        required_fields = ["coverages", "base_rates", "factors"]
        missing_fields = [f for f in required_fields if f not in rate_data]

        if missing_fields:
            return Err(
                f"Rate table missing required fields: {missing_fields}. "
                f"Required structure: coverages, base_rates, factors"
            )

        # Validate coverages
        coverages = rate_data.get("coverages", {})
        if not isinstance(coverages, dict):
            return Err("Coverages must be a dictionary mapping coverage types to rates")

        # Validate all rates are positive decimals
        for coverage_type, rate in coverages.items():
            try:
                rate_decimal = Decimal(str(rate))
                if rate_decimal <= 0:
                    return Err(f"Rate for {coverage_type} must be positive, got {rate}")
                if rate_decimal > Decimal("10000"):
                    return Err(
                        f"Rate for {coverage_type} exceeds maximum allowed (10000)"
                    )
            except Exception:
                return Err(
                    f"Invalid rate format for {coverage_type}: {rate}. "
                    f"Rates must be numeric values."
                )

        # Validate factors
        factors = rate_data.get("factors", {})
        if not isinstance(factors, dict):
            return Err("Factors must be a dictionary")

        for factor_name, factor_data in factors.items():
            if not isinstance(factor_data, dict):
                return Err(f"Factor {factor_name} must contain range definitions")

            if "min" not in factor_data or "max" not in factor_data:
                return Err(f"Factor {factor_name} must have 'min' and 'max' values")

            try:
                min_val = float(factor_data["min"])
                max_val = float(factor_data["max"])
                if min_val < 0.1 or max_val > 10.0:
                    return Err(
                        f"Factor {factor_name} values must be between 0.1 and 10.0"
                    )
                if min_val > max_val:
                    return Err(
                        f"Factor {factor_name} min ({min_val}) cannot exceed max ({max_val})"
                    )
            except Exception:
                return Err(f"Invalid factor values for {factor_name}")

        return Ok(True)

    @beartype
    async def _get_next_version_number(self, table_name: str) -> int:
        """Get next version number for table."""
        query = """
            SELECT MAX(version_number) as max_version
            FROM rate_table_versions
            WHERE table_name = $1
        """

        row = await self._db.fetchrow(query, table_name)
        max_version = row["max_version"] if row and row["max_version"] else 0
        return max_version + 1

    @beartype
    async def _activate_rate_version(self, version_id: UUID) -> Result[bool, str]:
        """Activate a rate version, deactivating previous versions."""
        try:
            # Get version details
            version_result = await self.get_rate_version(version_id)
            if isinstance(version_result, Err):
                return version_result

            version = version_result.value

            # Start transaction
            async with self._db.transaction():
                # Deactivate current active version
                deactivate_query = """
                    UPDATE rate_table_versions
                    SET status = 'superseded'
                    WHERE table_name = $1
                        AND status = 'active'
                        AND id != $2
                """

                await self._db.execute(deactivate_query, version.table_name, version_id)

                # Activate new version
                activate_query = """
                    UPDATE rate_table_versions
                    SET status = 'active'
                    WHERE id = $1
                """

                await self._db.execute(activate_query, version_id)

                # Update rate_tables with new active version
                # This is the denormalized table for fast lookups
                await self._update_active_rate_tables(version)

            # Clear all caches
            await self._invalidate_rate_cache(version.table_name)

            return Ok(True)

        except Exception as e:
            return Err(f"Rate activation failed: {str(e)}")

    @beartype
    async def _update_active_rate_tables(self, version: RateTableVersion) -> None:
        """Update denormalized rate_tables for fast lookups."""
        # Extract state and product from table name (e.g., "CA_auto_base_rates")
        parts = version.table_name.split("_")
        if len(parts) >= 3:
            state = parts[0]
            product_type = parts[1]

            # Clear existing rates
            delete_query = """
                DELETE FROM rate_tables
                WHERE state = $1 AND product_type = $2
            """
            await self._db.execute(delete_query, state, product_type)

            # Insert new rates
            coverages = version.rate_data.get("coverages", {})
            for coverage_type, base_rate in coverages.items():
                insert_query = """
                    INSERT INTO rate_tables (
                        state, product_type, coverage_type,
                        base_rate, version_id
                    ) VALUES ($1, $2, $3, $4, $5)
                """
                await self._db.execute(
                    insert_query,
                    state,
                    product_type,
                    coverage_type,
                    Decimal(str(base_rate)),
                    version.id,
                )

    @beartype
    async def _invalidate_rate_cache(self, table_name: str) -> None:
        """Invalidate all caches related to a rate table."""
        # Delete pattern-based cache entries
        await self._cache.delete(f"{self._cache_prefix}active:*")
        await self._cache.delete(f"{self._cache_prefix}version:*")
        await self._cache.delete("rating:base_rates:*")

    @beartype
    def _row_to_rate_version(self, row: Any) -> RateTableVersion:
        """Convert database row to RateTableVersion model."""
        return RateTableVersion(
            id=row["id"],
            table_name=row["table_name"],
            version_number=row["version_number"],
            rate_data=(
                json.loads(row["rate_data"])
                if isinstance(row["rate_data"], str)
                else row["rate_data"]
            ),
            effective_date=row["effective_date"],
            expiration_date=row.get("expiration_date"),
            status=row["status"],
            created_by=row["created_by"],
            created_at=row["created_at"],
            approved_by=row.get("approved_by"),
            approved_at=row.get("approved_at"),
            approval_notes=row.get("approval_notes"),
            notes=row.get("notes"),
        )

    @beartype
    def _calculate_rate_differences(
        self, rate_data_1: dict[str, Any], rate_data_2: dict[str, Any]
    ) -> dict[str, Any]:
        """Calculate differences between two rate structures."""
        differences: dict[str, dict[str, Any]] = {
            "added": {},
            "removed": {},
            "modified": {},
        }

        coverages_1 = rate_data_1.get("coverages", {})
        coverages_2 = rate_data_2.get("coverages", {})

        # Find added coverages
        for coverage in coverages_2:
            if coverage not in coverages_1:
                differences["added"][coverage] = coverages_2[coverage]

        # Find removed coverages
        for coverage in coverages_1:
            if coverage not in coverages_2:
                differences["removed"][coverage] = coverages_1[coverage]

        # Find modified coverages
        for coverage in coverages_1:
            if coverage in coverages_2:
                rate_1 = Decimal(str(coverages_1[coverage]))
                rate_2 = Decimal(str(coverages_2[coverage]))
                if rate_1 != rate_2:
                    differences["modified"][coverage] = {
                        "old": float(rate_1),
                        "new": float(rate_2),
                        "change": float(rate_2 - rate_1),
                        "change_pct": float((rate_2 - rate_1) / rate_1 * 100),
                    }

        return differences

    @beartype
    def _calculate_impact_summary(self, differences: dict[str, Any]) -> dict[str, Any]:
        """Calculate summary of rate change impacts."""
        modified = differences.get("modified", {})

        if not modified:
            return {
                "average_change": 0,
                "max_increase": 0,
                "max_decrease": 0,
                "coverages_affected": 0,
            }

        changes = [item["change_pct"] for item in modified.values()]

        return {
            "average_change": sum(changes) / len(changes) if changes else 0,
            "max_increase": max(changes) if changes else 0,
            "max_decrease": min(changes) if changes else 0,
            "coverages_affected": len(modified),
        }
