# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""User model compatibility layer for gradual migration.

This provides a User model that looks like the old monolithic model
but reads/writes to the new modular tables. This allows existing code
to work unchanged while we gradually migrate to use the modular tables directly.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field

from ..core.database import Database


@beartype
class UserCompat(BaseModel):
    """Compatibility layer that mimics the old User model interface.
    
    This model provides the same interface as the old monolithic users table
    but actually reads/writes from the new modular tables behind the scenes.
    """
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
    )
    
    # Core fields (from users table)
    id: UUID
    email: str
    password_hash: str | None = None
    is_active: bool = True
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    
    # Profile fields (from user_profiles)
    first_name: str | None = None
    last_name: str | None = None
    
    # Role field (from user_roles)
    role: str | None = None
    
    @classmethod
    @beartype
    async def from_email(cls, db: Database, email: str) -> "UserCompat | None":
        """Load user by email, joining across modular tables."""
        row = await db.fetchrow("""
            SELECT 
                u.id, u.email, u.password_hash, u.is_active,
                u.last_login_at, u.created_at, u.updated_at,
                up.first_name, up.last_name,
                ur.role
            FROM users u
            LEFT JOIN user_profiles up ON u.id = up.user_id
            LEFT JOIN user_roles ur ON u.id = ur.user_id AND ur.is_active = true
            WHERE u.email = $1
        """, email)
        
        if not row:
            return None
            
        return cls(**dict(row))
    
    @classmethod
    @beartype
    async def from_id(cls, db: Database, user_id: UUID) -> "UserCompat | None":
        """Load user by ID, joining across modular tables."""
        row = await db.fetchrow("""
            SELECT 
                u.id, u.email, u.password_hash, u.is_active,
                u.last_login_at, u.created_at, u.updated_at,
                up.first_name, up.last_name,
                ur.role
            FROM users u
            LEFT JOIN user_profiles up ON u.id = up.user_id
            LEFT JOIN user_roles ur ON u.id = ur.user_id AND ur.is_active = true
            WHERE u.id = $1
        """, user_id)
        
        if not row:
            return None
            
        return cls(**dict(row))
    
    @beartype
    async def update_last_login(self, db: Database) -> None:
        """Update last login timestamp."""
        await db.execute(
            "UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = $1",
            self.id
        )
    
    @beartype
    async def update_failed_login_attempts(self, db: Database, attempts: int) -> None:
        """Update failed login attempts."""
        await db.execute(
            "UPDATE users SET failed_login_attempts = $2 WHERE id = $1",
            self.id, attempts
        )


# For backward compatibility - alias the compat model as User
User = UserCompat