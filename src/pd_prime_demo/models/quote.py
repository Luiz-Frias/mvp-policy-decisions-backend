"""Quote domain models with full production features."""

import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any

from beartype import beartype
from pydantic import Field, computed_field, field_validator, model_validator
from pydantic.types import UUID4

if TYPE_CHECKING:
    from pydantic import ValidationInfo

from .base import BaseModelConfig, IdentifiableModel, TimestampedModel

# Additional Pydantic models to replace dict usage


@beartype
class CoverageOptions(BaseModelConfig):
    """Options for coverage-specific configurations."""

    gap_coverage: bool = Field(
        default=False, description="Whether gap coverage is included"
    )
    full_glass: bool = Field(
        default=False, description="Whether full glass coverage is included"
    )
    waiver_collision: bool = Field(
        default=False, description="Whether collision waiver is included"
    )
    extended_warranty: bool = Field(
        default=False, description="Whether extended warranty is included"
    )
    custom_equipment: Decimal | None = Field(
        None,
        ge=Decimal("0"),
        decimal_places=2,
        description="Custom equipment coverage amount",
    )
    rental_days: int | None = Field(
        None, ge=0, le=365, description="Number of rental days covered"
    )
    roadside_mileage: int | None = Field(
        None, ge=0, le=200, description="Roadside assistance mileage"
    )


@beartype
class Surcharge(BaseModelConfig):
    """Applied surcharge details with validation."""

    surcharge_type: str = Field(
        ..., min_length=1, max_length=100, description="Type of surcharge being applied"
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Human-readable description of the surcharge",
    )
    amount: Decimal = Field(
        ...,
        ge=Decimal("0"),
        decimal_places=2,
        description="Surcharge amount (positive for surcharges)",
    )
    percentage: Decimal | None = Field(
        None,
        ge=Decimal("0"),
        le=Decimal("100"),
        decimal_places=2,
        description="Surcharge percentage if percentage-based",
    )
    eligible: bool = Field(
        default=True, description="Whether surcharge is eligible for this customer"
    )
    validation_notes: str | None = Field(
        None, max_length=500, description="Notes about surcharge validation"
    )


@beartype
class RatingFactors(BaseModelConfig):
    """Detailed rating factors used in premium calculation."""

    base_rate: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("0"),
        decimal_places=4,
        description="Base rate factor",
    )
    territory_factor: Decimal = Field(
        default=Decimal("1"),
        ge=Decimal("0"),
        decimal_places=4,
        description="Territory/location factor",
    )
    vehicle_factor: Decimal = Field(
        default=Decimal("1"),
        ge=Decimal("0"),
        decimal_places=4,
        description="Vehicle-specific factor",
    )
    driver_factor: Decimal = Field(
        default=Decimal("1"),
        ge=Decimal("0"),
        decimal_places=4,
        description="Driver-specific factor",
    )
    coverage_factor: Decimal = Field(
        default=Decimal("1"),
        ge=Decimal("0"),
        decimal_places=4,
        description="Coverage selection factor",
    )
    credit_score_factor: Decimal | None = Field(
        None,
        ge=Decimal("0"),
        decimal_places=4,
        description="Credit score factor (if applicable)",
    )
    multi_policy_factor: Decimal | None = Field(
        None,
        ge=Decimal("0"),
        decimal_places=4,
        description="Multi-policy discount factor",
    )
    claim_free_factor: Decimal | None = Field(
        None,
        ge=Decimal("0"),
        decimal_places=4,
        description="Claim-free discount factor",
    )
    loyalty_factor: Decimal | None = Field(
        None, ge=Decimal("0"), decimal_places=4, description="Customer loyalty factor"
    )


@beartype
class AIRiskFactors(BaseModelConfig):
    """AI-identified risk factors and analysis."""

    risk_indicators: list[str] = Field(
        default_factory=list, description="List of AI-identified risk indicators"
    )
    protective_factors: list[str] = Field(
        default_factory=list, description="List of AI-identified protective factors"
    )
    risk_score: float | None = Field(
        None, ge=0.0, le=1.0, description="Overall AI risk score (0.0-1.0)"
    )
    confidence_score: float | None = Field(
        None, ge=0.0, le=1.0, description="AI confidence in risk assessment (0.0-1.0)"
    )
    model_version: str | None = Field(
        None, max_length=50, description="AI model version used for assessment"
    )
    last_updated: datetime | None = Field(
        None, description="When AI risk factors were last updated"
    )


@beartype
class PaymentDetails(BaseModelConfig):
    """Payment method specific details."""

    payment_type: str = Field(
        ...,
        pattern=r"^(credit_card|debit_card|bank_transfer|check|cash)$",
        description="Type of payment method",
    )
    card_last_four: str | None = Field(
        None, pattern=r"^\d{4}$", description="Last four digits of card (if applicable)"
    )
    card_brand: str | None = Field(
        None, max_length=20, description="Card brand (Visa, Mastercard, etc.)"
    )
    bank_name: str | None = Field(
        None, max_length=100, description="Bank name for transfers"
    )
    routing_number: str | None = Field(
        None, pattern=r"^\d{9}$", description="Bank routing number (if applicable)"
    )
    account_last_four: str | None = Field(
        None,
        pattern=r"^\d{4}$",
        description="Last four digits of account (if applicable)",
    )
    confirmation_number: str | None = Field(
        None, max_length=100, description="Payment confirmation number"
    )
    transaction_id: str | None = Field(
        None, max_length=100, description="Transaction identifier"
    )
    processing_fee: Decimal | None = Field(
        None, ge=Decimal("0"), decimal_places=2, description="Processing fee charged"
    )


@beartype
class OverrideData(BaseModelConfig):
    """Override specific data with original and new values."""

    field_name: str = Field(
        ..., min_length=1, max_length=100, description="Name of field being overridden"
    )
    original_value: Any = Field(..., description="Original value before override")
    new_value: Any = Field(..., description="New value after override")
    override_type: str = Field(
        ...,
        pattern=r"^(manual|system|exception|correction)$",
        description="Type of override",
    )
    requires_approval: bool = Field(
        default=False, description="Whether override requires approval"
    )
    approved_by: str | None = Field(
        None, max_length=100, description="Who approved the override"
    )
    approval_timestamp: datetime | None = Field(
        None, description="When override was approved"
    )

    @field_validator("new_value")
    @classmethod
    def validate_new_value_different(cls, v: Any, info: "ValidationInfo") -> Any:
        """Ensure new value is different from original."""
        if info.data.get("original_value") == v:
            raise ValueError("New value must be different from original value")
        return v


class QuoteStatus(str, Enum):
    """Quote lifecycle statuses with business rules."""

    DRAFT = "draft"
    CALCULATING = "calculating"
    QUOTED = "quoted"
    EXPIRED = "expired"
    BOUND = "bound"
    DECLINED = "declined"
    ARCHIVED = "archived"


class CoverageType(str, Enum):
    """Types of coverage available for auto insurance."""

    # Standard liability coverages
    BODILY_INJURY = "bodily_injury"
    PROPERTY_DAMAGE = "property_damage"

    # Physical damage coverages
    COLLISION = "collision"
    COMPREHENSIVE = "comprehensive"

    # Medical and PIP coverages
    MEDICAL = "medical"
    PERSONAL_INJURY_PROTECTION = "personal_injury_protection"

    # Uninsured/Underinsured motorist
    UNINSURED_MOTORIST = "uninsured_motorist"
    UNDERINSURED_MOTORIST = "underinsured_motorist"

    # Additional coverages
    RENTAL = "rental"
    ROADSIDE = "roadside"
    GAP = "gap"

    # Legacy support
    LIABILITY = "liability"  # Can map to bodily_injury for backward compatibility


class ProductType(str, Enum):
    """Insurance product types supported by the platform."""

    AUTO = "auto"
    HOME = "home"
    COMMERCIAL = "commercial"


class ContactMethod(str, Enum):
    """Contact method preferences."""

    EMAIL = "email"
    PHONE = "phone"
    TEXT = "text"


class VehicleType(str, Enum):
    """Vehicle body types for classification."""

    SEDAN = "sedan"
    COUPE = "coupe"
    SUV = "suv"
    TRUCK = "truck"
    VAN = "van"
    WAGON = "wagon"
    CONVERTIBLE = "convertible"
    HATCHBACK = "hatchback"


class DriverRelationship(str, Enum):
    """Driver relationship to policyholder."""

    SELF = "self"
    SPOUSE = "spouse"
    CHILD = "child"
    PARENT = "parent"
    OTHER = "other"


class DiscountType(str, Enum):
    """Available discount types with business justification."""

    MULTI_POLICY = "multi_policy"
    SAFE_DRIVER = "safe_driver"
    GOOD_STUDENT = "good_student"
    MILITARY = "military"
    SENIOR = "senior"
    LOYALTY = "loyalty"
    PAID_IN_FULL = "paid_in_full"
    PAPERLESS = "paperless"
    AUTO_PAY = "auto_pay"


@beartype
def char_to_num(ch: str) -> int:
    """Convert VIN characters to numeric values for checksum calculation per ISO 3779."""
    n = ord(ch)
    if n <= ord("9"):  # digits
        return n - ord("0")
    if n < ord("I"):  # A-H
        return n - ord("A") + 1
    if n <= ord("R"):  # J-R (I is excluded)
        return n - ord("J") + 1
    return n - ord("S") + 2  # S-Z


@beartype
def calculate_vin_checksum(vin: str) -> str:
    """Calculate the checksum for a VIN according to ISO 3779."""
    weights = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]
    total = 0
    for i, c in enumerate(vin):
        total += char_to_num(c) * weights[i]
    checksum_value = total % 11
    return "X" if checksum_value == 10 else str(checksum_value)


@beartype
def is_valid_vin_checksum(vin: str) -> bool:
    """Validate VIN checksum according to ISO 3779."""
    if len(vin) != 17:
        return False
    return calculate_vin_checksum(vin) == vin[8]


@beartype
class VehicleInfo(BaseModelConfig):
    """Vehicle information for auto quotes with comprehensive validation."""

    vin: str = Field(
        ...,
        min_length=17,
        max_length=17,
        pattern=r"^[A-HJ-NPR-Z0-9]{17}$",
        description="Vehicle Identification Number (17 characters, no I/O/Q)",
    )
    year: int = Field(
        ...,
        ge=1900,
        le=datetime.now().year + 1,
        description="Vehicle model year must be between 1900 and next year",
    )
    make: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Vehicle manufacturer (e.g., Toyota, Ford)",
    )
    model: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Vehicle model (e.g., Camry, F-150)",
    )
    trim: str | None = Field(
        None, max_length=50, description="Vehicle trim level (e.g., LX, EX-L)"
    )
    body_style: str | None = Field(
        None,
        max_length=30,
        pattern=r"^(sedan|coupe|suv|truck|van|wagon|convertible|hatchback)$",
        description="Vehicle body style",
    )
    engine: str | None = Field(
        None, max_length=50, description="Engine description (e.g., 2.5L 4-cylinder)"
    )

    # Usage info
    primary_use: str = Field(
        ...,
        pattern=r"^(commute|pleasure|business)$",
        description="Primary use: commute, pleasure, or business per insurance classification",
    )
    annual_mileage: int = Field(
        ...,
        ge=0,
        le=200000,
        description="Annual mileage must be between 0 and 200,000 miles",
    )
    garage_zip: str = Field(
        ...,
        pattern=r"^\d{5}(-\d{4})?$",
        description="ZIP code where vehicle is garaged (5 or 9 digits)",
    )
    garage_type: str = Field(
        default="garage",
        pattern=r"^(garage|carport|street|driveway)$",
        description="Where vehicle is typically parked per risk assessment",
    )

    # Safety features for discounts
    safety_features: list[str] = Field(
        default_factory=list,
        description="Safety features that may qualify for discounts",
    )
    anti_theft: bool = Field(
        default=False, description="Vehicle has anti-theft device per discount rules"
    )

    # Ownership
    owned: bool = Field(
        default=True,
        description="True if owned, False if leased per business rule VEH-001",
    )
    lease_company: str | None = Field(
        None, max_length=100, description="Leasing company name if vehicle is leased"
    )

    @field_validator("vin")
    @classmethod
    def validate_vin(cls, v: str) -> str:
        """Validate VIN format and checksum per ISO 3779."""
        # Normalize to uppercase
        vin = v.upper()

        # Check for invalid characters
        if re.search(r"[IOQ]", vin):
            raise ValueError("VIN cannot contain letters I, O, or Q")

        # Validate checksum
        if not is_valid_vin_checksum(vin):
            raise ValueError(f"Invalid VIN checksum for: {vin}")

        return vin

    @field_validator("year")
    @classmethod
    def validate_year(cls, v: int) -> int:
        """Ensure vehicle year is within insurable range."""
        current_year = datetime.now().year
        if v > current_year + 1:
            raise ValueError(f"Vehicle year cannot be more than {current_year + 1}")
        if v < 1900:
            raise ValueError("Vehicle year must be 1900 or later")
        # Business rule: vehicles older than 25 years may need special coverage
        if current_year - v > 25:
            # Note: This is informational only, not a hard validation failure
            pass
        return v

    @field_validator("safety_features")
    @classmethod
    def validate_safety_features(cls, v: list[str]) -> list[str]:
        """Ensure safety features are valid and unique."""
        # Remove duplicates while preserving order
        seen = set()
        unique_features = []
        for feature in v:
            feature_normalized = feature.strip().lower()
            if feature_normalized and feature_normalized not in seen:
                seen.add(feature_normalized)
                unique_features.append(feature.strip())
        return unique_features

    @model_validator(mode="after")
    def validate_lease_consistency(self) -> "VehicleInfo":
        """Ensure lease information is consistent."""
        if not self.owned and not self.lease_company:
            raise ValueError("Lease company must be specified for leased vehicles")
        if self.owned and self.lease_company:
            raise ValueError("Lease company should not be specified for owned vehicles")
        return self


# Valid US state codes for validation
VALID_US_STATE_CODES = {
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
    "DC",  # Washington D.C.
}


@beartype
class DriverInfo(BaseModelConfig):
    """Driver information for quotes with comprehensive validation."""

    # Personal info
    first_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z\s\-'\.]+$",
        description="First name with letters, spaces, hyphens, apostrophes only",
    )
    last_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z\s\-'\.]+$",
        description="Last name with letters, spaces, hyphens, apostrophes only",
    )
    middle_initial: str | None = Field(
        None,
        max_length=1,
        pattern=r"^[A-Z]$",
        description="Single uppercase letter for middle initial",
    )
    suffix: str | None = Field(
        None,
        max_length=10,
        pattern=r"^(Jr|Sr|III|IV|V|Jr\.|Sr\.)$",
        description="Name suffix (Jr, Sr, III, etc.)",
    )

    # Demographics
    date_of_birth: date = Field(
        ..., description="Driver's date of birth for age validation"
    )
    gender: str = Field(
        ...,
        pattern=r"^(M|F|X)$",
        description="Gender: M (Male), F (Female), X (Non-binary)",
    )
    marital_status: str = Field(
        ...,
        pattern=r"^(single|married|divorced|widowed)$",
        description="Marital status affects risk rating per actuarial tables",
    )

    # License info
    license_number: str = Field(
        ...,
        min_length=5,
        max_length=20,
        pattern=r"^[A-Z0-9\-]+$",
        description="Driver's license number (alphanumeric with hyphens)",
    )
    license_state: str = Field(
        ...,
        pattern=r"^[A-Z]{2}$",
        description="Two-letter US state code where license was issued",
    )
    license_status: str = Field(
        default="valid",
        pattern=r"^(valid|suspended|expired|restricted)$",
        description="Current license status per DMV records",
    )
    first_licensed_date: date = Field(
        ..., description="Date when driver was first licensed"
    )

    # Driving history
    accidents_3_years: int = Field(
        default=0,
        ge=0,
        le=10,
        description="Number of at-fault accidents in past 3 years (max 10)",
    )
    violations_3_years: int = Field(
        default=0,
        ge=0,
        le=10,
        description="Number of moving violations in past 3 years (max 10)",
    )
    dui_convictions: int = Field(
        default=0,
        ge=0,
        le=5,
        description="Number of DUI convictions (max 5 for insurability)",
    )
    claims_3_years: int = Field(
        default=0,
        ge=0,
        le=10,
        description="Number of insurance claims in past 3 years (max 10)",
    )

    # Education/occupation for discounts
    education_level: str | None = Field(
        None,
        pattern=r"^(high_school|some_college|bachelors|masters|doctorate)$",
        description="Education level for potential discounts",
    )
    occupation: str | None = Field(
        None,
        max_length=100,
        description="Occupation may affect risk rating and discounts",
    )
    good_student: bool = Field(
        default=False,
        description="Qualifies for good student discount (GPA 3.0+ or Dean's List)",
    )

    # Relationship to policyholder
    relationship: str = Field(
        default="self",
        pattern=r"^(self|spouse|child|parent|other)$",
        description="Relationship to primary policyholder",
    )

    @field_validator("date_of_birth")
    @classmethod
    def validate_driver_age(cls, v: date) -> date:
        """Validate driver meets minimum age requirements per state laws."""
        today = datetime.now().date()
        age_years = (today - v).days / 365.25

        if age_years < 16:
            raise ValueError(
                "Driver must be at least 16 years old per minimum driving age"
            )
        if age_years > 100:
            raise ValueError("Driver age exceeds maximum insurable age of 100")

        # Business rule: drivers 16-18 may have restrictions
        if age_years < 18:
            # Note: State-specific rules would apply here
            pass

        return v

    @field_validator("license_state")
    @classmethod
    def validate_license_state(cls, v: str) -> str:
        """Validate state code against known US states."""
        if v not in VALID_US_STATE_CODES:
            raise ValueError(f"Invalid US state code: {v}")
        return v

    @field_validator("first_licensed_date")
    @classmethod
    def validate_first_licensed_date(cls, v: date) -> date:
        """Ensure first licensed date is reasonable."""
        today = datetime.now().date()

        if v > today:
            raise ValueError("First licensed date cannot be in the future")

        # Can't be licensed more than 84 years ago (16 + 100 max age)
        max_years_ago = today - timedelta(days=84 * 365)
        if v < max_years_ago:
            raise ValueError("First licensed date is too far in the past")

        return v

    @field_validator("good_student")
    @classmethod
    def validate_good_student(cls, v: bool) -> bool:
        """Validate good student eligibility."""
        if v:
            # Business rule: good student discount typically for ages 16-25
            # This would be validated against date_of_birth in a model validator
            pass
        return v

    @computed_field  # type: ignore[prop-decorator]
    @property
    def years_licensed(self) -> int:
        """Calculate years of driving experience."""
        if hasattr(self, "first_licensed_date"):
            years = (datetime.now().date() - self.first_licensed_date).days / 365.25
            return max(0, int(years))
        return 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def age(self) -> int:
        """Calculate current age in years."""
        if hasattr(self, "date_of_birth"):
            years = (datetime.now().date() - self.date_of_birth).days / 365.25
            return max(0, int(years))
        return 0

    @model_validator(mode="after")
    def validate_driver_consistency(self) -> "DriverInfo":
        """Ensure driver information is internally consistent."""
        # First licensed date must be after birth date + 16 years
        min_license_date = self.date_of_birth + timedelta(days=16 * 365)
        if self.first_licensed_date < min_license_date:
            raise ValueError("Driver cannot be licensed before age 16")

        # Good student discount age validation
        if self.good_student and self.age > 25:
            raise ValueError(
                "Good student discount only available for drivers 25 and under"
            )

        # DUI affects license status
        if self.dui_convictions > 0 and self.license_status == "valid":
            # Note: This might require additional validation based on state laws
            pass

        return self


@beartype
class CoverageSelection(BaseModelConfig):
    """Individual coverage selection with limits and validation."""

    coverage_type: CoverageType = Field(
        ..., description="Type of coverage being selected"
    )
    limit: Decimal = Field(
        ...,
        ge=Decimal("0"),
        decimal_places=2,
        description="Coverage limit amount in dollars",
    )
    deductible: Decimal | None = Field(
        None,
        ge=Decimal("0"),
        decimal_places=2,
        description="Deductible amount for this coverage (if applicable)",
    )

    # Calculated premium for this coverage
    premium: Decimal | None = Field(
        None,
        ge=Decimal("0"),
        decimal_places=2,
        description="Calculated premium for this specific coverage",
    )

    # Additional options
    options: "CoverageOptions" = Field(
        default_factory=lambda: CoverageOptions(),
        description="Additional coverage-specific options",
    )

    @field_validator("limit")
    @classmethod
    def validate_coverage_limit(cls, v: Decimal) -> Decimal:
        """Validate coverage limits based on coverage type."""
        # Note: Can't access coverage_type here with beartype
        # Moving validation to model_validator
        return v

    @model_validator(mode="after")
    def validate_deductible_requirement(self) -> "CoverageSelection":
        """Ensure deductible is provided where required and validate limits."""
        # Validate coverage limits based on coverage type
        min_limits = {
            CoverageType.LIABILITY: Decimal("15000"),  # State minimum
            CoverageType.COLLISION: Decimal("0"),  # Can be zero (declined)
            CoverageType.COMPREHENSIVE: Decimal("0"),  # Can be zero (declined)
            CoverageType.MEDICAL: Decimal("1000"),  # Minimum if selected
            CoverageType.UNINSURED_MOTORIST: Decimal("15000"),
            CoverageType.RENTAL: Decimal("0"),
            CoverageType.ROADSIDE: Decimal("0"),
        }

        if self.limit > 0:  # If coverage is selected (not zero)
            min_limit = min_limits.get(self.coverage_type, Decimal("0"))
            if self.limit < min_limit:
                raise ValueError(
                    f"Minimum limit for {self.coverage_type} is ${min_limit}"
                )

        # Collision and Comprehensive require deductibles
        if self.coverage_type in [CoverageType.COLLISION, CoverageType.COMPREHENSIVE]:
            if self.limit > 0 and self.deductible is None:
                raise ValueError(f"{self.coverage_type} coverage requires a deductible")
        return self


@beartype
class Discount(BaseModelConfig):
    """Applied discount details with validation."""

    discount_type: DiscountType = Field(
        ..., description="Type of discount being applied"
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Human-readable description of the discount",
    )
    amount: Decimal = Field(
        ..., decimal_places=2, description="Discount amount (negative for discounts)"
    )
    percentage: Decimal | None = Field(
        None,
        ge=Decimal("0"),
        le=Decimal("100"),
        decimal_places=2,
        description="Discount percentage if percentage-based",
    )

    # Validation
    eligible: bool = Field(
        default=True, description="Whether customer is eligible for this discount"
    )
    validation_notes: str | None = Field(
        None, max_length=500, description="Notes about eligibility validation"
    )

    @field_validator("amount")
    @classmethod
    def validate_discount_amount(cls, v: Decimal) -> Decimal:
        """Ensure discount amounts are negative values."""
        if v > 0:
            raise ValueError("Discount amounts must be negative (reducing premium)")
        return v


@beartype
class QuoteBase(BaseModelConfig):
    """Base quote information shared across quote operations."""

    # Customer info
    customer_id: UUID4 = Field(
        ..., description="UUID of the customer requesting the quote"
    )

    # Quote basics
    product_type: str = Field(
        ...,
        pattern=r"^(auto|home|commercial)$",
        description="Type of insurance product being quoted",
    )
    state: str = Field(
        ..., pattern=r"^[A-Z]{2}$", description="Two-letter US state code for the quote"
    )
    zip_code: str = Field(
        ...,
        pattern=r"^\d{5}(-\d{4})?$",
        description="ZIP code for rating (5 or 9 digits)",
    )

    # Dates
    effective_date: date = Field(..., description="Requested policy effective date")
    requested_date: datetime = Field(
        default_factory=datetime.now, description="When the quote was requested"
    )

    # Product-specific data
    vehicle_info: VehicleInfo | None = Field(
        None, description="Vehicle information for auto quotes"
    )
    drivers: list[DriverInfo] = Field(
        default_factory=list, description="List of drivers (1-10) to be covered"
    )

    # Coverage selections
    coverage_selections: list[CoverageSelection] = Field(
        default_factory=list,
        description="Selected coverages with limits and deductibles",
    )

    # Contact preferences
    email: str = Field(
        ...,
        pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$",
        max_length=254,
        description="Contact email address",
    )
    phone: str | None = Field(
        None, pattern=r"^\+?1?\d{10,14}$", description="Contact phone number"
    )
    preferred_contact: str = Field(
        default="email",
        pattern=r"^(email|phone|text)$",
        description="Preferred contact method",
    )

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        """Validate state code."""
        if v not in VALID_US_STATE_CODES:
            raise ValueError(f"Invalid US state code: {v}")
        return v

    @field_validator("effective_date")
    @classmethod
    def validate_effective_date(cls, v: date) -> date:
        """Ensure effective date follows business rules."""
        today = datetime.now().date()

        # Business rule: Cannot be more than 30 days in the past
        if v < today:
            days_past = (today - v).days
            if days_past > 30:
                raise ValueError(
                    "Effective date cannot be more than 30 days in the past"
                )

        # Business rule: Cannot be more than 60 days in the future
        if v > today:
            days_future = (v - today).days
            if days_future > 60:
                raise ValueError(
                    "Effective date cannot be more than 60 days in the future"
                )

        return v

    @field_validator("drivers")
    @classmethod
    def validate_drivers(cls, v: list[DriverInfo]) -> list[DriverInfo]:
        """Ensure driver list follows business rules."""
        if not v:
            raise ValueError("At least one driver is required")

        # Ensure exactly one primary driver
        primary_drivers = [d for d in v if d.relationship == "self"]
        if len(primary_drivers) != 1:
            raise ValueError(
                "Exactly one primary driver (relationship='self') is required"
            )

        # Check for duplicate drivers (by license number)
        license_numbers = [d.license_number for d in v]
        if len(license_numbers) != len(set(license_numbers)):
            raise ValueError("Duplicate drivers detected (same license number)")

        return v

    @model_validator(mode="after")
    def validate_product_consistency(self) -> "QuoteBase":
        """Ensure product-specific data is consistent."""
        if self.product_type == "auto":
            if not self.vehicle_info:
                raise ValueError("Vehicle information is required for auto quotes")
            if not self.drivers:
                raise ValueError("At least one driver is required for auto quotes")

        # Ensure phone is provided if preferred contact is phone/text
        if self.preferred_contact in ["phone", "text"] and not self.phone:
            raise ValueError(
                f"Phone number required for {self.preferred_contact} contact preference"
            )

        return self


@beartype
class Quote(QuoteBase, IdentifiableModel, TimestampedModel):
    """Full quote model with calculations and metadata."""

    # Unique identifiers
    quote_number: str = Field(
        ...,
        pattern=r"^QUOT-\d{4}-\d{6}$",
        description="Unique quote number in format QUOT-YYYY-NNNNNN",
    )
    version: int = Field(
        default=1, ge=1, description="Quote version number (incremented on updates)"
    )
    parent_quote_id: UUID4 | None = Field(
        None, description="Reference to parent quote for versioning"
    )

    # Status
    status: QuoteStatus = Field(
        default=QuoteStatus.DRAFT,
        description="Current quote status per business workflow",
    )

    # Pricing (all nullable until calculated)
    base_premium: Decimal | None = Field(
        None,
        ge=Decimal("0"),
        decimal_places=2,
        description="Base premium before discounts/surcharges",
    )
    total_premium: Decimal | None = Field(
        None,
        ge=Decimal("0"),
        decimal_places=2,
        description="Total premium after all adjustments",
    )
    monthly_premium: Decimal | None = Field(
        None, ge=Decimal("0"), decimal_places=2, description="Monthly payment amount"
    )
    down_payment: Decimal | None = Field(
        None,
        ge=Decimal("0"),
        decimal_places=2,
        description="Required down payment amount",
    )

    # Applied discounts and surcharges
    discounts_applied: list[Discount] = Field(
        default_factory=list, description="List of applied discounts"
    )
    surcharges_applied: list["Surcharge"] = Field(
        default_factory=list, description="List of applied surcharges"
    )
    total_discount_amount: Decimal | None = Field(
        None,
        decimal_places=2,
        description="Sum of all discount amounts (negative value)",
    )
    total_surcharge_amount: Decimal | None = Field(
        None,
        ge=Decimal("0"),
        decimal_places=2,
        description="Sum of all surcharge amounts (positive value)",
    )

    # Rating details
    rating_factors: "RatingFactors" = Field(
        default_factory=lambda: RatingFactors(),
        description="Detailed rating factors used in calculation",
    )
    rating_tier: str | None = Field(
        None,
        max_length=20,
        pattern=r"^[A-Z0-9\-]+$",
        description="Assigned rating tier (e.g., PREFERRED, STANDARD)",
    )

    # AI enhancements
    ai_risk_score: float | None = Field(
        None, ge=0.0, le=1.0, description="AI-calculated risk score (0.0-1.0)"
    )
    ai_risk_factors: "AIRiskFactors" = Field(
        default_factory=lambda: AIRiskFactors(),
        description="AI-identified risk factors",
    )
    ai_recommendations: list[str] = Field(
        default_factory=list, description="AI-generated recommendations"
    )
    conversion_probability: float | None = Field(
        None, ge=0.0, le=1.0, description="AI-predicted probability of quote conversion"
    )

    # Expiration and conversion
    expires_at: datetime = Field(
        ..., description="When the quote expires (set by business rules)"
    )
    reminder_sent_at: datetime | None = Field(
        None, description="When expiration reminder was sent"
    )
    followup_count: int = Field(
        default=0, ge=0, le=10, description="Number of follow-up contacts made"
    )

    # If converted to policy
    converted_to_policy_id: UUID4 | None = Field(
        None, description="Policy ID if quote was converted"
    )
    converted_at: datetime | None = Field(
        None, description="When quote was converted to policy"
    )

    # Decline info
    declined_reasons: list[str] = Field(
        default_factory=list, description="Reasons for quote decline"
    )
    declined_at: datetime | None = Field(None, description="When quote was declined")

    # User tracking
    created_by: UUID4 | None = Field(None, description="User who created the quote")
    updated_by: UUID4 | None = Field(
        None, description="User who last updated the quote"
    )
    assigned_agent_id: UUID4 | None = Field(
        None, description="Assigned agent for follow-up"
    )

    # Analytics
    quote_source: str | None = Field(
        None,
        max_length=50,
        pattern=r"^(web|mobile|agent|partner|phone)$",
        description="Source channel for the quote",
    )
    referral_code: str | None = Field(
        None,
        max_length=20,
        pattern=r"^[A-Z0-9\-]+$",
        description="Referral or promo code used",
    )
    utm_source: str | None = Field(
        None, max_length=100, description="UTM source parameter"
    )
    utm_medium: str | None = Field(
        None, max_length=100, description="UTM medium parameter"
    )
    utm_campaign: str | None = Field(
        None, max_length=100, description="UTM campaign parameter"
    )

    @field_validator("quote_number")
    @classmethod
    def validate_quote_number(cls, v: str) -> str:
        """Ensure quote number follows business format."""
        parts = v.split("-")
        if len(parts) != 3:
            raise ValueError("Quote number must have format QUOT-YYYY-NNNNNN")

        year = int(parts[1])
        current_year = datetime.now().year
        if year < 2020 or year > current_year:
            raise ValueError(f"Quote year must be between 2020 and {current_year}")

        return v

    @field_validator("expires_at")
    @classmethod
    def validate_expiration(cls, v: datetime) -> datetime:
        """Ensure expiration follows business rules."""
        # Note: Can't access requested_date here with beartype
        # Basic validation only
        now = datetime.now()

        # Business rule: quotes expire between 1-60 days from now
        now + timedelta(days=1)
        max_expiration = now + timedelta(days=60)

        if v < now:
            raise ValueError("Expiration date cannot be in the past")
        if v > max_expiration:
            raise ValueError("Quote cannot be valid for more than 60 days from now")

        return v

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_expired(self) -> bool:
        """Check if quote has expired."""
        return datetime.now() > self.expires_at

    @computed_field  # type: ignore[prop-decorator]
    @property
    def days_until_expiration(self) -> int:
        """Calculate days until quote expires."""
        if self.is_expired:
            return 0
        delta = self.expires_at - datetime.now()
        return max(0, delta.days)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_savings(self) -> Decimal:
        """Calculate total savings from discounts."""
        if self.total_discount_amount:
            return abs(self.total_discount_amount)
        return Decimal("0")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_convertible(self) -> bool:
        """Check if quote can be converted to policy."""
        return (
            self.status == QuoteStatus.QUOTED
            and not self.is_expired
            and self.total_premium is not None
            and self.total_premium > 0
            and not self.converted_to_policy_id
        )

    @model_validator(mode="after")
    def validate_status_consistency(self) -> "Quote":
        """Ensure status is consistent with other fields."""
        # If converted, status should be BOUND
        if self.converted_to_policy_id and self.status != QuoteStatus.BOUND:
            raise ValueError("Converted quotes must have BOUND status")

        # If declined, must have decline reasons
        if self.status == QuoteStatus.DECLINED and not self.declined_reasons:
            raise ValueError("Declined quotes must have decline reasons")

        # If quoted, must have pricing
        if self.status == QuoteStatus.QUOTED:
            if not self.total_premium:
                raise ValueError("Quoted status requires calculated premium")

        return self

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "quote_number": "QUOT-2024-000001",
                "customer_id": "123e4567-e89b-12d3-a456-426614174000",
                "product_type": "auto",
                "state": "CA",
                "zip_code": "90210",
                "status": "quoted",
                "total_premium": "1200.00",
                "monthly_premium": "100.00",
                "expires_at": "2024-02-15T00:00:00Z",
            }
        }


@beartype
class QuoteCreate(QuoteBase):
    """Model for creating a new quote with multi-step wizard support."""

    # Override to make expiration optional on create (will be calculated)
    expires_at: datetime | None = Field(
        None, description="Optional expiration override (defaults to 30 days)"
    )

    # Override drivers validation to allow empty list for wizard workflow
    drivers: list[DriverInfo] = Field(
        default_factory=list,
        description="List of drivers (can be empty initially for wizard workflow)",
    )

    @field_validator("drivers")
    @classmethod
    def validate_drivers(cls, v: list[DriverInfo]) -> list[DriverInfo]:
        """Override parent validation - allow empty driver list for wizard workflow."""
        # For QuoteCreate, we allow empty drivers list initially
        # The validation will happen when converting to full Quote
        return v

    @model_validator(mode="after")
    def validate_product_consistency(self) -> "QuoteCreate":
        """Override parent validation to support wizard workflow."""
        # For QuoteCreate, we allow creation without complete data
        # This enables the multi-step wizard workflow

        # Still require phone if preferred contact is phone/text
        if self.preferred_contact in ["phone", "text"] and not self.phone:
            raise ValueError(
                f"Phone number required for {self.preferred_contact} contact preference"
            )

        return self


@beartype
class QuoteUpdate(BaseModelConfig):
    """Model for updating a quote with partial data."""

    # Allow updating coverage selections
    coverage_selections: list[CoverageSelection] | None = Field(
        None, description="Updated coverage selections"
    )

    # Allow adding/removing drivers
    drivers: list[DriverInfo] | None = Field(None, description="Updated driver list")

    # Update vehicle info
    vehicle_info: VehicleInfo | None = Field(
        None, description="Updated vehicle information"
    )

    # Update contact info
    email: str | None = Field(
        None,
        pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$",
        max_length=254,
        description="Updated email address",
    )
    phone: str | None = Field(
        None, pattern=r"^\+?1?\d{10,14}$", description="Updated phone number"
    )
    preferred_contact: str | None = Field(
        None, pattern=r"^(email|phone|text)$", description="Updated contact preference"
    )

    # Policy timing
    effective_date: date | None = Field(
        None, description="Updated effective date for policy"
    )

    # Agent assignment
    assigned_agent_id: UUID4 | None = Field(
        None, description="Assign or reassign agent"
    )


@beartype
class QuoteComparison(BaseModelConfig):
    """Model for comparing multiple quote versions."""

    quotes: list[Quote] = Field(..., description="Quotes to compare (2-10)")
    differences: dict[str, dict[str, Any]] = Field(
        default_factory=dict, description="Identified differences between quotes"
    )
    recommendation: str | None = Field(
        None, max_length=1000, description="AI-generated recommendation"
    )

    @field_validator("quotes")
    @classmethod
    def validate_quotes_for_comparison(cls, v: list[Quote]) -> list[Quote]:
        """Ensure quotes are comparable."""
        if len(v) < 2:
            raise ValueError("At least 2 quotes required for comparison")

        # All quotes should be for the same customer
        customer_ids = {q.customer_id for q in v}
        if len(customer_ids) > 1:
            raise ValueError("All quotes must be for the same customer")

        # All quotes should be for the same product type
        product_types = {q.product_type for q in v}
        if len(product_types) > 1:
            raise ValueError("All quotes must be for the same product type")

        return v


@beartype
class QuoteConversionRequest(BaseModelConfig):
    """Request model for converting quote to policy."""

    effective_date: date | None = Field(
        None,
        description="Override effective date for policy (defaults to quote effective date)",
    )
    payment_method: str = Field(
        ...,
        pattern=r"^(card|bank|check)$",
        description="Payment method: card, bank, or check",
    )
    payment_details: "PaymentDetails" = Field(
        default_factory=lambda: PaymentDetails(payment_type="credit_card"),
        description="Payment method specific details",
    )
    agent_id: UUID4 | None = Field(
        None, description="Agent facilitating the conversion"
    )
    referral_source: str | None = Field(
        None, max_length=50, description="Source of the conversion"
    )
    notes: str | None = Field(
        None, max_length=1000, description="Additional notes about the conversion"
    )

    @field_validator("effective_date")
    @classmethod
    def validate_conversion_effective_date(cls, v: date | None) -> date | None:
        """Validate conversion effective date."""
        if v is None:
            return v

        today = datetime.now().date()

        # Cannot be more than 30 days in the past
        if v < today - timedelta(days=30):
            raise ValueError("Effective date cannot be more than 30 days in the past")

        # Cannot be more than 60 days in the future
        if v > today + timedelta(days=60):
            raise ValueError("Effective date cannot be more than 60 days in the future")

        return v


@beartype
class QuoteOverrideRequest(BaseModelConfig):
    """Request model for admin quote overrides."""

    override_type: str = Field(
        ...,
        pattern=r"^(premium|coverage|discount|surcharge|status)$",
        description="Type of override being applied",
    )
    override_data: "OverrideData" = Field(
        ..., description="Override specific data (original and new values)"
    )
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Detailed reason for the override (minimum 10 characters)",
    )
    admin_notes: str | None = Field(
        None, max_length=1000, description="Additional admin notes"
    )
    notify_customer: bool = Field(
        default=False, description="Whether to notify customer of the override"
    )
    effective_immediately: bool = Field(
        default=True, description="Whether override takes effect immediately"
    )

    @field_validator("override_data")
    @classmethod
    def validate_override_data(cls, v: OverrideData) -> OverrideData:
        """Validate override data contains required fields."""
        # The OverrideData model already has its own validation
        # for ensuring new_value != original_value
        return v


# End of quote models
