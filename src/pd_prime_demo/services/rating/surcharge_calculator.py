"""Surcharge calculation for high-risk factors.

This module implements comprehensive surcharge calculations for various
risk factors including DUI, SR-22, accidents, and other high-risk indicators.
"""

# Standard lib
# Set decimal precision for financial calculations
from decimal import Decimal, getcontext
from typing import Any, Tuple

# Third-party
from beartype import beartype

from pd_prime_demo.core.result_types import Err, Ok, Result

# Project
from pd_prime_demo.models.quote import DriverInfo, VehicleInfo

getcontext().prec = 10


@beartype
class SurchargeCalculator:
    """Calculate and apply surcharges for high-risk factors."""

    @beartype
    @staticmethod
    def calculate_all_surcharges(
        drivers: list[DriverInfo],
        vehicle_info: VehicleInfo | None,
        state: str,
        base_premium: Decimal,
    ) -> Result[Tuple[list[dict[str, Any]], Decimal], str]:
        """Calculate all applicable surcharges.

        Args:
            drivers: List of drivers on the policy
            vehicle_info: Vehicle information
            state: State code
            base_premium: Base premium before surcharges

        Returns:
            Result containing (list of surcharges, total surcharge amount) or error
        """
        if base_premium <= 0:
            return Err("Base premium must be positive for surcharge calculation")

        surcharges = []
        total_surcharge_amount = Decimal("0")

        # DUI/SR-22 surcharges
        dui_result = SurchargeCalculator._calculate_dui_surcharges(
            drivers, state, base_premium
        )
        if dui_result.is_err():
            return Err(f"DUI surcharge calculation failed: {dui_result.unwrap_err()}")

        dui_surcharges, dui_amount = dui_result.unwrap()
        surcharges.extend(dui_surcharges)
        total_surcharge_amount += dui_amount

        # High-risk driver surcharges
        risk_result = SurchargeCalculator._calculate_high_risk_surcharges(
            drivers, state, base_premium
        )
        if risk_result.is_err():
            return Err(
                f"High-risk surcharge calculation failed: {risk_result.unwrap_err()}"
            )

        risk_surcharges, risk_amount = risk_result.unwrap()
        surcharges.extend(risk_surcharges)
        total_surcharge_amount += risk_amount

        # Young driver surcharges
        young_result = SurchargeCalculator._calculate_young_driver_surcharges(
            drivers, state, base_premium
        )
        if young_result.is_err():
            return Err(
                f"Young driver surcharge calculation failed: {young_result.unwrap_err()}"
            )

        young_surcharges, young_amount = young_result.unwrap()
        surcharges.extend(young_surcharges)
        total_surcharge_amount += young_amount

        # Inexperienced driver surcharges
        exp_result = SurchargeCalculator._calculate_inexperienced_driver_surcharges(
            drivers, state, base_premium
        )
        if exp_result.is_err():
            return Err(
                f"Inexperienced driver surcharge calculation failed: {exp_result.unwrap_err()}"
            )

        exp_surcharges, exp_amount = exp_result.unwrap()
        surcharges.extend(exp_surcharges)
        total_surcharge_amount += exp_amount

        # Lapse in coverage surcharge
        lapse_result = SurchargeCalculator._calculate_coverage_lapse_surcharge(
            drivers, state, base_premium
        )
        if lapse_result.is_err():
            return Err(
                f"Coverage lapse surcharge calculation failed: {lapse_result.unwrap_err()}"
            )

        lapse_surcharges, lapse_amount = lapse_result.unwrap()
        surcharges.extend(lapse_surcharges)
        total_surcharge_amount += lapse_amount

        # Vehicle-based surcharges
        if vehicle_info:
            vehicle_result = SurchargeCalculator._calculate_vehicle_surcharges(
                vehicle_info, state, base_premium
            )
            if vehicle_result.is_err():
                return Err(
                    f"Vehicle surcharge calculation failed: {vehicle_result.unwrap_err()}"
                )

            vehicle_surcharges, vehicle_amount = vehicle_result.unwrap()
            surcharges.extend(vehicle_surcharges)
            total_surcharge_amount += vehicle_amount

        # Apply state-specific surcharge caps
        capped_result = SurchargeCalculator._apply_state_surcharge_caps(
            surcharges, total_surcharge_amount, state, base_premium
        )
        if capped_result.is_err():
            return capped_result

        capped_surcharges, capped_amount = capped_result.unwrap()

        return Ok((capped_surcharges, capped_amount.quantize(Decimal("0.01"))))

    @beartype
    @staticmethod
    def _calculate_dui_surcharges(
        drivers: list[DriverInfo],
        state: str,
        base_premium: Decimal,
    ) -> Result[Tuple[list[dict[str, Any]], Decimal], str]:
        """Calculate DUI and SR-22 surcharges."""
        surcharges = []
        total_amount = Decimal("0")

        for driver in drivers:
            if driver.dui_convictions > 0:
                # DUI surcharge rates by number of convictions
                if driver.dui_convictions == 1:
                    surcharge_rate = Decimal("0.50")  # 50% surcharge
                elif driver.dui_convictions == 2:
                    surcharge_rate = Decimal("0.75")  # 75% surcharge
                else:
                    surcharge_rate = Decimal("1.00")  # 100% surcharge

                surcharge_amount = base_premium * surcharge_rate

                surcharges.append(
                    {
                        "type": "dui_conviction",
                        "driver_id": driver.id,
                        "driver_name": f"{driver.first_name} {driver.last_name}",
                        "reason": f"DUI conviction(s): {driver.dui_convictions}",
                        "rate": float(surcharge_rate),
                        "amount": surcharge_amount,
                        "severity": "high",
                    }
                )

                total_amount += surcharge_amount

                # SR-22 filing fee (flat fee, not percentage based)
                sr22_fee = Decimal("25.00")  # Standard SR-22 filing fee
                surcharges.append(
                    {
                        "type": "sr22_filing",
                        "driver_id": driver.id,
                        "driver_name": f"{driver.first_name} {driver.last_name}",
                        "reason": "SR-22 filing required",
                        "rate": 0.0,  # Flat fee, not a rate
                        "amount": sr22_fee,
                        "severity": "high",
                        "is_flat_fee": True,
                    }
                )

                total_amount += sr22_fee

        return Ok((surcharges, total_amount))

    @beartype
    @staticmethod
    def _calculate_high_risk_surcharges(
        drivers: list[DriverInfo],
        state: str,
        base_premium: Decimal,
    ) -> Result[Tuple[list[dict[str, Any]], Decimal], str]:
        """Calculate surcharges for high-risk drivers (multiple violations/accidents)."""
        surcharges = []
        total_amount = Decimal("0")

        for driver in drivers:
            # Calculate risk score based on violations and accidents
            risk_score = (driver.violations_3_years * 2) + (
                driver.accidents_3_years * 3
            )

            if risk_score >= 8:  # Very high risk
                surcharge_rate = Decimal("0.40")  # 40% surcharge
                risk_level = "very_high"
            elif risk_score >= 5:  # High risk
                surcharge_rate = Decimal("0.25")  # 25% surcharge
                risk_level = "high"
            elif risk_score >= 3:  # Moderate risk
                surcharge_rate = Decimal("0.15")  # 15% surcharge
                risk_level = "moderate"
            else:
                continue  # No surcharge for low risk

            surcharge_amount = base_premium * surcharge_rate

            surcharges.append(
                {
                    "type": "high_risk_driver",
                    "driver_id": driver.id,
                    "driver_name": f"{driver.first_name} {driver.last_name}",
                    "reason": f"{driver.violations_3_years} violations, {driver.accidents_3_years} accidents",
                    "rate": float(surcharge_rate),
                    "amount": surcharge_amount,
                    "severity": risk_level,
                    "risk_score": risk_score,
                }
            )

            total_amount += surcharge_amount

        return Ok((surcharges, total_amount))

    @beartype
    @staticmethod
    def _calculate_young_driver_surcharges(
        drivers: list[DriverInfo],
        state: str,
        base_premium: Decimal,
    ) -> Result[Tuple[list[dict[str, Any]], Decimal], str]:
        """Calculate surcharges for young drivers."""
        surcharges = []
        total_amount = Decimal("0")

        # State-specific young driver definitions
        young_driver_age_limits = {
            "CA": 25,  # Under 25 in California
            "TX": 25,  # Under 25 in Texas
            "NY": 26,  # Under 26 in New York
            "FL": 25,  # Under 25 in Florida
            "MI": 25,  # Under 25 in Michigan
            "PA": 25,  # Under 25 in Pennsylvania
        }

        age_limit = young_driver_age_limits.get(state, 25)

        for driver in drivers:
            if driver.age < age_limit:
                # Surcharge based on how young
                if driver.age < 18:
                    surcharge_rate = Decimal("0.50")  # 50% for very young
                elif driver.age < 21:
                    surcharge_rate = Decimal("0.35")  # 35% for under 21
                elif driver.age < 23:
                    surcharge_rate = Decimal("0.20")  # 20% for under 23
                else:
                    surcharge_rate = Decimal("0.10")  # 10% for under 25

                surcharge_amount = base_premium * surcharge_rate

                surcharges.append(
                    {
                        "type": "young_driver",
                        "driver_id": driver.id,
                        "driver_name": f"{driver.first_name} {driver.last_name}",
                        "reason": f"Driver age {driver.age} (under {age_limit})",
                        "rate": float(surcharge_rate),
                        "amount": surcharge_amount,
                        "severity": "medium",
                    }
                )

                total_amount += surcharge_amount

        return Ok((surcharges, total_amount))

    @beartype
    @staticmethod
    def _calculate_inexperienced_driver_surcharges(
        drivers: list[DriverInfo],
        state: str,
        base_premium: Decimal,
    ) -> Result[Tuple[list[dict[str, Any]], Decimal], str]:
        """Calculate surcharges for inexperienced drivers."""
        surcharges = []
        total_amount = Decimal("0")

        for driver in drivers:
            if driver.years_licensed < 3:
                # Surcharge based on experience level
                if driver.years_licensed < 1:
                    surcharge_rate = Decimal("0.30")  # 30% for brand new
                elif driver.years_licensed < 2:
                    surcharge_rate = Decimal("0.20")  # 20% for 1 year
                else:
                    surcharge_rate = Decimal("0.10")  # 10% for 2 years

                surcharge_amount = base_premium * surcharge_rate

                surcharges.append(
                    {
                        "type": "inexperienced_driver",
                        "driver_id": driver.id,
                        "driver_name": f"{driver.first_name} {driver.last_name}",
                        "reason": f"Licensed for only {driver.years_licensed} year(s)",
                        "rate": float(surcharge_rate),
                        "amount": surcharge_amount,
                        "severity": "medium",
                    }
                )

                total_amount += surcharge_amount

        return Ok((surcharges, total_amount))

    @beartype
    @staticmethod
    def _calculate_coverage_lapse_surcharge(
        drivers: list[DriverInfo],
        state: str,
        base_premium: Decimal,
    ) -> Result[Tuple[list[dict[str, Any]], Decimal], str]:
        """Calculate surcharge for lapse in coverage."""
        surcharges = []
        total_amount = Decimal("0")

        # Check if any driver has coverage lapse
        has_lapse = any(
            hasattr(driver, "coverage_lapse_days")
            and getattr(driver, "coverage_lapse_days", 0) > 0
            for driver in drivers
        )

        if has_lapse:
            # Find the driver with the longest lapse
            max_lapse_days = max(
                getattr(driver, "coverage_lapse_days", 0) for driver in drivers
            )

            if max_lapse_days > 90:
                surcharge_rate = Decimal("0.25")  # 25% for >90 days
            elif max_lapse_days > 30:
                surcharge_rate = Decimal("0.15")  # 15% for 31-90 days
            elif max_lapse_days > 7:
                surcharge_rate = Decimal("0.10")  # 10% for 8-30 days
            else:
                surcharge_rate = Decimal("0.05")  # 5% for 1-7 days

            surcharge_amount = base_premium * surcharge_rate

            surcharges.append(
                {
                    "type": "coverage_lapse",
                    "driver_id": None,  # Policy-level surcharge
                    "driver_name": "Policy",
                    "reason": f"Coverage lapse of {max_lapse_days} days",
                    "rate": float(surcharge_rate),
                    "amount": surcharge_amount,
                    "severity": "high" if max_lapse_days > 30 else "medium",
                }
            )

            total_amount += surcharge_amount

        return Ok((surcharges, total_amount))

    @beartype
    @staticmethod
    def _calculate_vehicle_surcharges(
        vehicle_info: VehicleInfo,
        state: str,
        base_premium: Decimal,
    ) -> Result[Tuple[list[dict[str, Any]], Decimal], str]:
        """Calculate vehicle-based surcharges."""
        surcharges = []
        total_amount = Decimal("0")

        # High-performance vehicle surcharge
        if hasattr(vehicle_info, "vehicle_type") and vehicle_info.vehicle_type in [
            "sports",
            "luxury",
        ]:
            surcharge_rate = Decimal("0.20")  # 20% for sports/luxury
            surcharge_amount = base_premium * surcharge_rate

            surcharges.append(
                {
                    "type": "high_performance_vehicle",
                    "driver_id": None,
                    "driver_name": "Vehicle",
                    "reason": f"{vehicle_info.vehicle_type.title()} vehicle classification",
                    "rate": float(surcharge_rate),
                    "amount": surcharge_amount,
                    "severity": "low",
                }
            )

            total_amount += surcharge_amount

        # Commercial use surcharge
        if (
            hasattr(vehicle_info, "usage_type")
            and vehicle_info.usage_type == "commercial"
        ):
            surcharge_rate = Decimal("0.30")  # 30% for commercial use
            surcharge_amount = base_premium * surcharge_rate

            surcharges.append(
                {
                    "type": "commercial_use",
                    "driver_id": None,
                    "driver_name": "Vehicle",
                    "reason": "Commercial vehicle usage",
                    "rate": float(surcharge_rate),
                    "amount": surcharge_amount,
                    "severity": "medium",
                }
            )

            total_amount += surcharge_amount

        # Modified vehicle surcharge
        if hasattr(vehicle_info, "is_modified") and vehicle_info.is_modified:
            surcharge_rate = Decimal("0.15")  # 15% for modifications
            surcharge_amount = base_premium * surcharge_rate

            surcharges.append(
                {
                    "type": "vehicle_modifications",
                    "driver_id": None,
                    "driver_name": "Vehicle",
                    "reason": "Vehicle has aftermarket modifications",
                    "rate": float(surcharge_rate),
                    "amount": surcharge_amount,
                    "severity": "low",
                }
            )

            total_amount += surcharge_amount

        return Ok((surcharges, total_amount))

    @beartype
    @staticmethod
    def _apply_state_surcharge_caps(
        surcharges: list[dict[str, Any]],
        total_amount: Decimal,
        state: str,
        base_premium: Decimal,
    ) -> Result[Tuple[list[dict[str, Any]], Decimal], str]:
        """Apply state-specific surcharge caps."""
        # State-specific maximum surcharge percentages
        state_caps = {
            "CA": Decimal("1.50"),  # 150% max surcharge in California
            "TX": Decimal("2.00"),  # 200% max surcharge in Texas
            "NY": Decimal("1.75"),  # 175% max surcharge in New York
            "FL": Decimal("2.50"),  # 250% max surcharge in Florida (hurricanes)
            "MI": Decimal("1.50"),  # 150% max surcharge in Michigan
            "PA": Decimal("1.75"),  # 175% max surcharge in Pennsylvania
        }

        max_surcharge_rate = state_caps.get(state, Decimal("2.00"))
        max_surcharge_amount = base_premium * max_surcharge_rate

        if total_amount > max_surcharge_amount:
            # Need to cap surcharges
            scaling_factor = max_surcharge_amount / total_amount

            capped_surcharges = []
            capped_total = Decimal("0")

            for surcharge in surcharges:
                # Don't scale flat fees
                if surcharge.get("is_flat_fee", False):
                    capped_surcharges.append(surcharge)
                    capped_total += surcharge["amount"]
                else:
                    capped_amount = surcharge["amount"] * scaling_factor
                    capped_surcharge = surcharge.copy()
                    capped_surcharge["amount"] = capped_amount
                    capped_surcharge["capped"] = True
                    capped_surcharge["original_amount"] = surcharge["amount"]
                    capped_surcharges.append(capped_surcharge)
                    capped_total += capped_amount

            return Ok((capped_surcharges, capped_total))

        return Ok((surcharges, total_amount))

    @beartype
    @staticmethod
    def format_surcharge_summary(
        surcharges: list[dict[str, Any]],
        total_amount: Decimal,
    ) -> dict[str, Any]:
        """Format surcharges into a summary report."""
        by_type = {}
        by_severity = {"high": [], "medium": [], "low": []}

        for surcharge in surcharges:
            surcharge_type = surcharge["type"]
            if surcharge_type not in by_type:
                by_type[surcharge_type] = {
                    "count": 0,
                    "total_amount": Decimal("0"),
                    "items": [],
                }

            by_type[surcharge_type]["count"] += 1
            by_type[surcharge_type]["total_amount"] += surcharge["amount"]
            by_type[surcharge_type]["items"].append(surcharge)

            severity = surcharge.get("severity", "low")
            by_severity[severity].append(surcharge)

        return {
            "total_surcharge_amount": float(total_amount),
            "surcharge_count": len(surcharges),
            "by_type": {
                k: {
                    "count": v["count"],
                    "total_amount": float(v["total_amount"]),
                    "items": v["items"],
                }
                for k, v in by_type.items()
            },
            "by_severity": {k: len(v) for k, v in by_severity.items()},
            "has_high_severity": len(by_severity["high"]) > 0,
            "requires_sr22": any(s["type"] == "sr22_filing" for s in surcharges),
        }
