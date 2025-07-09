"""Admin user management service."""

from datetime import datetime
from typing import Any
from uuid import UUID

from beartype import beartype
from passlib.context import CryptContext

from pd_prime_demo.core.result_types import Err, Ok, Result

from ...core.cache import Cache
from ...core.database import Database
from ...models.admin import AdminUser, AdminUserCreate
from ..cache_keys import CacheKeys

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


class AdminUserService:
    """Service for admin user management."""

    def __init__(self, db: Database, cache: Cache) -> None:
        """Initialize admin user service with dependency validation."""
        if not db or not hasattr(db, "execute"):
            raise ValueError("Database connection required and must be active")
        if not cache or not hasattr(cache, "get"):
            raise ValueError("Cache connection required and must be available")

        self._db = db
        self._cache = cache
        self._cache_ttl = 3600  # 1 hour

    @beartype
    async def create_admin(
        self,
        admin_data: AdminUserCreate,
        created_by: UUID,
    ) -> Result[AdminUser, str]:
        """Create new admin user with role assignment.

        Args:
            admin_data: Admin user creation data
            created_by: UUID of admin creating this user

        Returns:
            Result with created admin user or error message
        """
        # Validate creator has permission
        has_permission = await self.check_permission(
            created_by, "admin_users", "create"
        )
        if isinstance(has_permission, Err):
            return has_permission

        if not has_permission.unwrap():
            return Err("Insufficient permissions to create admin users")

        # Check if email already exists
        existing = await self._db.fetchrow(
            "SELECT id FROM admin_users WHERE email = $1", admin_data.email
        )
        if existing:
            return Err(f"Admin user with email {admin_data.email} already exists")

        # Hash password
        password_hash = pwd_context.hash(admin_data.password)

        # Split full name into first and last name
        name_parts = admin_data.full_name.strip().split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        # Create admin user
        query = """
            INSERT INTO admin_users (
                email, password_hash, first_name, last_name,
                role_id, is_active, created_by
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id, email, first_name, last_name, role_id,
                      is_active, is_super_admin, created_at, updated_at,
                      last_login_at, created_by
        """

        try:
            row = await self._db.fetchrow(
                query,
                admin_data.email,
                password_hash,
                first_name,
                last_name,
                admin_data.role_id,
                True,  # is_active
                created_by,
            )

            if not row:
                return Err("Failed to create admin user")

            admin_user = AdminUser(
                id=row["id"],
                email=row["email"],
                full_name=f"{row['first_name']} {row['last_name']}" if row["first_name"] and row["last_name"] else row["first_name"] or row["last_name"] or "",
                role_id=row["role_id"],
                is_super_admin=row["is_super_admin"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                last_login_at=row["last_login_at"],
                created_by=row["created_by"],
            )

            # Log activity
            await self._log_activity(
                created_by,
                "create_admin",
                "admin_user",
                admin_user.id,
                None,
                {"email": admin_user.email, "role_id": str(admin_user.role_id)},
            )

            return Ok(admin_user)

        except Exception as e:
            return Err(f"Database error: {str(e)}")

    @beartype
    async def update_admin_role(
        self,
        admin_id: UUID,
        role_id: UUID,
        updated_by: UUID,
    ) -> Result[AdminUser, str]:
        """Update admin user's role.

        Args:
            admin_id: Admin user to update
            role_id: New role ID
            updated_by: Admin performing the update

        Returns:
            Result with updated admin user or error
        """
        # Verify permissions
        has_permission = await self.check_permission(
            updated_by, "admin_users", "update_role"
        )
        if isinstance(has_permission, Err):
            return has_permission

        if not has_permission.unwrap():
            return Err("Insufficient permissions to update admin roles")

        # Get current admin data
        current = await self.get_admin(admin_id)
        if isinstance(current, Err):
            return current

        admin = current.unwrap()
        if not admin:
            return Err("Admin user not found")

        # Cannot change super admin role
        if admin.is_super_admin:
            return Err("Cannot change super admin role")

        # Update role
        query = """
            UPDATE admin_users
            SET role_id = $1, updated_at = NOW()
            WHERE id = $2
            RETURNING id, email, first_name, last_name, role_id,
                      is_active, is_super_admin, created_at, updated_at,
                      last_login_at, created_by
        """

        row = await self._db.fetchrow(query, role_id, admin_id)
        if not row:
            return Err("Failed to update admin role")

        updated_admin = AdminUser(
            id=row["id"],
            email=row["email"],
            full_name=f"{row['first_name']} {row['last_name']}" if row["first_name"] and row["last_name"] else row["first_name"] or row["last_name"] or "",
            role_id=row["role_id"],
            is_super_admin=row["is_super_admin"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_login_at=row["last_login_at"],
            created_by=row["created_by"],
        )

        # Invalidate cache
        await self._cache.delete(CacheKeys.admin_user_by_id(admin_id))
        await self._cache.delete(CacheKeys.admin_permissions(admin_id))

        # Log activity
        await self._log_activity(
            updated_by,
            "update_role",
            "admin_user",
            admin_id,
            {"role_id": str(admin.role_id)},
            {"role_id": str(role_id)},
        )

        return Ok(updated_admin)

    @beartype
    async def check_permission(
        self,
        admin_id: UUID,
        resource: str,
        action: str,
    ) -> Result[bool, str]:
        """Check if admin has specific permission.

        Args:
            admin_id: Admin user ID
            resource: Resource name (e.g., 'policies', 'customers')
            action: Action name (e.g., 'create', 'update', 'delete')

        Returns:
            Result with boolean indicating permission or error
        """
        # Check cache first
        cache_key = CacheKeys.admin_permissions(admin_id)
        cached = await self._cache.get(cache_key)

        if cached:
            permissions = cached.get("permissions", [])
            permission_key = f"{resource}:{action}"
            return Ok(permission_key in permissions)

        # Get admin user
        admin_result = await self.get_admin(admin_id)
        if isinstance(admin_result, Err):
            return admin_result

        admin = admin_result.unwrap()
        if not admin:
            return Err("Admin user not found")

        # Super admin has all permissions
        if admin.is_super_admin:
            return Ok(True)

        # Check role permissions
        query = """
            SELECT p.resource, p.action
            FROM admin_permissions p
            JOIN admin_role_permissions rp ON p.id = rp.permission_id
            WHERE rp.role_id = $1 AND p.resource = $2 AND p.action = $3
        """

        row = await self._db.fetchrow(query, admin.role_id, resource, action)
        has_permission = row is not None

        # Cache all permissions for this admin
        all_permissions_query = """
            SELECT p.resource, p.action
            FROM admin_permissions p
            JOIN admin_role_permissions rp ON p.id = rp.permission_id
            WHERE rp.role_id = $1
        """

        rows = await self._db.fetch(all_permissions_query, admin.role_id)
        permissions = [f"{row['resource']}:{row['action']}" for row in rows]

        await self._cache.set(
            cache_key, {"permissions": permissions}, self._cache_ttl
        )

        return Ok(has_permission)

    @beartype
    async def get_admin(self, admin_id: UUID) -> Result[AdminUser | None, str]:
        """Get admin user by ID.

        Args:
            admin_id: Admin user ID

        Returns:
            Result with admin user or None if not found
        """
        # Check cache
        cache_key = CacheKeys.admin_user_by_id(admin_id)
        cached = await self._cache.get(cache_key)

        if cached:
            return Ok(AdminUser(**cached))

        # Query database
        query = """
            SELECT id, email, first_name, last_name, role_id,
                   is_active, is_super_admin, created_at, updated_at,
                   last_login_at, created_by
            FROM admin_users
            WHERE id = $1
        """

        row = await self._db.fetchrow(query, admin_id)
        if not row:
            return Ok(None)

        admin = AdminUser(
            id=row["id"],
            email=row["email"],
            full_name=f"{row['first_name']} {row['last_name']}" if row["first_name"] and row["last_name"] else row["first_name"] or row["last_name"] or "",
            role_id=row["role_id"],
            is_super_admin=row["is_super_admin"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_login_at=row["last_login_at"],
            created_by=row["created_by"],
        )

        # Cache result
        await self._cache.set(
            cache_key, admin.model_dump(mode="json"), self._cache_ttl
        )

        return Ok(admin)

    @beartype
    async def _log_activity(
        self,
        admin_user_id: UUID,
        action: str,
        resource_type: str,
        resource_id: UUID | None = None,
        old_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
    ) -> None:
        """Log admin activity (fire and forget)."""
        try:
            await self._db.execute(
                """
                INSERT INTO admin_activity_logs (
                    admin_user_id, action, resource_type, resource_id,
                    old_values, new_values, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                admin_user_id,
                action,
                resource_type,
                resource_id,
                old_values,
                new_values,
                datetime.utcnow(),
            )
        except Exception:
            # Log errors but don't fail the main operation
            pass
