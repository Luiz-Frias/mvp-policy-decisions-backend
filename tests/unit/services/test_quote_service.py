"""Unit tests for quote service."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from pd_prime_demo.models.quote import (
    CoverageSelection,
    CoverageType,
    DriverInfo,
    ProductType,
    QuoteCreate,
    QuoteStatus,
    QuoteUpdate,
    VehicleInfo,
)
from pd_prime_demo.services.quote_service import QuoteService
from pd_prime_demo.services.result import Err, Ok


@pytest.fixture
def sample_vehicle_info():
    """Sample vehicle information."""
    return VehicleInfo(
        vin="1HGBH41JXMN109186",  # Valid Honda VIN for testing
        year=2022,
        make="Tesla",
        model="Model 3",
        body_style="sedan",
        annual_mileage=12000,
        primary_use="commute",
        garage_zip="94105",
        owned=True,
    )


@pytest.fixture
def sample_driver_info():
    """Sample driver information."""
    return DriverInfo(
        first_name="John",
        last_name="Doe",
        date_of_birth=date(1985, 5, 15),
        gender="M",
        marital_status="married",
        license_number="D1234567",
        license_state="CA",
        license_status="valid",
        first_licensed_date=date(2001, 5, 15),
        accidents_3_years=0,
        violations_3_years=0,
        dui_convictions=0,
        claims_3_years=0,
        good_student=False,
        relationship="self",
    )


@pytest.fixture
def sample_coverage_selections():
    """Sample coverage selections."""
    return [
        CoverageSelection(
            coverage_type=CoverageType.LIABILITY, limit=Decimal("100000.00")
        ),
        CoverageSelection(
            coverage_type=CoverageType.COLLISION,
            limit=Decimal("50000.00"),
            deductible=Decimal("500.00"),
        ),
        CoverageSelection(
            coverage_type=CoverageType.COMPREHENSIVE,
            limit=Decimal("50000.00"),
            deductible=Decimal("500.00"),
        ),
    ]


@pytest.fixture
def sample_quote_create(
    sample_vehicle_info, sample_driver_info, sample_coverage_selections
):
    """Sample quote creation data."""
    return QuoteCreate(
        customer_id=uuid4(),
        product_type="auto",
        state="CA",
        zip_code="94105",
        effective_date=date.today() + timedelta(days=7),
        email="john.doe@example.com",
        phone="14155550123",
        preferred_contact="email",
        vehicle_info=sample_vehicle_info,
        drivers=[sample_driver_info],
        coverage_selections=sample_coverage_selections,
    )


class TestQuoteService:
    """Test quote service functionality."""

    async def test_create_quote_success(self, mock_db, mock_cache, sample_quote_create):
        """Test successful quote creation."""
        # Setup
        service = QuoteService(mock_db, mock_cache)

        # Mock database responses
        mock_db.fetchval.return_value = 1  # Sequence number
        mock_db.fetchrow.return_value = {
            "id": uuid4(),
            "quote_number": "QUOT-2025-000001",
            "customer_id": None,
            "status": "draft",
            "product_type": "auto",
            "state": "CA",
            "zip_code": "94105",
            "effective_date": sample_quote_create.effective_date,
            "email": "john.doe@example.com",
            "phone": "415-555-0123",
            "preferred_contact": "email",
            "vehicle_info": sample_quote_create.vehicle_info.model_dump(),
            "drivers": [d.model_dump() for d in sample_quote_create.drivers],
            "coverage_selections": [
                c.model_dump() for c in sample_quote_create.coverage_selections
            ],
            "expires_at": datetime.now() + timedelta(days=30),
            "base_premium": None,
            "total_premium": None,
            "monthly_premium": None,
            "discounts_applied": [],
            "surcharges_applied": [],
            "total_discount_amount": None,
            "total_surcharge_amount": None,
            "rating_factors": None,
            "rating_tier": None,
            "ai_risk_score": None,
            "ai_risk_factors": None,
            "converted_to_policy_id": None,
            "converted_at": None,
            "created_by": None,
            "updated_by": None,
            "referral_source": "web",
            "version": 1,
            "parent_quote_id": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        # Execute
        result = await service.create_quote(sample_quote_create)

        # Assert
        assert isinstance(result, Ok)
        quote = result.value
        assert quote.quote_number == "QUOT-2025-000001"
        assert quote.status == QuoteStatus.DRAFT
        assert quote.product_type == ProductType.AUTO
        assert quote.state == "CA"

    async def test_create_quote_invalid_state(
        self, mock_db, mock_cache, sample_quote_create
    ):
        """Test quote creation with unsupported state."""
        # Setup
        service = QuoteService(mock_db, mock_cache)

        # Create new instance with unsupported state (can't modify frozen model)
        invalid_quote_create = sample_quote_create.model_copy(update={"state": "FL"})

        # Execute
        result = await service.create_quote(invalid_quote_create)

        # Assert
        assert isinstance(result, Err)
        assert "FL not supported" in result.error

    async def test_create_quote_invalid_effective_date(
        self, mock_db, mock_cache, sample_quote_create
    ):
        """Test quote creation with past effective date."""
        # Setup
        service = QuoteService(mock_db, mock_cache)

        # Create new instance with past effective date (can't modify frozen model)
        invalid_quote_create = sample_quote_create.model_copy(
            update={"effective_date": date.today() - timedelta(days=1)}
        )

        # Execute
        result = await service.create_quote(invalid_quote_create)

        # Assert
        assert isinstance(result, Err)
        assert "cannot be in the past" in result.error

    async def test_calculate_quote_success(self, mock_db, mock_cache):
        """Test successful quote calculation."""
        # Setup
        service = QuoteService(mock_db, mock_cache)
        quote_id = uuid4()

        # Mock existing quote
        mock_cache.get.return_value = None
        mock_db.fetchrow.side_effect = [
            # First call - get quote
            {
                "id": quote_id,
                "quote_number": "QUOT-2025-000001",
                "customer_id": None,
                "status": "DRAFT",
                "product_type": "AUTO",
                "state": "CA",
                "zip_code": "94105",
                "effective_date": date.today() + timedelta(days=7),
                "email": "john.doe@example.com",
                "phone": "415-555-0123",
                "preferred_contact": "email",
                "vehicle_info": {
                    "year": 2022,
                    "make": "Tesla",
                    "model": "Model 3",
                    "body_style": "sedan",
                    "annual_mileage": 12000,
                    "primary_use": "commute",
                    "garage_zip": "94105",
                    "owned": True,
                },
                "drivers": [
                    {
                        "driver_id": str(uuid4()),
                        "relationship": "SELF",
                        "first_name": "John",
                        "last_name": "Doe",
                        "date_of_birth": "1985-05-15",
                        "license_number": "D1234567",
                        "license_state": "CA",
                        "license_status": "valid",
                        "years_licensed": 15,
                        "accidents_3_years": 0,
                        "violations_3_years": 0,
                        "dui_convictions": 0,
                        "good_student": False,
                        "defensive_driving": True,
                    }
                ],
                "coverage_selections": [],
                "expires_at": datetime.now() + timedelta(days=30),
                "base_premium": None,
                "total_premium": None,
                "monthly_premium": None,
                "discounts_applied": [],
                "surcharges_applied": [],
                "total_discount_amount": None,
                "total_surcharge_amount": None,
                "rating_factors": None,
                "rating_tier": None,
                "ai_risk_score": None,
                "ai_risk_factors": None,
                "converted_to_policy_id": None,
                "converted_at": None,
                "created_by": None,
                "updated_by": None,
                "referral_source": "web",
                "version": 1,
                "parent_quote_id": None,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            },
            # Second call - update quote
            {
                "id": quote_id,
                "quote_number": "QUOT-2025-000001",
                "customer_id": None,
                "status": "quoted",
                "product_type": "auto",
                "state": "CA",
                "zip_code": "94105",
                "effective_date": date.today() + timedelta(days=7),
                "email": "john.doe@example.com",
                "phone": "415-555-0123",
                "preferred_contact": "email",
                "vehicle_info": {
                    "year": 2022,
                    "make": "Tesla",
                    "model": "Model 3",
                    "body_style": "sedan",
                    "annual_mileage": 12000,
                    "primary_use": "commute",
                    "garage_zip": "94105",
                    "owned": True,
                },
                "drivers": [
                    {
                        "driver_id": str(uuid4()),
                        "relationship": "SELF",
                        "first_name": "John",
                        "last_name": "Doe",
                        "date_of_birth": "1985-05-15",
                        "license_number": "D1234567",
                        "license_state": "CA",
                        "license_status": "valid",
                        "years_licensed": 15,
                        "accidents_3_years": 0,
                        "violations_3_years": 0,
                        "dui_convictions": 0,
                        "good_student": False,
                        "defensive_driving": True,
                    }
                ],
                "coverage_selections": [],
                "expires_at": datetime.now() + timedelta(days=30),
                "base_premium": Decimal("1200.00"),
                "total_premium": Decimal("1080.00"),
                "monthly_premium": Decimal("108.00"),
                "discounts_applied": [],
                "surcharges_applied": [],
                "total_discount_amount": Decimal("120.00"),
                "total_surcharge_amount": Decimal("0.00"),
                "rating_factors": {"base_rate": 1200.0},
                "rating_tier": "STANDARD",
                "ai_risk_score": Decimal("75.5"),
                "ai_risk_factors": {"driving_history": "good"},
                "converted_to_policy_id": None,
                "converted_at": None,
                "created_by": None,
                "updated_by": None,
                "referral_source": "web",
                "version": 1,
                "parent_quote_id": None,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            },
        ]

        # Execute
        result = await service.calculate_quote(quote_id)

        # Assert
        assert isinstance(result, Ok)
        quote = result.value
        assert quote.status == QuoteStatus.QUOTED
        assert quote.total_premium == Decimal("1080.00")
        assert quote.monthly_premium == Decimal("108.00")

    async def test_update_quote_creates_version(self, mock_db, mock_cache):
        """Test that major updates create new quote version."""
        # Setup
        service = QuoteService(mock_db, mock_cache)
        quote_id = uuid4()

        # Create update that changes vehicle
        update_data = QuoteUpdate(
            vehicle_info=VehicleInfo(
                vin="2HGBH41JXMN109187",  # Different valid VIN
                year=2023,
                make="Honda",
                model="Accord",
                body_style="sedan",
                annual_mileage=15000,
                primary_use="pleasure",
                garage_zip="94105",
                owned=True,
            )
        )

        # Mock existing quote
        mock_cache.get.return_value = None
        existing_quote_data = {
            "id": quote_id,
            "quote_number": "QUOT-2025-000001",
            "customer_id": None,
            "status": "draft",
            "product_type": "auto",
            "state": "CA",
            "zip_code": "94105",
            "effective_date": date.today() + timedelta(days=7),
            "email": "john.doe@example.com",
            "phone": "415-555-0123",
            "preferred_contact": "email",
            "vehicle_info": {
                "vin": "1HGBH41JXMN109186",
                "year": 2022,
                "make": "Tesla",
                "model": "Model 3",
                "vehicle_type": "SEDAN",
                "annual_mileage": 12000,
                "primary_use": "commute",
                "garage_zip": "94105",
                "owned": True,
            },
            "drivers": [],
            "coverage_selections": [],
            "expires_at": datetime.now() + timedelta(days=30),
            "base_premium": None,
            "total_premium": None,
            "monthly_premium": None,
            "discounts_applied": [],
            "surcharges_applied": [],
            "total_discount_amount": None,
            "total_surcharge_amount": None,
            "rating_factors": None,
            "rating_tier": None,
            "ai_risk_score": None,
            "ai_risk_factors": None,
            "converted_to_policy_id": None,
            "converted_at": None,
            "created_by": None,
            "updated_by": None,
            "referral_source": "web",
            "version": 1,
            "parent_quote_id": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        mock_db.fetchrow.side_effect = [
            existing_quote_data,  # Get existing quote
            {**existing_quote_data, "id": uuid4(), "version": 2},  # New version created
        ]

        # Execute
        result = await service.update_quote(quote_id, update_data)

        # Assert
        assert isinstance(result, Ok)
        # Should have called create_quote for new version
        assert mock_db.fetchval.called  # For sequence number
