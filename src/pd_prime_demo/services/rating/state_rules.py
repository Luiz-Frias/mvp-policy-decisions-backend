"""State-specific rating rules and regulations.

This module implements state-specific insurance rating rules including
California Proposition 103 compliance and other state regulations.
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Dict, List

from beartype import beartype

from ...services.result import Err, Ok
from ..performance_monitor import performance_monitor


@beartype
class StateRatingRules(ABC):
    """Base class for state-specific rating rules."""

    @abstractmethod
    def validate_factors(self, factors: dict[str, float]) -> dict[str, float]:
        """Validate and adjust factors per state regulations."""
        pass

    @abstractmethod
    def get_required_coverages(self) -> list[str]:
        """Get state-mandated coverages."""
        pass

    @abstractmethod
    def get_minimum_limits(self) -> dict[str, Decimal]:
        """Get state minimum coverage limits."""
        pass

    @abstractmethod
    def is_factor_allowed(self, factor_name: str) -> bool:
        """Check if a rating factor is allowed in this state."""
        pass

    @abstractmethod
    def get_state_code(self) -> str:
        """Get the state code."""
        pass


@beartype
class CaliforniaRules(StateRatingRules):
    """California Proposition 103 compliant rating rules."""

    @beartype
    def get_state_code(self) -> str:
        """Return state code."""
        return "CA"

    @beartype
    @performance_monitor("california_validate_factors")
    def validate_factors(self, factors: dict[str, float]) -> dict[str, float]:
        """Apply California-specific factor limits per Prop 103."""
        # Prop 103: Driving record, miles driven, years of experience
        # are primary factors (must account for 80%+ of rating variation)

        adjusted = factors.copy()

        # Remove prohibited factors
        prohibited = ["credit", "occupation", "education", "gender", "marital_status"]
        for factor in prohibited:
            adjusted.pop(factor, None)

        # Identify primary and secondary factors
        primary_factors = [
            "violations",
            "accidents",
            "experience",
            "low_mileage",
            "high_mileage",
            "driver_age",  # Age is allowed as it relates to experience
        ]

        # Calculate weights
        primary_weight = 1.0
        secondary_weight = 1.0

        for factor_name, factor_value in adjusted.items():
            if factor_name in primary_factors:
                primary_weight *= factor_value
            else:
                secondary_weight *= factor_value

        # Ensure primary factors dominate (80% rule)
        # If secondary factors have too much impact, scale them down
        total_deviation = abs(1.0 - primary_weight) + abs(1.0 - secondary_weight)
        primary_deviation = abs(1.0 - primary_weight)

        if total_deviation > 0 and primary_deviation / total_deviation < 0.8:
            # Scale down secondary factors
            scale_factor = 0.2  # Secondary factors can only account for 20%
            for key in list(adjusted.keys()):
                if key not in primary_factors:
                    # Move factor closer to 1.0
                    adjusted[key] = 1.0 + (adjusted[key] - 1.0) * scale_factor

        return adjusted

    @beartype
    def get_required_coverages(self) -> list[str]:
        """California required coverages."""
        return [
            "bodily_injury",  # 15/30
            "property_damage",  # 5
            "uninsured_motorist",  # 15/30 (UM BI is required)
        ]

    @beartype
    def get_minimum_limits(self) -> dict[str, Decimal]:
        """California minimum liability limits."""
        return {
            "bodily_injury_per_person": Decimal("15000"),
            "bodily_injury_per_accident": Decimal("30000"),
            "property_damage": Decimal("5000"),
            "uninsured_motorist_per_person": Decimal("15000"),
            "uninsured_motorist_per_accident": Decimal("30000"),
        }

    @beartype
    def is_factor_allowed(self, factor_name: str) -> bool:
        """Check if factor is allowed under Prop 103."""
        prohibited_factors = {
            "credit",
            "credit_score",
            "occupation",
            "education",
            "education_level",
            "gender",
            "marital_status",
            "zip_code",  # Can only use for determining territory, not as standalone
        }
        return factor_name.lower() not in prohibited_factors


@beartype
class TexasRules(StateRatingRules):
    """Texas rating rules - more permissive than California."""

    @beartype
    def get_state_code(self) -> str:
        """Return state code."""
        return "TX"

    @beartype
    def validate_factors(self, factors: dict[str, float]) -> dict[str, float]:
        """Texas allows most rating factors with few restrictions."""
        # Texas has fewer restrictions than California
        # Credit scoring is allowed, occupation is allowed, etc.
        return factors

    @beartype
    def get_required_coverages(self) -> list[str]:
        """Texas required coverages."""
        return [
            "bodily_injury",  # 30/60
            "property_damage",  # 25
        ]

    @beartype
    def get_minimum_limits(self) -> dict[str, Decimal]:
        """Texas minimum liability limits."""
        return {
            "bodily_injury_per_person": Decimal("30000"),
            "bodily_injury_per_accident": Decimal("60000"),
            "property_damage": Decimal("25000"),
        }

    @beartype
    def is_factor_allowed(self, factor_name: str) -> bool:
        """Texas allows most factors."""
        # Very few prohibited factors in Texas
        prohibited_factors = {
            "race",
            "religion",
            "national_origin",
        }
        return factor_name.lower() not in prohibited_factors


@beartype
class NewYorkRules(StateRatingRules):
    """New York rating rules."""

    @beartype
    def get_state_code(self) -> str:
        """Return state code."""
        return "NY"

    @beartype
    def validate_factors(self, factors: dict[str, float]) -> dict[str, float]:
        """Apply New York-specific factor limits."""
        adjusted = factors.copy()

        # New York has restrictions on credit scoring
        # Must be actuarially justified
        if "credit" in adjusted:
            # Cap credit factor impact
            credit_factor = adjusted["credit"]
            if credit_factor > 1.25:
                adjusted["credit"] = 1.25
            elif credit_factor < 0.80:
                adjusted["credit"] = 0.80

        return adjusted

    @beartype
    def get_required_coverages(self) -> list[str]:
        """New York required coverages."""
        return [
            "bodily_injury",  # 25/50
            "property_damage",  # 10
            "personal_injury_protection",  # No-fault state
            "uninsured_motorist",  # 25/50
        ]

    @beartype
    def get_minimum_limits(self) -> dict[str, Decimal]:
        """New York minimum liability limits."""
        return {
            "bodily_injury_per_person": Decimal("25000"),
            "bodily_injury_per_accident": Decimal("50000"),
            "property_damage": Decimal("10000"),
            "personal_injury_protection": Decimal("50000"),
            "uninsured_motorist_per_person": Decimal("25000"),
            "uninsured_motorist_per_accident": Decimal("50000"),
        }

    @beartype
    def is_factor_allowed(self, factor_name: str) -> bool:
        """Check if factor is allowed in New York."""
        prohibited_factors = {
            "race",
            "religion",
            "national_origin",
            "sexual_orientation",
        }
        return factor_name.lower() not in prohibited_factors


@beartype
class FloridaRules(StateRatingRules):
    """Florida rating rules with hurricane/catastrophe considerations."""

    @beartype
    def get_state_code(self) -> str:
        """Return state code."""
        return "FL"

    @beartype
    @performance_monitor("florida_validate_factors")
    def validate_factors(self, factors: dict[str, float]) -> dict[str, float]:
        """Apply Florida-specific factor limits."""
        adjusted = factors.copy()

        # Florida allows credit but has specific requirements
        # Cap extreme credit factors
        if "credit" in adjusted:
            credit_factor = adjusted["credit"]
            if credit_factor > 1.40:
                adjusted["credit"] = 1.40
            elif credit_factor < 0.60:
                adjusted["credit"] = 0.60

        # Hurricane zone considerations
        if "territory" in adjusted:
            territory_factor = adjusted["territory"]
            # Coastal areas have higher wind/flood risk
            if territory_factor > 1.50:  # High-risk coastal zones
                # Apply additional catastrophe factor
                adjusted["catastrophe_risk"] = 1.10
            elif territory_factor > 1.25:  # Moderate coastal risk
                adjusted["catastrophe_risk"] = 1.05

        return adjusted

    @beartype
    def get_required_coverages(self) -> list[str]:
        """Florida required coverages."""
        return [
            "property_damage",  # 10k minimum
            "personal_injury_protection",  # No-fault state, 10k PIP
        ]

    @beartype
    def get_minimum_limits(self) -> dict[str, Decimal]:
        """Florida minimum liability limits."""
        return {
            "property_damage": Decimal("10000"),
            "personal_injury_protection": Decimal("10000"),
            # Note: BI is not required unless DUI conviction or other violations
        }

    @beartype
    def is_factor_allowed(self, factor_name: str) -> bool:
        """Check if factor is allowed in Florida."""
        prohibited_factors = {
            "race",
            "religion",
            "national_origin",
        }
        return factor_name.lower() not in prohibited_factors


@beartype
class MichiganRules(StateRatingRules):
    """Michigan rating rules with no-fault PIP requirements."""

    @beartype
    def get_state_code(self) -> str:
        """Return state code."""
        return "MI"

    @beartype
    def validate_factors(self, factors: dict[str, float]) -> dict[str, float]:
        """Apply Michigan-specific factor limits."""
        adjusted = factors.copy()

        # Michigan restricts credit scoring
        adjusted.pop("credit", None)  # Credit scoring prohibited

        # Michigan has strict gender equality requirements
        adjusted.pop("gender", None)

        return adjusted

    @beartype
    def get_required_coverages(self) -> list[str]:
        """Michigan required coverages."""
        return [
            "bodily_injury",  # 20/40 minimum
            "property_damage",  # 10k minimum
            "personal_injury_protection",  # Unlimited PIP required
            "property_protection",  # $1M mini-tort coverage
        ]

    @beartype
    def get_minimum_limits(self) -> dict[str, Decimal]:
        """Michigan minimum liability limits."""
        return {
            "bodily_injury_per_person": Decimal("20000"),
            "bodily_injury_per_accident": Decimal("40000"),
            "property_damage": Decimal("10000"),
            "personal_injury_protection": Decimal("0"),  # Unlimited required
            "property_protection": Decimal("1000000"),  # $1M mini-tort
        }

    @beartype
    def is_factor_allowed(self, factor_name: str) -> bool:
        """Check if factor is allowed in Michigan."""
        prohibited_factors = {
            "race",
            "religion",
            "national_origin",
            "credit",
            "credit_score",
            "gender",
            "marital_status",
        }
        return factor_name.lower() not in prohibited_factors


@beartype
class PennsylvaniaRules(StateRatingRules):
    """Pennsylvania rating rules with choice no-fault options."""

    @beartype
    def get_state_code(self) -> str:
        """Return state code."""
        return "PA"

    @beartype
    @performance_monitor("pennsylvania_validate_factors")
    def validate_factors(self, factors: dict[str, float]) -> dict[str, float]:
        """Apply Pennsylvania-specific factor limits."""
        adjusted = factors.copy()

        # Pennsylvania allows most factors but has caps
        if "credit" in adjusted:
            credit_factor = adjusted["credit"]
            # Credit factor cannot exceed 1.35 or be below 0.75
            if credit_factor > 1.35:
                adjusted["credit"] = 1.35
            elif credit_factor < 0.75:
                adjusted["credit"] = 0.75

        return adjusted

    @beartype
    def get_required_coverages(self) -> list[str]:
        """Pennsylvania required coverages."""
        return [
            "bodily_injury",  # 15/30 minimum
            "property_damage",  # 5k minimum
            # Note: PIP is optional but must be offered
        ]

    @beartype
    def get_minimum_limits(self) -> dict[str, Decimal]:
        """Pennsylvania minimum liability limits."""
        return {
            "bodily_injury_per_person": Decimal("15000"),
            "bodily_injury_per_accident": Decimal("30000"),
            "property_damage": Decimal("5000"),
        }

    @beartype
    def is_factor_allowed(self, factor_name: str) -> bool:
        """Check if factor is allowed in Pennsylvania."""
        prohibited_factors = {
            "race",
            "religion",
            "national_origin",
        }
        return factor_name.lower() not in prohibited_factors


# Factory function
@beartype
@performance_monitor("get_state_rules")
def get_state_rules(state: str):
    """Get rules for a specific state - FAIL FAST if unsupported."""
    rules_map = {
        "CA": CaliforniaRules(),
        "TX": TexasRules(),
        "NY": NewYorkRules(),
        "FL": FloridaRules(),
        "MI": MichiganRules(),
        "PA": PennsylvaniaRules(),
        # DO NOT add defaults - explicit state support required
    }

    if state not in rules_map:
        return Err(
            f"State '{state}' is not supported for rating. "
            f"Supported states: {list(rules_map.keys())}. "
            f"Admin must add state support before quotes can proceed. "
            f"Required action: Implement state rules in rating engine configuration."
        )

    return Ok(rules_map[state])


@beartype
@performance_monitor("validate_coverage_limits")
def validate_coverage_limits(state: str, coverage_selections: list[Any]):
    """Validate that coverage selections meet state minimums."""
    state_rules_result = get_state_rules(state)
    if isinstance(state_rules_result, Err):
        return state_rules_result

    state_rules = state_rules_result.value
    minimums = state_rules.get_minimum_limits()

    # Build coverage map from selections
    coverage_map = {}
    for selection in coverage_selections:
        # Map coverage types to minimum requirement keys
        # Handle both enum and string values for coverage_type
        coverage_type_str = (
            selection.coverage_type.value
            if hasattr(selection.coverage_type, "value")
            else str(selection.coverage_type)
        )

        if coverage_type_str == "bodily_injury":
            # Assuming split limits
            coverage_map["bodily_injury_per_person"] = selection.limit
            coverage_map["bodily_injury_per_accident"] = selection.limit * 2
        elif coverage_type_str == "property_damage":
            coverage_map["property_damage"] = selection.limit
        elif coverage_type_str == "uninsured_motorist":
            coverage_map["uninsured_motorist_per_person"] = selection.limit
            coverage_map["uninsured_motorist_per_accident"] = selection.limit * 2
        elif coverage_type_str == "personal_injury_protection":
            coverage_map["personal_injury_protection"] = selection.limit

    # Check minimums
    for coverage_type, minimum in minimums.items():
        if coverage_type not in coverage_map:
            # Check if this is a required coverage
            base_coverage = coverage_type.split("_per_")[0]
            required = state_rules.get_required_coverages()
            if any(base_coverage.startswith(req) for req in required):
                return Err(
                    f"Missing required coverage: {coverage_type}. "
                    f"State {state} requires minimum ${minimum} for this coverage."
                )
        elif coverage_map[coverage_type] < minimum:
            return Err(
                f"Coverage {coverage_type} limit ${coverage_map[coverage_type]} "
                f"is below state {state} minimum of ${minimum}"
            )

    return Ok(True)
