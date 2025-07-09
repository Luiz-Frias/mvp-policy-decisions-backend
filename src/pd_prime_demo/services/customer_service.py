"""Customer business logic service."""

from datetime import datetime
from uuid import UUID

import asyncpg
from beartype import beartype

from pd_prime_demo.core.result_types import Err, Ok, Result

from ..core.cache import Cache
from ..core.database import Database
from ..models.customer import Customer, CustomerCreate, CustomerUpdate
from ..models.update_data import CustomerUpdateData
from ..schemas.common import PolicySummary
from .cache_keys import CacheKeys
from .performance_monitor import performance_monitor


class CustomerService:
    """Service for customer business logic."""

    def __init__(self, db: Database, cache: Cache) -> None:
        """Initialize customer service with dependency validation."""
        if not db or not hasattr(db, "execute"):
            raise ValueError("Database connection required and must be active")
        if not cache or not hasattr(cache, "get"):
            raise ValueError("Cache connection required and must be available")

        self._db = db
        self._cache = cache
        self._cache_ttl = 3600  # 1 hour

    @beartype
    @performance_monitor("create_customer")
    async def create(self, customer_data: CustomerCreate):
        """Create a new customer."""
        try:
            # Validate business rules
            validation_result = await self._validate_customer_data(customer_data)
            if isinstance(validation_result, Err):
                return validation_result

            # Create customer in database
            query = """
                INSERT INTO customers (external_id, data)
                VALUES ($1, $2)
                RETURNING id, external_id, data, created_at, updated_at
            """

            # Generate customer number
            import uuid

            customer_number = f"CUST-{str(uuid.uuid4())[:10].replace('-', '')}0"

            # Prepare JSONB data
            customer_json = {
                "first_name": customer_data.first_name,
                "last_name": customer_data.last_name,
                "email": str(customer_data.email),
                "phone_number": customer_data.phone_number,
                "date_of_birth": customer_data.date_of_birth.isoformat(),
                "address_line1": customer_data.address_line1,
                "address_line2": customer_data.address_line2,
                "city": customer_data.city,
                "state_province": customer_data.state_province,
                "postal_code": customer_data.postal_code,
                "country_code": customer_data.country_code,
                "customer_type": customer_data.customer_type.value,
                "tax_id_masked": customer_data.tax_id,
                "marketing_consent": customer_data.marketing_consent,
                "status": "ACTIVE",
                "total_policies": 0,
                "risk_score": None,
            }

            row = await self._db.fetchrow(
                query,
                customer_number,
                customer_json,
            )

            if not row:
                return Err("Failed to create customer")

            # Create Customer model from database row
            customer = self._row_to_customer(row)

            return Ok(customer)

        except asyncpg.UniqueViolationError:
            return Err("Customer with this email already exists")
        except Exception as e:
            return Err(f"Database error: {str(e)}")

    @beartype
    @performance_monitor("get_customer")
    async def get(self, customer_id: UUID):
        """Get customer by ID."""
        # Check cache first
        cache_key = CacheKeys.customer_by_id(customer_id)
        cached = await self._cache.get(cache_key)
        if cached:
            return Ok(Customer(**cached))

        # Query database
        query = """
            SELECT id, external_id, data, created_at, updated_at
            FROM customers
            WHERE id = $1
        """

        row = await self._db.fetchrow(query, customer_id)
        if not row:
            return Ok(None)

        customer = self._row_to_customer(row)

        # Cache the result
        await self._cache.set(
            cache_key,
            customer.model_dump(mode="json"),
            self._cache_ttl,
        )

        return Ok(customer)

    @beartype
    @performance_monitor("get_by_customer_number")
    async def get_by_customer_number(
        self,
        customer_number: str,
    ):
        """Get customer by customer number."""
        query = """
            SELECT id, external_id, data, created_at, updated_at
            FROM customers
            WHERE external_id = $1
        """

        row = await self._db.fetchrow(query, customer_number)
        if not row:
            return Ok(None)

        customer = self._row_to_customer(row)
        return Ok(customer)

    @beartype
    async def list_customers(
        self,
        limit: int = 10,
        offset: int = 0,
    ) -> Result[list[Customer], str]:
        """List customers with pagination."""
        query = """
            SELECT id, external_id, data, created_at, updated_at
            FROM customers
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
        """

        rows = await self._db.fetch(query, limit, offset)
        customers = [self._row_to_customer(row) for row in rows]

        return Ok(customers)

    @beartype
    @performance_monitor("update_customer")
    async def update(
        self,
        customer_id: UUID,
        customer_update: CustomerUpdate,
    ):
        """Update customer."""
        # Get existing customer
        existing_result = await self.get(customer_id)
        if isinstance(existing_result, Err):
            return existing_result

        existing = existing_result.unwrap()
        if not existing:
            return Ok(None)

        # Build update data using the strongly-typed model
        update_data_model = CustomerUpdateData(
            email=(
                str(customer_update.email)
                if customer_update.email is not None
                else None
            ),
            phone_number=customer_update.phone_number,
            address_line1=customer_update.address_line1,
            address_line2=customer_update.address_line2,
            city=customer_update.city,
            state_province=customer_update.state_province,
            postal_code=customer_update.postal_code,
            marketing_consent=customer_update.marketing_consent,
        )

        # Convert to JSONB dict, excluding None values
        update_data = update_data_model.model_dump_non_none()

        if not update_data:
            return Ok(existing)

        query = """
            UPDATE customers
            SET data = data || $1::jsonb, updated_at = NOW()
            WHERE id = $2
            RETURNING id, external_id, data, created_at, updated_at
        """

        row = await self._db.fetchrow(query, update_data, customer_id)
        if not row:
            return Err("Failed to update customer")

        customer = self._row_to_customer(row)

        # Invalidate cache
        await self._cache.delete(CacheKeys.customer_by_id(customer_id))
        # Also invalidate email lookup cache if we had one
        if customer.email:
            await self._cache.delete(CacheKeys.customer_by_email(customer.email))

        return Ok(customer)

    @beartype
    async def delete(self, customer_id: UUID):
        """Delete a customer and all related data."""
        # Note: This is a hard delete with CASCADE
        # In production, consider soft delete instead
        query = "DELETE FROM customers WHERE id = $1"

        result = await self._db.execute(query, customer_id)
        deleted = result.split()[-1] != "0"

        if deleted:
            # Invalidate cache
            await self._cache.delete(CacheKeys.customer_by_id(customer_id))

        return Ok(deleted)

    @beartype
    @performance_monitor("get_customer_policies")
    async def get_policies(self, customer_id: UUID) -> Result[list[PolicySummary], str]:
        """Get all policies for a customer."""
        query = """
            SELECT id, policy_number, data->>'type' as policy_type,
                   status, effective_date, expiration_date
            FROM policies
            WHERE customer_id = $1
            ORDER BY created_at DESC
        """

        rows = await self._db.fetch(query, customer_id)

        policies = [
            PolicySummary(
                id=str(row["id"]),
                policy_number=row["policy_number"],
                policy_type=row["policy_type"],
                status=row["status"],
                effective_date=row["effective_date"].isoformat(),
                expiration_date=row["expiration_date"].isoformat(),
            )
            for row in rows
        ]

        return Ok(policies)

    @beartype
    async def _validate_customer_data(
        self,
        customer_data: CustomerCreate,
    ):
        """Validate customer business rules."""
        # Check if email already exists
        query = "SELECT 1 FROM customers WHERE data->>'email' = $1"
        exists = await self._db.fetchval(query, customer_data.email)

        if exists:
            return Err(f"Email {customer_data.email} is already registered")

        # Additional business rule validations can be added here

        return Ok(True)

    @beartype
    @performance_monitor("row_to_customer")
    def _row_to_customer(self, row: asyncpg.Record) -> Customer:
        """Convert database row to Customer model."""
        data = dict(row["data"])
        from ..models.customer import CustomerStatus, CustomerType

        return Customer(
            id=row["id"],
            customer_number=row["external_id"],
            customer_type=CustomerType(data["customer_type"]),
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data["email"],
            phone_number=data["phone_number"],
            date_of_birth=datetime.fromisoformat(data["date_of_birth"]).date(),
            address_line1=data["address_line1"],
            address_line2=data.get("address_line2"),
            city=data["city"],
            state_province=data["state_province"],
            postal_code=data["postal_code"],
            country_code=data["country_code"],
            status=CustomerStatus(data["status"]),
            tax_id_masked=data["tax_id_masked"],
            marketing_consent=data["marketing_consent"],
            total_policies=data.get("total_policies", 0),
            risk_score=data.get("risk_score"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
