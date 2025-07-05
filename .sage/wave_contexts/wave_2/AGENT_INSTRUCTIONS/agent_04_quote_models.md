# Agent 04: Quote Model Builder

## YOUR MISSION

Create comprehensive quote models following existing patterns with full production features including multi-step wizard support, versioning, and real-time updates.

## NO SILENT FALLBACKS PRINCIPLE

### Pydantic Model Configuration Requirements

**NEVER use default field values without explicit business rules:**

```python
# ❌ FORBIDDEN: Default values without business justification
class Quote(BaseModel):
    status: str = "draft"           # No business rule documented
    premium: Optional[Decimal] = None  # Allows undefined state
    expires_at: datetime = datetime.now() + timedelta(days=30)  # Magic number

# ✅ REQUIRED: Explicit business rules for all defaults
class Quote(BaseModel):
    model_config = ConfigDict(
        frozen=True,  # MANDATORY: Immutable by default
        extra="forbid",  # MANDATORY: Strict validation
        validate_assignment=True
    )

    status: QuoteStatus = Field(
        default=QuoteStatus.DRAFT,
        description="Quote starts in DRAFT status per business rule QUO-001"
    )
    premium: Optional[Decimal] = Field(
        default=None,
        description="Premium remains None until rating calculation completes"
    )
    expires_at: datetime = Field(
        ...,  # REQUIRED: No default, must be explicitly calculated
        description="Expiration calculated based on state regulations"
    )
```

**NEVER allow silent data type conversions:**

```python
# ❌ FORBIDDEN: Implicit type conversion
class VehicleInfo(BaseModel):
    year: int               # Allows string->int conversion
    vin: str               # No format validation
    annual_mileage: float  # Precision loss possible

# ✅ REQUIRED: Explicit validation for all business constraints
class VehicleInfo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    year: int = Field(
        ...,
        ge=1900,
        le=datetime.now().year + 1,
        description="Vehicle year must be valid calendar year"
    )
    vin: str = Field(
        ...,
        min_length=17,
        max_length=17,
        pattern=r'^[A-HJ-NPR-Z0-9]{17}$',
        description="VIN must be exactly 17 characters, valid format"
    )
    annual_mileage: int = Field(
        ...,
        ge=0,
        le=200000,
        description="Annual mileage must be reasonable for insurance"
    )

    @field_validator('vin')
    @classmethod
    def validate_vin_checksum(cls, v: str) -> str:
        """Validate VIN checksum according to ISO 3779."""
        if not is_valid_vin_checksum(v):
            raise ValueError(f"Invalid VIN checksum: {v}")
        return v
```

**NEVER skip validation for business constraints:**

```python
# ❌ FORBIDDEN: Missing business rule validation
class DriverInfo(BaseModel):
    date_of_birth: date  # No age validation
    license_state: str   # No state code validation
    violations: int      # No reasonable limits

# ✅ REQUIRED: Complete business rule validation
class DriverInfo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    date_of_birth: date = Field(...)
    license_state: str = Field(
        ...,
        pattern=r'^[A-Z]{2}$',
        description="Must be valid US state code"
    )
    violations_3_years: int = Field(
        default=0,
        ge=0,
        le=10,
        description="Violations count limited to reasonable maximum"
    )

    @field_validator('date_of_birth')
    @classmethod
    def validate_driver_age(cls, v: date) -> date:
        """Validate driver meets minimum age requirements."""
        age_years = (datetime.now().date() - v).days / 365.25
        if age_years < 16:
            raise ValueError("Driver must be at least 16 years old")
        if age_years > 100:
            raise ValueError("Driver age must be reasonable")
        return v

    @field_validator('license_state')
    @classmethod
    def validate_license_state(cls, v: str) -> str:
        """Validate state code against known states."""
        if v not in VALID_US_STATE_CODES:
            raise ValueError(f"Invalid state code: {v}")
        return v
```

### Fail Fast Validation

If ANY model field lacks explicit validation, you MUST:

1. **Document the business rule** that governs the field
2. **Add appropriate Pydantic validators** for the rule
3. **Never allow invalid states** to be created
4. **Provide clear error messages** for validation failures

### Explicit Error Remediation

**When model validation fails:**

- Never catch validation errors and return defaults
- Always propagate ValidationError with field-specific details
- Provide business-rule context in error messages
- Document exact values that would be acceptable

**Required validation for each model:**

- All monetary fields use Decimal with appropriate precision
- All date fields validate business-appropriate ranges
- All enum fields restrict to valid business values
- All string fields enforce format and length constraints
- All numeric fields enforce reasonable business limits

## MANDATORY PRE-WORK

1. Read ALL documents listed in AGENT_TEMPLATE.md FIRST
2. Specifically study:
   - Existing models in `src/pd_prime_demo/models/`
   - BaseModel patterns, especially frozen=True usage
   - How PolicyModel is structured for reference

## SPECIFIC TASKS

### 1. Create Quote Models (`src/pd_prime_demo/models/quote.py`)

```python
"""Quote domain models with full production features."""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import Field, field_validator, computed_field

from .base import BaseModelConfig, TimestampedModel, IdentifiableModel


class QuoteStatus(str, Enum):
    """Quote lifecycle statuses."""
    DRAFT = "draft"
    CALCULATING = "calculating"
    QUOTED = "quoted"
    EXPIRED = "expired"
    BOUND = "bound"
    DECLINED = "declined"
    ARCHIVED = "archived"


class CoverageType(str, Enum):
    """Types of coverage available."""
    LIABILITY = "liability"
    COLLISION = "collision"
    COMPREHENSIVE = "comprehensive"
    MEDICAL = "medical"
    UNINSURED_MOTORIST = "uninsured_motorist"
    RENTAL = "rental"
    ROADSIDE = "roadside"


class DiscountType(str, Enum):
    """Available discount types."""
    MULTI_POLICY = "multi_policy"
    SAFE_DRIVER = "safe_driver"
    GOOD_STUDENT = "good_student"
    MILITARY = "military"
    SENIOR = "senior"
    LOYALTY = "loyalty"
    PAID_IN_FULL = "paid_in_full"
    PAPERLESS = "paperless"
    AUTO_PAY = "auto_pay"


class VehicleInfo(BaseModelConfig):
    """Vehicle information for auto quotes."""

    vin: str = Field(..., min_length=17, max_length=17, pattern=r'^[A-HJ-NPR-Z0-9]{17}$')
    year: int = Field(..., ge=1900, le=datetime.now().year + 1)
    make: str = Field(..., min_length=1, max_length=50)
    model: str = Field(..., min_length=1, max_length=50)
    trim: Optional[str] = Field(None, max_length=50)
    body_style: Optional[str] = Field(None, max_length=30)
    engine: Optional[str] = Field(None, max_length=50)

    # Usage info
    primary_use: str = Field(..., pattern=r'^(commute|pleasure|business)$')
    annual_mileage: int = Field(..., ge=0, le=200000)
    garage_zip: str = Field(..., pattern=r'^\d{5}(-\d{4})?$')
    garage_type: str = Field(default="garage", pattern=r'^(garage|carport|street|driveway)$')

    # Safety features for discounts
    safety_features: List[str] = Field(default_factory=list)
    anti_theft: bool = Field(default=False)

    # Ownership
    owned: bool = Field(default=True)
    lease_company: Optional[str] = Field(None, max_length=100)

    @field_validator('vin')
    @classmethod
    def validate_vin(cls, v: str) -> str:
        """Validate VIN format and checksum."""
        # Remove common invalid characters
        vin = v.upper().replace('I', '1').replace('O', '0').replace('Q', '0')

        # TODO: Add VIN checksum validation
        # For now, just ensure it's uppercase and right length
        if len(vin) != 17:
            raise ValueError("VIN must be exactly 17 characters")

        return vin

    @field_validator('year')
    @classmethod
    def validate_year(cls, v: int) -> int:
        """Ensure vehicle year is reasonable."""
        current_year = datetime.now().year
        if v > current_year + 1:
            raise ValueError(f"Vehicle year cannot be more than next year ({current_year + 1})")
        if v < 1900:
            raise ValueError("Vehicle year must be 1900 or later")
        return v


class DriverInfo(BaseModelConfig):
    """Driver information for quotes."""

    # Personal info
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    middle_initial: Optional[str] = Field(None, max_length=1)
    suffix: Optional[str] = Field(None, max_length=10)

    # Demographics
    date_of_birth: date
    gender: str = Field(..., pattern=r'^(M|F|X)$')  # M/F/X for non-binary
    marital_status: str = Field(..., pattern=r'^(single|married|divorced|widowed)$')

    # License info
    license_number: str = Field(..., min_length=5, max_length=20)
    license_state: str = Field(..., pattern=r'^[A-Z]{2}$')
    license_status: str = Field(default="valid", pattern=r'^(valid|suspended|expired|restricted)$')
    first_licensed_date: date

    # Driving history
    accidents_3_years: int = Field(default=0, ge=0, le=10)
    violations_3_years: int = Field(default=0, ge=0, le=10)
    dui_convictions: int = Field(default=0, ge=0, le=5)
    claims_3_years: int = Field(default=0, ge=0, le=10)

    # Education/occupation for discounts
    education_level: Optional[str] = Field(None, pattern=r'^(high_school|bachelors|masters|doctorate)$')
    occupation: Optional[str] = Field(None, max_length=100)
    good_student: bool = Field(default=False)

    # Relationship to policyholder
    relationship: str = Field(default="self", pattern=r'^(self|spouse|child|parent|other)$')

    @field_validator('date_of_birth')
    @classmethod
    def validate_age(cls, v: date) -> date:
        """Ensure driver is at least 16 years old."""
        age = (datetime.now().date() - v).days / 365.25
        if age < 16:
            raise ValueError("Driver must be at least 16 years old")
        if age > 100:
            raise ValueError("Driver age must be reasonable")
        return v

    @computed_field
    @property
    def years_licensed(self) -> int:
        """Calculate years of driving experience."""
        if hasattr(self, 'first_licensed_date'):
            years = (datetime.now().date() - self.first_licensed_date).days / 365.25
            return max(0, int(years))
        return 0

    @computed_field
    @property
    def age(self) -> int:
        """Calculate current age."""
        if hasattr(self, 'date_of_birth'):
            years = (datetime.now().date() - self.date_of_birth).days / 365.25
            return max(0, int(years))
        return 0


class CoverageSelection(BaseModelConfig):
    """Individual coverage selection with limits."""

    coverage_type: CoverageType
    limit: Decimal = Field(..., ge=Decimal('0'), decimal_places=2)
    deductible: Optional[Decimal] = Field(None, ge=Decimal('0'), decimal_places=2)

    # Calculated premium for this coverage
    premium: Optional[Decimal] = Field(None, ge=Decimal('0'), decimal_places=2)

    # Additional options
    options: Dict[str, Any] = Field(default_factory=dict)


class Discount(BaseModelConfig):
    """Applied discount details."""

    discount_type: DiscountType
    description: str = Field(..., min_length=1, max_length=200)
    amount: Decimal = Field(..., decimal_places=2)
    percentage: Optional[Decimal] = Field(None, ge=Decimal('0'), le=Decimal('100'), decimal_places=2)

    # Validation
    eligible: bool = Field(default=True)
    validation_notes: Optional[str] = None


class QuoteBase(BaseModelConfig):
    """Base quote information."""

    # Customer info
    customer_id: UUID

    # Quote basics
    product_type: str = Field(..., pattern=r'^(auto|home|commercial)$')
    state: str = Field(..., pattern=r'^[A-Z]{2}$')
    zip_code: str = Field(..., pattern=r'^\d{5}(-\d{4})?$')

    # Dates
    effective_date: date
    requested_date: datetime = Field(default_factory=datetime.now)

    # Product-specific data
    vehicle_info: Optional[VehicleInfo] = None
    drivers: List[DriverInfo] = Field(default_factory=list, min_length=1)

    # Coverage selections
    coverage_selections: List[CoverageSelection] = Field(default_factory=list)

    # Contact preferences
    email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    phone: Optional[str] = Field(None, pattern=r'^\+?1?\d{10,14}$')
    preferred_contact: str = Field(default="email", pattern=r'^(email|phone|text)$')

    @field_validator('effective_date')
    @classmethod
    def validate_effective_date(cls, v: date) -> date:
        """Ensure effective date is not too far in the past."""
        if v < datetime.now().date():
            days_past = (datetime.now().date() - v).days
            if days_past > 30:
                raise ValueError("Effective date cannot be more than 30 days in the past")
        return v

    @field_validator('drivers')
    @classmethod
    def validate_drivers(cls, v: List[DriverInfo]) -> List[DriverInfo]:
        """Ensure at least one driver and validate relationships."""
        if not v:
            raise ValueError("At least one driver is required")

        # Ensure exactly one primary driver
        primary_drivers = [d for d in v if d.relationship == "self"]
        if len(primary_drivers) != 1:
            raise ValueError("Exactly one primary driver required")

        return v


class Quote(QuoteBase, IdentifiableModel, TimestampedModel):
    """Full quote model with calculations and metadata."""

    # Unique identifiers
    quote_number: str = Field(..., pattern=r'^QUOT-\d{4}-\d{6}$')
    version: int = Field(default=1, ge=1)
    parent_quote_id: Optional[UUID] = None  # For quote versioning

    # Status
    status: QuoteStatus = Field(default=QuoteStatus.DRAFT)

    # Pricing (all nullable until calculated)
    base_premium: Optional[Decimal] = Field(None, ge=Decimal('0'), decimal_places=2)
    total_premium: Optional[Decimal] = Field(None, ge=Decimal('0'), decimal_places=2)
    monthly_premium: Optional[Decimal] = Field(None, ge=Decimal('0'), decimal_places=2)
    down_payment: Optional[Decimal] = Field(None, ge=Decimal('0'), decimal_places=2)

    # Applied discounts and surcharges
    discounts_applied: List[Discount] = Field(default_factory=list)
    surcharges_applied: List[Dict[str, Any]] = Field(default_factory=list)
    total_discount_amount: Optional[Decimal] = Field(None, decimal_places=2)
    total_surcharge_amount: Optional[Decimal] = Field(None, ge=Decimal('0'), decimal_places=2)

    # Rating details
    rating_factors: Dict[str, Any] = Field(default_factory=dict)
    rating_tier: Optional[str] = Field(None, max_length=20)

    # AI enhancements
    ai_risk_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    ai_risk_factors: List[str] = Field(default_factory=list)
    ai_recommendations: List[str] = Field(default_factory=list)
    conversion_probability: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Expiration and conversion
    expires_at: datetime
    reminder_sent_at: Optional[datetime] = None
    followup_count: int = Field(default=0, ge=0)

    # If converted to policy
    converted_to_policy_id: Optional[UUID] = None
    converted_at: Optional[datetime] = None

    # Decline info
    declined_reasons: List[str] = Field(default_factory=list)
    declined_at: Optional[datetime] = None

    # User tracking
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None
    assigned_agent_id: Optional[UUID] = None

    # Analytics
    quote_source: Optional[str] = Field(None, max_length=50)  # web, mobile, agent, partner
    referral_code: Optional[str] = Field(None, max_length=20)
    utm_source: Optional[str] = Field(None, max_length=100)
    utm_medium: Optional[str] = Field(None, max_length=100)
    utm_campaign: Optional[str] = Field(None, max_length=100)

    @computed_field
    @property
    def is_expired(self) -> bool:
        """Check if quote has expired."""
        return datetime.now() > self.expires_at

    @computed_field
    @property
    def days_until_expiration(self) -> int:
        """Calculate days until quote expires."""
        if self.is_expired:
            return 0
        delta = self.expires_at - datetime.now()
        return delta.days

    @computed_field
    @property
    def total_savings(self) -> Decimal:
        """Calculate total savings from discounts."""
        if self.total_discount_amount:
            return abs(self.total_discount_amount)
        return Decimal('0')

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
                "monthly_premium": "100.00"
            }
        }


class QuoteCreate(QuoteBase):
    """Model for creating a new quote."""
    pass


class QuoteUpdate(BaseModelConfig):
    """Model for updating a quote."""

    # Allow updating coverage selections
    coverage_selections: Optional[List[CoverageSelection]] = None

    # Allow adding/removing drivers
    drivers: Optional[List[DriverInfo]] = None

    # Update vehicle info
    vehicle_info: Optional[VehicleInfo] = None

    # Update contact info
    email: Optional[str] = Field(None, pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    phone: Optional[str] = Field(None, pattern=r'^\+?1?\d{10,14}$')
    preferred_contact: Optional[str] = Field(None, pattern=r'^(email|phone|text)$')

    # Agent assignment
    assigned_agent_id: Optional[UUID] = None


class QuoteComparison(BaseModelConfig):
    """Model for comparing multiple quote versions."""

    quotes: List[Quote] = Field(..., min_length=2)
    differences: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    recommendation: Optional[str] = None
```

### 2. Create Quote Schemas (`src/pd_prime_demo/schemas/quote.py`)

Create corresponding API schemas following the pattern from `schemas/policy.py` but for quotes.

### 3. Create Supporting Enums (`src/pd_prime_demo/models/enums.py`)

Add any additional enums needed for quotes that don't exist yet.

## SEARCH TRIGGERS (30-second timeout)

If confidence < 95% on:

- VIN validation → Search: "python VIN checksum validation"
- Insurance terms → Search: "auto insurance coverage types"
- Pydantic patterns → Search: "pydantic v2 computed fields"

## DELIVERABLES

1. **Quote Models**: Complete model hierarchy
2. **API Schemas**: Request/response schemas
3. **Enums**: All necessary enumerations
4. **Validation**: Comprehensive field validation
5. **Documentation**: Docstrings for all models

## SUCCESS CRITERIA

1. All models use frozen=True
2. Comprehensive validation on all fields
3. Computed fields for derived values
4. Proper inheritance hierarchy
5. Type hints on everything

## PARALLEL COORDINATION

- Agent 01 will create the database tables
- Agent 05 needs these models for the service
- Agent 06 will use these for rating calculations

Remember: These models will handle 10,000 concurrent quotes!

## ADDITIONAL REQUIREMENT: Admin Models

**IMPORTANT**: You must ALSO read `.sage/wave_contexts/wave_2/AGENT_DEPLOYMENT_SUMMARY.md` to understand the full system context.

### 4. Create Admin Models (`src/pd_prime_demo/models/admin.py`)

You must also create comprehensive admin models:

```python
"""Admin system models."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import Field, field_validator, EmailStr

from .base import BaseModelConfig, TimestampedModel, IdentifiableModel


class AdminRole(str, Enum):
    """Admin role types."""
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    SUPPORT = "support"
    VIEWER = "viewer"


class Permission(str, Enum):
    """System permissions."""
    # User management
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"

    # Quote management
    QUOTE_READ = "quote:read"
    QUOTE_WRITE = "quote:write"
    QUOTE_APPROVE = "quote:approve"
    QUOTE_OVERRIDE = "quote:override"

    # Policy management
    POLICY_READ = "policy:read"
    POLICY_WRITE = "policy:write"
    POLICY_CANCEL = "policy:cancel"

    # Claim management
    CLAIM_READ = "claim:read"
    CLAIM_WRITE = "claim:write"
    CLAIM_APPROVE = "claim:approve"

    # Rate management
    RATE_READ = "rate:read"
    RATE_WRITE = "rate:write"
    RATE_APPROVE = "rate:approve"

    # System settings
    SETTINGS_READ = "settings:read"
    SETTINGS_WRITE = "settings:write"

    # Admin management
    ADMIN_READ = "admin:read"
    ADMIN_WRITE = "admin:write"
    ADMIN_DELETE = "admin:delete"

    # Analytics
    ANALYTICS_READ = "analytics:read"
    ANALYTICS_EXPORT = "analytics:export"

    # Audit logs
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"


class AdminRoleModel(BaseModelConfig, IdentifiableModel):
    """Admin role with permissions."""

    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=200)
    permissions: List[Permission] = Field(default_factory=list)
    parent_role_id: Optional[UUID] = None

    @field_validator('permissions')
    @classmethod
    def validate_permissions(cls, v: List[Permission]) -> List[Permission]:
        """Ensure unique permissions."""
        return list(set(v))


class AdminUserBase(BaseModelConfig):
    """Base admin user model."""

    email: EmailStr
    role_id: UUID
    is_super_admin: bool = False
    two_factor_enabled: bool = False

    # Profile
    full_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, pattern=r'^\+?1?\d{10,14}$')
    department: Optional[str] = Field(None, max_length=50)

    # Settings
    notification_preferences: Dict[str, bool] = Field(default_factory=dict)
    dashboard_config: Dict[str, Any] = Field(default_factory=dict)


class AdminUser(AdminUserBase, IdentifiableModel, TimestampedModel):
    """Full admin user model."""

    # Security
    last_login_at: Optional[datetime] = None
    last_login_ip: Optional[str] = None
    failed_login_attempts: int = Field(default=0, ge=0)
    locked_until: Optional[datetime] = None

    # Audit
    created_by: Optional[UUID] = None
    deactivated_at: Optional[datetime] = None

    # Relationships
    role: Optional[AdminRoleModel] = None

    @property
    def is_locked(self) -> bool:
        """Check if account is locked."""
        if self.locked_until:
            return datetime.utcnow() < self.locked_until
        return False

    @property
    def effective_permissions(self) -> List[Permission]:
        """Get all permissions including role and super admin."""
        if self.is_super_admin:
            return list(Permission)  # All permissions

        if self.role:
            return self.role.permissions

        return []


class AdminUserCreate(AdminUserBase):
    """Model for creating admin user."""
    password: str = Field(..., min_length=8, max_length=100)

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Ensure password meets security requirements."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain digit")
        if not any(c in "!@#$%^&*" for c in v):
            raise ValueError("Password must contain special character")
        return v


class AdminUserUpdate(BaseModelConfig):
    """Model for updating admin user."""
    role_id: Optional[UUID] = None
    is_super_admin: Optional[bool] = None
    two_factor_enabled: Optional[bool] = None
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, pattern=r'^\+?1?\d{10,14}$')
    department: Optional[str] = Field(None, max_length=50)
    notification_preferences: Optional[Dict[str, bool]] = None
    dashboard_config: Optional[Dict[str, Any]] = None


class SystemSetting(BaseModelConfig, IdentifiableModel):
    """System configuration setting."""

    category: str = Field(..., min_length=1, max_length=50)
    key: str = Field(..., min_length=1, max_length=100)
    value: Any
    data_type: str = Field(..., pattern=r'^(string|number|boolean|json|datetime)$')

    # Metadata
    description: Optional[str] = Field(None, max_length=500)
    validation_rules: Optional[Dict[str, Any]] = None

    # Security
    is_sensitive: bool = False
    encrypted: bool = False

    # Audit
    last_modified_by: Optional[UUID] = None
    last_modified_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator('value')
    @classmethod
    def validate_value_type(cls, v: Any, info) -> Any:
        """Validate value matches declared type."""
        data_type = info.data.get('data_type')

        if data_type == 'string' and not isinstance(v, str):
            raise ValueError("Value must be string")
        elif data_type == 'number' and not isinstance(v, (int, float, Decimal)):
            raise ValueError("Value must be number")
        elif data_type == 'boolean' and not isinstance(v, bool):
            raise ValueError("Value must be boolean")

        return v


class AdminActivityLog(BaseModelConfig, IdentifiableModel):
    """Admin activity audit log."""

    admin_user_id: UUID
    action: str = Field(..., min_length=1, max_length=100)
    resource_type: str = Field(..., min_length=1, max_length=50)
    resource_id: Optional[UUID] = None

    # Change tracking
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None

    # Context
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[UUID] = None

    # Result
    status: str = Field(..., pattern=r'^(success|failed|unauthorized)$')
    error_message: Optional[str] = None
    duration_ms: Optional[int] = Field(None, ge=0)

    created_at: datetime = Field(default_factory=datetime.utcnow)


class AdminDashboard(BaseModelConfig, IdentifiableModel):
    """Admin dashboard configuration."""

    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r'^[a-z0-9-]+$')
    description: Optional[str] = Field(None, max_length=500)

    # Layout configuration
    layout: Dict[str, Any] = Field(default_factory=dict)
    widgets: List[Dict[str, Any]] = Field(default_factory=list)

    # Settings
    refresh_interval: int = Field(default=60, ge=10, le=3600)  # seconds
    required_permission: Optional[Permission] = None

    # Metadata
    is_default: bool = False
    is_public: bool = False
    created_by: Optional[UUID] = None
```

### 5. Create Admin API Schemas (`src/pd_prime_demo/schemas/admin.py`)

Create corresponding API schemas for admin endpoints following the existing pattern.

Make sure all admin models use frozen=True and include proper validation!
