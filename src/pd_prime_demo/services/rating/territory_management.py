# PolicyCore - Policy Decision Management System
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.
"""Territory management for geographic rating factors.

This module handles ZIP code to territory mapping, territory factor
calculation, and geographic risk assessment for rating.
"""

import json
from typing import Any
from uuid import UUID

from beartype import beartype
from pydantic import Field

from pd_prime_demo.core.cache import Cache
from pd_prime_demo.core.database import Database
from pd_prime_demo.core.result_types import Err, Ok, Result
from pd_prime_demo.models.base import BaseModelConfig

from ...schemas.rating import TerritoryRiskFactors

# Auto-generated models


@beartype
class MetricsData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class TerritoryDefinition:
    """Definition of a rating territory."""

    def __init__(
        self,
        territory_id: str,
        state: str,
        zip_codes: list[str],
        base_factor: float,
        risk_factors: TerritoryRiskFactors,
        description: str,
    ):
        """Initialize territory definition.

        Args:
            territory_id: Unique territory identifier
            state: State code
            zip_codes: List of ZIP codes in this territory
            base_factor: Base rating factor for this territory
            risk_factors: Additional risk factors (crime, weather, etc.)
            description: Human-readable description
        """
        self.territory_id = territory_id
        self.state = state
        self.zip_codes = zip_codes
        self.base_factor = base_factor
        self.risk_factors = risk_factors
        self.description = description

    @beartype
    def calculate_composite_factor(self) -> float:
        """Calculate composite territory factor from all risk components."""
        composite = self.base_factor

        # Apply risk factor multipliers using structured model
        composite *= 1.0 + self.risk_factors.crime_rate * 0.10  # Max 10% impact
        composite *= 1.0 + self.risk_factors.weather_risk * 0.15  # Max 15% impact
        composite *= 1.0 + self.risk_factors.traffic_density * 0.08  # Max 8% impact
        composite *= 1.0 + self.risk_factors.catastrophe_risk * 0.20  # Max 20% impact

        # Ensure factor stays within reasonable bounds
        return max(0.50, min(2.50, composite))


@beartype
class TerritoryManager:
    """Manager for territory definitions and geographic rating."""

    def __init__(self, db: Database, cache: Cache) -> None:
        """Initialize territory manager.

        Args:
            db: Database connection
            cache: Redis cache instance
        """
        self._db = db
        self._cache = cache
        self._cache_prefix = "territory:"
        self._cache_ttl = 86400  # 24 hours - territories change infrequently

        # In-memory cache for frequently accessed territories
        self._territory_cache: dict[str, TerritoryDefinition] = {}

    @beartype
    async def get_territory_factor(
        self, state: str, zip_code: str
    ) -> Result[float, str]:
        """Get territory factor for a specific ZIP code.

        Args:
            state: State code
            zip_code: ZIP code

        Returns:
            Result containing territory factor or error
        """
        # Normalize ZIP code (handle ZIP+4 format)
        zip_base = zip_code[:5] if len(zip_code) > 5 else zip_code

        # Check cache first
        cache_key = f"{self._cache_prefix}{state}:{zip_base}"
        cached = await self._cache.get(cache_key)
        if cached:
            try:
                return Ok(float(cached))
            except ValueError:
                pass  # Fall through to database lookup

        # Look up territory
        territory_result = await self._get_territory_for_zip(state, zip_base)
        if isinstance(territory_result, Err):
            return territory_result

        territory = territory_result.value
        factor = territory.calculate_composite_factor()

        # Cache the result
        await self._cache.set(cache_key, str(factor), self._cache_ttl)

        return Ok(factor)

    @beartype
    async def create_territory(
        self,
        territory_id: str,
        state: str,
        zip_codes: list[str],
        base_factor: float,
        risk_factors: TerritoryRiskFactors,
        description: str,
        admin_user_id: UUID,
    ) -> Result[bool, str]:
        """Create new territory definition.

        Args:
            territory_id: Unique territory identifier
            state: State code
            zip_codes: List of ZIP codes in this territory
            base_factor: Base rating factor
            risk_factors: Risk factor components
            description: Description of territory
            admin_user_id: ID of admin user creating territory

        Returns:
            Result indicating success or error
        """
        try:
            # Validate inputs
            if not 0.5 <= base_factor <= 2.5:
                return Err(
                    f"Base factor {base_factor} outside allowed range [0.5, 2.5]"
                )

            # Validate risk factors using structured model validation
            # The validation is already handled by the TerritoryRiskFactors model

            # Check for ZIP code conflicts
            conflict_check = await self._check_zip_conflicts(
                state, zip_codes, territory_id
            )
            if isinstance(conflict_check, Err):
                return conflict_check

            # Create territory definition
            territory = TerritoryDefinition(
                territory_id, state, zip_codes, base_factor, risk_factors, description
            )

            # Save to database
            save_result = await self._save_territory(territory, admin_user_id)
            if isinstance(save_result, Err):
                return save_result

            # Update cache
            self._territory_cache[f"{state}:{territory_id}"] = territory
            await self._invalidate_zip_cache(state, zip_codes)

            return Ok(True)

        except Exception as e:
            return Err(f"Territory creation failed: {str(e)}")

    @beartype
    async def update_territory_risk_factors(
        self,
        territory_id: str,
        state: str,
        risk_factors: TerritoryRiskFactors,
        admin_user_id: UUID,
    ) -> Result[bool, str]:
        """Update risk factors for existing territory.

        Args:
            territory_id: Territory identifier
            state: State code
            risk_factors: Updated risk factors
            admin_user_id: ID of admin user making update

        Returns:
            Result indicating success or error
        """
        try:
            # Get existing territory
            territory_result = await self._get_territory_definition(state, territory_id)
            if isinstance(territory_result, Err):
                return territory_result

            territory = territory_result.value

            # Update risk factors with new structured model
            territory.risk_factors = risk_factors

            # Save updated territory
            save_result = await self._save_territory(territory, admin_user_id)
            if isinstance(save_result, Err):
                return save_result

            # Update cache
            self._territory_cache[f"{state}:{territory_id}"] = territory
            await self._invalidate_zip_cache(state, territory.zip_codes)

            return Ok(True)

        except Exception as e:
            return Err(f"Territory update failed: {str(e)}")

    @beartype
    async def get_territories_for_state(
        self, state: str
    ) -> Result[list[TerritoryDefinition], str]:
        """Get all territories for a state.

        Args:
            state: State code

        Returns:
            Result containing list of territories or error
        """
        query = """
            SELECT territory_id, state, zip_codes, base_factor,
                   risk_factors, description
            FROM territory_definitions
            WHERE state = $1 AND active = true
            ORDER BY territory_id
        """

        try:
            rows = await self._db.fetch(query, state)
            territories = []

            for row in rows:
                # Parse risk factors from JSON and create structured model
                risk_factors_data = json.loads(row["risk_factors"])
                risk_factors = TerritoryRiskFactors(
                    crime_rate=risk_factors_data.get("crime_rate", 0.0),
                    weather_risk=risk_factors_data.get("weather_risk", 0.0),
                    traffic_density=risk_factors_data.get("traffic_density", 0.0),
                    catastrophe_risk=risk_factors_data.get("catastrophe_risk", 0.0),
                )

                territory = TerritoryDefinition(
                    territory_id=row["territory_id"],
                    state=row["state"],
                    zip_codes=json.loads(row["zip_codes"]),
                    base_factor=float(row["base_factor"]),
                    risk_factors=risk_factors,
                    description=row["description"],
                )
                territories.append(territory)

            return Ok(territories)

        except Exception as e:
            return Err(f"Failed to get territories: {str(e)}")

    @beartype
    async def calculate_risk_metrics(
        self, state: str, zip_code: str
    ) -> Result[dict[str, Any], str]:
        """Calculate comprehensive risk metrics for a ZIP code.

        Args:
            state: State code
            zip_code: ZIP code

        Returns:
            Result containing risk metrics or error
        """
        try:
            # Get territory
            territory_result = await self._get_territory_for_zip(state, zip_code)
            if isinstance(territory_result, Err):
                return territory_result

            territory = territory_result.value

            # Calculate detailed metrics
            metrics: MetricsData = {
                "territory_id": territory.territory_id,
                "base_factor": territory.base_factor,
                "composite_factor": territory.calculate_composite_factor(),
                "risk_components": {},
                "risk_assessment": self._assess_overall_risk(territory),
            }

            # Detail each risk component using structured model
            for factor_name in [
                "crime_rate",
                "weather_risk",
                "traffic_density",
                "catastrophe_risk",
            ]:
                factor_value = getattr(territory.risk_factors, factor_name)
                metrics["risk_components"][factor_name] = {
                    "raw_value": factor_value,
                    "impact": territory.risk_factors.get_risk_impact(factor_name),
                    "description": territory.risk_factors.get_risk_description(
                        factor_name
                    ),
                }

            return Ok(metrics)

        except Exception as e:
            return Err(f"Risk metrics calculation failed: {str(e)}")

    @beartype
    async def bulk_territory_update(
        self,
        state: str,
        updates: list[dict[str, Any]],
        admin_user_id: UUID,
    ) -> Result[dict[str, Any], str]:
        """Perform bulk updates to territories.

        Args:
            state: State code
            updates: List of territory updates
            admin_user_id: ID of admin user

        Returns:
            Result containing update summary or error
        """
        success_count = 0
        failed_updates = []

        async with self._db.transaction():
            for update in updates:
                try:
                    territory_id = update["territory_id"]
                    risk_factors = update["risk_factors"]

                    result = await self.update_territory_risk_factors(
                        territory_id, state, risk_factors, admin_user_id
                    )

                    if result.is_ok():
                        success_count += 1
                    else:
                        failed_updates.append(
                            {
                                "territory_id": territory_id,
                                "error": result.err_value,
                            }
                        )

                except Exception as e:
                    failed_updates.append(
                        {
                            "territory_id": update.get("territory_id", "unknown"),
                            "error": str(e),
                        }
                    )

        return Ok(
            {
                "total_updates": len(updates),
                "successful": success_count,
                "failed": len(failed_updates),
                "failures": failed_updates,
            }
        )

    @beartype
    async def _get_territory_for_zip(
        self, state: str, zip_code: str
    ) -> Result[TerritoryDefinition, str]:
        """Get territory definition for a ZIP code.

        Args:
            state: State code
            zip_code: ZIP code

        Returns:
            Result containing territory definition or error
        """
        query = """
            SELECT territory_id, state, zip_codes, base_factor,
                   risk_factors, description
            FROM territory_definitions
            WHERE state = $1 AND $2 = ANY(zip_codes::text[]) AND active = true
            LIMIT 1
        """

        try:
            row = await self._db.fetchrow(query, state, zip_code)

            if not row:
                # Try to find a default territory
                default_query = """
                    SELECT territory_id, state, zip_codes, base_factor,
                           risk_factors, description
                    FROM territory_definitions
                    WHERE state = $1 AND territory_id = 'default' AND active = true
                    LIMIT 1
                """
                row = await self._db.fetchrow(default_query, state)

            if not row:
                return Err(
                    f"No territory found for ZIP {zip_code} in {state}. "
                    f"Admin must configure territory mapping before quotes can proceed."
                )

            # Parse risk factors from JSON and create structured model
            risk_factors_data = json.loads(row["risk_factors"])
            risk_factors = TerritoryRiskFactors(
                crime_rate=risk_factors_data.get("crime_rate", 0.0),
                weather_risk=risk_factors_data.get("weather_risk", 0.0),
                traffic_density=risk_factors_data.get("traffic_density", 0.0),
                catastrophe_risk=risk_factors_data.get("catastrophe_risk", 0.0),
            )

            territory = TerritoryDefinition(
                territory_id=row["territory_id"],
                state=row["state"],
                zip_codes=json.loads(row["zip_codes"]),
                base_factor=float(row["base_factor"]),
                risk_factors=risk_factors,
                description=row["description"],
            )

            return Ok(territory)

        except Exception as e:
            return Err(f"Territory lookup failed: {str(e)}")

    @beartype
    async def _get_territory_definition(
        self, state: str, territory_id: str
    ) -> Result[TerritoryDefinition, str]:
        """Get territory definition by ID.

        Args:
            state: State code
            territory_id: Territory identifier

        Returns:
            Result containing territory definition or error
        """
        cache_key = f"{state}:{territory_id}"
        if cache_key in self._territory_cache:
            return Ok(self._territory_cache[cache_key])

        query = """
            SELECT territory_id, state, zip_codes, base_factor,
                   risk_factors, description
            FROM territory_definitions
            WHERE state = $1 AND territory_id = $2 AND active = true
        """

        try:
            row = await self._db.fetchrow(query, state, territory_id)

            if not row:
                return Err(f"Territory {territory_id} not found in {state}")

            # Parse risk factors from JSON and create structured model
            risk_factors_data = json.loads(row["risk_factors"])
            risk_factors = TerritoryRiskFactors(
                crime_rate=risk_factors_data.get("crime_rate", 0.0),
                weather_risk=risk_factors_data.get("weather_risk", 0.0),
                traffic_density=risk_factors_data.get("traffic_density", 0.0),
                catastrophe_risk=risk_factors_data.get("catastrophe_risk", 0.0),
            )

            territory = TerritoryDefinition(
                territory_id=row["territory_id"],
                state=row["state"],
                zip_codes=json.loads(row["zip_codes"]),
                base_factor=float(row["base_factor"]),
                risk_factors=risk_factors,
                description=row["description"],
            )

            # Cache for future use
            self._territory_cache[cache_key] = territory

            return Ok(territory)

        except Exception as e:
            return Err(f"Territory lookup failed: {str(e)}")

    @beartype
    async def _check_zip_conflicts(
        self, state: str, zip_codes: list[str], exclude_territory: str | None = None
    ) -> Result[bool, str]:
        """Check for ZIP code conflicts with existing territories.

        Args:
            state: State code
            zip_codes: ZIP codes to check
            exclude_territory: Territory to exclude from conflict check

        Returns:
            Result indicating if conflicts exist
        """
        query = """
            SELECT territory_id, zip_codes
            FROM territory_definitions
            WHERE state = $1 AND active = true
        """
        params = [state]

        if exclude_territory:
            query += " AND territory_id != $2"
            params.append(exclude_territory)

        try:
            rows = await self._db.fetch(query, *params)

            conflicts = []
            for row in rows:
                existing_zips = set(json.loads(row["zip_codes"]))
                new_zips = set(zip_codes)

                overlap = existing_zips.intersection(new_zips)
                if overlap:
                    conflicts.append(
                        {
                            "territory_id": row["territory_id"],
                            "conflicting_zips": list(overlap),
                        }
                    )

            if conflicts:
                return Err(
                    f"ZIP code conflicts found: {conflicts}. "
                    f"Each ZIP code can only belong to one territory."
                )

            return Ok(True)

        except Exception as e:
            return Err(f"Conflict check failed: {str(e)}")

    @beartype
    async def _save_territory(
        self, territory: TerritoryDefinition, admin_user_id: UUID
    ) -> Result[bool, str]:
        """Save territory definition to database.

        Args:
            territory: Territory definition to save
            admin_user_id: ID of admin user

        Returns:
            Result indicating success or error
        """
        query = """
            INSERT INTO territory_definitions (
                territory_id, state, zip_codes, base_factor,
                risk_factors, description, created_by, active
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, true)
            ON CONFLICT (territory_id, state)
            DO UPDATE SET
                zip_codes = EXCLUDED.zip_codes,
                base_factor = EXCLUDED.base_factor,
                risk_factors = EXCLUDED.risk_factors,
                description = EXCLUDED.description,
                updated_by = $7,
                updated_at = CURRENT_TIMESTAMP
        """

        try:
            await self._db.execute(
                query,
                territory.territory_id,
                territory.state,
                json.dumps(territory.zip_codes),
                territory.base_factor,
                territory.risk_factors.model_dump_json(),
                territory.description,
                admin_user_id,
            )

            return Ok(True)

        except Exception as e:
            return Err(f"Territory save failed: {str(e)}")

    @beartype
    async def _invalidate_zip_cache(self, state: str, zip_codes: list[str]) -> None:
        """Invalidate cache entries for ZIP codes.

        Args:
            state: State code
            zip_codes: ZIP codes to invalidate
        """
        for zip_code in zip_codes:
            cache_key = f"{self._cache_prefix}{state}:{zip_code}"
            await self._cache.delete(cache_key)

    @beartype
    def _assess_overall_risk(self, territory: TerritoryDefinition) -> str:
        """Assess overall risk level for territory.

        Args:
            territory: Territory definition

        Returns:
            Risk assessment string
        """
        composite_factor = territory.calculate_composite_factor()

        if composite_factor >= 1.5:
            return "high"
        elif composite_factor >= 1.2:
            return "elevated"
        elif composite_factor >= 0.9:
            return "standard"
        elif composite_factor >= 0.7:
            return "below_average"
        else:
            return "low"

    @beartype
    def _calculate_risk_impact(self, factor_name: str, factor_value: float) -> float:
        """Calculate the impact of a specific risk factor.

        Args:
            factor_name: Name of the risk factor
            factor_value: Value of the risk factor

        Returns:
            Impact percentage
        """
        impact_multipliers = {
            "crime_rate": 0.10,
            "weather_risk": 0.15,
            "traffic_density": 0.08,
            "catastrophe_risk": 0.20,
        }

        multiplier = impact_multipliers.get(factor_name, 0.05)
        return factor_value * multiplier

    @beartype
    def _get_risk_description(self, factor_name: str, factor_value: float) -> str:
        """Get human-readable description of risk factor.

        Args:
            factor_name: Name of the risk factor
            factor_value: Value of the risk factor

        Returns:
            Risk description string
        """
        if factor_value > 0.5:
            level = "high"
        elif factor_value > 0.2:
            level = "elevated"
        elif factor_value > -0.2:
            level = "average"
        else:
            level = "low"

        descriptions = {
            "crime_rate": f"{level.title()} crime rate impact",
            "weather_risk": f"{level.title()} weather-related risk",
            "traffic_density": f"{level.title()} traffic density impact",
            "catastrophe_risk": f"{level.title()} natural disaster risk",
        }

        return descriptions.get(factor_name, f"{level.title()} risk factor")
