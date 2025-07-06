"""Business rule validation for rating calculations.

This module implements comprehensive business rule validation to ensure
all rating calculations follow proper insurance industry standards and
regulatory requirements.
"""

from decimal import Decimal
from typing import Any

from beartype import beartype

from ...models.quote import CoverageSelection, DriverInfo, VehicleInfo
from ..result import Err, Ok, Result


@beartype
class BusinessRuleViolation:
    """Represents a business rule violation."""

    def __init__(
        self,
        rule_id: str,
        severity: str,  # "error", "warning", "info"
        message: str,
        field: str | None = None,
        suggested_action: str | None = None,
    ):
        """Initialize business rule violation.

        Args:
            rule_id: Unique identifier for the rule
            severity: Severity level of the violation
            message: Human-readable description
            field: Field that caused the violation
            suggested_action: Recommended action to resolve
        """
        self.rule_id = rule_id
        self.severity = severity
        self.message = message
        self.field = field
        self.suggested_action = suggested_action

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "message": self.message,
            "field": self.field,
            "suggested_action": self.suggested_action,
        }


@beartype
class RatingBusinessRules:
    """Comprehensive business rule validation for rating calculations."""

    def __init__(self):
        """Initialize business rules validator."""
        # Define maximum factor limits to prevent extreme ratings
        self._max_factor_limits = {
            "driver_age": 3.0,  # 300% maximum
            "violations": 2.5,  # 250% maximum
            "accidents": 3.0,  # 300% maximum
            "dui": 4.0,  # 400% maximum
            "vehicle_age": 1.5,  # 150% maximum
            "territory": 2.0,  # 200% maximum
            "credit": 1.5,  # 150% maximum
        }

        # Define minimum factor limits to prevent unrealistic discounts
        self._min_factor_limits = {
            "driver_age": 0.6,  # 40% minimum (60% discount max)
            "violations": 0.8,  # 20% discount max for clean record
            "accidents": 0.8,  # 20% discount max for no accidents
            "vehicle_age": 0.7,  # 30% discount max for older vehicles
            "territory": 0.5,  # 50% minimum (very low risk areas)
            "credit": 0.7,  # 30% discount max for excellent credit
        }

    @beartype
    async def validate_premium_calculation(
        self,
        state: str,
        product_type: str,
        vehicle_info: VehicleInfo | None,
        drivers: list[DriverInfo],
        coverage_selections: list[CoverageSelection],
        factors: dict[str, float],
        base_premium: Decimal,
        total_premium: Decimal,
        discounts: list[Any],
        surcharges: list[dict[str, Any]],
    ) -> Result[list[BusinessRuleViolation], str]:
        """Validate complete premium calculation against business rules.

        Args:
            state: State code
            product_type: Product type (auto, home, etc.)
            vehicle_info: Vehicle information
            drivers: List of drivers
            coverage_selections: Coverage selections
            factors: Calculated rating factors
            base_premium: Base premium before factors
            total_premium: Final calculated premium
            discounts: Applied discounts
            surcharges: Applied surcharges

        Returns:
            Result containing list of violations or error
        """
        violations = []

        try:
            # Validate factor ranges
            factor_violations = await self._validate_factor_ranges(factors)
            violations.extend(factor_violations)

            # Validate premium reasonableness
            premium_violations = await self._validate_premium_reasonableness(
                base_premium, total_premium, factors
            )
            violations.extend(premium_violations)

            # Validate discount stacking
            discount_violations = await self._validate_discount_stacking(
                discounts, base_premium
            )
            violations.extend(discount_violations)

            # Validate surcharge logic
            surcharge_violations = await self._validate_surcharge_logic(
                surcharges, drivers, vehicle_info
            )
            violations.extend(surcharge_violations)

            # Validate coverage appropriateness
            coverage_violations = await self._validate_coverage_appropriateness(
                coverage_selections, vehicle_info, drivers, state
            )
            violations.extend(coverage_violations)

            # Validate driver eligibility
            if drivers:
                driver_violations = await self._validate_driver_eligibility(
                    drivers, state
                )
                violations.extend(driver_violations)

            # Validate vehicle eligibility
            if vehicle_info:
                vehicle_violations = await self._validate_vehicle_eligibility(
                    vehicle_info, state
                )
                violations.extend(vehicle_violations)

            # Validate regulatory compliance
            regulatory_violations = await self._validate_regulatory_compliance(
                state, factors, total_premium, coverage_selections
            )
            violations.extend(regulatory_violations)

            return Ok(violations)

        except Exception as e:
            return Err(f"Business rule validation failed: {str(e)}")

    @beartype
    async def _validate_factor_ranges(
        self, factors: dict[str, float]
    ) -> list[BusinessRuleViolation]:
        """Validate that all factors are within acceptable ranges."""
        violations = []

        for factor_name, factor_value in factors.items():
            # Check maximum limits
            max_limit = self._max_factor_limits.get(factor_name)
            if max_limit and factor_value > max_limit:
                violations.append(
                    BusinessRuleViolation(
                        rule_id=f"FACTOR_MAX_{factor_name.upper()}",
                        severity="error",
                        message=f"Factor {factor_name} value {factor_value:.3f} exceeds maximum allowed {max_limit}",
                        field=factor_name,
                        suggested_action=f"Cap factor at maximum value {max_limit}",
                    )
                )

            # Check minimum limits
            min_limit = self._min_factor_limits.get(factor_name)
            if min_limit and factor_value < min_limit:
                violations.append(
                    BusinessRuleViolation(
                        rule_id=f"FACTOR_MIN_{factor_name.upper()}",
                        severity="error",
                        message=f"Factor {factor_name} value {factor_value:.3f} below minimum allowed {min_limit}",
                        field=factor_name,
                        suggested_action=f"Set factor to minimum value {min_limit}",
                    )
                )

            # Check for extreme values that might indicate calculation errors
            if factor_value <= 0:
                violations.append(
                    BusinessRuleViolation(
                        rule_id=f"FACTOR_ZERO_{factor_name.upper()}",
                        severity="error",
                        message=f"Factor {factor_name} is zero or negative: {factor_value}",
                        field=factor_name,
                        suggested_action="Investigate factor calculation logic",
                    )
                )
            elif factor_value > 10:
                violations.append(
                    BusinessRuleViolation(
                        rule_id=f"FACTOR_EXTREME_{factor_name.upper()}",
                        severity="warning",
                        message=f"Factor {factor_name} is extremely high: {factor_value:.3f}",
                        field=factor_name,
                        suggested_action="Review factor calculation for accuracy",
                    )
                )

        return violations

    @beartype
    async def _validate_premium_reasonableness(
        self,
        base_premium: Decimal,
        total_premium: Decimal,
        factors: dict[str, float],
    ) -> list[BusinessRuleViolation]:
        """Validate that premiums are within reasonable ranges."""
        violations = []

        # Check for negative premiums
        if total_premium < 0:
            violations.append(
                BusinessRuleViolation(
                    rule_id="PREMIUM_NEGATIVE",
                    severity="error",
                    message=f"Total premium is negative: ${total_premium}",
                    field="total_premium",
                    suggested_action="Check discount calculations and factor applications",
                )
            )

        # Check for zero premiums (unless legitimately free)
        if total_premium == 0:
            violations.append(
                BusinessRuleViolation(
                    rule_id="PREMIUM_ZERO",
                    severity="warning",
                    message="Total premium is zero - verify this is intentional",
                    field="total_premium",
                    suggested_action="Review calculation logic for zero premium scenarios",
                )
            )

        # Check for extremely high premiums
        if total_premium > Decimal("50000"):
            violations.append(
                BusinessRuleViolation(
                    rule_id="PREMIUM_EXTREME_HIGH",
                    severity="warning",
                    message=f"Total premium is extremely high: ${total_premium}",
                    field="total_premium",
                    suggested_action="Review high-risk factors and verify calculation accuracy",
                )
            )

        # Check for unreasonable premium changes from base
        if base_premium > 0:
            premium_ratio = float(total_premium / base_premium)

            if premium_ratio > 5.0:
                violations.append(
                    BusinessRuleViolation(
                        rule_id="PREMIUM_RATIO_HIGH",
                        severity="warning",
                        message=f"Premium increased by {premium_ratio:.1f}x from base (${base_premium} to ${total_premium})",
                        field="total_premium",
                        suggested_action="Review factor applications for excessive multiplication",
                    )
                )
            elif premium_ratio < 0.2:
                violations.append(
                    BusinessRuleViolation(
                        rule_id="PREMIUM_RATIO_LOW",
                        severity="warning",
                        message=f"Premium decreased by {1/premium_ratio:.1f}x from base (${base_premium} to ${total_premium})",
                        field="total_premium",
                        suggested_action="Review discount applications for excessive reduction",
                    )
                )

        return violations

    @beartype
    async def _validate_discount_stacking(
        self,
        discounts: list[Any],
        base_premium: Decimal,
    ) -> list[BusinessRuleViolation]:
        """Validate discount stacking rules."""
        violations = []

        if not discounts:
            return violations

        # Calculate total discount percentage
        total_discount_amount = sum(d.amount for d in discounts)
        if base_premium > 0:
            total_discount_pct = float(total_discount_amount / base_premium * 100)
        else:
            total_discount_pct = 0

        # Check maximum total discount limit
        if total_discount_pct > 50:
            violations.append(
                BusinessRuleViolation(
                    rule_id="DISCOUNT_STACKING_LIMIT",
                    severity="error",
                    message=f"Total discounts ({total_discount_pct:.1f}%) exceed 50% maximum",
                    field="discounts",
                    suggested_action="Apply discount capping rules to limit total to 50%",
                )
            )

        # Check for conflicting discount types
        discount_types = {d.discount_type.value for d in discounts}

        # Good student and senior discounts shouldn't stack
        if "good_student" in discount_types and "senior" in discount_types:
            violations.append(
                BusinessRuleViolation(
                    rule_id="DISCOUNT_CONFLICT_STUDENT_SENIOR",
                    severity="error",
                    message="Good student and senior discounts cannot both apply",
                    field="discounts",
                    suggested_action="Apply only the applicable discount based on driver age",
                )
            )

        # Check individual discount limits
        for discount in discounts:
            discount_pct = float(discount.percentage)

            if discount_pct > 25:  # No single discount should exceed 25%
                violations.append(
                    BusinessRuleViolation(
                        rule_id=f"DISCOUNT_INDIVIDUAL_LIMIT_{discount.discount_type.value.upper()}",
                        severity="warning",
                        message=f"{discount.discount_type.value} discount ({discount_pct:.1f}%) exceeds typical 25% limit",
                        field="discounts",
                        suggested_action="Review discount calculation for this type",
                    )
                )

        return violations

    @beartype
    async def _validate_surcharge_logic(
        self,
        surcharges: list[dict[str, Any]],
        drivers: list[DriverInfo],
        vehicle_info: VehicleInfo | None,
    ) -> list[BusinessRuleViolation]:
        """Validate surcharge application logic."""
        violations = []

        # Check SR-22 surcharge logic
        sr22_surcharges = [s for s in surcharges if s.get("type") == "sr22_filing"]
        has_dui_drivers = any(d.dui_convictions > 0 for d in drivers)

        if sr22_surcharges and not has_dui_drivers:
            violations.append(
                BusinessRuleViolation(
                    rule_id="SURCHARGE_SR22_INVALID",
                    severity="error",
                    message="SR-22 surcharge applied without DUI conviction",
                    field="surcharges",
                    suggested_action="Remove SR-22 surcharge or verify DUI history",
                )
            )

        if has_dui_drivers and not sr22_surcharges:
            violations.append(
                BusinessRuleViolation(
                    rule_id="SURCHARGE_SR22_MISSING",
                    severity="warning",
                    message="DUI conviction present but no SR-22 surcharge applied",
                    field="surcharges",
                    suggested_action="Add required SR-22 filing surcharge",
                )
            )

        # Check high-risk surcharge logic
        high_risk_surcharges = [s for s in surcharges if s.get("type") == "high_risk"]
        high_risk_drivers = [
            d for d in drivers if d.violations_3_years > 3 or d.accidents_3_years > 2
        ]

        if high_risk_surcharges and not high_risk_drivers:
            violations.append(
                BusinessRuleViolation(
                    rule_id="SURCHARGE_HIGH_RISK_INVALID",
                    severity="warning",
                    message="High-risk surcharge applied without qualifying drivers",
                    field="surcharges",
                    suggested_action="Review high-risk criteria and driver records",
                )
            )

        return violations

    @beartype
    async def _validate_coverage_appropriateness(
        self,
        coverage_selections: list[CoverageSelection],
        vehicle_info: VehicleInfo | None,
        drivers: list[DriverInfo],
        state: str,
    ) -> list[BusinessRuleViolation]:
        """Validate coverage selections are appropriate."""
        violations = []

        # Check for extremely high coverage on old vehicles
        if vehicle_info:
            vehicle_age = 2024 - vehicle_info.year

            for coverage in coverage_selections:
                if coverage.coverage_type.value in ["collision", "comprehensive"]:
                    if vehicle_age > 10 and coverage.limit > Decimal("20000"):
                        violations.append(
                            BusinessRuleViolation(
                                rule_id="COVERAGE_HIGH_LIMIT_OLD_VEHICLE",
                                severity="warning",
                                message=f"High {coverage.coverage_type.value} limit (${coverage.limit}) on {vehicle_age}-year-old vehicle",
                                field="coverage_selections",
                                suggested_action="Consider reducing coverage limits for older vehicles",
                            )
                        )

        # Check for suspiciously low liability limits
        liability_coverages = [
            c for c in coverage_selections if c.coverage_type.value == "liability"
        ]

        for liability in liability_coverages:
            if liability.limit < Decimal("100000"):
                violations.append(
                    BusinessRuleViolation(
                        rule_id="COVERAGE_LOW_LIABILITY",
                        severity="info",
                        message=f"Liability limit (${liability.limit}) below recommended minimum $100,000",
                        field="coverage_selections",
                        suggested_action="Consider increasing liability coverage for better protection",
                    )
                )

        # Check for missing recommended coverages
        coverage_types = {c.coverage_type.value for c in coverage_selections}

        if "uninsured_motorist" not in coverage_types:
            violations.append(
                BusinessRuleViolation(
                    rule_id="COVERAGE_MISSING_UM",
                    severity="info",
                    message="Uninsured motorist coverage not selected",
                    field="coverage_selections",
                    suggested_action="Consider adding uninsured motorist protection",
                )
            )

        return violations

    @beartype
    async def _validate_driver_eligibility(
        self, drivers: list[DriverInfo], state: str
    ) -> list[BusinessRuleViolation]:
        """Validate driver eligibility and risk factors."""
        violations = []

        for i, driver in enumerate(drivers):
            driver_field = f"drivers[{i}]"

            # Age validation
            if driver.age < 16:
                violations.append(
                    BusinessRuleViolation(
                        rule_id="DRIVER_AGE_TOO_YOUNG",
                        severity="error",
                        message=f"Driver {driver.first_name} {driver.last_name} is under minimum age (16)",
                        field=driver_field,
                        suggested_action="Remove unlicensed driver or verify age",
                    )
                )
            elif driver.age > 90:
                violations.append(
                    BusinessRuleViolation(
                        rule_id="DRIVER_AGE_VERY_HIGH",
                        severity="warning",
                        message=f"Driver {driver.first_name} {driver.last_name} is {driver.age} years old",
                        field=driver_field,
                        suggested_action="Verify driver age and consider additional restrictions",
                    )
                )

            # License validation
            if driver.years_licensed > (driver.age - 15):
                violations.append(
                    BusinessRuleViolation(
                        rule_id="DRIVER_LICENSE_YEARS_INVALID",
                        severity="error",
                        message=f"Driver {driver.first_name} {driver.last_name} has more years licensed than possible",
                        field=driver_field,
                        suggested_action="Verify years licensed data",
                    )
                )

            # Excessive violations
            if driver.violations_3_years > 10:
                violations.append(
                    BusinessRuleViolation(
                        rule_id="DRIVER_EXCESSIVE_VIOLATIONS",
                        severity="error",
                        message=f"Driver {driver.first_name} {driver.last_name} has excessive violations ({driver.violations_3_years})",
                        field=driver_field,
                        suggested_action="Review driver record and consider policy restrictions",
                    )
                )

            # Multiple DUIs
            if driver.dui_convictions > 2:
                violations.append(
                    BusinessRuleViolation(
                        rule_id="DRIVER_MULTIPLE_DUI",
                        severity="error",
                        message=f"Driver {driver.first_name} {driver.last_name} has multiple DUI convictions",
                        field=driver_field,
                        suggested_action="Consider declining coverage or special underwriting",
                    )
                )

        return violations

    @beartype
    async def _validate_vehicle_eligibility(
        self, vehicle_info: VehicleInfo, state: str
    ) -> list[BusinessRuleViolation]:
        """Validate vehicle eligibility and characteristics."""
        violations = []

        # Vehicle age validation
        vehicle_age = 2024 - vehicle_info.year
        if vehicle_age > 30:
            violations.append(
                BusinessRuleViolation(
                    rule_id="VEHICLE_AGE_EXTREME",
                    severity="warning",
                    message=f"Vehicle is {vehicle_age} years old (very old)",
                    field="vehicle_info",
                    suggested_action="Verify vehicle condition and consider coverage limitations",
                )
            )

        # Mileage validation
        if vehicle_info.annual_mileage > 50000:
            violations.append(
                BusinessRuleViolation(
                    rule_id="VEHICLE_HIGH_MILEAGE",
                    severity="warning",
                    message=f"Vehicle has very high annual mileage ({vehicle_info.annual_mileage})",
                    field="vehicle_info",
                    suggested_action="Verify mileage and consider commercial use classification",
                )
            )
        elif vehicle_info.annual_mileage < 1000:
            violations.append(
                BusinessRuleViolation(
                    rule_id="VEHICLE_LOW_MILEAGE",
                    severity="info",
                    message=f"Vehicle has very low annual mileage ({vehicle_info.annual_mileage})",
                    field="vehicle_info",
                    suggested_action="Consider low-mileage discount programs",
                )
            )

        return violations

    @beartype
    async def _validate_regulatory_compliance(
        self,
        state: str,
        factors: dict[str, float],
        total_premium: Decimal,
        coverage_selections: list[CoverageSelection],
    ) -> list[BusinessRuleViolation]:
        """Validate regulatory compliance for specific states."""
        violations = []

        # California Prop 103 compliance
        if state == "CA":
            # Check for prohibited factors
            prohibited_factors = ["credit", "occupation", "education"]
            for factor in prohibited_factors:
                if factor in factors:
                    violations.append(
                        BusinessRuleViolation(
                            rule_id="CA_PROP103_PROHIBITED_FACTOR",
                            severity="error",
                            message=f"Factor '{factor}' is prohibited under California Proposition 103",
                            field="factors",
                            suggested_action=f"Remove {factor} factor from California calculations",
                        )
                    )

            # Check primary factor dominance (simplified check)
            primary_factors = ["violations", "accidents", "experience"]
            primary_impact = 1.0
            for factor in primary_factors:
                if factor in factors:
                    primary_impact *= factors[factor]

            if (
                abs(1.0 - primary_impact) < 0.1
            ):  # Very little impact from primary factors
                violations.append(
                    BusinessRuleViolation(
                        rule_id="CA_PROP103_PRIMARY_FACTORS",
                        severity="warning",
                        message="Primary factors (driving record, experience) have minimal rating impact",
                        field="factors",
                        suggested_action="Ensure primary factors account for majority of rating variation",
                    )
                )

        # Michigan no-fault requirements
        elif state == "MI":
            pip_coverages = [
                c
                for c in coverage_selections
                if c.coverage_type.value == "personal_injury_protection"
            ]

            if not pip_coverages:
                violations.append(
                    BusinessRuleViolation(
                        rule_id="MI_PIP_REQUIRED",
                        severity="error",
                        message="Personal Injury Protection (PIP) coverage is required in Michigan",
                        field="coverage_selections",
                        suggested_action="Add required PIP coverage",
                    )
                )

        return violations

    @beartype
    def get_critical_violations(
        self, violations: list[BusinessRuleViolation]
    ) -> list[BusinessRuleViolation]:
        """Get only critical (error-level) violations that must be fixed."""
        return [v for v in violations if v.severity == "error"]

    @beartype
    def format_violations_report(
        self, violations: list[BusinessRuleViolation]
    ) -> dict[str, Any]:
        """Format violations into a comprehensive report."""
        by_severity = {"error": [], "warning": [], "info": []}

        for violation in violations:
            by_severity[violation.severity].append(violation.to_dict())

        return {
            "total_violations": len(violations),
            "critical_violations": len(by_severity["error"]),
            "warnings": len(by_severity["warning"]),
            "info_messages": len(by_severity["info"]),
            "violations_by_severity": by_severity,
            "compliance_status": "fail" if by_severity["error"] else "pass",
        }
