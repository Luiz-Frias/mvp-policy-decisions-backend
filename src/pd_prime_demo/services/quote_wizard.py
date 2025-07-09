"""Multi-step quote wizard state management."""

import json
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field

from pd_prime_demo.core.result_types import Err, Ok, Result

from ..core.cache import Cache


class WizardStep(BaseModel):
    """Individual wizard step configuration."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    step_id: str
    title: str
    description: str
    fields: list[str]
    validations: dict[str, Any]
    next_step: str | None
    previous_step: str | None
    is_conditional: bool = False
    condition_field: str | None = None
    condition_value: Any | None = None


class WizardState(BaseModel):
    """Current state of quote wizard."""

    model_config = ConfigDict(
        frozen=False,  # Must be mutable for state updates
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    session_id: UUID
    quote_id: UUID | None
    current_step: str
    completed_steps: list[str]
    data: dict[str, Any]
    validation_errors: dict[str, list[str]] = Field(default_factory=dict)
    started_at: datetime
    last_updated: datetime
    expires_at: datetime
    is_complete: bool = False
    completion_percentage: int = 0


class WizardValidation(BaseModel):
    """Validation result for wizard step."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    is_valid: bool
    errors: dict[str, list[str]] = Field(default_factory=dict)
    warnings: dict[str, list[str]] = Field(default_factory=dict)


class QuoteWizardService:
    """Manage multi-step quote wizard state."""

    def __init__(self, cache: Cache) -> None:
        """Initialize wizard service."""
        self._cache = cache
        self._cache_prefix = "wizard:"
        self._session_ttl = 3600  # 1 hour
        self._steps = self._initialize_wizard_steps()

    def _initialize_wizard_steps(self) -> dict[str, WizardStep]:
        """Define wizard flow configuration."""
        return {
            "start": WizardStep(
                step_id="start",
                title="Get Started",
                description="Basic information about your insurance needs",
                fields=["product_type", "state", "zip_code", "effective_date"],
                validations={
                    "product_type": ["required", "in:AUTO,HOME,COMMERCIAL"],
                    "state": ["required", "in:CA,TX,NY"],
                    "zip_code": ["required", "regex:^\\d{5}(-\\d{4})?$"],
                    "effective_date": ["required", "date", "future:60"],
                },
                next_step="customer",
                previous_step=None,
            ),
            "customer": WizardStep(
                step_id="customer",
                title="About You",
                description="Tell us about yourself",
                fields=["email", "phone", "date_of_birth", "preferred_contact"],
                validations={
                    "email": ["required", "email"],
                    "phone": ["required", "phone"],
                    "date_of_birth": ["required", "date", "age:16"],
                    "preferred_contact": ["required", "in:EMAIL,PHONE,SMS"],
                },
                next_step="vehicle",  # For auto quotes
                previous_step="start",
                is_conditional=True,
                condition_field="product_type",
                condition_value="AUTO",
            ),
            "vehicle": WizardStep(
                step_id="vehicle",
                title="Vehicle Information",
                description="Details about your vehicle",
                fields=[
                    "vin",
                    "year",
                    "make",
                    "model",
                    "vehicle_type",
                    "annual_mileage",
                    "primary_use",
                    "garage_zip",
                    "owned",
                ],
                validations={
                    "vin": ["optional", "length:17", "vin"],
                    "year": [
                        "required",
                        "integer",
                        "min:1900",
                        f"max:{datetime.now().year + 1}",
                    ],
                    "make": ["required", "string", "min:1", "max:50"],
                    "model": ["required", "string", "min:1", "max:50"],
                    "vehicle_type": [
                        "required",
                        "in:SEDAN,SUV,TRUCK,VAN,MOTORCYCLE,OTHER",
                    ],
                    "annual_mileage": ["required", "integer", "min:0", "max:200000"],
                    "primary_use": ["required", "in:commute,pleasure,business"],
                    "garage_zip": ["required", "regex:^\\d{5}(-\\d{4})?$"],
                    "owned": ["required", "boolean"],
                },
                next_step="drivers",
                previous_step="customer",
            ),
            "drivers": WizardStep(
                step_id="drivers",
                title="Driver Information",
                description="Who will be driving?",
                fields=["drivers"],
                validations={"drivers": ["required", "array", "min:1", "max:5"]},
                next_step="coverage",
                previous_step="vehicle",
            ),
            "coverage": WizardStep(
                step_id="coverage",
                title="Coverage Selection",
                description="Choose your coverage levels",
                fields=["coverage_selections"],
                validations={"coverage_selections": ["required", "array", "min:1"]},
                next_step="review",
                previous_step="drivers",
            ),
            "review": WizardStep(
                step_id="review",
                title="Review Quote",
                description="Review and get your price",
                fields=[],
                validations={},
                next_step=None,
                previous_step="coverage",
            ),
        }

    @beartype
    async def start_session(self, initial_data: dict[str, Any] | None = None) -> Result[WizardState, str]:
        """Start a new wizard session."""
        session_id = uuid4()
        now = datetime.now()

        state = WizardState(
            session_id=session_id,
            quote_id=None,
            current_step="start",
            completed_steps=[],
            data=initial_data or {},
            started_at=now,
            last_updated=now,
            expires_at=now + timedelta(seconds=self._session_ttl),
        )

        # Calculate initial completion
        completion_percentage = self._calculate_completion(state)
        state = state.model_copy(update={'completion_percentage': completion_percentage})

        # Save to cache
        cache_key = f"{self._cache_prefix}{session_id}"
        await self._cache.set(
            cache_key,
            state.model_dump_json(),
            self._session_ttl,
        )

        return Ok(state)

    @beartype
    async def get_session(self, session_id: UUID) -> Result[WizardState | None, str]:
        """Get wizard session by ID."""
        cache_key = f"{self._cache_prefix}{session_id}"
        cached = await self._cache.get(cache_key)

        if not cached:
            return Ok(None)

        try:
            state_data = json.loads(cached) if isinstance(cached, str) else cached
            state = WizardState(**state_data)

            # Check expiration
            if datetime.now() > state.expires_at:
                await self._cache.delete(cache_key)
                return Ok(None)

            return Ok(state)
        except Exception as e:
            return Err(f"Failed to deserialize session: {str(e)}")

    @beartype
    async def update_step(self, session_id: UUID, step_data: dict[str, Any]) -> Result[WizardState, str]:
        """Update current step with data."""
        # Get session
        session_result = await self.get_session(session_id)
        if isinstance(session_result, Err):
            return session_result

        state = session_result.unwrap()
        if not state:
            return Err("Session not found or expired")

        # Get current step config
        current_step = self._steps.get(state.current_step)
        if not current_step:
            return Err(f"Invalid step: {state.current_step}")

        # Validate step data
        validation = self._validate_step_data(current_step, step_data)
        if not validation.is_valid:
            updated_state = state.model_copy(update={'validation_errors': validation.errors})
            # Still save state with errors
            await self._save_state(updated_state)
            return Err("Validation failed")

        # Clear validation errors and update state data
        updated_data = state.data.copy()
        updated_data.update(step_data)
        
        # Mark step as completed if not already
        updated_completed_steps = state.completed_steps.copy()
        if state.current_step not in updated_completed_steps:
            updated_completed_steps.append(state.current_step)

        # Calculate completion
        completion_percentage = self._calculate_completion(state)
        
        # Create updated state
        state = state.model_copy(update={
            'validation_errors': {},
            'data': updated_data,
            'last_updated': datetime.now(),
            'completed_steps': updated_completed_steps,
            'completion_percentage': completion_percentage
        })

        # Save state
        await self._save_state(state)

        return Ok(state)

    @beartype
    async def next_step(self, session_id: UUID) -> Result[WizardState, str]:
        """Move to next step in wizard."""
        # Get session
        session_result = await self.get_session(session_id)
        if isinstance(session_result, Err):
            return session_result

        state = session_result.unwrap()
        if not state:
            return Err("Session not found or expired")

        # Get current step
        current_step = self._steps.get(state.current_step)
        if not current_step:
            return Err(f"Invalid step: {state.current_step}")

        # Check if current step is completed
        if state.current_step not in state.completed_steps:
            return Err("Current step must be completed before proceeding")

        # Determine next step
        next_step_id = self._determine_next_step(current_step, state.data)
        if not next_step_id:
            # Wizard complete
            state = state.model_copy(update={
                'is_complete': True,
                'completion_percentage': 100,
                'last_updated': datetime.now()
            })
        else:
            state = state.model_copy(update={
                'current_step': next_step_id,
                'last_updated': datetime.now()
            })
        await self._save_state(state)

        return Ok(state)

    @beartype
    async def previous_step(self, session_id: UUID) -> Result[WizardState, str]:
        """Move to previous step in wizard."""
        # Get session
        session_result = await self.get_session(session_id)
        if isinstance(session_result, Err):
            return session_result

        state = session_result.unwrap()
        if not state:
            return Err("Session not found or expired")

        # Get current step
        current_step = self._steps.get(state.current_step)
        if not current_step or not current_step.previous_step:
            return Err("No previous step available")

        state = state.model_copy(update={
            'current_step': current_step.previous_step,
            'last_updated': datetime.now()
        })

        await self._save_state(state)

        return Ok(state)

    @beartype
    async def jump_to_step(self, session_id: UUID, step_id: str) -> Result[WizardState, str]:
        """Jump to a specific step (if allowed)."""
        # Get session
        session_result = await self.get_session(session_id)
        if isinstance(session_result, Err):
            return session_result

        state = session_result.unwrap()
        if not state:
            return Err("Session not found or expired")

        # Check if step exists
        if step_id not in self._steps:
            return Err(f"Invalid step: {step_id}")

        # Check if step has been completed or is accessible
        if step_id not in state.completed_steps and step_id != "start":
            # Check if all previous steps are completed
            if not self._can_access_step(step_id, state.completed_steps):
                return Err("Cannot jump to uncompleted step")

        state = state.model_copy(update={
            'current_step': step_id,
            'last_updated': datetime.now()
        })

        await self._save_state(state)

        return Ok(state)

    @beartype
    async def get_step_info(self, step_id: str) -> Result[dict[str, Any], str]:
        """Get information about a specific step."""
        step = self._steps.get(step_id)
        if not step:
            return Err(f"Invalid step: {step_id}")
        return Ok(step.model_dump())

    @beartype
    async def get_all_steps(self) -> Result[list[WizardStep], str]:
        """Get all wizard steps in order."""
        # Return steps in logical order
        ordered_steps = []
        current: str | None = "start"

        while current:
            step = self._steps.get(current)
            if not step:
                break
            ordered_steps.append(step)
            current = step.next_step

        return Ok(ordered_steps)

    @beartype
    async def validate_session(self, session_id: UUID) -> Result[WizardValidation, str]:
        """Validate entire session data."""
        # Get session
        session_result = await self.get_session(session_id)
        if isinstance(session_result, Err):
            return session_result

        state = session_result.unwrap()
        if not state:
            return Err("Session not found or expired")

        validation = WizardValidation(is_valid=True)

        # Validate each completed step
        for step_id in state.completed_steps:
            step = self._steps.get(step_id)
            if not step:
                continue

            step_data = self._extract_step_data(step, state.data)
            step_validation = self._validate_step_data(step, step_data)

            if not step_validation.is_valid:
                validation = validation.model_copy(update={
                    'is_valid': False,
                    'errors': {**validation.errors, step_id: step_validation.errors}
                })

        return Ok(validation)

    @beartype
    async def complete_session(self, session_id: UUID) -> Result[dict[str, Any], str]:
        """Complete wizard session and return collected data."""
        # Get session
        session_result = await self.get_session(session_id)
        if isinstance(session_result, Err):
            return session_result

        state = session_result.unwrap()
        if not state:
            return Err("Session not found or expired")

        # Validate all data
        validation_result = await self.validate_session(session_id)
        if isinstance(validation_result, Err):
            return validation_result

        validation = validation_result.unwrap()
        if not validation.is_valid:
            return Err("Session data is not valid")

        # Mark as complete
        state = state.model_copy(update={
            'is_complete': True,
            'completion_percentage': 100
        })
        await self._save_state(state)

        # Return collected data
        return Ok(
            {
                "session_id": str(session_id),
                "quote_data": state.data,
                "completed_at": datetime.now().isoformat(),
                "steps_completed": state.completed_steps,
            }
        )

    @beartype
    async def extend_session(self, session_id: UUID, additional_minutes: int = 30) -> Result[WizardState, str]:
        """Extend session expiration time."""
        # Get session
        session_result = await self.get_session(session_id)
        if isinstance(session_result, Err):
            return session_result

        state = session_result.unwrap()
        if not state:
            return Err("Session not found or expired")

        # Extend expiration
        state = state.model_copy(update={
            'expires_at': datetime.now() + timedelta(minutes=additional_minutes),
            'last_updated': datetime.now()
        })

        # Update TTL in cache
        new_ttl = additional_minutes * 60
        await self._save_state(state, ttl=new_ttl)

        return Ok(state)

    # Private helper methods

    @beartype
    async def _save_state(self, state: WizardState, ttl: int | None = None) -> None:
        """Save wizard state to cache."""
        cache_key = f"{self._cache_prefix}{state.session_id}"
        ttl = ttl or self._session_ttl

        await self._cache.set(
            cache_key,
            state.model_dump_json(),
            ttl,
        )

    @beartype
    def _validate_step_data(
        self, step: WizardStep, data: dict[str, Any]
    ) -> WizardValidation:
        """Validate data for a specific step."""
        validation = WizardValidation(is_valid=True)
        errors: dict[str, list[str]] = {}

        for field, rules in step.validations.items():
            field_value = data.get(field)
            field_errors = []

            for rule in rules:
                if isinstance(rule, str) and ":" in rule:
                    rule_name, rule_value = rule.split(":", 1)
                else:
                    rule_name = rule
                    rule_value = None

                error = self._apply_validation_rule(
                    field, field_value, rule_name, rule_value
                )
                if error:
                    field_errors.append(error)

            if field_errors:
                errors[field] = field_errors
                validation = validation.model_copy(update={'is_valid': False})

        return validation.model_copy(update={'errors': errors})

    @beartype
    def _apply_validation_rule(
        self, field: str, value: Any, rule: str, rule_value: str | None
    ) -> str | None:
        """Apply a single validation rule."""
        if rule == "required" and not value:
            return f"{field} is required"

        if rule == "optional" and not value:
            return None  # Optional fields can be empty

        if rule == "email" and value:
            import re

            if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", value):
                return f"{field} must be a valid email address"

        if rule == "phone" and value:
            import re

            if not re.match(r"^[0-9+\-\(\)\s]+$", value):
                return f"{field} must be a valid phone number"

        if rule == "date" and value:
            try:
                if isinstance(value, str):
                    datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                return f"{field} must be a valid date (YYYY-MM-DD)"

        if rule == "age" and rule_value and value:
            try:
                if isinstance(value, str):
                    birth_date = datetime.strptime(value, "%Y-%m-%d").date()
                else:
                    birth_date = value
                age = (date.today() - birth_date).days / 365.25
                min_age = int(rule_value)
                if age < min_age:
                    return f"Must be at least {min_age} years old"
            except Exception:
                return "Invalid date of birth"

        if rule == "future" and rule_value and value:
            try:
                if isinstance(value, str):
                    check_date = datetime.strptime(value, "%Y-%m-%d").date()
                else:
                    check_date = value
                max_days = int(rule_value)
                if check_date < date.today():
                    return f"{field} cannot be in the past"
                if check_date > date.today() + timedelta(days=max_days):
                    return f"{field} cannot be more than {max_days} days in the future"
            except Exception:
                return "Invalid date"

        if rule == "in" and rule_value and value:
            allowed_values = rule_value.split(",")
            if value not in allowed_values:
                return f"{field} must be one of: {', '.join(allowed_values)}"

        if rule == "min" and rule_value and value is not None:
            try:
                min_val = float(rule_value)
                if float(value) < min_val:
                    return f"{field} must be at least {min_val}"
            except (ValueError, TypeError):
                pass

        if rule == "max" and rule_value and value is not None:
            try:
                max_val = float(rule_value)
                if float(value) > max_val:
                    return f"{field} must be at most {max_val}"
            except (ValueError, TypeError):
                pass

        if rule == "length" and rule_value and value:
            expected_length = int(rule_value)
            if len(str(value)) != expected_length:
                return f"{field} must be exactly {expected_length} characters"

        if rule == "regex" and rule_value and value:
            import re

            if not re.match(rule_value, str(value)):
                return f"{field} format is invalid"

        if rule == "array" and value is not None:
            if not isinstance(value, list):
                return f"{field} must be a list"

        if rule == "vin" and value:
            # Enhanced VIN validation following ISO 3779
            if len(value) != 17:
                return "VIN must be 17 characters"

            # Check for invalid characters
            if any(char in value.upper() for char in "IOQ"):
                return "VIN cannot contain I, O, or Q per ISO 3779 standard"

            # Validate characters are alphanumeric
            if not re.match(r"^[A-HJ-NPR-Z0-9]+$", value.upper()):
                return "VIN can only contain letters A-H, J-N, P-R, T-Z and numbers 0-9"

            # Basic checksum validation (simplified)
            try:
                vin_upper = value.upper()
                # Position 9 should be check digit
                check_digit = vin_upper[8]
                if not (check_digit.isdigit() or check_digit == "X"):
                    return "VIN check digit (position 9) must be 0-9 or X"
            except (IndexError, AttributeError):
                return "Invalid VIN format"

        if rule == "boolean" and value is not None:
            if not isinstance(value, bool):
                return f"{field} must be true or false"

        if rule == "integer" and value is not None:
            try:
                int(value)
            except (ValueError, TypeError):
                return f"{field} must be a whole number"

        if rule == "string" and value is not None:
            if not isinstance(value, str):
                return f"{field} must be text"

        return None

    @beartype
    def _determine_next_step(
        self, current_step: WizardStep, data: dict[str, Any]
    ) -> str | None:
        """Determine next step based on current step and data."""
        if not current_step.next_step:
            return None

        # Check conditional steps
        next_step = self._steps.get(current_step.next_step)
        if next_step and next_step.is_conditional:
            # Check if condition is met
            if next_step.condition_field and next_step.condition_value:
                field_value = data.get(next_step.condition_field)
                if field_value != next_step.condition_value:
                    # Skip this step, go to its next
                    return self._determine_next_step(next_step, data)

        return current_step.next_step

    @beartype
    def _can_access_step(self, step_id: str, completed_steps: list[str]) -> bool:
        """Check if a step can be accessed based on completed steps."""
        # Find all steps that must be completed before this one
        required_steps = []
        current: str | None = "start"

        while current and current != step_id:
            required_steps.append(current)
            step = self._steps.get(current)
            if not step:
                break
            current = step.next_step

        # Check if all required steps are completed
        return all(step in completed_steps for step in required_steps)

    @beartype
    def _calculate_completion(self, state: WizardState) -> int:
        """Calculate completion percentage."""
        total_steps = len(self._steps) - 1  # Exclude review step
        completed = len(state.completed_steps)

        if state.is_complete:
            return 100

        return int((completed / total_steps) * 100) if total_steps > 0 else 0

    @beartype
    def _extract_step_data(
        self, step: WizardStep, all_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract data relevant to a specific step."""
        return {field: all_data.get(field) for field in step.fields}

    @beartype
    async def get_business_intelligence_for_step(
        self, session_id: UUID, step_id: str
    ) -> Result[dict[str, Any], str]:
        """Get business intelligence data for current step to help user decisions."""
        # Get session
        session_result = await self.get_session(session_id)
        if isinstance(session_result, Err):
            return session_result

        state = session_result.unwrap()
        if not state:
            return Err("Session not found or expired")

        intelligence: dict[str, Any] = {}

        # Provide step-specific intelligence
        if step_id == "start":
            intelligence = {
                "popular_products": ["auto", "home"],
                "state_info": {
                    "CA": {
                        "min_liability": 15000,
                        "required_coverages": ["bodily_injury", "property_damage"],
                    },
                    "TX": {
                        "min_liability": 30000,
                        "required_coverages": ["bodily_injury", "property_damage"],
                    },
                    "NY": {
                        "min_liability": 25000,
                        "required_coverages": [
                            "bodily_injury",
                            "property_damage",
                            "pip",
                        ],
                    },
                },
                "effective_date_guidance": "Most customers choose a date 1-14 days in the future",
            }

        elif step_id == "vehicle":
            intelligence = {
                "popular_makes": ["Toyota", "Honda", "Ford", "Chevrolet", "Nissan"],
                "safety_tips": [
                    "Vehicles with safety features like ABS and airbags often qualify for discounts",
                    "Anti-theft devices can reduce your premium",
                    "Newer vehicles may cost more to insure but have better safety ratings",
                ],
                "mileage_brackets": {
                    "low": {"max": 7500, "typical_discount": "5-15%"},
                    "average": {"min": 7500, "max": 15000, "typical_discount": "0%"},
                    "high": {"min": 15000, "typical_surcharge": "10-25%"},
                },
            }

        elif step_id == "drivers":
            intelligence = {
                "discount_opportunities": [
                    "Good student discount available for drivers under 25 with GPA 3.0+",
                    "Military discount available for active and veteran service members",
                    "Clean driving record discount for drivers with no violations or accidents",
                ],
                "experience_factors": {
                    "new_driver": "Drivers with <3 years experience may have higher rates",
                    "experienced": "Drivers with 5+ years typically qualify for experience discounts",
                },
            }

        elif step_id == "coverage":
            product_type = state.data.get("product_type", "auto")
            coverage_state = state.data.get("state", "CA")

            if product_type == "auto":
                intelligence = {
                    "required_coverages": self._get_required_coverages_for_state(
                        coverage_state
                    ),
                    "recommended_coverages": [
                        {
                            "type": "collision",
                            "reason": "Protects your vehicle in accidents",
                        },
                        {
                            "type": "comprehensive", 
                            "reason": "Protects against theft, vandalism, weather",
                        },
                        {
                            "type": "uninsured_motorist",
                            "reason": "Protects you from uninsured drivers",
                        },
                    ],
                    "deductible_guidance": {
                        "low": {
                            "amount": "$250-$500",
                            "effect": "Higher premium, lower out-of-pocket",
                        },
                        "high": {
                            "amount": "$1000+",
                            "effect": "Lower premium, higher out-of-pocket",
                        },
                    },
                    "coverage_limits": {
                        "liability": f"State minimum: ${self._get_state_minimum_liability(coverage_state):,}",
                        "recommendation": "Consider higher limits to protect your assets",
                    },
                }

        return Ok(intelligence)

    def _get_required_coverages_for_state(self, state: str) -> list[str]:
        """Get required coverages for specific state."""
        state_requirements = {
            "CA": ["bodily_injury", "property_damage"],
            "TX": ["bodily_injury", "property_damage"],
            "NY": ["bodily_injury", "property_damage", "personal_injury_protection"],
        }
        return state_requirements.get(state, ["bodily_injury", "property_damage"])

    def _get_state_minimum_liability(self, state: str) -> int:
        """Get minimum liability coverage for state."""
        minimums = {
            "CA": 15000,  # $15K/$30K/$5K
            "TX": 30000,  # $30K/$60K/$25K
            "NY": 25000,  # $25K/$50K/$10K
        }
        return minimums.get(state, 15000)
