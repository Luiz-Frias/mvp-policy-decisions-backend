"""Unit tests for rating calculators ensuring penny precision."""

from datetime import datetime
from decimal import Decimal

import pytest

from pd_prime_demo.services.rating.calculators import (
    AIRiskScorer,
    CreditBasedInsuranceScorer,
    DiscountCalculator,
    ExternalDataIntegrator,
    PremiumCalculator,
)


class TestPremiumCalculator:
    """Test premium calculation with penny precision."""

    def test_calculate_base_premium_success(self):
        """Test successful base premium calculation."""
        # Test case: $100,000 coverage, 0.5% rate, 1 exposure unit
        result = PremiumCalculator.calculate_base_premium(
            coverage_limit=Decimal("100000"),
            base_rate=Decimal("0.005"),
            exposure_units=Decimal("1"),
        )

        assert result.is_ok()
        assert result.unwrap() == Decimal("0.50")  # $100,000 * 0.005 / 1000 = $0.50

    def test_calculate_base_premium_rounding(self):
        """Test proper rounding to nearest penny."""
        # Test case that would result in 0.333333...
        result = PremiumCalculator.calculate_base_premium(
            coverage_limit=Decimal("66666.67"),
            base_rate=Decimal("0.005"),
            exposure_units=Decimal("1"),
        )

        assert result.is_ok()
        assert result.unwrap() == Decimal("0.33")  # Rounded to nearest penny

    def test_calculate_base_premium_validation(self):
        """Test input validation."""
        # Negative coverage limit
        result = PremiumCalculator.calculate_base_premium(
            coverage_limit=Decimal("-100000"),
            base_rate=Decimal("0.005"),
        )
        assert result.is_err()
        assert "Coverage limit must be positive" in result.unwrap_err()

        # Zero base rate
        result = PremiumCalculator.calculate_base_premium(
            coverage_limit=Decimal("100000"),
            base_rate=Decimal("0"),
        )
        assert result.is_err()
        assert "Base rate must be positive" in result.unwrap_err()

    def test_apply_multiplicative_factors_success(self):
        """Test applying rating factors with detailed breakdown."""
        base_premium = Decimal("1000.00")
        factors = {
            "territory": 1.2,  # 20% increase
            "driver_age": 0.9,  # 10% discount
            "violations": 1.5,  # 50% increase
        }

        result = PremiumCalculator.apply_multiplicative_factors(base_premium, factors)

        assert result.is_ok()
        final_premium, impacts = result.unwrap()

        # Final premium: 1000 * 1.2 * 0.9 * 1.5 = 1620
        assert final_premium == Decimal("1620.00")

        # Check individual impacts
        assert impacts["territory"] == Decimal("200.00")  # 1000 * 0.2
        assert impacts["driver_age"] == Decimal("-120.00")  # 1200 * -0.1
        assert impacts["violations"] == Decimal("540.00")  # 1080 * 0.5

    def test_apply_multiplicative_factors_validation(self):
        """Test factor validation."""
        base_premium = Decimal("1000.00")

        # Factor too low
        result = PremiumCalculator.apply_multiplicative_factors(
            base_premium, {"territory": 0.05}
        )
        assert result.is_err()
        assert "outside valid range" in result.unwrap_err()

        # Factor too high
        result = PremiumCalculator.apply_multiplicative_factors(
            base_premium, {"territory": 6.0}
        )
        assert result.is_err()
        assert "outside valid range" in result.unwrap_err()

    def test_calculate_territory_factor_success(self):
        """Test territory factor calculation."""
        territory_data = {
            "base_loss_cost": 100,
            "90210": {
                "loss_cost": 120,
                "credibility": 0.8,
            },
        }

        result = PremiumCalculator.calculate_territory_factor("90210", territory_data)

        assert result.is_ok()
        # Factor = 0.8 * (120/100) + 0.2 * 1.0 = 0.8 * 1.2 + 0.2 = 1.16
        assert abs(result.unwrap() - 1.16) < 0.001

    def test_calculate_territory_factor_missing_data(self):
        """Test territory factor with missing base loss cost."""
        territory_data = {}

        result = PremiumCalculator.calculate_territory_factor("90210", territory_data)

        assert result.is_err()
        assert "base_loss_cost is required" in result.unwrap_err()
        assert "Admin > Rate Management > Territory Rates" in result.unwrap_err()

    def test_calculate_driver_risk_score_young_driver(self):
        """Test driver risk score for young driver."""
        driver_data = {
            "age": 18,
            "years_licensed": 2,
            "violations_3_years": 1,
            "accidents_3_years": 0,
        }

        result = PremiumCalculator.calculate_driver_risk_score(driver_data)

        assert result.is_ok()
        score, factors = result.unwrap()

        assert 0.0 <= score <= 1.0
        assert "Young driver (age 18)" in factors
        assert "New driver (2 years)" in factors
        assert "1 violations" in factors

    def test_calculate_driver_risk_score_validation(self):
        """Test driver risk score validation."""
        # Missing required field
        result = PremiumCalculator.calculate_driver_risk_score({"age": 30})
        assert result.is_err()
        assert "years_licensed is required" in result.unwrap_err()

        # Invalid age
        result = PremiumCalculator.calculate_driver_risk_score(
            {"age": 150, "years_licensed": 5}
        )
        assert result.is_err()
        assert "Invalid driver age" in result.unwrap_err()

    def test_calculate_vehicle_risk_score_success(self):
        """Test vehicle risk score calculation."""
        vehicle_data = {
            "type": "sports",
            "age": 2,
            "safety_features": ["abs", "airbags", "automatic_braking"],
            "theft_rate": 1.2,
        }

        result = PremiumCalculator.calculate_vehicle_risk_score(vehicle_data)

        assert result.is_ok()
        score = result.unwrap()

        # Sports car base: 1.4
        # Age factor: 1.0 - (0.05 * 2) = 0.9
        # Safety credits: 1.0 - 0.02 - 0.03 - 0.05 = 0.9
        # Expected: 1.4 * 0.9 * 0.9 * 1.2 = 1.3608
        assert 1.3 <= score <= 1.4

    def test_calculate_vehicle_risk_score_validation(self):
        """Test vehicle risk score validation."""
        # Missing vehicle type
        result = PremiumCalculator.calculate_vehicle_risk_score({})
        assert result.is_err()
        assert "type is required" in result.unwrap_err()

        # Unknown vehicle type
        result = PremiumCalculator.calculate_vehicle_risk_score({"type": "unknown"})
        assert result.is_err()
        assert "Unknown vehicle type" in result.unwrap_err()


class TestDiscountCalculator:
    """Test discount stacking calculations."""

    def test_calculate_stacked_discounts_simple(self):
        """Test simple discount stacking."""
        base_premium = Decimal("1000.00")
        discounts = [
            {"rate": 0.10, "priority": 1, "stackable": True},  # 10% discount
            {"rate": 0.05, "priority": 2, "stackable": True},  # 5% discount
        ]

        result = DiscountCalculator.calculate_stacked_discounts(base_premium, discounts)

        assert result.is_ok()
        applied, total = result.unwrap()

        # First discount: $100 off $1000
        # Second discount: $45 off $900
        # Total: $145
        assert total == Decimal("145.00")
        assert len(applied) == 2
        assert applied[0]["amount"] == Decimal("100.00")
        assert applied[1]["amount"] == Decimal("45.00")

    def test_calculate_stacked_discounts_max_limit(self):
        """Test discount stacking with maximum limit."""
        base_premium = Decimal("1000.00")
        discounts = [
            {"rate": 0.25, "priority": 1, "stackable": True},  # 25% discount
            {"rate": 0.20, "priority": 2, "stackable": True},  # 20% discount
        ]

        result = DiscountCalculator.calculate_stacked_discounts(
            base_premium, discounts, max_total_discount=Decimal("0.40")
        )

        assert result.is_ok()
        applied, total = result.unwrap()

        # Should stop at 40% total discount
        assert total == Decimal("400.00")  # 40% of $1000
        # Applied rates should add up correctly
        # First: 25% of $1000 = $250
        # Second: ($400 - $250) / $750 = $150 / $750 = 0.20
        assert applied[0]["applied_rate"] == 0.25  # First discount fully applied
        assert (
            abs(applied[1]["applied_rate"] - 0.20) < 0.001
        )  # Second discount approximately 20%

    def test_calculate_stacked_discounts_non_stackable(self):
        """Test non-stackable discount handling."""
        base_premium = Decimal("1000.00")
        discounts = [
            {"rate": 0.10, "priority": 1, "stackable": True},  # 10% stackable
            {"rate": 0.15, "priority": 2, "stackable": False},  # 15% non-stackable
        ]

        result = DiscountCalculator.calculate_stacked_discounts(base_premium, discounts)

        assert result.is_ok()
        applied, total = result.unwrap()

        # Non-stackable 15% is better than stackable 10%
        assert len(applied) == 1
        assert total == Decimal("150.00")
        assert applied[0]["rate"] == 0.15

    def test_calculate_stacked_discounts_validation(self):
        """Test discount validation."""
        base_premium = Decimal("1000.00")

        # Missing rate
        result = DiscountCalculator.calculate_stacked_discounts(
            base_premium, [{"priority": 1}]
        )
        assert result.is_err()
        assert "discount rate is required" in result.unwrap_err()

        # Invalid rate
        result = DiscountCalculator.calculate_stacked_discounts(
            base_premium, [{"rate": 1.5}]
        )
        assert result.is_err()
        assert "Invalid discount rate" in result.unwrap_err()

    def test_calculate_stacked_discounts_state_rules(self):
        """Test state-specific discount rules."""
        base_premium = Decimal("1000.00")
        discounts = [
            {"rate": 0.30, "priority": 1, "stackable": True},
            {"rate": 0.20, "priority": 2, "stackable": True},
        ]
        state_rules = {"max_discount": 0.35}  # State limits to 35%

        result = DiscountCalculator.calculate_stacked_discounts(
            base_premium, discounts, state_rules=state_rules
        )

        assert result.is_ok()
        applied, total = result.unwrap()

        # Should respect state limit of 35%
        assert total == Decimal("350.00")  # 35% of $1000


class TestAIRiskScorer:
    """Test AI risk scoring functionality."""

    @pytest.mark.asyncio
    async def test_calculate_ai_risk_score_success(self):
        """Test successful AI risk score calculation."""
        scorer = AIRiskScorer(load_models=True)

        customer_data = {
            "policy_count": 2,
            "years_as_customer": 5,
            "previous_claims": 0,
        }
        vehicle_data = {
            "age": 3,
            "value": 25000,
            "annual_mileage": 12000,
            "safety_features": ["abs", "airbags"],
        }
        driver_data = [
            {
                "age": 35,
                "years_licensed": 15,
                "violations_3_years": 0,
                "accidents_3_years": 0,
            }
        ]

        result = await scorer.calculate_ai_risk_score(
            customer_data, vehicle_data, driver_data
        )

        assert result.is_ok()
        score_data = result.unwrap()

        assert "score" in score_data
        assert 0.0 <= score_data["score"] <= 1.0
        assert "components" in score_data
        assert "claim_probability" in score_data["components"]
        assert "expected_severity" in score_data["components"]
        assert "fraud_risk" in score_data["components"]
        assert "confidence" in score_data
        assert "model_version" in score_data

    @pytest.mark.asyncio
    async def test_calculate_ai_risk_score_validation(self):
        """Test AI risk score validation."""
        scorer = AIRiskScorer()

        # Missing vehicle data
        result = await scorer.calculate_ai_risk_score(
            {"policy_count": 1},
            {},  # Missing required fields
            [{"age": 30}],
        )

        assert result.is_err()
        assert "Vehicle age and value are required" in result.unwrap_err()

        # No drivers
        result = await scorer.calculate_ai_risk_score(
            {"policy_count": 1},
            {"age": 5, "value": 20000},
            [],  # Empty driver list
        )

        assert result.is_err()
        assert "At least one driver is required" in result.unwrap_err()

    @pytest.mark.asyncio
    async def test_calculate_ai_risk_score_model_fallback(self):
        """Test AI risk score fallback when models unavailable."""
        scorer = AIRiskScorer()
        # Models are not loaded by default

        result = await scorer.calculate_ai_risk_score(
            {"policy_count": 1},
            {"age": 5, "value": 20000},
            [{"age": 30, "years_licensed": 10}],
        )

        assert result.is_err()
        assert "AI scoring error: Models not loaded" in result.unwrap_err()
        assert "Using traditional actuarial scoring" in result.unwrap_err()


class TestPennyPrecision:
    """Test penny precision across all calculations."""

    def test_complex_calculation_precision(self):
        """Test precision in complex multi-step calculations."""
        # Start with base premium
        base_result = PremiumCalculator.calculate_base_premium(
            coverage_limit=Decimal("123456.78"),
            base_rate=Decimal("0.00789"),
            exposure_units=Decimal("1.5"),
        )
        assert base_result.is_ok()
        base_premium = base_result.unwrap()

        # Apply factors
        factors = {
            "territory": 1.123,
            "driver_age": 0.987,
            "experience": 1.045,
            "vehicle_age": 0.923,
        }
        factor_result = PremiumCalculator.apply_multiplicative_factors(
            base_premium, factors
        )
        assert factor_result.is_ok()
        factored_premium, _ = factor_result.unwrap()

        # Apply discounts
        discounts = [
            {"rate": 0.127, "priority": 1},
            {"rate": 0.083, "priority": 2},
            {"rate": 0.051, "priority": 3},
        ]
        discount_result = DiscountCalculator.calculate_stacked_discounts(
            factored_premium, discounts
        )
        assert discount_result.is_ok()
        _, total_discount = discount_result.unwrap()

        final_premium = factored_premium - total_discount

        # Verify all amounts have exactly 2 decimal places
        assert (
            str(base_premium).split(".")[-1]
            == str(base_premium.quantize(Decimal("0.01"))).split(".")[-1]
        )
        assert (
            str(factored_premium).split(".")[-1]
            == str(factored_premium.quantize(Decimal("0.01"))).split(".")[-1]
        )
        assert (
            str(total_discount).split(".")[-1]
            == str(total_discount.quantize(Decimal("0.01"))).split(".")[-1]
        )
        assert (
            str(final_premium).split(".")[-1]
            == str(final_premium.quantize(Decimal("0.01"))).split(".")[-1]
        )

    def test_rounding_consistency(self):
        """Test that rounding is consistent across operations."""
        # Test various amounts that could cause rounding issues
        test_amounts = [
            Decimal("0.005"),  # Should round to 0.01
            Decimal("0.004"),  # Should round to 0.00
            Decimal("99.995"),  # Should round to 100.00
            Decimal("1.235"),  # Should round to 1.24
            Decimal("1.225"),  # Should round to 1.23 (banker's rounding)
        ]

        for amount in test_amounts:
            # Test in premium calculation
            result = PremiumCalculator.calculate_base_premium(
                coverage_limit=amount * 1000,
                base_rate=Decimal("0.001"),
            )
            if result.is_ok():
                premium = result.unwrap()
                # Verify exactly 2 decimal places
                assert len(str(premium).split(".")[-1]) <= 2


class TestCreditBasedInsuranceScorer:
    """Test credit-based insurance scoring functionality."""

    def test_calculate_credit_factor_excellent_credit(self):
        """Test credit factor for excellent credit score."""
        result = CreditBasedInsuranceScorer.calculate_credit_factor(
            credit_score=780, state="TX", product_type="auto"
        )

        assert result.is_ok()
        factor = result.unwrap()
        assert factor == 0.85  # Excellent credit discount

    def test_calculate_credit_factor_prohibited_state(self):
        """Test credit factor in state that prohibits credit scoring."""
        result = CreditBasedInsuranceScorer.calculate_credit_factor(
            credit_score=750,
            state="CA",  # California prohibits credit scoring
            product_type="auto",
        )

        assert result.is_err()
        error = result.unwrap_err()
        assert "Credit-based insurance scoring prohibited in CA" in error
        assert "Admin > Rating Rules > State Regulations" in error

    def test_calculate_credit_factor_invalid_score(self):
        """Test credit factor with invalid credit score."""
        result = CreditBasedInsuranceScorer.calculate_credit_factor(
            credit_score=900, state="TX", product_type="auto"  # Invalid - too high
        )

        assert result.is_err()
        assert "Invalid credit score: 900" in result.unwrap_err()

    def test_calculate_insurance_score_success(self):
        """Test insurance score calculation."""
        result = CreditBasedInsuranceScorer.calculate_insurance_score(
            credit_score=720,
            payment_history=0.95,  # Excellent payment history
            credit_utilization=0.20,  # Good utilization
            length_of_credit=10,  # 10 years
            new_credit_inquiries=1,  # 1 recent inquiry
        )

        assert result.is_ok()
        score = result.unwrap()
        assert 200 <= score <= 997
        assert score > 720  # Should be higher than base FICO due to good factors

    def test_calculate_insurance_score_validation(self):
        """Test insurance score input validation."""
        # Invalid payment history
        result = CreditBasedInsuranceScorer.calculate_insurance_score(
            credit_score=720,
            payment_history=1.5,  # Invalid - too high
            credit_utilization=0.20,
            length_of_credit=10,
            new_credit_inquiries=1,
        )
        assert result.is_err()
        assert "Payment history must be between 0.0 and 1.0" in result.unwrap_err()

        # Negative credit utilization
        result = CreditBasedInsuranceScorer.calculate_insurance_score(
            credit_score=720,
            payment_history=0.95,
            credit_utilization=-0.1,  # Invalid - negative
            length_of_credit=10,
            new_credit_inquiries=1,
        )
        assert result.is_err()
        assert "Credit utilization cannot be negative" in result.unwrap_err()


class TestExternalDataIntegrator:
    """Test external data integration functionality."""

    @pytest.mark.asyncio
    async def test_get_weather_risk_factor_hurricane_zone(self):
        """Test weather risk factor for hurricane-prone area."""
        result = await ExternalDataIntegrator.get_weather_risk_factor(
            zip_code="33101", effective_date=datetime.now()  # Miami, FL
        )

        assert result.is_ok()
        factor = result.unwrap()
        assert factor == 1.25  # High risk for Florida

    @pytest.mark.asyncio
    async def test_get_weather_risk_factor_low_risk(self):
        """Test weather risk factor for low-risk area."""
        result = await ExternalDataIntegrator.get_weather_risk_factor(
            zip_code="50309", effective_date=datetime.now()  # Des Moines, IA
        )

        assert result.is_ok()
        factor = result.unwrap()
        assert factor == 1.00  # Normal risk

    @pytest.mark.asyncio
    async def test_get_weather_risk_factor_invalid_zip(self):
        """Test weather risk factor with invalid ZIP code."""
        from datetime import datetime

        result = await ExternalDataIntegrator.get_weather_risk_factor(
            zip_code="invalid", effective_date=datetime.now()
        )

        assert result.is_err()
        assert "Invalid ZIP code format" in result.unwrap_err()

    @pytest.mark.asyncio
    async def test_get_crime_risk_factor_high_crime(self):
        """Test crime risk factor for high-crime area."""
        result = await ExternalDataIntegrator.get_crime_risk_factor(
            zip_code="60601"  # Chicago downtown
        )

        assert result.is_ok()
        factor = result.unwrap()
        assert factor == 1.15  # High crime area

    @pytest.mark.asyncio
    async def test_get_crime_risk_factor_suburban(self):
        """Test crime risk factor for suburban area."""
        result = await ExternalDataIntegrator.get_crime_risk_factor(
            zip_code="85001"  # Phoenix suburban
        )

        assert result.is_ok()
        factor = result.unwrap()
        assert factor == 0.95  # Lower risk suburban

    @pytest.mark.asyncio
    async def test_validate_vehicle_data_success(self):
        """Test successful VIN validation and enhancement."""
        result = await ExternalDataIntegrator.validate_vehicle_data(
            vin="4T1BF1FK0CU123456"  # Valid format
        )

        assert result.is_ok()
        data = result.unwrap()

        # Check enhanced data structure
        assert "make" in data
        assert "model" in data
        assert "year" in data
        assert "safety_features" in data
        assert "msrp" in data
        assert "theft_rate" in data
        assert "validated" in data
        assert data["validated"] is True

    @pytest.mark.asyncio
    async def test_validate_vehicle_data_invalid_vin(self):
        """Test VIN validation with invalid VIN."""
        result = await ExternalDataIntegrator.validate_vehicle_data(
            vin="invalid"  # Too short
        )

        assert result.is_err()
        assert "VIN must be exactly 17 characters" in result.unwrap_err()


class TestAdvancedCalculationIntegration:
    """Test integration of advanced calculation features."""

    @pytest.mark.asyncio
    async def test_comprehensive_risk_assessment(self):
        """Test comprehensive risk assessment using all calculators."""
        # Base premium calculation
        base_result = PremiumCalculator.calculate_base_premium(
            coverage_limit=Decimal("100000"),
            base_rate=Decimal("0.005"),
        )
        assert base_result.is_ok()
        base_premium = base_result.unwrap()

        # Credit-based adjustment (for allowed state)
        credit_result = CreditBasedInsuranceScorer.calculate_credit_factor(
            credit_score=750, state="TX"
        )
        assert credit_result.is_ok()
        credit_factor = credit_result.unwrap()

        # External risk factors
        weather_result = await ExternalDataIntegrator.get_weather_risk_factor(
            zip_code="75201", effective_date=datetime.now()  # Dallas, TX
        )
        assert weather_result.is_ok()
        weather_factor = weather_result.unwrap()

        crime_result = await ExternalDataIntegrator.get_crime_risk_factor(
            zip_code="75201"
        )
        assert crime_result.is_ok()
        crime_factor = crime_result.unwrap()

        # AI risk scoring
        ai_scorer = AIRiskScorer(load_models=True)
        ai_result = await ai_scorer.calculate_ai_risk_score(
            customer_data={
                "policy_count": 1,
                "years_as_customer": 2,
                "previous_claims": 0,
            },
            vehicle_data={"age": 3, "value": 25000, "annual_mileage": 12000},
            driver_data=[{"age": 30, "years_licensed": 12, "violations_3_years": 0}],
        )
        assert ai_result.is_ok()
        ai_data = ai_result.unwrap()

        # Calculate final premium with all factors
        all_factors = {
            "credit": float(credit_factor),
            "weather": weather_factor,
            "crime": crime_factor,
            "ai_risk": 0.5 + ai_data["score"],  # Convert AI score to factor
        }

        factor_result = PremiumCalculator.apply_multiplicative_factors(
            base_premium, all_factors
        )
        assert factor_result.is_ok()
        final_premium, impacts = factor_result.unwrap()

        # Verify all factors were applied
        assert len(impacts) == len(all_factors)
        assert final_premium > 0
        assert isinstance(final_premium, Decimal)

    def test_state_specific_credit_compliance(self):
        """Test that credit scoring respects state-specific regulations."""
        prohibited_states = ["CA", "HI", "MA", "MD", "MI", "MT", "NC", "OR", "UT", "WA"]
        allowed_states = ["TX", "FL", "NY", "IL", "OH"]

        credit_score = 750

        # Test prohibited states
        for state in prohibited_states:
            result = CreditBasedInsuranceScorer.calculate_credit_factor(
                credit_score=credit_score, state=state
            )
            assert result.is_err()
            assert "prohibited" in result.unwrap_err().lower()

        # Test allowed states
        for state in allowed_states:
            result = CreditBasedInsuranceScorer.calculate_credit_factor(
                credit_score=credit_score, state=state
            )
            assert result.is_ok()
            factor = result.unwrap()
            assert 0.5 <= factor <= 1.5  # Reasonable range


class TestStatisticalRatingModels:
    """Test advanced statistical rating models."""

    def test_calculate_generalized_linear_model_factor_log_link(self):
        """Test GLM calculation with log link function."""
        from pd_prime_demo.services.rating.calculators import StatisticalRatingModels

        features = {
            "age": 30.0,
            "experience": 10.0,
            "violations": 1.0,
        }
        coefficients = {
            "intercept": -0.5,
            "age": -0.01,
            "experience": -0.02,
            "violations": 0.3,
        }

        result = StatisticalRatingModels.calculate_generalized_linear_model_factor(
            features, coefficients, "log"
        )

        assert result.is_ok()
        factor = result.unwrap()
        assert 0.1 <= factor <= 10.0  # Within bounds

        # Manual calculation: exp(-0.5 + 30*(-0.01) + 10*(-0.02) + 1*(0.3))
        # = exp(-0.5 - 0.3 - 0.2 + 0.3) = exp(-0.7) ≈ 0.497
        assert abs(factor - 0.497) < 0.01

    def test_calculate_generalized_linear_model_factor_logit_link(self):
        """Test GLM calculation with logit link function."""
        from pd_prime_demo.services.rating.calculators import StatisticalRatingModels

        features = {"risk_score": 0.5}
        coefficients = {"intercept": 0.0, "risk_score": 2.0}

        result = StatisticalRatingModels.calculate_generalized_linear_model_factor(
            features, coefficients, "logit"
        )

        assert result.is_ok()
        factor = result.unwrap()
        assert 0.0 <= factor <= 1.0  # Logit produces probabilities

        # Manual calculation: 1/(1 + exp(-(0 + 0.5*2))) = 1/(1 + exp(-1)) ≈ 0.731
        assert abs(factor - 0.731) < 0.01

    def test_calculate_generalized_linear_model_factor_validation(self):
        """Test GLM validation errors."""
        from pd_prime_demo.services.rating.calculators import StatisticalRatingModels

        # No features
        result = StatisticalRatingModels.calculate_generalized_linear_model_factor(
            {}, {"intercept": 1.0}, "log"
        )
        assert result.is_err()
        assert "Features are required" in result.unwrap_err()

        # No coefficients
        result = StatisticalRatingModels.calculate_generalized_linear_model_factor(
            {"age": 30.0}, {}, "log"
        )
        assert result.is_err()
        assert "Coefficients are required" in result.unwrap_err()

        # Invalid link function
        result = StatisticalRatingModels.calculate_generalized_linear_model_factor(
            {"age": 30.0}, {"intercept": 1.0}, "invalid"
        )
        assert result.is_err()
        assert "Unsupported link function" in result.unwrap_err()

    def test_calculate_loss_cost_relativity_high_credibility(self):
        """Test loss cost relativity with high credibility."""
        from pd_prime_demo.services.rating.calculators import StatisticalRatingModels

        exposure_data = {"exposure_years": 100}
        loss_data = {
            "claim_count": 25,  # High credibility (25 > 16)
            "claim_amount": 150000,  # $150k total losses
            "manual_loss_cost": 100,  # $100 manual rate
        }

        result = StatisticalRatingModels.calculate_loss_cost_relativity(
            exposure_data, loss_data
        )

        assert result.is_ok()
        relativity = result.unwrap()

        # Observed loss cost = 150000 / 100 = 1500
        # Credibility = sqrt(25/16) = 1.25, capped at 1.0
        # Relativity = 1.0 * (1500/100) + 0.0 * 1.0 = 15.0
        # But should be capped at 4.0
        assert relativity == 4.0

    def test_calculate_loss_cost_relativity_low_credibility(self):
        """Test loss cost relativity with low credibility."""
        from pd_prime_demo.services.rating.calculators import StatisticalRatingModels

        exposure_data = {"exposure_years": 10}
        loss_data = {
            "claim_count": 2,  # Low credibility
            "claim_amount": 50000,
            "manual_loss_cost": 100,
        }

        result = StatisticalRatingModels.calculate_loss_cost_relativity(
            exposure_data, loss_data, credibility_threshold=0.5
        )

        assert result.is_ok()
        relativity = result.unwrap()

        # Low credibility should result in manual rate (1.0)
        assert relativity == 1.0

    def test_calculate_frequency_severity_model_success(self):
        """Test frequency/severity model calculation."""
        from pd_prime_demo.services.rating.calculators import StatisticalRatingModels

        driver_profile = {
            "age": 35,
            "prior_claims": 0,
        }
        vehicle_profile = {
            "age": 3,
            "annual_mileage": 12000,
            "value": 30000,
            "safety_features": ["abs", "airbags"],
        }
        territory_profile = {
            "urban": True,
        }

        result = StatisticalRatingModels.calculate_frequency_severity_model(
            driver_profile, vehicle_profile, territory_profile
        )

        assert result.is_ok()
        model_data = result.unwrap()

        assert "frequency_factor" in model_data
        assert "severity_factor" in model_data
        assert "expected_claims" in model_data
        assert "expected_severity" in model_data
        assert "pure_premium_factor" in model_data

        # All factors should be positive
        assert model_data["frequency_factor"] > 0
        assert model_data["severity_factor"] > 0
        assert model_data["expected_severity"] > 0

    def test_calculate_catastrophe_loading_hurricane_zone(self):
        """Test catastrophe loading for hurricane zone."""
        from pd_prime_demo.services.rating.calculators import StatisticalRatingModels

        result = StatisticalRatingModels.calculate_catastrophe_loading(
            zip_code="33101",  # Miami, FL
            coverage_types=["comprehensive", "collision"],
        )

        assert result.is_ok()
        loading = result.unwrap()
        assert loading == 1.15  # 15% hurricane loading

    def test_calculate_catastrophe_loading_earthquake_zone(self):
        """Test catastrophe loading for earthquake zone."""
        from pd_prime_demo.services.rating.calculators import StatisticalRatingModels

        result = StatisticalRatingModels.calculate_catastrophe_loading(
            zip_code="90210",  # Beverly Hills, CA
            coverage_types=["comprehensive"],
        )

        assert result.is_ok()
        loading = result.unwrap()
        assert loading == 1.08  # 8% earthquake loading

    def test_calculate_catastrophe_loading_with_dwelling_credits(self):
        """Test catastrophe loading with dwelling characteristics."""
        from pd_prime_demo.services.rating.calculators import StatisticalRatingModels

        dwelling_chars = {
            "construction_type": "masonry",
            "roof_type": "impact_resistant",
        }

        result = StatisticalRatingModels.calculate_catastrophe_loading(
            zip_code="33101",  # Hurricane zone
            coverage_types=["comprehensive"],
            dwelling_characteristics=dwelling_chars,
        )

        assert result.is_ok()
        loading = result.unwrap()

        # Base hurricane loading (1.15) * masonry credit (0.95) * impact roof credit (0.90)
        expected = 1.15 * 0.95 * 0.90
        assert abs(loading - expected) < 0.001

    def test_calculate_trend_factors_future_date(self):
        """Test trend factors for future policy date."""
        from datetime import datetime

        from pd_prime_demo.services.rating.calculators import StatisticalRatingModels

        # Policy effective 1 year in the future
        policy_date = datetime(2025, 1, 1)

        result = StatisticalRatingModels.calculate_trend_factors(
            policy_effective_date=policy_date,
            loss_trend_rate=0.05,
            expense_trend_rate=0.03,
        )

        assert result.is_ok()
        trends = result.unwrap()

        assert "loss_trend_factor" in trends
        assert "expense_trend_factor" in trends
        assert "composite_trend_factor" in trends
        assert "years_elapsed" in trends

        # 1 year forward should be approximately base rates * (1 + trend)
        assert abs(trends["loss_trend_factor"] - 1.05) < 0.01
        assert abs(trends["expense_trend_factor"] - 1.03) < 0.01
        assert abs(trends["years_elapsed"] - 1.0) < 0.1


class TestAdvancedPerformanceCalculator:
    """Test advanced performance calculation features."""

    def test_batch_calculate_factors(self):
        """Test batch factor calculation."""
        from pd_prime_demo.services.rating.calculators import (
            AdvancedPerformanceCalculator,
        )

        calculator = AdvancedPerformanceCalculator()

        # Batch of calculation requests
        requests = [
            {"age": 25, "years_licensed": 5, "violations": 0},
            {"age": 45, "years_licensed": 20, "violations": 1},
            {"age": 18, "years_licensed": 1, "violations": 2},
        ]

        result = calculator.batch_calculate_factors(requests)

        assert result.is_ok()
        factors_list = result.unwrap()

        assert len(factors_list) == 3

        # Check each result has required factors
        for factors in factors_list:
            assert "age_factor" in factors
            assert "experience_factor" in factors
            assert "violation_factor" in factors
            assert "combined_factor" in factors

            # All factors should be positive
            assert factors["age_factor"] > 0
            assert factors["experience_factor"] > 0
            assert factors["violation_factor"] > 0
            assert factors["combined_factor"] > 0

    def test_lookup_factor_direct(self):
        """Test direct factor lookup."""
        from pd_prime_demo.services.rating.calculators import (
            AdvancedPerformanceCalculator,
        )

        calculator = AdvancedPerformanceCalculator()

        # Initialize lookup tables
        calculator.precompute_lookup_tables(
            {
                "age_factors": {},
                "territory_factors": {},
            }
        )

        # Test age factor lookup
        result = calculator.lookup_factor("age_factors", 30)
        assert result.is_ok()
        factor = result.unwrap()
        assert factor == 0.9  # Mature driver discount

    def test_lookup_factor_interpolation(self):
        """Test interpolated factor lookup."""
        from pd_prime_demo.services.rating.calculators import (
            AdvancedPerformanceCalculator,
        )

        calculator = AdvancedPerformanceCalculator()

        # Create simple lookup table for testing
        calculator._lookup_tables["test_table"] = {
            10: 1.0,
            20: 2.0,
            30: 3.0,
        }

        # Test interpolation
        result = calculator.lookup_factor("test_table", 25)
        assert result.is_ok()
        factor = result.unwrap()
        assert factor == 2.5  # Linear interpolation between 20 and 30

    def test_lookup_factor_errors(self):
        """Test lookup factor error handling."""
        from pd_prime_demo.services.rating.calculators import (
            AdvancedPerformanceCalculator,
        )

        calculator = AdvancedPerformanceCalculator()

        # Table not found
        result = calculator.lookup_factor("nonexistent_table", 25)
        assert result.is_err()
        assert "not found" in result.unwrap_err()

        # Key not found in table
        calculator._lookup_tables["empty_table"] = {}
        result = calculator.lookup_factor("empty_table", "missing_key")
        assert result.is_err()
        assert "not found" in result.unwrap_err()


class TestRegulatoryComplianceCalculator:
    """Test regulatory compliance calculations."""

    def test_validate_rate_deviation_within_limits(self):
        """Test rate deviation validation within limits."""
        from decimal import Decimal

        from pd_prime_demo.services.rating.calculators import (
            RegulatoryComplianceCalculator,
        )

        result = RegulatoryComplianceCalculator.validate_rate_deviation(
            calculated_rate=Decimal("105.00"),
            filed_rate=Decimal("100.00"),
            state="CA",
            coverage_type="auto",
        )

        assert result.is_ok()
        assert result.unwrap() is True

    def test_validate_rate_deviation_exceeds_limits(self):
        """Test rate deviation validation exceeding limits."""
        from decimal import Decimal

        from pd_prime_demo.services.rating.calculators import (
            RegulatoryComplianceCalculator,
        )

        result = RegulatoryComplianceCalculator.validate_rate_deviation(
            calculated_rate=Decimal("120.00"),
            filed_rate=Decimal("100.00"),
            state="CA",  # CA has 5% tolerance for auto
            coverage_type="auto",
        )

        assert result.is_err()
        error = result.unwrap_err()
        assert "exceeds CA limit of 5.0%" in error
        assert "Calculated: 120.00, Filed: 100.00" in error

    def test_validate_rate_deviation_invalid_filed_rate(self):
        """Test rate deviation with invalid filed rate."""
        from decimal import Decimal

        from pd_prime_demo.services.rating.calculators import (
            RegulatoryComplianceCalculator,
        )

        result = RegulatoryComplianceCalculator.validate_rate_deviation(
            calculated_rate=Decimal("100.00"),
            filed_rate=Decimal("0.00"),  # Invalid
            state="TX",
            coverage_type="auto",
        )

        assert result.is_err()
        assert "Filed rate must be positive" in result.unwrap_err()

    def test_apply_mandatory_coverages_california(self):
        """Test mandatory coverage application for California."""
        from pd_prime_demo.services.rating.calculators import (
            RegulatoryComplianceCalculator,
        )

        result = RegulatoryComplianceCalculator.apply_mandatory_coverages(
            state="CA",
            selected_coverages=["collision", "comprehensive"],
        )

        assert result.is_ok()
        coverages = result.unwrap()

        # CA requires liability and uninsured motorist
        assert "liability" in coverages
        assert "uninsured_motorist" in coverages
        assert "collision" in coverages
        assert "comprehensive" in coverages

    def test_apply_mandatory_coverages_new_york(self):
        """Test mandatory coverage application for New York."""
        from pd_prime_demo.services.rating.calculators import (
            RegulatoryComplianceCalculator,
        )

        result = RegulatoryComplianceCalculator.apply_mandatory_coverages(
            state="NY",
            selected_coverages=["collision"],
        )

        assert result.is_ok()
        coverages = result.unwrap()

        # NY requires liability, uninsured motorist, and PIP
        assert "liability" in coverages
        assert "uninsured_motorist" in coverages
        assert "pip" in coverages
        assert "collision" in coverages
        # NY requires comprehensive with collision
        assert "comprehensive" in coverages
