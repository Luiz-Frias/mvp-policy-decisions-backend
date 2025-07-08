"""Advanced rating calculation algorithms."""

import math
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, getcontext
from typing import Any

import numpy as np
from beartype import beartype
from numpy.typing import NDArray

from ...core.result_types import Err, Ok, Result
from ..performance_monitor import performance_monitor

# Set decimal precision for financial calculations
getcontext().prec = 10


class PremiumCalculator:
    """Advanced premium calculation with statistical methods."""

    @beartype
    @staticmethod
    @performance_monitor("calculate_base_premium")
    def calculate_base_premium(
        coverage_limit: Decimal,
        base_rate: Decimal,
        exposure_units: Decimal = Decimal("1"),
    ) -> Result[Decimal, str]:
        """Calculate base premium with proper rounding.

        Args:
            coverage_limit: The coverage limit amount
            base_rate: The base rate factor
            exposure_units: Number of exposure units (default 1)

        Returns:
            Result containing calculated premium or error message
        """
        # Validate inputs
        if coverage_limit <= 0:
            return Err("Coverage limit must be positive")
        if base_rate <= 0:
            return Err("Base rate must be positive")
        if exposure_units <= 0:
            return Err("Exposure units must be positive")

        # Premium = Coverage Limit × Base Rate × Exposure Units
        premium = (coverage_limit * base_rate * exposure_units) / Decimal("1000")
        return Ok(premium.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    @beartype
    @staticmethod
    @performance_monitor("apply_multiplicative_factors")
    def apply_multiplicative_factors(
        base_premium: Decimal,
        factors: dict[str, float],
    ) -> Result[dict[str, Any], str]:
        """Apply rating factors with detailed breakdown.

        Args:
            base_premium: The base premium amount
            factors: Dictionary of factor names to multipliers

        Returns:
            Result containing (final premium, factor impacts) or error
        """
        if base_premium <= 0:
            return Err("Base premium must be positive")

        factor_impacts = {}
        current_premium = base_premium

        # Apply factors in specific order for consistency
        factor_order = [
            "territory",
            "driver_age",
            "experience",
            "vehicle_age",
            "safety_features",
            "credit",
            "violations",
            "accidents",
        ]

        # Process all factors (ordered first, then any additional ones)
        all_factor_names = factor_order + [
            f for f in factors.keys() if f not in factor_order
        ]

        for factor_name in all_factor_names:
            if factor_name in factors:
                factor_value = Decimal(str(factors[factor_name]))

                # Validate factor range
                if factor_value < Decimal("0.1") or factor_value > Decimal("5.0"):
                    return Err(
                        f"Factor {factor_name} value {factor_value} outside valid range [0.1, 5.0]"
                    )

                # Calculate impact
                impact = current_premium * (factor_value - Decimal("1"))
                factor_impacts[factor_name] = impact.quantize(Decimal("0.01"))

                # Apply factor
                current_premium *= factor_value

        return Ok((current_premium.quantize(Decimal("0.01")), factor_impacts))

    @beartype
    @staticmethod
    @performance_monitor("calculate_territory_factor")
    def calculate_territory_factor(
        zip_code: str,
        territory_data: dict[str, Any],
    ):
        """Calculate territory factor using actuarial data.

        Args:
            zip_code: The ZIP code for rating
            territory_data: Territory loss cost data

        Returns:
            Result containing territory factor or error
        """
        if not zip_code:
            return Err("ZIP code is required for territory rating")

        # Get loss cost data for ZIP
        base_loss_cost = territory_data.get("base_loss_cost")
        if not base_loss_cost or base_loss_cost <= 0:
            return Err(
                "Territory calculation error: base_loss_cost is required but not provided. "
                "Required action: Ensure territory rate tables are loaded. "
                "Check: Admin > Rate Management > Territory Rates"
            )

        zip_data = territory_data.get(zip_code, {})
        zip_loss_cost = zip_data.get("loss_cost", base_loss_cost)

        # Calculate relativity
        relativity = zip_loss_cost / base_loss_cost

        # Apply credibility weighting
        credibility = zip_data.get("credibility", 0.5)
        if credibility < 0 or credibility > 1:
            return Err(f"Invalid credibility value {credibility} for ZIP {zip_code}")

        # Blend with base: Factor = Credibility × Relativity + (1 - Credibility) × 1.0
        factor = credibility * relativity + (1 - credibility) * 1.0

        # Cap factor range
        return Ok(max(0.5, min(3.0, factor)))

    @beartype
    @staticmethod
    @performance_monitor("calculate_driver_risk_score")
    def calculate_driver_risk_score(
        driver_data: dict[str, Any],
    ) -> dict:
        """Calculate driver risk score using statistical model.

        Args:
            driver_data: Driver information including age, experience, violations

        Returns:
            Result containing (risk score, risk factors) or error
        """
        # Validate required fields
        required_fields = ["age", "years_licensed"]
        for field in required_fields:
            if field not in driver_data:
                return Err(
                    f"Driver risk calculation error: {field} is required but not provided. "
                    "Required action: Ensure all driver information is collected. "
                    "Check: Quote > Driver Information section"
                )

        risk_factors = []

        # Base risk components
        age = driver_data.get("age", 30)
        experience = driver_data.get("years_licensed", 10)
        violations = driver_data.get("violations_3_years", 0)
        accidents = driver_data.get("accidents_3_years", 0)

        # Validate data ranges
        if age < 16 or age > 100:
            return Err(f"Invalid driver age: {age}")
        if experience < 0 or experience > age - 16:
            return Err(f"Invalid years licensed: {experience}")

        # Age risk curve (U-shaped)
        age_risk = 0.0
        if age < 25:
            age_risk = 0.3 * (25 - age) / 5  # Linear increase for young
            risk_factors.append(f"Young driver (age {age})")
        elif age > 70:
            age_risk = 0.2 * (age - 70) / 10  # Linear increase for senior
            risk_factors.append(f"Senior driver (age {age})")

        # Experience curve (exponential decay)
        exp_risk = 0.3 * math.exp(-experience / 5)
        if experience < 3:
            risk_factors.append(f"New driver ({experience} years)")

        # Violation risk (linear)
        viol_risk = 0.15 * violations
        if violations > 0:
            risk_factors.append(f"{violations} violations")

        # Accident risk (exponential)
        acc_risk = 0.25 * (math.exp(min(accidents, 5)) - 1)
        if accidents > 0:
            risk_factors.append(f"{accidents} accidents")

        # Combine risks (weighted sum)
        total_risk = age_risk + exp_risk + viol_risk + acc_risk

        # Normalize to 0-1 scale
        risk_score = 1 / (1 + math.exp(-2 * total_risk))

        return Ok((risk_score, risk_factors))

    @beartype
    @staticmethod
    @performance_monitor("calculate_vehicle_risk_score")
    def calculate_vehicle_risk_score(
        vehicle_data: dict[str, Any],
    ):
        """Calculate vehicle risk score based on characteristics.

        Args:
            vehicle_data: Vehicle information including type, age, safety features

        Returns:
            Result containing vehicle risk score or error
        """
        # Validate required fields
        if "type" not in vehicle_data:
            return Err(
                "Vehicle risk calculation error: type is required but not provided. "
                "Required action: Ensure vehicle type is selected. "
                "Check: Quote > Vehicle Information > Vehicle Type"
            )

        # Base scores by vehicle type
        type_scores = {
            "sedan": 1.0,
            "suv": 1.1,
            "truck": 1.15,
            "sports": 1.4,
            "luxury": 1.3,
            "economy": 0.9,
        }

        vehicle_type = vehicle_data.get("type", "sedan")
        base_score = type_scores.get(vehicle_type)
        if base_score is None:
            return Err(f"Unknown vehicle type: {vehicle_type}")

        # Age factor (depreciation curve)
        age = vehicle_data.get("age", 5)
        if age < 0 or age > 50:
            return Err(f"Invalid vehicle age: {age}")

        age_factor = 1.0 - (0.05 * min(age, 10))  # 5% per year, max 50%

        # Safety feature credits
        safety_features = vehicle_data.get("safety_features", [])
        safety_credit = 1.0

        feature_credits = {
            "abs": 0.02,
            "airbags": 0.03,
            "stability_control": 0.04,
            "blind_spot": 0.03,
            "automatic_braking": 0.05,
            "lane_assist": 0.03,
        }

        for feature in safety_features:
            if feature in feature_credits:
                safety_credit -= feature_credits[feature]

        # Theft risk factor
        theft_rate = vehicle_data.get("theft_rate", 1.0)  # Relative theft rate
        if theft_rate < 0.1 or theft_rate > 5.0:
            return Err(f"Invalid theft rate: {theft_rate}")

        # Combine factors
        vehicle_risk = base_score * age_factor * safety_credit * theft_rate

        return Ok(max(0.5, min(2.0, vehicle_risk)))


class DiscountCalculator:
    """Calculate and validate discount stacking."""

    @beartype
    @staticmethod
    def calculate_stacked_discounts(
        base_premium: Decimal,
        applicable_discounts: list[dict[str, Any]],
        max_total_discount: Decimal = Decimal("0.40"),
        state_rules: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Calculate discounts with proper stacking rules.

        Args:
            base_premium: The base premium before discounts
            applicable_discounts: List of applicable discounts
            max_total_discount: Maximum total discount allowed (default 40%)
            state_rules: State-specific discount rules

        Returns:
            Result containing (applied discounts, total discount amount) or error
        """
        if base_premium <= 0:
            return Err("Base premium must be positive")

        if not applicable_discounts:
            return Ok(([], Decimal("0")))

        # Apply state-specific max discount if provided
        if state_rules and "max_discount" in state_rules:
            state_max = Decimal(str(state_rules["max_discount"]))
            max_total_discount = min(max_total_discount, state_max)

        # Validate discount structures
        for discount in applicable_discounts:
            if "rate" not in discount:
                return Err(
                    "Discount stacking error: discount rate is required but not provided. "
                    "Required action: Review discount configuration in admin panel."
                )
            if discount["rate"] < 0 or discount["rate"] > 1:
                return Err(f"Invalid discount rate: {discount['rate']}")

        # Sort by priority (higher priority applies first)
        sorted_discounts = sorted(
            applicable_discounts, key=lambda d: d.get("priority", 100)
        )

        applied_discounts = []
        remaining_premium = base_premium
        total_discount_amount = Decimal("0")

        for discount in sorted_discounts:
            if discount.get("stackable", True):
                # Apply to remaining premium
                discount_rate = Decimal(str(discount["rate"]))
                discount_amount = remaining_premium * discount_rate

                # Check if we exceed max total discount
                if (
                    total_discount_amount + discount_amount
                ) / base_premium > max_total_discount:
                    # Apply partial discount to reach max
                    discount_amount = (
                        base_premium * max_total_discount - total_discount_amount
                    )
                    discount["applied_rate"] = float(
                        discount_amount / remaining_premium
                    )
                else:
                    discount["applied_rate"] = discount["rate"]

                discount["amount"] = discount_amount.quantize(Decimal("0.01"))
                applied_discounts.append(discount)

                total_discount_amount += discount_amount
                remaining_premium -= discount_amount

                # Stop if we've reached max discount
                if total_discount_amount / base_premium >= max_total_discount:
                    break
            else:
                # Non-stackable discount (applies to base)
                discount_rate = Decimal(str(discount["rate"]))
                discount_amount = base_premium * discount_rate

                # Only apply if it's better than current total
                if discount_amount > total_discount_amount:
                    applied_discounts = [discount]
                    discount["amount"] = discount_amount.quantize(Decimal("0.01"))
                    discount["applied_rate"] = discount["rate"]
                    total_discount_amount = discount_amount

        return Ok((applied_discounts, total_discount_amount.quantize(Decimal("0.01"))))


class CreditBasedInsuranceScorer:
    """Credit-based insurance scoring for premium adjustments."""

    @beartype
    @staticmethod
    def calculate_credit_factor(
        credit_score: int,
        state: str,
        product_type: str = "auto",
    ):
        """Calculate credit-based insurance factor.

        Args:
            credit_score: FICO score (300-850)
            state: State code for regulatory compliance
            product_type: Insurance product type

        Returns:
            Result containing credit factor or error
        """
        # States that prohibit credit-based insurance scoring
        prohibited_states = {"CA", "HI", "MA", "MD", "MI", "MT", "NC", "OR", "UT", "WA"}

        if state in prohibited_states:
            return Err(
                f"Credit-based insurance scoring prohibited in {state}. "
                "Required action: Use traditional underwriting factors only. "
                "Check: Admin > Rating Rules > State Regulations"
            )

        # Validate credit score range
        if credit_score < 300 or credit_score > 850:
            return Err(f"Invalid credit score: {credit_score}. Must be 300-850.")

        # Credit score to factor mapping (industry standard)
        if credit_score >= 760:
            factor = 0.85  # Excellent credit discount
        elif credit_score >= 700:
            factor = 0.95  # Good credit
        elif credit_score >= 650:
            factor = 1.00  # Fair credit (neutral)
        elif credit_score >= 600:
            factor = 1.10  # Poor credit surcharge
        else:
            factor = 1.25  # Very poor credit

        return Ok(factor)

    @beartype
    @staticmethod
    def calculate_insurance_score(
        credit_score: int,
        payment_history: float,  # 0.0-1.0 (1.0 = perfect)
        credit_utilization: float,  # 0.0-1.0+ (0.3+ is concerning)
        length_of_credit: int,  # Years
        new_credit_inquiries: int,  # Last 12 months
    ):
        """Calculate insurance-specific credit score.

        This differs from FICO by weighting factors differently for insurance risk.

        Returns:
            Result containing insurance score (200-997) or error
        """
        # Validate inputs
        if not (0.0 <= payment_history <= 1.0):
            return Err("Payment history must be between 0.0 and 1.0")
        if credit_utilization < 0.0:
            return Err("Credit utilization cannot be negative")
        if length_of_credit < 0:
            return Err("Length of credit cannot be negative")
        if new_credit_inquiries < 0:
            return Err("New credit inquiries cannot be negative")

        # Insurance scoring weights (different from FICO)
        base_score = credit_score

        # Payment history impact (35% weight)
        payment_adjustment = (payment_history - 0.5) * 100

        # Credit utilization impact (30% weight)
        if credit_utilization <= 0.10:
            util_adjustment = 20  # Very low utilization is good
        elif credit_utilization <= 0.30:
            util_adjustment = 0  # Normal utilization
        else:
            util_adjustment = -50 * (
                credit_utilization - 0.30
            )  # High utilization penalty

        # Length of credit impact (15% weight)
        length_adjustment = min(length_of_credit * 2, 30)  # Max 30 points

        # New credit impact (10% weight)
        inquiry_adjustment = -5 * new_credit_inquiries  # -5 per inquiry

        # Calculate final insurance score
        insurance_score = int(
            base_score
            + payment_adjustment * 0.35
            + util_adjustment * 0.30
            + length_adjustment * 0.15
            + inquiry_adjustment * 0.10
        )

        # Clamp to valid range
        insurance_score = max(200, min(997, insurance_score))

        return Ok(insurance_score)


class ExternalDataIntegrator:
    """Integration with external data sources for enhanced rating."""

    @beartype
    @staticmethod
    async def get_weather_risk_factor(
        zip_code: str,
        effective_date: datetime,
    ):
        """Get weather-based risk factor for geographic area.

        Args:
            zip_code: ZIP code for location
            effective_date: Policy effective date

        Returns:
            Result containing weather risk factor or error
        """
        # Simulate external weather API call
        # In production, integrate with NOAA, Weather.com, etc.

        # Mock weather risk based on ZIP code patterns
        try:
            zip_int = int(zip_code[:3])

            # Hurricane zones (Southeast/Gulf Coast)
            if 300 <= zip_int <= 349:  # Florida
                return Ok(1.25)
            elif 700 <= zip_int <= 729:  # Louisiana/Texas Gulf Coast
                return Ok(1.20)

            # Tornado alley
            elif 730 <= zip_int <= 739:  # Texas
                return Ok(1.15)
            elif 660 <= zip_int <= 679:  # Kansas/Missouri
                return Ok(1.18)

            # Earthquake zones
            elif 900 <= zip_int <= 959:  # California
                return Ok(1.12)

            # Wildfire zones
            elif 800 <= zip_int <= 899:  # Mountain West
                return Ok(1.08)

            # Lower risk areas
            else:
                return Ok(1.00)

        except ValueError:
            return Err(f"Invalid ZIP code format: {zip_code}")

    @beartype
    @staticmethod
    async def get_crime_risk_factor(
        zip_code: str,
    ):
        """Get crime-based risk factor for geographic area.

        Args:
            zip_code: ZIP code for location

        Returns:
            Result containing crime risk factor or error
        """
        # Simulate external crime data API call
        # In production, integrate with FBI crime statistics, local PD data

        try:
            zip_int = int(zip_code[:3])

            # High crime urban areas (simplified)
            high_crime_zips = {
                100,
                101,
                102,  # Boston area
                112,
                113,
                114,  # Boston suburbs
                200,
                201,
                202,  # DC area
                100,
                104,
                105,  # NYC area
                600,
                601,
                602,
                606,
                607,
                608,  # Chicago area
                900,
                901,
                902,  # LA area
                941,
                945,
                946,  # SF Bay area
            }

            if zip_int in high_crime_zips:
                return Ok(1.15)  # 15% increase for high crime
            elif zip_int % 100 < 20:  # Urban center pattern
                return Ok(1.08)  # 8% increase for urban
            else:
                return Ok(0.95)  # 5% discount for suburban/rural

        except ValueError:
            return Err(f"Invalid ZIP code format: {zip_code}")

    @beartype
    @staticmethod
    async def validate_vehicle_data(
        vin: str,
    ) -> dict:
        """Validate and enhance vehicle data via VIN decode.

        Args:
            vin: Vehicle Identification Number

        Returns:
            Result containing enhanced vehicle data or error
        """
        # Simulate external VIN decode API call
        # In production, integrate with NHTSA, Polk, Experian APIs

        if len(vin) != 17:
            return Err("VIN must be exactly 17 characters")

        # PRODUCTION REQUIREMENT: Real VIN API integration required
        # NO MOCK DATA ALLOWED - must integrate with:
        # - NHTSA VIN Decoder API
        # - Polk Vehicle Data API
        # - Experian AutoCheck API

        return Err(
            "VIN decoding service not configured. "
            "Production system requires integration with NHTSA/Polk/Experian APIs. "
            "Contact system administrator to configure VIN decoder service. "
            "Required environment variables: VIN_API_KEY, VIN_API_ENDPOINT"
        )


class AIRiskScorer:
    """AI-enhanced risk scoring using machine learning models."""

    def __init__(self, load_models: bool = False):
        """Initialize AI models.

        Args:
            load_models: Whether to load models (for testing)
        """
        # In production, load pre-trained models
        self._models = {}
        self._model_version = "1.0.0"

        # For testing, allow models to be "loaded"
        if load_models:
            self._models = {
                "claim_probability": {"loaded": True},
                "severity": {"loaded": True},
                "fraud": {"loaded": True},
            }

    @beartype
    async def calculate_ai_risk_score(
        self,
        customer_data: dict[str, Any],
        vehicle_data: dict[str, Any],
        driver_data: list[dict[str, Any]],
        external_data: dict[str, Any] | None = None,
    ) -> dict:
        """Calculate AI risk score using multiple models.

        Args:
            customer_data: Customer information
            vehicle_data: Vehicle information
            driver_data: List of driver information
            external_data: Optional external data (credit, weather, etc.)

        Returns:
            Result containing risk score data or error
        """
        try:
            features_result = self._extract_features(
                customer_data, vehicle_data, driver_data, external_data
            )

            if features_result.is_err():
                return Err(f"Feature extraction failed: {features_result.unwrap_err()}")

            features = features_result.unwrap()
            if features is None:
                return Err("Feature extraction returned None")

            # Simulate model predictions (in production, use real ML models)
            # Check if models are loaded
            if not self._models:
                # Fallback to rule-based scoring if AI models unavailable
                return Err(
                    "AI scoring error: Models not loaded. "
                    "Required action: Verify AI model deployment status. "
                    "Fallback: Using traditional actuarial scoring. "
                    "Check: Admin > System Status > AI Models"
                )

            # Claim probability model
            claim_prob = self._predict_claim_probability(features)

            # Severity model
            expected_severity = self._predict_claim_severity(features)

            # Fraud risk model
            fraud_risk = self._predict_fraud_risk(features)

            # Combine into overall risk score
            risk_score = (
                0.5 * claim_prob
                + 0.3 * (expected_severity / 10000)  # Normalize severity
                + 0.2 * fraud_risk
            )

            # Identify key risk factors
            risk_factors = self._identify_risk_factors(
                features,
                {
                    "claim_prob": claim_prob,
                    "severity": expected_severity,
                    "fraud": fraud_risk,
                },
            )

            return Ok(
                {
                    "score": min(1.0, max(0.0, risk_score)),
                    "components": {
                        "claim_probability": claim_prob,
                        "expected_severity": expected_severity,
                        "fraud_risk": fraud_risk,
                    },
                    "factors": risk_factors,
                    "confidence": 0.85,  # Model confidence
                    "model_version": self._model_version,
                }
            )

        except Exception as e:
            return Err(f"AI scoring failed: {str(e)}")

    @beartype
    def _extract_features(
        self,
        customer_data: dict[str, Any],
        vehicle_data: dict[str, Any],
        driver_data: list[dict[str, Any]],
        external_data: dict[str, Any] | None,
    ) -> dict:
        """Extract features for ML models.

        Returns:
            Result containing feature array or error
        """
        features = []

        # Customer features
        features.extend(
            [
                customer_data.get("policy_count", 0),
                customer_data.get("years_as_customer", 0),
                customer_data.get("previous_claims", 0),
            ]
        )

        # Vehicle features
        if "age" not in vehicle_data or "value" not in vehicle_data:
            return Err("Vehicle age and value are required for AI scoring")

        features.extend(
            [
                vehicle_data.get("age", 5),
                vehicle_data.get("value", 20000) / 1000,  # Normalize
                vehicle_data.get("annual_mileage", 12000) / 1000,
                len(vehicle_data.get("safety_features", [])),
            ]
        )

        # Driver features (aggregate)
        if not driver_data:
            return Err("At least one driver is required for AI scoring")

        primary_driver = driver_data[0]
        features.extend(
            [
                primary_driver.get("age", 30),
                primary_driver.get("years_licensed", 10),
                sum(d.get("violations_3_years", 0) for d in driver_data),
                sum(d.get("accidents_3_years", 0) for d in driver_data),
            ]
        )

        # External features (if available)
        if external_data:
            features.extend(
                [
                    external_data.get("credit_score", 700) / 100,
                    external_data.get("area_crime_rate", 1.0),
                    external_data.get("weather_risk", 1.0),
                ]
            )

        return Ok(np.array(features))

    @beartype
    def _predict_claim_probability(self, features: NDArray[np.float64]) -> float:
        """Predict probability of claim in next 12 months."""
        # Simulate logistic regression model
        # In production, use trained model

        # Mock coefficients
        coefficients = np.array(
            [
                -0.01,  # policy_count (negative = lower risk)
                -0.02,  # years_as_customer
                0.15,  # previous_claims
                0.01,  # vehicle_age
                0.005,  # vehicle_value
                0.02,  # annual_mileage
                -0.05,  # safety_features
                0.03,  # driver_age (U-shaped, simplified)
                -0.02,  # years_licensed
                0.20,  # violations
                0.30,  # accidents
            ]
        )

        # Pad coefficients if needed
        if len(features) > len(coefficients):
            coefficients = np.pad(coefficients, (0, len(features) - len(coefficients)))

        # Calculate logit
        logit = np.dot(features[: len(coefficients)], coefficients) - 2.0

        # Convert to probability
        probability = 1 / (1 + np.exp(-logit))

        return float(probability)

    @beartype
    def _predict_claim_severity(self, features: NDArray[np.float64]) -> float:
        """Predict expected claim severity if claim occurs."""
        # Simulate gamma regression model
        # Base severity
        base_severity = 5000

        # Factors that increase severity
        severity_multiplier = 1.0

        # Vehicle value factor
        vehicle_value_normalized = features[4] if len(features) > 4 else 20
        severity_multiplier *= 0.5 + 0.5 * vehicle_value_normalized / 50

        # Speed/accident factor
        violations = features[9] if len(features) > 9 else 0
        severity_multiplier *= 1 + 0.1 * violations

        return base_severity * severity_multiplier

    @beartype
    def _predict_fraud_risk(self, features: NDArray[np.float64]) -> float:
        """Predict fraud risk score."""
        # Simple rule-based fraud detection
        # In production, use anomaly detection model

        fraud_score = 0.0

        # New customer with high coverage
        if features[1] < 0.5:  # Less than 6 months
            fraud_score += 0.2

        # Multiple recent claims
        if features[2] > 2:
            fraud_score += 0.3

        # Unusual patterns
        # Add more sophisticated checks in production

        return min(1.0, fraud_score)

    @beartype
    def _identify_risk_factors(
        self,
        features: NDArray[np.float64],
        predictions: dict[str, float],
    ) -> list[str]:
        """Identify top risk factors for explanation."""
        factors = []

        # High claim probability factors
        if predictions["claim_prob"] > 0.3:
            if features[9] > 0:  # violations
                factors.append("Recent traffic violations")
            if features[10] > 0:  # accidents
                factors.append("Previous accidents")

        # High severity factors
        if predictions["severity"] > 7500:
            factors.append("High vehicle value")

        # Fraud risk factors
        if predictions["fraud"] > 0.3:
            factors.append("New customer profile")

        return factors[:5]  # Top 5 factors


class StatisticalRatingModels:
    """Advanced statistical models for insurance rating."""

    @beartype
    @staticmethod
    def calculate_generalized_linear_model_factor(
        features: dict[str, float],
        coefficients: dict[str, float],
        link_function: str = "log",
    ):
        """Calculate GLM-based rating factor.

        Args:
            features: Feature values for the model
            coefficients: Model coefficients
            link_function: Link function ('log', 'logit', 'identity')

        Returns:
            Result containing calculated factor or error
        """
        try:
            if not features:
                return Err("Features are required for GLM calculation")
            if not coefficients:
                return Err("Coefficients are required for GLM calculation")

            # Calculate linear predictor
            linear_predictor = coefficients.get("intercept", 0.0)

            for feature_name, feature_value in features.items():
                if feature_name in coefficients:
                    linear_predictor += coefficients[feature_name] * feature_value

            # Apply inverse link function
            if link_function == "log":
                factor = math.exp(linear_predictor)
            elif link_function == "logit":
                factor = 1 / (1 + math.exp(-linear_predictor))
            elif link_function == "identity":
                factor = linear_predictor
            else:
                return Err(f"Unsupported link function: {link_function}")

            # Ensure factor is within reasonable bounds
            factor = max(0.1, min(10.0, factor))
            return Ok(factor)

        except Exception as e:
            return Err(f"GLM calculation failed: {str(e)}")

    @beartype
    @staticmethod
    def calculate_loss_cost_relativity(
        exposure_data: dict[str, Any],
        loss_data: dict[str, Any],
        credibility_threshold: float = 0.3,
    ):
        """Calculate loss cost relativity using Buhlmann credibility.

        Args:
            exposure_data: Exposure information
            loss_data: Loss experience data
            credibility_threshold: Minimum credibility for experience rating

        Returns:
            Result containing loss cost relativity or error
        """
        try:
            # Extract required data
            claim_count = loss_data.get("claim_count", 0)
            claim_amount = loss_data.get("claim_amount", 0.0)
            exposure_years = exposure_data.get("exposure_years", 0.0)

            if exposure_years <= 0:
                return Err("Exposure years must be positive")

            # Calculate observed loss cost
            observed_loss_cost = (
                claim_amount / exposure_years if exposure_years > 0 else 0.0
            )

            # Get manual loss cost (industry average)
            manual_loss_cost = loss_data.get("manual_loss_cost", 100.0)

            # Calculate credibility using square root rule (simplified)
            # In practice, use more sophisticated credibility methods
            credibility = min(
                1.0, math.sqrt(claim_count / 16.0)
            )  # 16 claims for full credibility

            if credibility < credibility_threshold:
                # Low credibility - use manual rate
                relativity = 1.0
            else:
                # Credibility-weighted relativity
                relativity = (
                    credibility * (observed_loss_cost / manual_loss_cost)
                    + (1 - credibility) * 1.0
                )

            # Cap relativity range
            relativity = max(0.25, min(4.0, relativity))

            return Ok(relativity)

        except Exception as e:
            return Err(f"Loss cost relativity calculation failed: {str(e)}")

    @beartype
    @staticmethod
    def calculate_frequency_severity_model(
        driver_profile: dict[str, Any],
        vehicle_profile: dict[str, Any],
        territory_profile: dict[str, Any],
    ) -> dict:
        """Calculate separate frequency and severity models.

        Args:
            driver_profile: Driver characteristics
            vehicle_profile: Vehicle characteristics
            territory_profile: Territory characteristics

        Returns:
            Result containing frequency and severity factors or error
        """
        try:
            # Frequency model (Poisson regression simulation)
            freq_features = {
                "driver_age": float(driver_profile.get("age", 30)),
                "vehicle_age": float(vehicle_profile.get("age", 5)),
                "annual_mileage": float(vehicle_profile.get("annual_mileage", 12000)),
                "urban_indicator": float(
                    1 if territory_profile.get("urban", False) else 0
                ),
                "prior_claims": float(driver_profile.get("prior_claims", 0)),
            }

            # Frequency coefficients (example values)
            freq_coefficients = {
                "intercept": -4.5,
                "driver_age": -0.02 if freq_features["driver_age"] > 25 else 0.05,
                "vehicle_age": 0.01,
                "annual_mileage": 0.000001,  # Per mile
                "urban_indicator": 0.3,
                "prior_claims": 0.4,
            }

            freq_result = (
                StatisticalRatingModels.calculate_generalized_linear_model_factor(
                    freq_features, freq_coefficients, "log"
                )
            )
            if freq_result.is_err():
                return Err(f"Frequency model failed: {freq_result.unwrap_err()}")
            frequency_factor = freq_result.unwrap()

            # Severity model (Gamma regression simulation)
            sev_features = {
                "vehicle_value": float(vehicle_profile.get("value", 25000)),
                "driver_age": float(driver_profile.get("age", 30)),
                "vehicle_safety_score": float(
                    len(vehicle_profile.get("safety_features", []))
                ),
            }

            # Severity coefficients (example values)
            sev_coefficients = {
                "intercept": 8.5,  # Log of base severity
                "vehicle_value": 0.00001,  # Per dollar of vehicle value
                "driver_age": -0.005 if sev_features["driver_age"] > 25 else 0.01,
                "vehicle_safety_score": -0.1,  # Credit for safety features
            }

            sev_result = (
                StatisticalRatingModels.calculate_generalized_linear_model_factor(
                    sev_features, sev_coefficients, "log"
                )
            )
            if sev_result.is_err():
                return Err(f"Severity model failed: {sev_result.unwrap_err()}")
            severity_factor = sev_result.unwrap()

            return Ok(
                {
                    "frequency_factor": frequency_factor,
                    "severity_factor": severity_factor,
                    "expected_claims": frequency_factor,
                    "expected_severity": severity_factor * 5000,  # Base severity $5,000
                    "pure_premium_factor": frequency_factor * severity_factor,
                }
            )

        except Exception as e:
            return Err(f"Frequency/severity model calculation failed: {str(e)}")

    @beartype
    @staticmethod
    def calculate_catastrophe_loading(
        zip_code: str,
        coverage_types: list[str],
        dwelling_characteristics: dict[str, Any] | None = None,
    ):
        """Calculate catastrophe loading factor.

        Args:
            zip_code: Property ZIP code
            coverage_types: List of coverage types
            dwelling_characteristics: Optional dwelling details

        Returns:
            Result containing catastrophe loading factor or error
        """
        try:
            if not zip_code:
                return Err("ZIP code is required for catastrophe loading")

            # Initialize base loading
            cat_loading = 1.0

            # Hurricane/windstorm loading
            if zip_code.startswith(("3", "7", "2")):  # FL, TX, LA coastal areas
                if "comprehensive" in coverage_types or "collision" in coverage_types:
                    cat_loading *= 1.15  # 15% hurricane loading

            # Earthquake loading
            elif zip_code.startswith(("9", "8")):  # CA, WA earthquake zones
                if "comprehensive" in coverage_types:
                    cat_loading *= 1.08  # 8% earthquake loading

            # Hail loading
            elif zip_code.startswith(("7", "6")):  # TX, CO hail corridor
                if "comprehensive" in coverage_types:
                    cat_loading *= 1.05  # 5% hail loading

            # Wildfire loading
            elif zip_code.startswith(("8", "9")):  # Mountain West
                if "comprehensive" in coverage_types:
                    cat_loading *= 1.06  # 6% wildfire loading

            # Apply dwelling-specific adjustments if available
            if dwelling_characteristics:
                construction_type = dwelling_characteristics.get(
                    "construction_type", "wood_frame"
                )
                roof_type = dwelling_characteristics.get("roof_type", "asphalt_shingle")

                # Construction adjustments
                if construction_type == "masonry":
                    cat_loading *= 0.95  # Credit for masonry construction
                elif construction_type == "mobile_home":
                    cat_loading *= 1.25  # Surcharge for mobile homes

                # Roof adjustments for hail
                if roof_type == "impact_resistant":
                    cat_loading *= 0.90  # Credit for impact-resistant roof

            return Ok(cat_loading)

        except Exception as e:
            return Err(f"Catastrophe loading calculation failed: {str(e)}")

    @beartype
    @staticmethod
    def calculate_trend_factors(
        policy_effective_date: datetime,
        loss_trend_rate: float = 0.05,  # 5% annual loss trend
        expense_trend_rate: float = 0.03,  # 3% annual expense trend
    ) -> dict:
        """Calculate trend factors for rate adequacy.

        Args:
            policy_effective_date: Policy effective date
            loss_trend_rate: Annual loss trend rate
            expense_trend_rate: Annual expense trend rate

        Returns:
            Result containing trend factors or error
        """
        try:
            # Base period (when rates were developed)
            base_date = datetime(2024, 1, 1)

            # Calculate years from base period to policy effective date
            years_elapsed = (policy_effective_date - base_date).days / 365.25

            # Calculate compound trend factors
            loss_trend_factor = (1 + loss_trend_rate) ** years_elapsed
            expense_trend_factor = (1 + expense_trend_rate) ** years_elapsed

            # Composite trend (weighted average - 75% losses, 25% expenses)
            composite_trend = 0.75 * loss_trend_factor + 0.25 * expense_trend_factor

            # Cap trend factors to reasonable ranges
            loss_trend_factor = max(0.8, min(1.5, loss_trend_factor))
            expense_trend_factor = max(0.8, min(1.5, expense_trend_factor))
            composite_trend = max(0.8, min(1.5, composite_trend))

            return Ok(
                {
                    "loss_trend_factor": loss_trend_factor,
                    "expense_trend_factor": expense_trend_factor,
                    "composite_trend_factor": composite_trend,
                    "years_elapsed": years_elapsed,
                }
            )

        except Exception as e:
            return Err(f"Trend factor calculation failed: {str(e)}")


class AdvancedPerformanceCalculator:
    """High-performance calculation engine for complex rating scenarios."""

    def __init__(self):
        """Initialize performance calculator with optimization settings."""
        self._vector_cache: dict[str, NDArray[np.float64]] = {}
        self._lookup_tables: dict[str, dict[Any, float]] = {}

    @beartype
    def precompute_lookup_tables(
        self, table_definitions: dict[str, dict[str, Any]]
    ) -> None:
        """Precompute lookup tables for fast factor retrieval.

        Args:
            table_definitions: Dictionary of table definitions
        """
        for table_name, definition in table_definitions.items():
            self._lookup_tables[table_name] = {}

            # Example: Age-based factors
            if table_name == "age_factors":
                for age in range(16, 100):
                    if age < 25:
                        factor = 2.0 - (age - 16) * 0.1  # Decreasing from 2.0 to 1.1
                    elif age <= 65:
                        factor = 0.9  # Mature driver discount
                    else:
                        factor = 0.9 + (age - 65) * 0.02  # Increasing after 65
                    self._lookup_tables[table_name][age] = max(0.5, min(3.0, factor))

            # Example: Territory factors
            elif table_name == "territory_factors":
                # Simplified ZIP-based territories
                for zip_prefix in range(100, 1000):
                    # Mock territory factor based on ZIP prefix
                    if zip_prefix < 200:  # Northeast
                        factor = 1.15
                    elif zip_prefix < 400:  # Southeast
                        factor = 1.10
                    elif zip_prefix < 600:  # Midwest
                        factor = 0.95
                    elif zip_prefix < 800:  # Mountain
                        factor = 0.90
                    else:  # West Coast
                        factor = 1.20
                    self._lookup_tables[table_name][zip_prefix] = factor

    @beartype
    def batch_calculate_factors(
        self,
        factor_requests: list[dict[str, Any]],
    ) -> dict:
        """Batch calculate factors for multiple risks.

        Args:
            factor_requests: List of factor calculation requests

        Returns:
            Result containing list of calculated factors or error
        """
        try:
            results = []

            # Vectorize calculations where possible
            ages = np.array([req.get("age", 30) for req in factor_requests])
            years_licensed = np.array(
                [req.get("years_licensed", 10) for req in factor_requests]
            )
            violations = np.array([req.get("violations", 0) for req in factor_requests])

            # Vectorized age factor calculation
            age_factors = np.where(
                ages < 25,
                2.0 - (ages - 16) * 0.1,
                np.where(ages <= 65, 0.9, 0.9 + (ages - 65) * 0.02),
            )
            age_factors = np.clip(age_factors, 0.5, 3.0)

            # Vectorized experience factor
            exp_factors = 1.0 - np.exp(-years_licensed / 8.0) * 0.3

            # Vectorized violation factor
            viol_factors = 1.0 + violations * 0.15

            # Combine results
            for i, request in enumerate(factor_requests):
                result = {
                    "age_factor": float(age_factors[i]),
                    "experience_factor": float(exp_factors[i]),
                    "violation_factor": float(viol_factors[i]),
                    "combined_factor": float(
                        age_factors[i] * exp_factors[i] * viol_factors[i]
                    ),
                }
                results.append(result)

            return Ok(results)

        except Exception as e:
            return Err(f"Batch calculation failed: {str(e)}")

    @beartype
    def lookup_factor(self, table_name: str, key: Any):
        """Fast lookup of precomputed factors.

        Args:
            table_name: Name of the lookup table
            key: Key to lookup

        Returns:
            Result containing factor value or error
        """
        if table_name not in self._lookup_tables:
            return Err(f"Lookup table '{table_name}' not found")

        table = self._lookup_tables[table_name]

        # Direct lookup
        if key in table:
            return Ok(table[key])

        # Interpolated lookup for numeric keys
        if isinstance(key, (int, float)):
            sorted_keys = sorted(
                [k for k in table.keys() if isinstance(k, (int, float))]
            )
            if not sorted_keys:
                return Err(f"No numeric keys found in table '{table_name}'")

            # Find bounds for interpolation
            lower_key = None
            upper_key = None

            for table_key in sorted_keys:
                if table_key <= key:
                    lower_key = table_key
                elif table_key > key and upper_key is None:
                    upper_key = table_key
                    break

            if lower_key is None:
                return Ok(table[sorted_keys[0]])  # Below range
            elif upper_key is None:
                return Ok(table[lower_key])  # Above range or exact match
            else:
                # Linear interpolation
                t = (key - lower_key) / (upper_key - lower_key)
                interpolated = table[lower_key] * (1 - t) + table[upper_key] * t
                return Ok(interpolated)

        return Err(f"Key '{key}' not found in table '{table_name}'")


class RegulatoryComplianceCalculator:
    """Ensure calculations comply with state-specific regulations."""

    @beartype
    @staticmethod
    def validate_rate_deviation(
        calculated_rate: Decimal,
        filed_rate: Decimal,
        state: str,
        coverage_type: str,
    ):
        """Validate that calculated rate is within acceptable deviation from filed rate.

        Args:
            calculated_rate: Rate produced by rating algorithm
            filed_rate: Filed rate with regulatory authority
            state: State jurisdiction
            coverage_type: Type of coverage

        Returns:
            Result indicating compliance or error
        """
        try:
            if filed_rate <= 0:
                return Err("Filed rate must be positive")

            deviation_pct = abs((calculated_rate - filed_rate) / filed_rate) * 100

            # State-specific deviation tolerances
            tolerances = {
                "CA": {"auto": 5.0, "home": 7.0},  # California strict tolerance
                "TX": {"auto": 10.0, "home": 15.0},  # Texas more flexible
                "NY": {"auto": 7.5, "home": 10.0},  # New York moderate
                "FL": {
                    "auto": 15.0,
                    "home": 20.0,
                },  # Florida more flexible due to catastrophes
            }

            default_tolerance = {"auto": 10.0, "home": 15.0}
            state_tolerance = tolerances.get(state, default_tolerance)
            max_deviation = state_tolerance.get(coverage_type, 10.0)

            if deviation_pct > max_deviation:
                return Err(
                    f"Rate deviation {deviation_pct:.2f}% exceeds {state} limit of {max_deviation}% "
                    f"for {coverage_type} coverage. Calculated: {calculated_rate}, Filed: {filed_rate}"
                )

            return Ok(True)

        except Exception as e:
            return Err(f"Rate deviation validation failed: {str(e)}")

    @beartype
    @staticmethod
    def apply_mandatory_coverages(
        state: str,
        selected_coverages: list[str],
        vehicle_type: str = "auto",
    ) -> dict:
        """Apply state-mandated coverage requirements.

        Args:
            state: State jurisdiction
            selected_coverages: Customer-selected coverages
            vehicle_type: Type of vehicle

        Returns:
            Result containing complete coverage list or error
        """
        try:
            # State-specific mandatory coverages
            mandatory_by_state = {
                "CA": ["liability", "uninsured_motorist"],
                "NY": ["liability", "uninsured_motorist", "pip"],
                "FL": ["liability", "pip"],
                "TX": ["liability"],
                "MI": ["liability", "pip", "uninsured_motorist"],
            }

            mandatory = mandatory_by_state.get(state, ["liability"])

            # Combine selected and mandatory coverages
            all_coverages = set(selected_coverages + mandatory)

            # Validate coverage combinations
            if "collision" in all_coverages and "comprehensive" not in all_coverages:
                # Some states require comprehensive with collision
                if state in ["CA", "NY"]:
                    all_coverages.add("comprehensive")

            return Ok(sorted(list(all_coverages)))

        except Exception as e:
            return Err(f"Mandatory coverage application failed: {str(e)}")
